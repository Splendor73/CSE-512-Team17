"""
Integration Tests for Complete System
======================================

Tests the full system with live MongoDB and all services working together.

Prerequisites:
- MongoDB running on localhost:27017
- Phoenix Regional API on port 8001
- LA Regional API on port 8002
- Global Coordinator on port 8000

Run with: pytest tests/integration/test_integration.py -v
"""

import pytest
import asyncio
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone


# Test configuration
MONGODB_URI = "mongodb://localhost:27017"
COORDINATOR_URL = "http://localhost:8000"
PHOENIX_API_URL = "http://localhost:8001"
LA_API_URL = "http://localhost:8002"


@pytest.fixture(scope="function")
async def mongodb_client():
    """Create MongoDB client for integration tests"""
    client = AsyncIOMotorClient(MONGODB_URI)
    yield client
    client.close()


@pytest.fixture(scope="function")
async def http_client():
    """Create HTTP client for API calls"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        yield client


@pytest.fixture(scope="function")
async def clean_database(mongodb_client):
    """Clean database before each test"""
    db = mongodb_client["rideshare"]

    # Drop all collections
    await db["phoenix_rides"].delete_many({})
    await db["la_rides"].delete_many({})
    await db["transactions"].delete_many({})

    yield

    # Clean up after test
    await db["phoenix_rides"].delete_many({})
    await db["la_rides"].delete_many({})
    await db["transactions"].delete_many({})


@pytest.mark.integration
@pytest.mark.asyncio
class TestRegionalAPIs:
    """Integration tests for Regional APIs"""

    async def test_phoenix_api_health(self, http_client):
        """Test Phoenix API health endpoint"""
        response = await http_client.get(f"{PHOENIX_API_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["region"] == "Phoenix"

    async def test_la_api_health(self, http_client):
        """Test LA API health endpoint"""
        response = await http_client.get(f"{LA_API_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["region"] == "Los Angeles"

    async def test_create_ride_phoenix(self, http_client, clean_database):
        """Test creating a ride in Phoenix"""
        ride_data = {
            "rideId": "R-INT-001",
            "vehicleId": "AV-PHX-001",
            "customerId": "C-001",
            "status": "IN_PROGRESS",
            "city": "Phoenix",
            "fare": 25.50,
            "startLocation": {"lat": 33.4484, "lon": -112.0740},
            "currentLocation": {"lat": 33.4484, "lon": -112.0740},
            "endLocation": {"lat": 33.5000, "lon": -112.1000},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        response = await http_client.post(f"{PHOENIX_API_URL}/rides", json=ride_data)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Ride created successfully"
        assert data["rideId"] == "R-INT-001"

    async def test_get_ride_phoenix(self, http_client, clean_database):
        """Test retrieving a ride from Phoenix"""
        # First create a ride
        ride_data = {
            "rideId": "R-INT-002",
            "vehicleId": "AV-PHX-002",
            "customerId": "C-002",
            "status": "COMPLETED",
            "city": "Phoenix",
            "fare": 30.00,
            "startLocation": {"lat": 33.4484, "lon": -112.0740},
            "currentLocation": {"lat": 33.5000, "lon": -112.1000},
            "endLocation": {"lat": 33.5000, "lon": -112.1000},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await http_client.post(f"{PHOENIX_API_URL}/rides", json=ride_data)

        # Now retrieve it
        response = await http_client.get(f"{PHOENIX_API_URL}/rides/R-INT-002")
        assert response.status_code == 200
        data = response.json()
        assert data["rideId"] == "R-INT-002"
        assert data["city"] == "Phoenix"
        assert data["fare"] == 30.00


@pytest.mark.integration
@pytest.mark.asyncio
class TestTwoPhaseCommit:
    """Integration tests for Two-Phase Commit handoff"""

    async def test_successful_handoff(self, http_client, clean_database):
        """Test successful ride handoff from Phoenix to LA"""
        # Step 1: Create a ride in Phoenix
        ride_data = {
            "rideId": "R-HANDOFF-001",
            "vehicleId": "AV-PHX-HANDOFF",
            "customerId": "C-HANDOFF",
            "status": "IN_PROGRESS",
            "city": "Phoenix",
            "fare": 50.00,
            "startLocation": {"lat": 33.4484, "lon": -112.0740},
            "currentLocation": {"lat": 33.9000, "lon": -112.5000},  # Near border
            "endLocation": {"lat": 34.0522, "lon": -118.2437},  # LA destination
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        create_response = await http_client.post(f"{PHOENIX_API_URL}/rides", json=ride_data)
        assert create_response.status_code == 200

        # Step 2: Initiate handoff via coordinator
        handoff_request = {
            "ride_id": "R-HANDOFF-001",
            "source": "Phoenix",
            "target": "Los Angeles"
        }

        handoff_response = await http_client.post(
            f"{COORDINATOR_URL}/handoff",
            json=handoff_request
        )

        assert handoff_response.status_code == 200
        handoff_data = handoff_response.json()
        assert handoff_data["status"] in ["SUCCESS", "BUFFERED"]

        if handoff_data["status"] == "SUCCESS":
            # Step 3: Verify ride is now in LA and removed from Phoenix
            await asyncio.sleep(0.5)  # Give time for async operations

            # Check Phoenix - should not exist
            phoenix_response = await http_client.get(f"{PHOENIX_API_URL}/rides/R-HANDOFF-001")
            assert phoenix_response.status_code == 404

            # Check LA - should exist
            la_response = await http_client.get(f"{LA_API_URL}/rides/R-HANDOFF-001")
            assert la_response.status_code == 200
            la_data = la_response.json()
            assert la_data["rideId"] == "R-HANDOFF-001"
            assert la_data["city"] == "Los Angeles"

    async def test_handoff_nonexistent_ride(self, http_client, clean_database):
        """Test handoff of non-existent ride fails gracefully"""
        handoff_request = {
            "ride_id": "R-NONEXISTENT",
            "source": "Phoenix",
            "target": "Los Angeles"
        }

        handoff_response = await http_client.post(
            f"{COORDINATOR_URL}/handoff",
            json=handoff_request
        )

        assert handoff_response.status_code == 200
        data = handoff_response.json()
        assert data["status"] in ["FAILED", "BUFFERED"]


@pytest.mark.integration
@pytest.mark.asyncio
class TestScatterGather:
    """Integration tests for scatter-gather queries"""

    async def test_local_query_phoenix(self, http_client, clean_database):
        """Test local query to Phoenix only"""
        # Create rides in Phoenix
        for i in range(3):
            ride_data = {
                "rideId": f"R-PHX-{i}",
                "vehicleId": f"AV-PHX-{i}",
                "customerId": f"C-{i}",
                "status": "COMPLETED",
                "city": "Phoenix",
                "fare": 20.0 + i * 5,
                "startLocation": {"lat": 33.4484, "lon": -112.0740},
                "currentLocation": {"lat": 33.5000, "lon": -112.1000},
                "endLocation": {"lat": 33.5000, "lon": -112.1000},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await http_client.post(f"{PHOENIX_API_URL}/rides", json=ride_data)

        # Query via coordinator with local scope
        query = {
            "scope": "local",
            "city": "Phoenix",
            "limit": 10
        }

        response = await http_client.post(f"{COORDINATOR_URL}/rides/search", json=query)
        assert response.status_code == 200
        rides = response.json()
        assert len(rides) == 3
        assert all(r["city"] == "Phoenix" for r in rides)

    async def test_global_live_query(self, http_client, clean_database):
        """Test global-live scatter-gather across both regions"""
        # Create rides in Phoenix
        for i in range(2):
            ride_data = {
                "rideId": f"R-PHX-GLOBAL-{i}",
                "vehicleId": f"AV-PHX-{i}",
                "customerId": f"C-{i}",
                "status": "COMPLETED",
                "city": "Phoenix",
                "fare": 25.0,
                "startLocation": {"lat": 33.4484, "lon": -112.0740},
                "currentLocation": {"lat": 33.5000, "lon": -112.1000},
                "endLocation": {"lat": 33.5000, "lon": -112.1000},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await http_client.post(f"{PHOENIX_API_URL}/rides", json=ride_data)

        # Create rides in LA
        for i in range(2):
            ride_data = {
                "rideId": f"R-LA-GLOBAL-{i}",
                "vehicleId": f"AV-LA-{i}",
                "customerId": f"C-{i}",
                "status": "COMPLETED",
                "city": "Los Angeles",
                "fare": 30.0,
                "startLocation": {"lat": 34.0522, "lon": -118.2437},
                "currentLocation": {"lat": 34.1000, "lon": -118.3000},
                "endLocation": {"lat": 34.1000, "lon": -118.3000},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await http_client.post(f"{LA_API_URL}/rides", json=ride_data)

        # Query with global-live scope
        query = {
            "scope": "global-live",
            "limit": 10
        }

        response = await http_client.post(f"{COORDINATOR_URL}/rides/search", json=query)
        assert response.status_code == 200
        rides = response.json()

        # Should get rides from both regions
        assert len(rides) == 4
        phoenix_rides = [r for r in rides if r["city"] == "Phoenix"]
        la_rides = [r for r in rides if r["city"] == "Los Angeles"]
        assert len(phoenix_rides) == 2
        assert len(la_rides) == 2

    async def test_query_with_fare_filter(self, http_client, clean_database):
        """Test query with min/max fare filters"""
        # Create rides with different fares
        fares = [15.0, 25.0, 35.0, 45.0]
        for i, fare in enumerate(fares):
            ride_data = {
                "rideId": f"R-FARE-{i}",
                "vehicleId": f"AV-{i}",
                "customerId": f"C-{i}",
                "status": "COMPLETED",
                "city": "Phoenix",
                "fare": fare,
                "startLocation": {"lat": 33.4484, "lon": -112.0740},
                "currentLocation": {"lat": 33.5000, "lon": -112.1000},
                "endLocation": {"lat": 33.5000, "lon": -112.1000},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await http_client.post(f"{PHOENIX_API_URL}/rides", json=ride_data)

        # Query with fare filter
        query = {
            "scope": "local",
            "city": "Phoenix",
            "min_fare": 20.0,
            "max_fare": 40.0,
            "limit": 10
        }

        response = await http_client.post(f"{COORDINATOR_URL}/rides/search", json=query)
        assert response.status_code == 200
        rides = response.json()

        # Should only get rides with fare between 20 and 40
        assert len(rides) == 2
        assert all(20.0 <= r["fare"] <= 40.0 for r in rides)


@pytest.mark.integration
@pytest.mark.asyncio
class TestHealthMonitoring:
    """Integration tests for health monitoring"""

    async def test_coordinator_health(self, http_client):
        """Test coordinator health endpoint"""
        response = await http_client.get(f"{COORDINATOR_URL}/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Global Coordinator"
        assert "regions" in data

    async def test_all_services_healthy(self, http_client):
        """Test that all services report healthy status"""
        # Check Phoenix
        phoenix_response = await http_client.get(f"{PHOENIX_API_URL}/health")
        assert phoenix_response.status_code == 200
        assert phoenix_response.json()["status"] == "healthy"

        # Check LA
        la_response = await http_client.get(f"{LA_API_URL}/health")
        assert la_response.status_code == 200
        assert la_response.json()["status"] == "healthy"

        # Check Coordinator
        coord_response = await http_client.get(f"{COORDINATOR_URL}/")
        assert coord_response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
