"""
Global Coordinator with Two-Phase Commit
=========================================

Orchestrates cross-region ride handoffs using 2PC protocol.
Provides scatter-gather queries across all regions.

Run: uvicorn services.coordinator:app --host 0.0.0.0 --port 8000
"""

import logging
import uuid
import time
import httpx
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException, status
from contextlib import asynccontextmanager

from services.models import (
    HandoffRequest, HandoffResponse,
    PrepareRequest, CommitRequest, AbortRequest,
    RegionalStats, RideQuery, RideResponse
)
from services.database import GlobalDatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database manager
db_manager = GlobalDatabaseManager()

# Regional API endpoints
REGIONAL_APIS = {
    "Phoenix": "http://localhost:8001",
    "Los Angeles": "http://localhost:8002"
}

# HTTP client for inter-service communication
http_client = None


class HealthMonitor:

    def __init__(self):
        self.health_status = {region: True for region in REGIONAL_APIS}
        self.running = False
        self._task = None

    async def start(self):
        """Start monitoring loop"""
        self.running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Health Monitor started")

    async def stop(self):
        """Stop monitoring loop"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health Monitor stopped")

    async def _monitor_loop(self):
        """Periodic health check loop"""
        while self.running:
            for region, url in REGIONAL_APIS.items():
                try:
                    if http_client:
                        response = await http_client.get(f"{url}/health", timeout=2.0)
                        is_healthy = response.status_code == 200
                    else:
                        is_healthy = False
                except Exception:
                    is_healthy = False
                
                if self.health_status.get(region) != is_healthy:
                    logger.warning(f"Region {region} health changed: {self.health_status.get(region)} -> {is_healthy}")
                
                self.health_status[region] = is_healthy

            await asyncio.sleep(5)

    def is_healthy(self, region: str) -> bool:
        """Check if a region is healthy"""
        return self.health_status.get(region, False)


# Global health monitor instance
health_monitor = HealthMonitor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup/shutdown"""
    global http_client

    # Startup
    logger.info("Starting Global Coordinator...")
    await db_manager.connect()
    http_client = httpx.AsyncClient(timeout=10.0)
    await health_monitor.start()

    yield

    # Shutdown
    logger.info("Shutting down Global Coordinator...")
    await health_monitor.stop()
    await db_manager.disconnect()
    await http_client.aclose()


app = FastAPI(
    title="Global Coordinator",
    version="2.0.0",
    description="Two-Phase Commit coordinator for cross-region handoffs",
    lifespan=lifespan
)


# ============================================
# TWO-PHASE COMMIT COORDINATOR
# ============================================

class TwoPhaseCommitCoordinator:
    """Orchestrates 2PC protocol for cross-region handoffs"""

    def __init__(self, tx_id: str, ride_id: str, source: str, target: str):
        self.tx_id = tx_id
        self.ride_id = ride_id
        self.source = source
        self.target = target
        self.ride_data = None
        self.start_time = time.time()

    async def execute(self) -> HandoffResponse:
        """Execute the complete 2PC handoff protocol"""
        try:
            # PHASE 1: PREPARE
            logger.info(f"[{self.tx_id}] Starting 2PC for ride {self.ride_id}: {self.source} → {self.target}")

            # Step 1a: Prepare source (DELETE)
            source_vote = await self._prepare_source()
            if source_vote != "COMMIT":
                logger.warning(f"[{self.tx_id}] Source vote: ABORT")
                return HandoffResponse(
                    status="ABORTED",
                    tx_id=self.tx_id,
                    reason="Source region aborted transaction",
                    latency_ms=self._get_latency()
                )

            # Step 1b: Prepare target (INSERT)
            target_vote = await self._prepare_target()
            if target_vote != "COMMIT":
                logger.warning(f"[{self.tx_id}] Target vote: ABORT")
                await self._abort_all()
                return HandoffResponse(
                    status="ABORTED",
                    tx_id=self.tx_id,
                    reason="Target region aborted transaction",
                    latency_ms=self._get_latency()
                )

            # PHASE 2: COMMIT
            logger.info(f"[{self.tx_id}] Both regions voted COMMIT, proceeding to commit phase")

            # Step 2a: Commit source (DELETE)
            await self._commit_source()

            # Step 2b: Commit target (INSERT)
            await self._commit_target()

            logger.info(f"[{self.tx_id}] Handoff completed successfully")

            # Log to global database
            await self._log_transaction("SUCCESS")

            return HandoffResponse(
                status="SUCCESS",
                tx_id=self.tx_id,
                reason=None,
                latency_ms=self._get_latency()
            )

        except Exception as e:
            logger.error(f"[{self.tx_id}] Handoff failed: {e}")
            await self._abort_all()
            await self._log_transaction("ABORTED", str(e))

            return HandoffResponse(
                status="ABORTED",
                tx_id=self.tx_id,
                reason=str(e),
                latency_ms=self._get_latency()
            )

    async def _prepare_source(self) -> str:
        """Phase 1a: Ask source region to prepare DELETE"""
        try:
            source_url = REGIONAL_APIS[self.source]
            response = await http_client.post(
                f"{source_url}/2pc/prepare",
                json={
                    "ride_id": self.ride_id,
                    "tx_id": self.tx_id,
                    "operation": "DELETE"
                }
            )

            if response.status_code != 200:
                logger.error(f"Source prepare failed: {response.status_code}")
                return "ABORT"

            result = response.json()
            vote = result.get("vote")

            if vote == "COMMIT":
                # Save ride data for target insertion
                self.ride_data = result.get("ride_data")
                logger.info(f"[{self.tx_id}] Source prepared successfully")

            return vote

        except Exception as e:
            logger.error(f"[{self.tx_id}] Source prepare error: {e}")
            return "ABORT"

    async def _prepare_target(self) -> str:
        """Phase 1b: Ask target region to prepare INSERT"""
        try:
            target_url = REGIONAL_APIS[self.target]
            response = await http_client.post(
                f"{target_url}/2pc/prepare",
                json={
                    "ride_id": self.ride_id,
                    "tx_id": self.tx_id,
                    "operation": "INSERT"
                }
            )

            if response.status_code != 200:
                logger.error(f"Target prepare failed: {response.status_code}")
                return "ABORT"

            result = response.json()
            vote = result.get("vote")

            if vote == "COMMIT":
                logger.info(f"[{self.tx_id}] Target prepared successfully")

            return vote

        except Exception as e:
            logger.error(f"[{self.tx_id}] Target prepare error: {e}")
            return "ABORT"

    async def _commit_source(self):
        """Phase 2a: Commit DELETE at source"""
        try:
            source_url = REGIONAL_APIS[self.source]
            response = await http_client.post(
                f"{source_url}/2pc/commit",
                json={
                    "ride_id": self.ride_id,
                    "tx_id": self.tx_id,
                    "operation": "DELETE",
                    "ride_data": None
                }
            )

            if response.status_code == 200:
                logger.info(f"[{self.tx_id}] Source committed DELETE")
            else:
                logger.error(f"[{self.tx_id}] Source commit failed: {response.status_code}")

        except Exception as e:
            logger.error(f"[{self.tx_id}] Source commit error: {e}")
            # Continue anyway - transaction is committed

    async def _commit_target(self):
        """Phase 2b: Commit INSERT at target"""
        try:
            # Update ride data with new city
            if self.ride_data:
                self.ride_data["city"] = self.target
                self.ride_data["handoff_status"] = "COMPLETED"
                self.ride_data["locked"] = False
                self.ride_data["transaction_id"] = None

            target_url = REGIONAL_APIS[self.target]
            response = await http_client.post(
                f"{target_url}/2pc/commit",
                json={
                    "ride_id": self.ride_id,
                    "tx_id": self.tx_id,
                    "operation": "INSERT",
                    "ride_data": self.ride_data
                }
            )

            if response.status_code == 200:
                logger.info(f"[{self.tx_id}] Target committed INSERT")
            else:
                logger.error(f"[{self.tx_id}] Target commit failed: {response.status_code}")

        except Exception as e:
            logger.error(f"[{self.tx_id}] Target commit error: {e}")
            # Continue anyway - transaction is committed

    async def _abort_all(self):
        """Abort transaction at both regions"""
        try:
            # Abort source
            source_url = REGIONAL_APIS[self.source]
            await http_client.post(
                f"{source_url}/2pc/abort",
                json={"tx_id": self.tx_id}
            )

            # Abort target
            target_url = REGIONAL_APIS[self.target]
            await http_client.post(
                f"{target_url}/2pc/abort",
                json={"tx_id": self.tx_id}
            )

            logger.info(f"[{self.tx_id}] Transaction aborted at both regions")

        except Exception as e:
            logger.error(f"[{self.tx_id}] Abort error: {e}")

    async def _log_transaction(self, status: str, error: Optional[str] = None):
        """Log transaction to global database"""
        try:
            tx_collection = db_manager.get_transactions_collection()
            await tx_collection.insert_one({
                "tx_id": self.tx_id,
                "ride_id": self.ride_id,
                "source": self.source,
                "target": self.target,
                "status": status,
                "error": error,
                "latency_ms": self._get_latency(),
                "timestamp": datetime.utcnow()
            })
        except Exception as e:
            logger.error(f"[{self.tx_id}] Failed to log transaction: {e}")

    def _get_latency(self) -> float:
        """Calculate latency in milliseconds"""
        return round((time.time() - self.start_time) * 1000, 2)


# ============================================
# HANDOFF ENDPOINT
# ============================================

@app.post("/handoff", response_model=HandoffResponse)
async def initiate_handoff(request: HandoffRequest):
    """
    Initiate cross-region ride handoff using 2PC

    This endpoint coordinates the atomic transfer of a ride from one region to another.
    """
    # Check target region health
    if not health_monitor.is_healthy(request.target):
        logger.warning(f"Handoff buffered: Target region {request.target} is unhealthy")
        return HandoffResponse(
            status="BUFFERED",
            tx_id=str(uuid.uuid4()),
            reason=f"Target region {request.target} is currently unavailable",
            latency_ms=0.0
        )

    # Generate transaction ID
    tx_id = str(uuid.uuid4())

    logger.info(f"Handoff request: {request.ride_id} from {request.source} to {request.target}")

    # Create and execute 2PC coordinator
    coordinator = TwoPhaseCommitCoordinator(
        tx_id=tx_id,
        ride_id=request.ride_id,
        source=request.source,
        target=request.target
    )

    result = await coordinator.execute()

    return result


# ============================================
# QUERY ROUTER & SCATTER-GATHER
# ============================================

class QueryRouter:
    """Routes queries to appropriate regions based on scope"""

    async def search(self, query: RideQuery) -> List[RideResponse]:
        """Execute search based on scope"""
        if query.scope == "local":
            return await self._search_local(query)
        elif query.scope == "global-fast":
            return await self._search_global_fast(query)
        elif query.scope == "global-live":
            return await self._search_global_live(query)
        else:
            return []

    async def _search_local(self, query: RideQuery) -> List[RideResponse]:
        """Route to specific region (must provide city)"""
        if not query.city:
            raise HTTPException(status_code=400, detail="City required for local scope")
        
        region_url = REGIONAL_APIS.get(query.city)
        if not region_url:
            raise HTTPException(status_code=400, detail="Invalid city")

        return await self._fetch_from_region(region_url, query)

    async def _search_global_fast(self, query: RideQuery) -> List[RideResponse]:
        """Query global replica (eventual consistency)"""
        # For now, we'll simulate this by querying the global DB directly
        # In a real system, this would hit the read-only replica
        try:
            rides_collection = db_manager.get_rides_collection()
            filter_query = self._build_mongo_query(query)
            
            cursor = rides_collection.find(filter_query).limit(query.limit)
            rides = await cursor.to_list(length=query.limit)
            
            return [RideResponse(**ride) for ride in rides]
        except Exception as e:
            logger.error(f"Global fast query failed: {e}")
            return []

    async def _search_global_live(self, query: RideQuery) -> List[RideResponse]:
        """Scatter-gather to all regions (strong consistency)"""
        tasks = []
        for url in REGIONAL_APIS.values():
            tasks.append(self._fetch_from_region(url, query))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_rides = []
        for res in results:
            if isinstance(res, list):
                all_rides.extend(res)
            else:
                logger.warning(f"Scatter query failed for one region: {res}")

        # Sort by timestamp descending
        all_rides.sort(key=lambda x: x.timestamp, reverse=True)
        return all_rides[:query.limit]

    async def _fetch_from_region(self, url: str, query: RideQuery) -> List[RideResponse]:
        """Fetch rides from a single region"""
        try:
            # Forward query parameters
            params = query.model_dump(exclude_none=True, exclude={'scope'})
            response = await http_client.get(f"{url}/rides", params=params, timeout=5.0)
            
            if response.status_code == 200:
                return [RideResponse(**r) for r in response.json()]
            return []
        except Exception as e:
            logger.error(f"Fetch from {url} failed: {e}")
            return []

    def _build_mongo_query(self, query: RideQuery) -> dict:
        """Build MongoDB filter from query params"""
        filter_q = {}
        if query.city:
            filter_q["city"] = query.city
        if query.status:
            filter_q["status"] = query.status
        
        if query.min_fare or query.max_fare:
            fare_filter = {}
            if query.min_fare:
                fare_filter["$gte"] = query.min_fare
            if query.max_fare:
                fare_filter["$lte"] = query.max_fare
            filter_q["fare"] = fare_filter
            
        return filter_q


query_router = QueryRouter()


@app.post("/rides/search", response_model=List[RideResponse])
async def search_rides(query: RideQuery):
    """
    Search for rides with configurable consistency scope.
    
    Scopes:
    - local: Query specific region (fastest, requires city)
    - global-fast: Query global replica (eventual consistency)
    - global-live: Scatter-gather to all regions (strong consistency)
    """
    return await query_router.search(query)


# ============================================
# SCATTER-GATHER QUERY ENDPOINTS
# ============================================

@app.get("/stats/all")
async def get_all_statistics() -> Dict[str, RegionalStats]:
    """
    Scatter-gather query: Get statistics from all regions
    """
    try:
        stats = {}

        for region, base_url in REGIONAL_APIS.items():
            try:
                response = await http_client.get(f"{base_url}/stats", timeout=5.0)
                if response.status_code == 200:
                    stats[region] = response.json()
                else:
                    logger.warning(f"Failed to get stats from {region}: {response.status_code}")
                    stats[region] = None

            except Exception as e:
                logger.error(f"Error fetching stats from {region}: {e}")
                stats[region] = None

        return stats

    except Exception as e:
        logger.error(f"Scatter-gather failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/health/all")
async def check_all_health():
    """
    Scatter-gather query: Check health of all regional services
    """
    try:
        health_status = {}

        for region, base_url in REGIONAL_APIS.items():
            try:
                response = await http_client.get(f"{base_url}/health", timeout=5.0)
                if response.status_code == 200:
                    health_status[region] = response.json()
                else:
                    health_status[region] = {"status": "unhealthy", "error": f"HTTP {response.status_code}"}

            except Exception as e:
                health_status[region] = {"status": "unreachable", "error": str(e)}

        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/transactions/history")
async def get_transaction_history(limit: int = 50):
    """Get recent transaction history from global database"""
    try:
        tx_collection = db_manager.get_transactions_collection()

        cursor = tx_collection.find().sort("timestamp", -1).limit(limit)
        transactions = await cursor.to_list(length=limit)

        # Remove MongoDB _id fields
        for tx in transactions:
            tx.pop("_id", None)
            # Convert datetime to ISO string
            if tx.get("timestamp"):
                tx["timestamp"] = tx["timestamp"].isoformat()

        return {
            "total": len(transactions),
            "transactions": transactions
        }

    except Exception as e:
        logger.error(f"Failed to get transaction history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "service": "Global Coordinator",
        "version": "2.0.0",
        "endpoints": {
            "handoff": "POST /handoff - Initiate cross-region ride handoff",
            "search": "POST /rides/search - Search rides (local/global)",
            "stats": "GET /stats/all - Get statistics from all regions",
            "health": "GET /health/all - Check health of all regions",
            "history": "GET /transactions/history - Get transaction history"
        },
        "regions": list(REGIONAL_APIS.keys())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
