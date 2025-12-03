"""
Phoenix Regional API Service
=============================

FastAPI service for Phoenix regional ride management.
Handles CRUD operations and 2PC participant logic.

Run: uvicorn services.phoenix_api:app --host 0.0.0.0 --port 8001
"""

import logging
import time
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from services.models import (
    RideCreate, RideUpdate, RideResponse,
    PrepareRequest, PrepareResponse,
    CommitRequest, CommitResponse,
    AbortRequest, RegionalStats, HealthResponse
)
from services.database import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database manager
db_manager = DatabaseManager("Phoenix")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup/shutdown"""
    # Startup
    logger.info("Starting Phoenix Regional API...")
    await db_manager.connect()
    yield
    # Shutdown
    logger.info("Shutting down Phoenix Regional API...")
    await db_manager.disconnect()


app = FastAPI(
    title="Phoenix Regional API",
    version="2.0.0",
    description="Regional service for Phoenix AV fleet management",
    lifespan=lifespan
)


# ============================================
# HEALTH CHECK ENDPOINTS
# ============================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    start_time = time.time()

    try:
        health_info = await db_manager.health_check()

        return HealthResponse(
            status="healthy" if health_info["status"] == "healthy" else "unhealthy",
            region="Phoenix",
            mongodb_primary=health_info.get("primary", "unknown"),
            mongodb_status=health_info["status"],
            replication_lag_ms=health_info.get("replication_lag_ms"),
            last_write=health_info.get("last_write"),
            uptime_seconds=time.time() - start_time
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "region": "Phoenix",
                "error": str(e)
            }
        )


# ============================================
# RIDE CRUD ENDPOINTS
# ============================================

@app.post("/rides", response_model=RideResponse, status_code=status.HTTP_201_CREATED)
async def create_ride(ride: RideCreate):
    """Create a new ride in Phoenix"""
    try:
        rides_collection = db_manager.get_rides_collection()

        # Check if ride already exists
        existing = await rides_collection.find_one({"rideId": ride.rideId})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ride {ride.rideId} already exists"
            )

        # Insert ride
        ride_dict = ride.model_dump()
        await rides_collection.insert_one(ride_dict)

        logger.info(f"Created ride {ride.rideId} in Phoenix")

        return RideResponse(**ride_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@app.get("/rides/{ride_id}", response_model=RideResponse)
async def get_ride(ride_id: str):
    """Get a specific ride by ID"""
    try:
        rides_collection = db_manager.get_rides_collection()
        ride = await rides_collection.find_one({"rideId": ride_id})

        if not ride:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ride {ride_id} not found"
            )

        # Remove MongoDB _id field
        ride.pop("_id", None)
        return RideResponse(**ride)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@app.get("/rides", response_model=List[RideResponse])
async def list_rides(
    city: Optional[str] = None,
    min_fare: Optional[float] = None,
    max_fare: Optional[float] = None,
    status: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
):
    """List rides with optional filtering"""
    try:
        rides_collection = db_manager.get_rides_collection()

        # Build query
        query = {}
        if city:
            query["city"] = city
        if status:
            query["status"] = status
        
        # Fare range query
        if min_fare is not None or max_fare is not None:
            query["fare"] = {}
            if min_fare is not None:
                query["fare"]["$gte"] = min_fare
            if max_fare is not None:
                query["fare"]["$lte"] = max_fare

        # Execute query
        cursor = rides_collection.find(query).skip(skip).limit(limit)
        rides = await cursor.to_list(length=limit)

        # Remove MongoDB _id fields
        for ride in rides:
            ride.pop("_id", None)

        return [RideResponse(**ride) for ride in rides]

    except Exception as e:
        logger.error(f"Failed to list rides: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@app.put("/rides/{ride_id}", response_model=RideResponse)
async def update_ride(ride_id: str, ride_update: RideUpdate):
    """Update a ride"""
    try:
        rides_collection = db_manager.get_rides_collection()

        # Build update document
        update_doc = {k: v for k, v in ride_update.model_dump().items() if v is not None}

        if not update_doc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        # Update ride
        result = await rides_collection.find_one_and_update(
            {"rideId": ride_id},
            {"$set": update_doc},
            return_document=True
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ride {ride_id} not found"
            )

        logger.info(f"Updated ride {ride_id} in Phoenix")

        result.pop("_id", None)
        return RideResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@app.delete("/rides/{ride_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ride(ride_id: str):
    """Delete a ride"""
    try:
        rides_collection = db_manager.get_rides_collection()

        result = await rides_collection.delete_one({"rideId": ride_id})

        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ride {ride_id} not found"
            )

        logger.info(f"Deleted ride {ride_id} from Phoenix")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete ride: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


# ============================================
# STATISTICS ENDPOINTS
# ============================================

@app.get("/stats", response_model=RegionalStats)
async def get_statistics():
    """Get regional statistics"""
    try:
        rides_collection = db_manager.get_rides_collection()

        # Run aggregation pipeline
        pipeline = [
            {
                "$facet": {
                    "total": [{"$count": "count"}],
                    "by_status": [
                        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
                    ],
                    "revenue": [
                        {"$group": {"_id": None, "total": {"$sum": "$fare"}, "avg": {"$avg": "$fare"}}}
                    ]
                }
            }
        ]

        result = await rides_collection.aggregate(pipeline).to_list(length=1)
        stats = result[0] if result else {}

        # Extract counts
        total_rides = stats.get("total", [{}])[0].get("count", 0)

        status_counts = {item["_id"]: item["count"] for item in stats.get("by_status", [])}
        completed = status_counts.get("COMPLETED", 0)
        active = status_counts.get("IN_PROGRESS", 0)
        cancelled = status_counts.get("CANCELLED", 0)

        revenue_data = stats.get("revenue", [{}])[0]
        total_revenue = revenue_data.get("total", 0.0)
        avg_fare = revenue_data.get("avg", 0.0)

        return RegionalStats(
            region="Phoenix",
            total_rides=total_rides,
            active_rides=active,
            completed_rides=completed,
            cancelled_rides=cancelled,
            total_revenue=round(total_revenue, 2),
            avg_fare=round(avg_fare, 2)
        )

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


# ============================================
# TWO-PHASE COMMIT ENDPOINTS (2PC Participant)
# ============================================

@app.post("/2pc/prepare", response_model=PrepareResponse)
async def prepare_transaction(request: PrepareRequest):
    """
    Phase 1 of 2PC: Prepare to commit transaction

    For DELETE: Lock the ride and vote COMMIT if found
    For INSERT: Vote COMMIT (space always available)
    """
    try:
        rides_collection = db_manager.get_rides_collection()
        tx_collection = db_manager.get_transactions_collection()

        if request.operation == "DELETE":
            # Find and lock the ride
            ride = await rides_collection.find_one({"rideId": request.ride_id})

            if not ride:
                logger.warning(f"Prepare failed: Ride {request.ride_id} not found")
                return PrepareResponse(
                    vote="ABORT",
                    reason=f"Ride {request.ride_id} not found in Phoenix"
                )

            # Check if already locked
            if ride.get("locked"):
                logger.warning(f"Prepare failed: Ride {request.ride_id} already locked")
                return PrepareResponse(
                    vote="ABORT",
                    reason=f"Ride {request.ride_id} is locked by another transaction"
                )

            # Lock the ride
            await rides_collection.update_one(
                {"rideId": request.ride_id},
                {
                    "$set": {
                        "locked": True,
                        "transaction_id": request.tx_id,
                        "handoff_status": "PREPARING"
                    }
                }
            )

            # Save transaction state
            ride.pop("_id", None)
            await tx_collection.insert_one({
                "tx_id": request.tx_id,
                "ride_id": request.ride_id,
                "operation": request.operation,
                "state": "PREPARED",
                "ride_data": ride,
                "timestamp": datetime.utcnow()
            })

            logger.info(f"Prepared DELETE for ride {request.ride_id} (tx: {request.tx_id})")
            return PrepareResponse(vote="COMMIT", ride_data=ride)

        elif request.operation == "INSERT":
            # For INSERT, just record the transaction
            await tx_collection.insert_one({
                "tx_id": request.tx_id,
                "ride_id": request.ride_id,
                "operation": request.operation,
                "state": "PREPARED",
                "timestamp": datetime.utcnow()
            })

            logger.info(f"Prepared INSERT for ride {request.ride_id} (tx: {request.tx_id})")
            return PrepareResponse(vote="COMMIT")

    except Exception as e:
        logger.error(f"Prepare failed: {e}")
        return PrepareResponse(vote="ABORT", reason=str(e))


@app.post("/2pc/commit", response_model=CommitResponse)
async def commit_transaction(request: CommitRequest):
    """
    Phase 2 of 2PC: Commit the transaction

    For DELETE: Actually delete the locked ride
    For INSERT: Insert the new ride data
    """
    try:
        rides_collection = db_manager.get_rides_collection()
        tx_collection = db_manager.get_transactions_collection()

        if request.operation == "DELETE":
            # Delete the ride
            result = await rides_collection.delete_one({"rideId": request.ride_id})

            # Update transaction state
            await tx_collection.update_one(
                {"tx_id": request.tx_id},
                {"$set": {"state": "COMMITTED"}}
            )

            logger.info(f"Committed DELETE for ride {request.ride_id} (tx: {request.tx_id})")
            return CommitResponse(status="COMMITTED", deleted_count=result.deleted_count)

        elif request.operation == "INSERT":
            # Insert the ride
            ride_data = request.ride_data
            if ride_data:
                await rides_collection.insert_one(ride_data)

            # Update transaction state
            await tx_collection.update_one(
                {"tx_id": request.tx_id},
                {"$set": {"state": "COMMITTED"}}
            )

            logger.info(f"Committed INSERT for ride {request.ride_id} (tx: {request.tx_id})")
            return CommitResponse(status="COMMITTED", inserted_id=request.ride_id)

    except Exception as e:
        logger.error(f"Commit failed: {e}")
        return CommitResponse(status="ABORTED")


@app.post("/2pc/abort")
async def abort_transaction(request: AbortRequest):
    """Abort transaction and release locks"""
    try:
        rides_collection = db_manager.get_rides_collection()
        tx_collection = db_manager.get_transactions_collection()

        # Find transaction
        tx = await tx_collection.find_one({"tx_id": request.tx_id})

        if tx:
            # Unlock ride if it was locked
            if tx["operation"] == "DELETE":
                await rides_collection.update_one(
                    {"transaction_id": request.tx_id},
                    {
                        "$set": {
                            "locked": False,
                            "transaction_id": None,
                            "handoff_status": None
                        }
                    }
                )

            # Mark transaction as aborted
            await tx_collection.update_one(
                {"tx_id": request.tx_id},
                {"$set": {"state": "ABORTED"}}
            )

        logger.info(f"Aborted transaction {request.tx_id}")
        return {"status": "ABORTED"}

    except Exception as e:
        logger.error(f"Abort failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
