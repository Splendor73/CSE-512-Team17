"""
Pydantic Models for AV Fleet Management System
===============================================

Data validation models for ride documents and API requests/responses.
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, validator


# ============================================
# LOCATION MODELS
# ============================================

class Location(BaseModel):
    """GPS coordinates"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude (-90 to 90)")
    lon: float = Field(..., ge=-180, le=180, description="Longitude (-180 to 180)")

    class Config:
        json_schema_extra = {
            "example": {
                "lat": 33.4484,
                "lon": -112.0740
            }
        }


# ============================================
# RIDE MODELS
# ============================================

class RideBase(BaseModel):
    """Base ride fields (shared across requests)"""
    rideId: str = Field(..., pattern=r"^R-\d+$", description="Unique ride ID (format: R-123456)")
    vehicleId: str = Field(..., pattern=r"^AV-\d+$", description="Vehicle ID (format: AV-1234)")
    customerId: str = Field(..., pattern=r"^C-\d+$", description="Customer ID (format: C-123456)")
    status: Literal["COMPLETED", "IN_PROGRESS", "CANCELLED"] = Field(..., description="Ride status")
    city: Literal["Phoenix", "Los Angeles"] = Field(..., description="City where ride is registered")
    fare: float = Field(..., ge=0, le=1000, description="Ride fare in USD")
    startLocation: Location = Field(..., description="Ride start location")
    currentLocation: Location = Field(..., description="Current vehicle location")
    endLocation: Location = Field(..., description="Ride end location")

    @validator("fare")
    def fare_must_be_reasonable(cls, v):
        """Validate fare is within reasonable range"""
        if v < 5.0 and v > 0:
            raise ValueError("Fare must be at least $5.00")
        return round(v, 2)


class RideCreate(RideBase):
    """Request model for creating a new ride"""
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Ride timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "rideId": "R-876158",
                "vehicleId": "AV-8752",
                "customerId": "C-117425",
                "status": "IN_PROGRESS",
                "city": "Phoenix",
                "fare": 25.50,
                "startLocation": {"lat": 33.4484, "lon": -112.0740},
                "currentLocation": {"lat": 33.4500, "lon": -112.0800},
                "endLocation": {"lat": 33.4600, "lon": -112.0900}
            }
        }


class RideUpdate(BaseModel):
    """Request model for updating a ride"""
    status: Optional[Literal["COMPLETED", "IN_PROGRESS", "CANCELLED"]] = None
    currentLocation: Optional[Location] = None
    endLocation: Optional[Location] = None
    fare: Optional[float] = Field(None, ge=0, le=1000)

    @validator("fare")
    def fare_must_be_reasonable(cls, v):
        if v is not None and v < 5.0 and v > 0:
            raise ValueError("Fare must be at least $5.00")
        return round(v, 2) if v is not None else None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "COMPLETED",
                "currentLocation": {"lat": 33.4600, "lon": -112.0900},
                "endLocation": {"lat": 33.4600, "lon": -112.0900},
                "fare": 28.75
            }
        }


class RideResponse(RideBase):
    """Response model for ride data"""
    timestamp: datetime
    handoff_status: Optional[str] = None
    locked: bool = False
    transaction_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "rideId": "R-876158",
                "vehicleId": "AV-8752",
                "customerId": "C-117425",
                "status": "COMPLETED",
                "city": "Phoenix",
                "fare": 28.75,
                "timestamp": "2024-12-02T10:30:00Z",
                "startLocation": {"lat": 33.4484, "lon": -112.0740},
                "currentLocation": {"lat": 33.4600, "lon": -112.0900},
                "endLocation": {"lat": 33.4600, "lon": -112.0900},
                "handoff_status": None,
                "locked": False,
                "transaction_id": None
            }
        }


# ============================================
# STATISTICS MODELS
# ============================================

class RegionalStats(BaseModel):
    """Statistics for a single region"""
    region: str
    total_rides: int
    active_rides: int
    completed_rides: int
    cancelled_rides: int
    total_revenue: float
    avg_fare: float

    class Config:
        json_schema_extra = {
            "example": {
                "region": "Phoenix",
                "total_rides": 5020,
                "active_rides": 25,
                "completed_rides": 4990,
                "cancelled_rides": 5,
                "total_revenue": 125500.00,
                "avg_fare": 25.00
            }
        }


# ============================================
# HEALTH CHECK MODELS
# ============================================

class HealthResponse(BaseModel):
    """Health check response"""
    status: Literal["healthy", "degraded", "unhealthy"]
    region: str
    mongodb_primary: str
    mongodb_status: str
    replication_lag_ms: Optional[int] = None
    last_write: Optional[datetime] = None
    uptime_seconds: float

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "region": "Phoenix",
                "mongodb_primary": "mongodb-phx-1:27017",
                "mongodb_status": "connected",
                "replication_lag_ms": 23,
                "last_write": "2024-12-02T10:30:00Z",
                "uptime_seconds": 3600.5
            }
        }


# ============================================
# TWO-PHASE COMMIT MODELS (Phase 2)
# ============================================

class PrepareRequest(BaseModel):
    """2PC Phase 1: Prepare request"""
    ride_id: str
    tx_id: str
    operation: Literal["INSERT", "DELETE"]

    class Config:
        json_schema_extra = {
            "example": {
                "ride_id": "R-876158",
                "tx_id": "a7f3e91c-4b2a-4d8f-9c3a-7e8b5a1d2f9e",
                "operation": "DELETE"
            }
        }


class PrepareResponse(BaseModel):
    """2PC Phase 1: Prepare response"""
    vote: Literal["COMMIT", "ABORT"]
    reason: Optional[str] = None
    ride_data: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "vote": "COMMIT",
                "reason": None,
                "ride_data": {"rideId": "R-876158", "city": "Phoenix"}
            }
        }


class CommitRequest(BaseModel):
    """2PC Phase 2: Commit request"""
    ride_id: str
    tx_id: str
    operation: Literal["INSERT", "DELETE"]
    ride_data: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "ride_id": "R-876158",
                "tx_id": "a7f3e91c-4b2a-4d8f-9c3a-7e8b5a1d2f9e",
                "operation": "DELETE",
                "ride_data": None
            }
        }


class CommitResponse(BaseModel):
    """2PC Phase 2: Commit response"""
    status: Literal["COMMITTED", "ABORTED"]
    deleted_count: Optional[int] = None
    inserted_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "COMMITTED",
                "deleted_count": 1,
                "inserted_id": None
            }
        }


class AbortRequest(BaseModel):
    """2PC Abort request"""
    tx_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "tx_id": "a7f3e91c-4b2a-4d8f-9c3a-7e8b5a1d2f9e"
            }
        }


class HandoffRequest(BaseModel):
    """Request to initiate cross-region handoff"""
    ride_id: str = Field(..., pattern=r"^R-\d+$")
    source: Literal["Phoenix", "Los Angeles"]
    target: Literal["Phoenix", "Los Angeles"]

    @validator("target")
    def source_and_target_must_differ(cls, v, values):
        if "source" in values and v == values["source"]:
            raise ValueError("Source and target must be different regions")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "ride_id": "R-876158",
                "source": "Phoenix",
                "target": "Los Angeles"
            }
        }


class HandoffResponse(BaseModel):
    """Response from handoff operation"""
    status: Literal["SUCCESS", "ABORTED", "BUFFERED"]
    tx_id: str
    reason: Optional[str] = None
    latency_ms: Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "SUCCESS",
                "tx_id": "a7f3e91c-4b2a-4d8f-9c3a-7e8b5a1d2f9e",
                "reason": None,
                "latency_ms": 245.3
            }
        }


# ============================================
# QUERY MODELS (Phase 2)
# ============================================

class RideQuery(BaseModel):
    """Query parameters for ride search"""
    city: Optional[Literal["Phoenix", "Los Angeles"]] = None
    min_fare: Optional[float] = Field(None, ge=0)
    max_fare: Optional[float] = Field(None, ge=0)
    status: Optional[Literal["COMPLETED", "IN_PROGRESS", "CANCELLED"]] = None
    scope: Literal["local", "global-fast", "global-live"] = "global-fast"
    limit: int = Field(50, ge=1, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "city": "Phoenix",
                "min_fare": 20.0,
                "status": "COMPLETED",
                "scope": "global-live",
                "limit": 10
            }
        }
