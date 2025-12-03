"""
Unit Tests for Database Connection Module
==========================================
"""

import pytest
from services.database import DatabaseManager, GlobalDatabaseManager


class TestDatabaseManager:
    """Test DatabaseManager initialization and configuration"""

    def test_phoenix_initialization(self):
        """Test initialization for Phoenix region"""
        db_manager = DatabaseManager("Phoenix")
        assert db_manager.region == "Phoenix"
        assert db_manager.db_name == "av_fleet"
        assert "rs-phoenix" in db_manager.mongo_uri

    def test_la_initialization(self):
        """Test initialization for Los Angeles region"""
        db_manager = DatabaseManager("Los Angeles")
        assert db_manager.region == "Los Angeles"
        assert db_manager.db_name == "av_fleet"
        assert "rs-la" in db_manager.mongo_uri

    def test_invalid_region(self):
        """Test invalid region raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            DatabaseManager("Invalid Region")
        assert "Invalid region" in str(exc_info.value)

    def test_connection_not_established(self):
        """Test accessing collections before connection raises error"""
        db_mgr = DatabaseManager("Phoenix")
        with pytest.raises(RuntimeError) as exc_info:
            db_mgr.get_rides_collection()
        assert "Database not connected" in str(exc_info.value)


class TestGlobalDatabaseManager:
    """Test GlobalDatabaseManager initialization"""

    def test_initialization(self):
        """Test global database manager initialization"""
        db_mgr = GlobalDatabaseManager()
        assert db_mgr.db_name == "av_fleet_global"
        assert "rs-global" in db_mgr.mongo_uri

    def test_connection_not_established(self):
        """Test accessing collections before connection raises error"""
        db_mgr = GlobalDatabaseManager()
        with pytest.raises(RuntimeError) as exc_info:
            db_mgr.get_rides_collection()
        assert "Database not connected" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
