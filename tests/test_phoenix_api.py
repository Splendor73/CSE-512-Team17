"""
Unit Tests for Phoenix Regional API
====================================

Tests for FastAPI endpoints and request/response models.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

# Mock the database manager before importing the app
with patch('services.phoenix_api.db_manager') as mock_db:
    mock_db.connect = AsyncMock()
    mock_db.disconnect = AsyncMock()
    from services.phoenix_api import app

client = TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint"""

    @patch('services.phoenix_api.db_manager')
    def test_health_check_healthy(self, mock_db_manager):
        """Test health check returns healthy status"""
        mock_db_manager.health_check = AsyncMock(return_value={
            "status": "healthy",
            "primary": "mongodb-phx-1:27017",
            "replication_lag_ms": 10,
            "last_write": None
        })

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["region"] == "Phoenix"


class TestRideEndpoints:
    """Test ride CRUD endpoints"""

    def test_create_ride_validation(self):
        """Test ride creation with invalid data"""
        invalid_ride = {
            "rideId": "INVALID",  # Wrong format
            "vehicleId": "AV-1234",
            "customerId": "C-567890",
            "status": "IN_PROGRESS",
            "city": "Phoenix",
            "fare": 25.50,
            "startLocation": {"lat": 33.45, "lon": -112.07},
            "currentLocation": {"lat": 33.46, "lon": -112.08},
            "endLocation": {"lat": 33.47, "lon": -112.09}
        }

        response = client.post("/rides", json=invalid_ride)
        assert response.status_code == 422  # Validation error


class TestStatisticsEndpoint:
    """Test statistics endpoint"""

    @patch('services.phoenix_api.db_manager')
    def test_get_statistics(self, mock_db_manager):
        """Test statistics aggregation"""
        mock_collection = MagicMock()
        mock_collection.aggregate = MagicMock()
        mock_collection.aggregate.return_value.to_list = AsyncMock(return_value=[{
            "total": [{"count": 5000}],
            "by_status": [
                {"_id": "COMPLETED", "count": 4900},
                {"_id": "IN_PROGRESS", "count": 50},
                {"_id": "CANCELLED", "count": 50}
            ],
            "revenue": [{"total": 125000.0, "avg": 25.0}]
        }])

        mock_db_manager.get_rides_collection.return_value = mock_collection

        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["region"] == "Phoenix"
        assert "total_rides" in data
        assert "total_revenue" in data


class Test2PCEndpoints:
    """Test Two-Phase Commit endpoints"""

    @patch('services.phoenix_api.db_manager')
    def test_prepare_delete_not_found(self, mock_db_manager):
        """Test prepare phase when ride doesn't exist"""
        mock_collection = MagicMock()
        mock_collection.find_one = AsyncMock(return_value=None)

        mock_db_manager.get_rides_collection.return_value = mock_collection
        mock_db_manager.get_transactions_collection.return_value = mock_collection

        prepare_request = {
            "ride_id": "R-999999",
            "tx_id": "test-tx-123",
            "operation": "DELETE"
        }

        response = client.post("/2pc/prepare", json=prepare_request)
        assert response.status_code == 200
        data = response.json()
        assert data["vote"] == "ABORT"
        assert "not found" in data["reason"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
