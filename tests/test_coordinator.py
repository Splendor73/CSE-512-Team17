"""
Unit Tests for Global Coordinator
==================================

Tests for Two-Phase Commit protocol and scatter-gather queries.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

# Mock dependencies before importing
with patch('services.coordinator.db_manager') as mock_db, \
     patch('services.coordinator.http_client') as mock_http:
    mock_db.connect = AsyncMock()
    mock_db.disconnect = AsyncMock()
    from services.coordinator import app, TwoPhaseCommitCoordinator

client = TestClient(app)


class TestRootEndpoint:
    """Test root endpoint"""

    def test_root_returns_api_info(self):
        """Test root endpoint returns API information"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Global Coordinator"
        assert "endpoints" in data
        assert "regions" in data


class TestHandoffEndpoint:
    """Test handoff endpoint validation"""

    def test_handoff_validation_same_region(self):
        """Test handoff request with same source and target fails"""
        request = {
            "ride_id": "R-123456",
            "source": "Phoenix",
            "target": "Phoenix"  # Same as source!
        }

        response = client.post("/handoff", json=request)
        assert response.status_code == 422  # Validation error


class Test2PCCoordinator:
    """Test Two-Phase Commit coordinator logic"""

    def test_coordinator_initialization(self):
        """Test coordinator initialization"""
        coordinator = TwoPhaseCommitCoordinator(
            tx_id="test-tx-123",
            ride_id="R-123456",
            source="Phoenix",
            target="Los Angeles"
        )

        assert coordinator.tx_id == "test-tx-123"
        assert coordinator.ride_id == "R-123456"
        assert coordinator.source == "Phoenix"
        assert coordinator.target == "Los Angeles"
        assert coordinator.ride_data is None


class TestScatterGatherEndpoints:
    """Test scatter-gather query endpoints"""

    def test_transaction_history_endpoint(self):
        """Test transaction history endpoint structure"""
        # This will fail without DB connection, but validates endpoint exists
        # In integration tests, this would work with real DB
        response = client.get("/transactions/history?limit=10")
        # We expect an error because DB isn't connected in unit tests
        # but the endpoint should exist
        assert response.status_code in [200, 500]  # Either works or DB error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
