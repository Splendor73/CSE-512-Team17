"""
MongoDB Connection Management
==============================

Handles connections to regional MongoDB replica sets.
"""

import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages MongoDB connections for regional services"""

    def __init__(self, region: str):
        """
        Initialize database manager for a specific region

        Args:
            region: Region name ("Phoenix" or "Los Angeles")
        """
        self.region = region
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None

        # Configure connection URIs based on region
        if region == "Phoenix":
            self.mongo_uri = os.getenv(
                "MONGO_URI_PHX",
                "mongodb://localhost:27017,localhost:27018,localhost:27019/?replicaSet=rs-phoenix"
            )
            self.db_name = "av_fleet"
        elif region == "Los Angeles":
            self.mongo_uri = os.getenv(
                "MONGO_URI_LA",
                "mongodb://localhost:27020,localhost:27021,localhost:27022/?replicaSet=rs-la"
            )
            self.db_name = "av_fleet"
        else:
            raise ValueError(f"Invalid region: {region}. Must be 'Phoenix' or 'Los Angeles'")

    async def connect(self):
        """Establish connection to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=10000,
                retryWrites=True,
                w="majority"  # Write concern for durability
            )

            # Verify connection
            await self.client.admin.command('ping')
            self.db = self.client[self.db_name]

            logger.info(f"Connected to MongoDB for {self.region} region")

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB for {self.region}: {e}")
            raise

    async def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info(f"Disconnected from MongoDB for {self.region} region")

    async def health_check(self) -> dict:
        """
        Check MongoDB health and replication status

        Returns:
            dict: Health check information
        """
        try:
            # Ping database
            await self.client.admin.command('ping')

            # Get replica set status
            rs_status = await self.client.admin.command('replSetGetStatus')

            # Find primary node
            primary = None
            for member in rs_status.get('members', []):
                if member.get('stateStr') == 'PRIMARY':
                    primary = member.get('name')
                    break

            # Get last write timestamp
            oplog = self.client.local.oplog.rs
            last_write = None
            async for entry in oplog.find().sort('ts', -1).limit(1):
                last_write = entry.get('ts').as_datetime() if entry.get('ts') else None

            return {
                "status": "healthy",
                "region": self.region,
                "primary": primary,
                "replication_lag_ms": 0,  # Simplified - would need calculation
                "last_write": last_write
            }

        except Exception as e:
            logger.error(f"Health check failed for {self.region}: {e}")
            return {
                "status": "unhealthy",
                "region": self.region,
                "error": str(e)
            }

    def get_rides_collection(self):
        """Get rides collection"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db.rides

    def get_transactions_collection(self):
        """Get transactions collection for 2PC"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db.transactions


class GlobalDatabaseManager:
    """Manages connection to global replica set"""

    def __init__(self):
        self.mongo_uri = os.getenv(
            "MONGO_URI_GLOBAL",
            "mongodb://localhost:27023,localhost:27024,localhost:27025/?replicaSet=rs-global"
        )
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.db_name = "av_fleet_global"

    async def connect(self):
        """Establish connection to global MongoDB"""
        try:
            self.client = AsyncIOMotorClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=10000,
                retryWrites=True,
                w="majority"
            )

            await self.client.admin.command('ping')
            self.db = self.client[self.db_name]

            logger.info("Connected to Global MongoDB")

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to Global MongoDB: {e}")
            raise

    async def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from Global MongoDB")

    def get_rides_collection(self):
        """Get global rides collection"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db.rides

    def get_transactions_collection(self):
        """Get global transactions collection"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db.transactions
