"""
Unit Tests for Pydantic Models
===============================
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from services.models import (
    Location, RideCreate, RideUpdate, RideResponse,
    PrepareRequest, HandoffRequest, RegionalStats
)


class TestLocationModel:
    """Test Location model validation"""

    def test_valid_location(self):
        """Test valid GPS coordinates"""
        loc = Location(lat=33.4484, lon=-112.0740)
        assert loc.lat == 33.4484
        assert loc.lon == -112.0740

    def test_invalid_latitude(self):
        """Test latitude out of range"""
        with pytest.raises(ValidationError):
            Location(lat=100.0, lon=-112.0740)  # Lat > 90

    def test_invalid_longitude(self):
        """Test longitude out of range"""
        with pytest.raises(ValidationError):
            Location(lat=33.4484, lon=-200.0)  # Lon < -180


class TestRideCreateModel:
    """Test RideCreate model validation"""

    def test_valid_ride_create(self):
        """Test creating valid ride"""
        ride = RideCreate(
            rideId="R-123456",
            vehicleId="AV-1234",
            customerId="C-567890",
            status="IN_PROGRESS",
            city="Phoenix",
            fare=25.50,
            startLocation={"lat": 33.45, "lon": -112.07},
            currentLocation={"lat": 33.46, "lon": -112.08},
            endLocation={"lat": 33.47, "lon": -112.09}
        )
        assert ride.rideId == "R-123456"
        assert ride.city == "Phoenix"
        assert ride.fare == 25.50

    def test_invalid_ride_id_format(self):
        """Test ride ID format validation"""
        with pytest.raises(ValidationError):
            RideCreate(
                rideId="INVALID",  # Must be R-123456 format
                vehicleId="AV-1234",
                customerId="C-567890",
                status="IN_PROGRESS",
                city="Phoenix",
                fare=25.50,
                startLocation={"lat": 33.45, "lon": -112.07},
                currentLocation={"lat": 33.46, "lon": -112.08},
                endLocation={"lat": 33.47, "lon": -112.09}
            )

    def test_invalid_status(self):
        """Test status must be valid enum"""
        with pytest.raises(ValidationError):
            RideCreate(
                rideId="R-123456",
                vehicleId="AV-1234",
                customerId="C-567890",
                status="INVALID_STATUS",  # Not a valid status
                city="Phoenix",
                fare=25.50,
                startLocation={"lat": 33.45, "lon": -112.07},
                currentLocation={"lat": 33.46, "lon": -112.08},
                endLocation={"lat": 33.47, "lon": -112.09}
            )

    def test_fare_validation(self):
        """Test fare must be >= $5.00"""
        with pytest.raises(ValidationError):
            RideCreate(
                rideId="R-123456",
                vehicleId="AV-1234",
                customerId="C-567890",
                status="IN_PROGRESS",
                city="Phoenix",
                fare=2.00,  # Too low
                startLocation={"lat": 33.45, "lon": -112.07},
                currentLocation={"lat": 33.46, "lon": -112.08},
                endLocation={"lat": 33.47, "lon": -112.09}
            )


class TestHandoffRequestModel:
    """Test HandoffRequest model validation"""

    def test_valid_handoff_request(self):
        """Test valid handoff request"""
        handoff = HandoffRequest(
            ride_id="R-123456",
            source="Phoenix",
            target="Los Angeles"
        )
        assert handoff.source == "Phoenix"
        assert handoff.target == "Los Angeles"

    def test_source_and_target_same(self):
        """Test source and target must be different"""
        with pytest.raises(ValidationError):
            HandoffRequest(
                ride_id="R-123456",
                source="Phoenix",
                target="Phoenix"  # Same as source!
            )


class TestRegionalStatsModel:
    """Test RegionalStats model"""

    def test_valid_stats(self):
        """Test valid regional statistics"""
        stats = RegionalStats(
            region="Phoenix",
            total_rides=5020,
            active_rides=25,
            completed_rides=4990,
            cancelled_rides=5,
            total_revenue=125500.00,
            avg_fare=25.00
        )
        assert stats.region == "Phoenix"
        assert stats.total_rides == 5020
        assert stats.avg_fare == 25.00


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
