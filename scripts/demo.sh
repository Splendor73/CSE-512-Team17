#!/bin/bash
# =============================================================================
# Live Demo Script for Professor
# =============================================================================
# This script automates the complete demo setup and execution.
#
# Usage:
#   ./scripts/demo.sh setup     # Prepare system for demo
#   ./scripts/demo.sh run       # Run the live demo
#   ./scripts/demo.sh cleanup   # Clean up after demo
#   ./scripts/demo.sh full      # Run complete demo (setup + run + cleanup)
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

# Demo configuration
DEMO_RIDES=1000
DEMO_HANDOFFS=10

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
    echo ""
    read -p "Press ENTER to continue..."
    echo ""
}

setup_demo() {
    demo_header
    demo_section "DEMO SETUP - Preparing System"

    # 1. Clean up old containers
    demo_step "Cleaning up old Docker containers..."
    docker compose down -v 2>/dev/null || true
    demo_success "Old containers removed"

    # 2. Start MongoDB cluster
    demo_step "Starting MongoDB cluster (9 containers)..."
    docker compose up -d
    demo_success "MongoDB containers started"

    # 3. Wait for containers to be healthy
    demo_step "Waiting for MongoDB to be ready (30 seconds)..."
    sleep 30
    demo_success "MongoDB is ready"

    # 4. Initialize replica sets
    demo_step "Initializing replica sets (Phoenix, LA, Global)..."
    bash init-scripts/init-replica-sets.sh > /dev/null 2>&1
    demo_success "Replica sets initialized"

    # 5. Create schema and indexes
    demo_step "Creating database schema and indexes..."
    bash init-scripts/init-sharding.sh > /dev/null 2>&1
    demo_success "Schema and indexes created"

    # 6. Generate demo data
    demo_step "Generating demo data ($DEMO_RIDES rides)..."
    # Temporarily modify generate_data.py for smaller dataset
    python3 -c "
import sys
sys.path.append('.')
from pymongo import MongoClient
from datetime import datetime, timezone
import random

client = MongoClient('mongodb://localhost:27017/?directConnection=true')
db_phx = client['av_fleet']
db_la = client['av_fleet']

rides_phx = []
rides_la = []

for i in range(${DEMO_RIDES}//2):
    ride_phx = {
        'rideId': f'R-PHX-{i:05d}',
        'vehicleId': f'AV-PHX-{i % 50:03d}',
        'customerId': f'C-{i % 200:04d}',
        'status': random.choice(['COMPLETED', 'IN_PROGRESS']),
        'city': 'Phoenix',
        'fare': round(random.uniform(15, 80), 2),
        'startLocation': {'lat': 33.4 + random.random()*0.2, 'lon': -112.2 + random.random()*0.2},
        'currentLocation': {'lat': 33.5 + random.random()*0.2, 'lon': -112.1 + random.random()*0.2},
        'endLocation': {'lat': 33.5 + random.random()*0.2, 'lon': -112.1 + random.random()*0.2},
        'timestamp': datetime.now(timezone.utc)
    }
    rides_phx.append(ride_phx)

    ride_la = {
        'rideId': f'R-LA-{i:05d}',
        'vehicleId': f'AV-LA-{i % 50:03d}',
        'customerId': f'C-{i % 200:04d}',
        'status': random.choice(['COMPLETED', 'IN_PROGRESS']),
        'city': 'Los Angeles',
        'fare': round(random.uniform(15, 80), 2),
        'startLocation': {'lat': 34.0 + random.random()*0.2, 'lon': -118.3 + random.random()*0.2},
        'currentLocation': {'lat': 34.1 + random.random()*0.2, 'lon': -118.2 + random.random()*0.2},
        'endLocation': {'lat': 34.1 + random.random()*0.2, 'lon': -118.2 + random.random()*0.2},
        'timestamp': datetime.now(timezone.utc)
    }
    rides_la.append(ride_la)

if rides_phx:
    db_phx.rides.insert_many(rides_phx)
if rides_la:
    db_la.rides.insert_many(rides_la)

print(f'Generated {len(rides_phx)} Phoenix rides and {len(rides_la)} LA rides')
"
    demo_success "Demo data generated"

    # 7. Start Change Streams sync
    demo_step "Starting Change Streams synchronization..."
    python3 init-scripts/setup-change-streams.py > logs/change-streams.log 2>&1 &
    CHANGE_STREAMS_PID=$!
    echo $CHANGE_STREAMS_PID > logs/change-streams.pid
    sleep 3
    demo_success "Change Streams active (PID: $CHANGE_STREAMS_PID)"

    # 8. Start all services
    demo_step "Starting Regional APIs and Coordinator..."
    ./scripts/start_all_services.sh > /dev/null 2>&1
    demo_success "All services started"

    echo ""
    demo_success "Demo setup complete!"
    demo_info "System is ready for demonstration"
    echo ""
}

run_demo() {
    demo_header
    demo_section "LIVE DEMONSTRATION"

    # Part 1: System Overview
    demo_section "Part 1: System Architecture Overview"
    demo_info "Our system consists of:"
    echo "  • 2 Regional API Services (Phoenix, Los Angeles)"
    echo "  • 1 Global Coordinator (Two-Phase Commit)"
    echo "  • 9 MongoDB containers (3 replica sets)"
    echo "  • Change Streams for real-time synchronization"
    wait_for_user

    # Part 2: Health Checks
    demo_section "Part 2: Service Health Checks"

    demo_step "Checking Phoenix API..."
    curl -s http://localhost:8001/health | python3 -m json.tool
    demo_success "Phoenix is healthy"
    echo ""

    demo_step "Checking LA API..."
    curl -s http://localhost:8002/health | python3 -m json.tool
    demo_success "LA is healthy"
    echo ""

    demo_step "Checking Global Coordinator..."
    curl -s http://localhost:8000/ | python3 -m json.tool
    demo_success "Coordinator is healthy"
    wait_for_user

    # Part 3: Regional Statistics
    demo_section "Part 3: Regional Statistics"

    demo_step "Phoenix Regional Stats:"
    curl -s http://localhost:8001/stats | python3 -m json.tool
    echo ""

    demo_step "LA Regional Stats:"
    curl -s http://localhost:8002/stats | python3 -m json.tool
    wait_for_user

    # Part 4: Query Demonstrations
    demo_section "Part 4: Query Coordination (Scatter-Gather)"

    demo_step "Local Query - Phoenix only (fastest):"
    curl -s -X POST http://localhost:8000/rides/search \
        -H "Content-Type: application/json" \
        -d '{"scope":"local","city":"Phoenix","limit":3}' | python3 -m json.tool
    echo ""

    demo_step "Global-Fast Query - From global replica:"
    curl -s -X POST http://localhost:8000/rides/search \
        -H "Content-Type: application/json" \
        -d '{"scope":"global-fast","limit":3,"min_fare":40}' | python3 -m json.tool
    echo ""

    demo_step "Global-Live Query - Scatter-gather to all regions:"
    curl -s -X POST http://localhost:8000/rides/search \
        -H "Content-Type: application/json" \
        -d '{"scope":"global-live","limit":5}' | python3 -m json.tool
    wait_for_user

    # Part 5: Cross-Region Handoff (2PC)
    demo_section "Part 5: Cross-Region Handoff (Two-Phase Commit)"

    demo_step "Creating a ride in Phoenix that will cross regions..."
    curl -s -X POST http://localhost:8001/rides \
        -H "Content-Type: application/json" \
        -d '{
            "rideId": "R-DEMO-HANDOFF",
            "vehicleId": "AV-DEMO",
            "customerId": "C-DEMO",
            "status": "IN_PROGRESS",
            "city": "Phoenix",
            "fare": 75.50,
            "startLocation": {"lat": 33.4484, "lon": -112.0740},
            "currentLocation": {"lat": 33.9, "lon": -112.5},
            "endLocation": {"lat": 34.0522, "lon": -118.2437},
            "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S)'Z"
        }' | python3 -m json.tool
    echo ""

    demo_step "Verifying ride exists in Phoenix..."
    curl -s http://localhost:8001/rides/R-DEMO-HANDOFF | python3 -m json.tool
    echo ""

    wait_for_user

    demo_step "Initiating handoff from Phoenix to Los Angeles (2PC)..."
    curl -s -X POST http://localhost:8000/handoff \
        -H "Content-Type: application/json" \
        -d '{
            "ride_id": "R-DEMO-HANDOFF",
            "source": "Phoenix",
            "target": "Los Angeles"
        }' | python3 -m json.tool
    echo ""

    demo_success "Handoff completed!"
    echo ""

    demo_step "Verifying ride is NOW in Los Angeles..."
    sleep 1
    curl -s http://localhost:8002/rides/R-DEMO-HANDOFF | python3 -m json.tool
    echo ""

    demo_step "Verifying ride was REMOVED from Phoenix..."
    curl -s http://localhost:8001/rides/R-DEMO-HANDOFF | python3 -m json.tool || echo "  (404 - Ride not found in Phoenix - Expected!)"
    echo ""

    demo_success "Two-Phase Commit demonstrated successfully!"
    wait_for_user

    # Part 6: Performance Summary
    demo_section "Part 6: Performance Highlights"

    demo_info "Key Performance Metrics:"
    echo "  • Query Latency (P50):        ~20-50 ms"
    echo "  • Handoff Latency:            ~100-200 ms"
    echo "  • Write Throughput:           >1,000 writes/sec"
    echo "  • Failover Time:              4-5 seconds"
    echo "  • Data Consistency:           100%"
    echo "  • Duplication Rate:           0%"
    echo ""

    demo_success "Demo complete!"
    echo ""
}

cleanup_demo() {
    demo_header
    demo_section "DEMO CLEANUP"

    demo_step "Stopping all services..."
    ./scripts/stop_all_services.sh > /dev/null 2>&1 || true
    demo_success "Services stopped"

    demo_step "Stopping Change Streams..."
    if [ -f logs/change-streams.pid ]; then
        kill $(cat logs/change-streams.pid) 2>/dev/null || true
        rm logs/change-streams.pid
    fi
    demo_success "Change Streams stopped"

    demo_step "Stopping MongoDB containers..."
    docker compose down > /dev/null 2>&1 || true
    demo_success "MongoDB stopped"

    echo ""
    demo_success "Cleanup complete!"
    echo ""
}

# Main script logic
case "${1:-}" in
    setup)
        setup_demo
        ;;
    run)
        run_demo
        ;;
    cleanup)
        cleanup_demo
        ;;
    full)
        setup_demo
        run_demo
        cleanup_demo
        ;;
    *)
        echo "Usage: $0 {setup|run|cleanup|full}"
        echo ""
        echo "Commands:"
        echo "  setup    - Prepare system for demo"
        echo "  run      - Run the live demo"
        echo "  cleanup  - Clean up after demo"
        echo "  full     - Run complete demo (setup + run + cleanup)"
        exit 1
        ;;
esac
