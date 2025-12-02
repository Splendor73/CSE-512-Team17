"""
Unit Tests for Los Angeles Regional API
========================================

Tests for FastAPI endpoints and request/response models.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

# Mock the database manager before importing the app
with patch('services.la_api.db_manager') as mock_db:
    mock_db.connect = AsyncMock()
    mock_db.disconnect = AsyncMock()
    from services.la_api import app

client = TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint"""

    @patch('services.la_api.db_manager')
    def test_health_check_healthy(self, mock_db_manager):
        """Test health check returns healthy status"""
        mock_db_manager.health_check = AsyncMock(return_value={
            "status": "healthy",
            "primary": "mongodb-la-1:27020",
            "replication_lag_ms": 10,
            "last_write": None
        })

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["region"] == "Los Angeles"


class TestRideEndpoints:
    """Test ride CRUD endpoints"""

    def test_create_ride_validation(self):
        """Test ride creation with invalid data"""
        invalid_ride = {
            "rideId": "INVALID",  # Wrong format
            "vehicleId": "AV-1234",
            "customerId": "C-567890",
            "status": "IN_PROGRESS",
            "city": "Los Angeles",
            "fare": 25.50,
            "startLocation": {"lat": 34.05, "lon": -118.24},
            "currentLocation": {"lat": 34.06, "lon": -118.25},
            "endLocation": {"lat": 34.07, "lon": -118.26}
        }

        response = client.post("/rides", json=invalid_ride)
        assert response.status_code == 422  # Validation error


class TestStatisticsEndpoint:
    """Test statistics endpoint"""

    @patch('services.la_api.db_manager')
    def test_get_statistics(self, mock_db_manager):
        """Test statistics aggregation"""
        mock_collection = MagicMock()
        mock_collection.aggregate = MagicMock()
        mock_collection.aggregate.return_value.to_list = AsyncMock(return_value=[{
            "total": [{"count": 3000}],
            "by_status": [
                {"_id": "COMPLETED", "count": 2900},
                {"_id": "IN_PROGRESS", "count": 60},
                {"_id": "CANCELLED", "count": 40}
            ],
            "revenue": [{"total": 75000.0, "avg": 25.0}]
        }])

        mock_db_manager.get_rides_collection.return_value = mock_collection

        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["region"] == "Los Angeles"
        assert "total_rides" in data
        assert "total_revenue" in data


class Test2PCEndpoints:
    """Test Two-Phase Commit endpoints"""

    @patch('services.la_api.db_manager')
    def test_prepare_insert_success(self, mock_db_manager):
        """Test prepare phase for INSERT operation"""
        mock_collection = MagicMock()
        mock_collection.insert_one = AsyncMock()

        mock_db_manager.get_transactions_collection.return_value = mock_collection

        prepare_request = {
            "ride_id": "R-123456",
            "tx_id": "test-tx-456",
            "operation": "INSERT"
        }

        response = client.post("/2pc/prepare", json=prepare_request)
        assert response.status_code == 200
        data = response.json()
        assert data["vote"] == "COMMIT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
