#!/bin/bash
# =============================================================================
# Live Demo Script for Professor
# =============================================================================
# This script automates the complete demo setup and execution, strictly following
# the "Step-by-Step Manual Setup" and "Live Demonstrations" sections in 
# docs/codbase_info.md.
#
# Usage:
#   ./scripts/demo.sh
# =============================================================================

set -e

# Default to interactive mode unless specified
if [ "$1" == "--non-interactive" ]; then
    export NON_INTERACTIVE=true
else
    unset NON_INTERACTIVE
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

demo_header() {
    echo ""
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║${NC}     ${CYAN}Distributed Fleet Management System - Live Demo${NC}        ${MAGENTA}║${NC}"
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo ""
}

demo_section() {
    echo ""
    echo -e "${BLUE}┌────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${BLUE}│${NC} $1"
    echo -e "${BLUE}└────────────────────────────────────────────────────────────┘${NC}"
    echo ""
}

demo_step() {
    echo -e "${YELLOW}▶${NC} $1"
}

demo_success() {
    echo -e "${GREEN}✓${NC} $1"
}

demo_info() {
    echo -e "${CYAN}ℹ${NC} $1"
}

wait_for_user() {
    if [ "${NON_INTERACTIVE}" != "true" ]; then
        echo ""
        read -p "Press ENTER to continue..."
        echo ""
    else
        echo ""
        echo "Continuing (Non-Interactive Mode)..."
        sleep 2
        echo ""
    fi
}

# =============================================================================
# Step 1: Start MongoDB Cluster
# =============================================================================
demo_header
demo_section "Step 1: Start MongoDB Cluster"
demo_info "Testing: Infrastructure Setup"
demo_info "Goal: Start 9 MongoDB containers (3 replica sets x 3 nodes)."

demo_step "Cleaning up old containers..."
docker compose down -v 2>/dev/null || true

demo_step "Starting 9 MongoDB containers..."
docker compose up -d

demo_step "Waiting 30 seconds for MongoDB startup..."
sleep 30

demo_step "Verifying containers..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep mongodb
demo_success "MongoDB cluster started successfully."
wait_for_user

# =============================================================================
# Step 2: Initialize Replica Sets
# =============================================================================
demo_section "Step 2: Initialize Replica Sets"
demo_info "Testing: Fault Tolerance Configuration"
demo_info "Goal: Configure Raft consensus for automatic failover."

demo_step "Initializing replica sets..."
bash init-scripts/init-replica-sets.sh
demo_success "Replica sets initialized."
wait_for_user

# =============================================================================
# Step 3: Create Database Schema
# =============================================================================
demo_section "Step 3: Create Database Schema"
demo_info "Testing: Database Design & Indexing"
demo_info "Goal: Create collections and indexes for performance."

demo_step "Creating schema and indexes..."
bash init-scripts/init-sharding.sh
demo_success "Schema and indexes created."
wait_for_user

# =============================================================================
# Step 4: Generate Test Data
# =============================================================================
demo_section "Step 4: Generate Test Data"
demo_info "Testing: Data Ingestion"
demo_info "Goal: Generate 10,030 synthetic rides across regions."

demo_step "Generating 10,030 rides..."
python3 data-generation/generate_data.py
demo_success "Data generation complete."
wait_for_user

# =============================================================================
# Step 5: Start Change Streams Sync
# =============================================================================
demo_section "Step 5: Start Change Streams Sync"
demo_info "Testing: Real-Time Synchronization"
demo_info "Goal: Sync Phoenix/LA data to Global replica for analytics."

demo_step "Starting Change Streams..."
mkdir -p logs
NON_INTERACTIVE=true python3 init-scripts/setup-change-streams.py > logs/change-streams.log 2>&1 &
CHANGE_STREAMS_PID=$!
echo $CHANGE_STREAMS_PID > logs/change-streams.pid
sleep 3
demo_success "Change Streams active (PID: $CHANGE_STREAMS_PID)."
wait_for_user

# =============================================================================
# Step 6: Start Application Services
# =============================================================================
demo_section "Step 6: Start Application Services"
demo_info "Testing: API & Coordinator Services"
demo_info "Goal: Start Regional APIs and Global Coordinator."

demo_step "Starting services..."
./scripts/start_all_services.sh > /dev/null 2>&1
demo_success "All services started."
wait_for_user

# =============================================================================
# Step 7: Verify Everything Works
# =============================================================================
demo_section "Step 7: Verify Everything Works"
demo_info "Testing: System Health & Data Integrity"
demo_info "Goal: Ensure all components are healthy and data is partitioned."

demo_step "Test 1: Check service health"
curl -s http://localhost:8001/health | python3 -m json.tool
curl -s http://localhost:8002/health | python3 -m json.tool
curl -s http://localhost:8000/ | python3 -m json.tool
echo ""

demo_step "Test 2: Count rides in each database"
echo "Phoenix Rides (Expected: 5020):"
mongosh "mongodb://localhost:27017/av_fleet" --quiet --eval "db.rides.countDocuments({city: 'Phoenix'})"
echo "LA Rides (Expected: 5010):"
mongosh "mongodb://localhost:27020/av_fleet" --quiet --eval "db.rides.countDocuments({city: 'Los Angeles'})"
echo "Global Rides (Expected: 10030):"
mongosh "mongodb://localhost:27023/av_fleet" --quiet --eval "db.rides.countDocuments({})"
echo ""

demo_step "Test 3: Verify replica set status"
mongosh --port 27017 --quiet --eval "rs.status().members.forEach(m => print(m.name, '-', m.stateStr))"
demo_success "System verification complete."
wait_for_user

# =============================================================================
# Demo 1: Query Performance
# =============================================================================
demo_section "Demo 1: Query Performance (Partitioning)"
demo_info "Testing: Geographic Partitioning"
demo_info "Goal: Show that local queries are fast and global queries scan all regions."

demo_step "Local Query - Phoenix only (Fastest):"
time curl -s -X POST http://localhost:8000/rides/search \
  -H "Content-Type: application/json" \
  -d '{"scope":"local","city":"Phoenix","status":"IN_PROGRESS","limit":3}' | python3 -m json.tool
demo_success "Local query returned results from Phoenix only."
wait_for_user

demo_step "Scatter-gather query (all regions):"
time curl -s -X POST http://localhost:8000/rides/search \
  -H "Content-Type: application/json" \
  -d '{"scope":"global-live","status":"IN_PROGRESS","limit":3}' | python3 -m json.tool
demo_success "Global query returned results from Phoenix AND LA."
wait_for_user

# =============================================================================
# Demo 2: Two-Phase Commit
# =============================================================================
demo_section "Demo 2: Two-Phase Commit (Atomic Handoff)"
demo_info "Testing: Atomic Data Transfer"
demo_info "Goal: Move a ride from Phoenix to LA without duplication or loss."

demo_step "Step 1: Create a ride in Phoenix"
curl -s -X POST http://localhost:8001/rides \
  -H "Content-Type: application/json" \
  -d '{
    "rideId": "R-888888",
    "vehicleId": "AV-8888",
    "customerId": "C-888888",
    "status": "IN_PROGRESS",
    "city": "Phoenix",
    "fare": 75.50,
    "startLocation": {"lat": 33.4484, "lon": -112.0740},
    "currentLocation": {"lat": 33.9, "lon": -112.5},
    "endLocation": {"lat": 34.0522, "lon": -118.2437},
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }' | python3 -m json.tool

demo_step "Step 2: Verify ride exists in Phoenix"
curl -s http://localhost:8001/rides/R-888888 | python3 -m json.tool
wait_for_user

demo_step "Step 3: Trigger handoff (Phoenix → LA)"
curl -s -X POST http://localhost:8000/handoff \
  -H "Content-Type: application/json" \
  -d '{
    "ride_id": "R-888888",
    "source": "Phoenix",
    "target": "Los Angeles"
  }' | python3 -m json.tool

demo_step "Step 4: Verify ride is NOW in LA"
curl -s http://localhost:8002/rides/R-888888 | python3 -m json.tool
wait_for_user

demo_step "Step 5: Verify ride was REMOVED from Phoenix"
curl -s http://localhost:8001/rides/R-888888 | python3 -m json.tool || echo "Ride not found (Expected)"

demo_success "Two-Phase Commit demonstrated successfully."
wait_for_user

# =============================================================================
# Demo 3: Automatic Failover
# =============================================================================
demo_section "Demo 3: Automatic Failover (Fault Tolerance)"
demo_info "Testing: Database Replication & Leader Election"
demo_info "Goal: Show that the system survives a primary node crash."

demo_step "Step 1: Check Phoenix replica set status"
mongosh --port 27017 --quiet --eval "rs.status().members.forEach(m => print(m.name, '-', m.stateStr))"
wait_for_user

demo_step "Step 2: Kill the primary node (simulate server crash)"
docker stop mongodb-phx-1
demo_info "Waiting 5 seconds for automatic failover..."
sleep 5

demo_step "Step 3: Check replica set status again"
mongosh --port 27018 --quiet --eval "rs.status().members.forEach(m => print(m.name, '-', m.stateStr))"
wait_for_user

demo_step "Step 4: Verify Phoenix API still works (auto-reconnected)"
curl -s http://localhost:8001/health | python3 -m json.tool
wait_for_user

demo_step "Step 5: Restart crashed node"
docker start mongodb-phx-1
demo_info "Waiting 10 seconds for it to sync..."
sleep 10

demo_step "Step 6: Check status (phx-1 rejoins as secondary)"
mongosh --port 27018 --quiet --eval "rs.status().members.forEach(m => print(m.name, '-', m.stateStr))"

demo_success "Automatic failover demonstrated successfully."
wait_for_user

# =============================================================================
# Demo 4: Change Streams
# =============================================================================
demo_section "Demo 4: Change Streams (Real-Time Sync)"
demo_info "Testing: Real-Time Synchronization"
demo_info "Goal: Sync Phoenix/LA data to Global replica for analytics."

demo_step "Step 1: Check Global count before insert"
mongosh "mongodb://localhost:27023/av_fleet" --quiet --eval "db.rides.countDocuments({})"
wait_for_user

demo_step "Step 2: Insert a new ride into Phoenix"
mongosh "mongodb://localhost:27017/av_fleet" --quiet --eval "
db.rides.insertOne({
  rideId: 'R-SYNC-TEST-' + Date.now(),
  vehicleId: 'AV-SYNC',
  customerId: 'C-SYNC',
  city: 'Phoenix',
  status: 'IN_PROGRESS',
  fare: 30.00,
  timestamp: new Date(),
  startLocation: {lat: 33.45, lon: -112.07},
  currentLocation: {lat: 33.50, lon: -112.10},
  endLocation: {lat: 33.50, lon: -112.10}
})
"
wait_for_user

demo_step "Step 3: Wait 2 seconds (Change Streams sync lag)"
sleep 2

demo_step "Step 4: Check Global count after sync"
mongosh "mongodb://localhost:27023/av_fleet" --quiet --eval "db.rides.countDocuments({})"
wait_for_user

demo_step "Step 5: Verify the specific ride exists in Global"
mongosh "mongodb://localhost:27023/av_fleet" --quiet --eval "
var ride = db.rides.findOne({vehicleId: 'AV-SYNC'});
if (ride) {
  print('✅ Ride synced to Global!');
  print('   RideId:', ride.rideId);
  print('   City:', ride.city);
} else {
  print('❌ Ride not found in Global');
}
"
demo_success "Real-time sync demonstrated successfully."
wait_for_user

# =============================================================================
# Demo 5: Vehicle Simulator
# =============================================================================
demo_section "Demo 5: Vehicle Simulator (Boundary Crossing & Handoffs)"
demo_info "Testing: End-to-End System with Live Traffic"
demo_info "Goal: Simulate 100 autonomous vehicles crossing boundaries (Stress Test)."

demo_step "Running simulator for 60 seconds (100 vehicles)..."
python3 services/vehicle_simulator.py --vehicles 100 --speed 50 --duration 60

demo_success "Simulation complete."
wait_for_user

# =============================================================================
# Shutdown
# =============================================================================
demo_section "Shutdown"
demo_info "Cleaning up resources..."

demo_step "Stopping all services..."
./scripts/stop_all_services.sh > /dev/null 2>&1 || true

demo_step "Stopping Change Streams..."
if [ -f logs/change-streams.pid ]; then
    kill $(cat logs/change-streams.pid) 2>/dev/null || true
    rm logs/change-streams.pid
fi

demo_step "Stopping MongoDB containers..."
docker compose down > /dev/null 2>&1 || true

demo_success "Cleanup complete!"
echo ""
