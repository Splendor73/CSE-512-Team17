#!/bin/bash
# =============================================================================
# Setup Script for Testing
# =============================================================================
# Prepares the system for testing by running all setup steps from demo.sh
# (Steps 1-7) without running the actual demos.
#
# After this completes, all services will be running and ready for:
# - Load testing
# - Consistency verification
# - Benchmark tests
#
# Usage:
#   ./scripts/setup_for_testing.sh
# =============================================================================

set -e

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
    echo -e "${MAGENTA}║${NC}     ${CYAN}Fleet Management System - Setup for Testing${NC}           ${MAGENTA}║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════════╝${NC}"
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

# =============================================================================
# Step 1: Start MongoDB Cluster
# =============================================================================
demo_header
demo_section "Step 1: Start MongoDB Cluster"
demo_info "Goal: Start 9 MongoDB containers (3 replica sets x 3 nodes)."

demo_step "Cleaning up old containers and volumes..."
docker compose down -v 2>/dev/null || true
docker system prune -f --volumes 2>/dev/null || true

demo_step "Starting 9 MongoDB containers..."
docker compose up -d

demo_step "Waiting 30 seconds for MongoDB startup..."
sleep 30

demo_step "Verifying containers..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep mongodb
demo_success "MongoDB cluster started successfully."

# =============================================================================
# Step 2: Initialize Replica Sets
# =============================================================================
demo_section "Step 2: Initialize Replica Sets"
demo_info "Goal: Configure Raft consensus for automatic failover."

demo_step "Initializing replica sets..."
bash init-scripts/init-replica-sets.sh
demo_success "Replica sets initialized."

# =============================================================================
# Step 3: Create Database Schema
# =============================================================================
demo_section "Step 3: Create Database Schema"
demo_info "Goal: Create collections and indexes for performance."

demo_step "Creating schema and indexes..."
bash init-scripts/init-sharding.sh
demo_success "Schema and indexes created."

# =============================================================================
# Step 4: Generate Test Data
# =============================================================================
demo_section "Step 4: Generate Test Data"
demo_info "Goal: Generate 10,030 synthetic rides across regions."

demo_step "Generating 10,030 rides..."
python3 data-generation/generate_data.py
demo_success "Data generation complete."

# =============================================================================
# Step 5: Start Change Streams Sync
# =============================================================================
demo_section "Step 5: Start Change Streams Sync"
demo_info "Goal: Sync Phoenix/LA data to Global replica for analytics."

demo_step "Starting Change Streams..."
mkdir -p logs
export NON_INTERACTIVE=true
python3 init-scripts/setup-change-streams.py > logs/change-streams.log 2>&1 &
CHANGE_STREAMS_PID=$!
echo $CHANGE_STREAMS_PID > logs/change-streams.pid
sleep 3
demo_success "Change Streams active (PID: $CHANGE_STREAMS_PID)."

# =============================================================================
# Step 6: Start Application Services
# =============================================================================
demo_section "Step 6: Start Application Services"
demo_info "Goal: Start Regional APIs and Global Coordinator."

demo_step "Starting services..."
./scripts/start_all_services.sh > /dev/null 2>&1
demo_success "All services started."

# =============================================================================
# Step 7: Verify Everything Works
# =============================================================================
demo_section "Step 7: Verify Everything Works"

demo_step "Checking health endpoints..."
curl -s http://localhost:8001/health > /dev/null && demo_success "Phoenix API: healthy" || echo -e "${RED}✗${NC} Phoenix API failed"
curl -s http://localhost:8002/health > /dev/null && demo_success "LA API: healthy" || echo -e "${RED}✗${NC} LA API failed"
curl -s http://localhost:8000/health > /dev/null && demo_success "Coordinator: healthy" || echo -e "${RED}✗${NC} Coordinator failed"

demo_step "Fetching statistics..."
curl -s http://localhost:8001/stats | python3 -m json.tool 2>/dev/null | grep -E "(total_rides|region)" | head -5

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}                ${CYAN}Setup Complete! Ready for Testing${NC}              ${GREEN}║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Services Running:${NC}"
echo "  Phoenix API:    http://localhost:8001"
echo "  LA API:         http://localhost:8002"
echo "  Coordinator:    http://localhost:8000"
echo ""
echo -e "${CYAN}API Documentation:${NC}"
echo "  Phoenix Docs:   http://localhost:8001/docs"
echo "  LA Docs:        http://localhost:8002/docs"
echo "  Coordinator:    http://localhost:8000/docs"
echo ""
echo -e "${CYAN}Logs:${NC}"
echo "  logs/phoenix_api.log"
echo "  logs/la_api.log"
echo "  logs/coordinator.log"
echo "  logs/change-streams.log"
echo ""
echo -e "${YELLOW}Now you can run individual tests:${NC}"
echo ""
echo "  # Load test (Phoenix)"
echo "  locust -f tests/load/locustfile.py RegionalAPIUser --host http://localhost:8001 --users 100 --spawn-rate 10 --run-time 5m --headless"
echo ""
echo "  # Consistency verification"
echo "  python tests/benchmark.py --consistency-check --operations 1000"
echo ""
echo "  # All benchmarks"
echo "  python tests/benchmark.py --all"
echo ""
echo -e "${YELLOW}To stop services:${NC}"
echo "  ./scripts/stop_all_services.sh"
echo "  kill \$(cat logs/change-streams.pid)"
echo ""
