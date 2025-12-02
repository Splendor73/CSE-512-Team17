# Integration Tests

This directory contains integration tests that verify the complete rideshare system with all services running together.

## Prerequisites

### 1. MongoDB
Ensure MongoDB is running on `localhost:27017`:

```bash
# Start MongoDB (macOS with Homebrew)
brew services start mongodb-community

# OR run MongoDB manually
mongod --dbpath /path/to/data
```

Verify MongoDB is running:
```bash
mongosh --eval "db.adminCommand('ping')"
```

### 2. Python Environment
Activate the conda environment:
```bash
conda activate cse512
```

### 3. Install Dependencies
```bash
pip install httpx pytest pytest-asyncio motor
```

## Running Integration Tests

### Step 1: Start All Services

From the project root, run:
```bash
./scripts/start_all_services.sh
```

This will start:
- Phoenix Regional API on `http://localhost:8001`
- Los Angeles Regional API on `http://localhost:8002`
- Global Coordinator on `http://localhost:8000`

Verify services are running:
```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8000/
```

### Step 2: Run Integration Tests

Run all integration tests:
```bash
pytest tests/integration/ -v -m integration
```

Run specific test classes:
```bash
# Test Regional APIs only
pytest tests/integration/test_integration.py::TestRegionalAPIs -v

# Test Two-Phase Commit only
pytest tests/integration/test_integration.py::TestTwoPhaseCommit -v

# Test Scatter-Gather only
pytest tests/integration/test_integration.py::TestScatterGather -v

# Test Health Monitoring only
pytest tests/integration/test_integration.py::TestHealthMonitoring -v
```

### Step 3: Stop All Services

When done testing:
```bash
./scripts/stop_all_services.sh
```

## Test Coverage

### TestRegionalAPIs
- ✅ Health check endpoints for both regions
- ✅ Create ride in Phoenix
- ✅ Retrieve ride from Phoenix
- ✅ Create ride in Los Angeles
- ✅ Retrieve ride from Los Angeles

### TestTwoPhaseCommit
- ✅ Successful ride handoff from Phoenix to LA
- ✅ Verify ride removed from source region
- ✅ Verify ride added to target region
- ✅ Handle handoff of non-existent ride

### TestScatterGather
- ✅ Local query to specific region (Phoenix)
- ✅ Local query to specific region (LA)
- ✅ Global-live query across both regions
- ✅ Query with fare filters (min/max)
- ✅ Query with status filters

### TestHealthMonitoring
- ✅ Coordinator health endpoint
- ✅ All services report healthy status
- ✅ Health monitor detects unhealthy regions

## Troubleshooting

### MongoDB Not Running
**Error:** `ServerSelectionTimeoutError`

**Solution:**
```bash
brew services start mongodb-community
# Wait a few seconds, then retry
```

### Port Already in Use
**Error:** `Address already in use`

**Solution:**
```bash
# Find and kill processes using ports 8000-8002
lsof -ti:8000 | xargs kill -9
lsof -ti:8001 | xargs kill -9
lsof -ti:8002 | xargs kill -9

# Or use the stop script
./scripts/stop_all_services.sh
```

### Service Not Responding
**Error:** Test fails with connection timeout

**Solution:**
1. Check service logs:
   ```bash
   tail -f logs/phoenix_api.log
   tail -f logs/la_api.log
   tail -f logs/coordinator.log
   ```

2. Restart services:
   ```bash
   ./scripts/stop_all_services.sh
   ./scripts/start_all_services.sh
   ```

### Tests Fail with "Collection not found"
**Solution:** The test fixtures automatically clean the database before each test. If you see this error, ensure MongoDB is properly connected.

## Test Data Cleanup

Integration tests use the `clean_database` fixture which:
- Deletes all documents from `phoenix_rides` collection before each test
- Deletes all documents from `la_rides` collection before each test
- Deletes all documents from `transactions` collection before each test
- Cleans up after each test completes

This ensures tests are isolated and repeatable.

## Running with Coverage

To see code coverage from integration tests:

```bash
pytest tests/integration/ -v --cov=services --cov-report=html
```

Open `htmlcov/index.html` in your browser to view the coverage report.

## Continuous Integration

To run integration tests in CI/CD:

1. Start MongoDB in CI environment
2. Start all services in background
3. Wait for health checks to pass
4. Run integration tests
5. Stop all services
6. Stop MongoDB

Example GitHub Actions workflow snippet:
```yaml
- name: Start MongoDB
  run: |
    brew services start mongodb-community
    sleep 5

- name: Start Services
  run: ./scripts/start_all_services.sh

- name: Run Integration Tests
  run: pytest tests/integration/ -v -m integration

- name: Stop Services
  run: ./scripts/stop_all_services.sh
```

## Performance Benchmarks

Expected test execution times:
- **TestRegionalAPIs**: ~2-3 seconds
- **TestTwoPhaseCommit**: ~3-4 seconds (includes 2PC protocol)
- **TestScatterGather**: ~2-3 seconds (parallel queries)
- **TestHealthMonitoring**: ~1-2 seconds

Total integration test suite: **~10-15 seconds**

## Next Steps

After integration tests pass:
1. Run load tests with Locust (see `tests/load/`)
2. Measure latency and throughput
3. Generate performance reports
4. Run chaos engineering tests (region failures)
