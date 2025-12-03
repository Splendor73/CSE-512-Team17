"""
Tests for Query Coordination (Scatter-Gather)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from services.coordinator import QueryRouter, app, query_router
from services.models import RideQuery, RideResponse

@pytest.mark.asyncio
class TestQueryRouter:
    """Test QueryRouter class"""

    @patch("services.coordinator.http_client", new_callable=AsyncMock)
    async def test_search_local(self, mock_http):
        """Test local scope routing"""
        router = QueryRouter()
        query = RideQuery(scope="local", city="Phoenix", limit=5)

        # Mock regional response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "rideId": "R-100001",
                "vehicleId": "AV-1",
                "customerId": "C-1",
                "status": "COMPLETED",
                "city": "Phoenix",
                "fare": 20.0,
                "startLocation": {"lat": 0, "lon": 0},
                "currentLocation": {"lat": 0, "lon": 0},
                "endLocation": {"lat": 0, "lon": 0},
                "timestamp": "2024-12-02T10:00:00Z"
            }
        ]
        mock_http.get.return_value = mock_response

        results = await router.search(query)
        assert len(results) == 1
        assert results[0].city == "Phoenix"
        
        # Verify correct URL called
        mock_http.get.assert_called_with(
            "http://localhost:8001/rides", 
            params={"city": "Phoenix", "limit": 5}, 
            timeout=5.0
        )

    @patch("services.coordinator.db_manager")
    async def test_search_global_fast(self, mock_db):
        """Test global-fast scope (direct DB access)"""
        router = QueryRouter()
        query = RideQuery(scope="global-fast", limit=5)

        # Mock DB cursor
        mock_collection = MagicMock()
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = [
            {
                "rideId": "R-100002",
                "vehicleId": "AV-2",
                "customerId": "C-2",
                "status": "IN_PROGRESS",
                "city": "Los Angeles",
                "fare": 30.0,
                "startLocation": {"lat": 0, "lon": 0},
                "currentLocation": {"lat": 0, "lon": 0},
                "endLocation": {"lat": 0, "lon": 0},
                "timestamp": "2024-12-02T11:00:00Z"
            }
        ]
        mock_collection.find.return_value.limit.return_value = mock_cursor
        mock_db.get_rides_collection.return_value = mock_collection

        results = await router.search(query)
        assert len(results) == 1
        assert results[0].rideId == "R-100002"

    @patch("services.coordinator.http_client", new_callable=AsyncMock)
    async def test_search_global_live(self, mock_http):
        """Test global-live scope (scatter-gather)"""
        router = QueryRouter()
        query = RideQuery(scope="global-live", limit=10)

        # Mock responses for Phoenix and LA
        # We need to mock separate calls for different URLs
        
        async def side_effect(url, params=None, timeout=None):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if "8001" in url: # Phoenix
                mock_resp.json.return_value = [{
                    "rideId": "R-100001",
                    "vehicleId": "AV-1",
                    "customerId": "C-1",
                    "status": "COMPLETED",
                    "city": "Phoenix",
                    "fare": 20.0,
                    "startLocation": {"lat": 0, "lon": 0},
                    "currentLocation": {"lat": 0, "lon": 0},
                    "endLocation": {"lat": 0, "lon": 0},
                    "timestamp": "2024-12-02T10:00:00Z"
                }]
            else: # LA
                mock_resp.json.return_value = [{
                    "rideId": "R-100002",
                    "vehicleId": "AV-2",
                    "customerId": "C-2",
                    "status": "COMPLETED",
                    "city": "Los Angeles",
                    "fare": 25.0,
                    "startLocation": {"lat": 0, "lon": 0},
                    "currentLocation": {"lat": 0, "lon": 0},
                    "endLocation": {"lat": 0, "lon": 0},
                    "timestamp": "2024-12-02T11:00:00Z" # Later timestamp
                }]
            return mock_resp

        mock_http.get.side_effect = side_effect

        results = await router.search(query)
        
        # Should have 2 results
        assert len(results) == 2
        
        # Should be sorted by timestamp desc (LA first)
        assert results[0].rideId == "R-100002"
        assert results[1].rideId == "R-100001"


from fastapi.testclient import TestClient

client = TestClient(app)

class TestSearchEndpoint:
    """Test /rides/search endpoint"""

    @patch("services.coordinator.query_router.search")
    def test_search_endpoint(self, mock_search):
        """Test endpoint delegates to router"""
        mock_search.return_value = []
        
        response = client.post("/rides/search", json={
            "scope": "global-live",
            "min_fare": 15.0
        })
        
        assert response.status_code == 200
        mock_search.assert_called_once()
