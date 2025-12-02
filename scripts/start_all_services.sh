#!/bin/bash
# =============================================================================
# Start All Services Script
# =============================================================================
# This script starts all three microservices for the rideshare system:
# 1. Phoenix Regional API (port 8001)
# 2. Los Angeles Regional API (port 8002)
# 3. Global Coordinator (port 8000)
#
# Prerequisites:
# - MongoDB running on localhost:27017
# - conda environment 'cse512' activated
#
# Usage:
#   ./scripts/start_all_services.sh
#
# To stop all services:
#   ./scripts/stop_all_services.sh
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Rideshare System - Starting Services${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if MongoDB is running
echo -e "${YELLOW}[1/4] Checking MongoDB connection...${NC}"
if ! mongosh --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; then
    echo -e "${RED}ERROR: MongoDB is not running on localhost:27017${NC}"
    echo -e "${YELLOW}Please start MongoDB first:${NC}"
    echo -e "  brew services start mongodb-community"
    echo -e "  OR"
    echo -e "  mongod --dbpath /path/to/data"
    exit 1
fi
echo -e "${GREEN}✓ MongoDB is running${NC}"
echo ""

# Create logs directory
mkdir -p logs

# Start Phoenix Regional API
echo -e "${YELLOW}[2/4] Starting Phoenix Regional API (port 8001)...${NC}"
cd services
uvicorn phoenix_api:app --host 0.0.0.0 --port 8001 > ../logs/phoenix_api.log 2>&1 &
PHOENIX_PID=$!
echo $PHOENIX_PID > ../logs/phoenix_api.pid
cd ..
echo -e "${GREEN}✓ Phoenix API started (PID: $PHOENIX_PID)${NC}"
echo ""

# Wait a moment for Phoenix to start
sleep 2

# Start LA Regional API
echo -e "${YELLOW}[3/4] Starting Los Angeles Regional API (port 8002)...${NC}"
cd services
uvicorn la_api:app --host 0.0.0.0 --port 8002 > ../logs/la_api.log 2>&1 &
LA_PID=$!
echo $LA_PID > ../logs/la_api.pid
cd ..
echo -e "${GREEN}✓ LA API started (PID: $LA_PID)${NC}"
echo ""

# Wait a moment for LA to start
sleep 2

# Start Global Coordinator
echo -e "${YELLOW}[4/4] Starting Global Coordinator (port 8000)...${NC}"
cd services
uvicorn coordinator:app --host 0.0.0.0 --port 8000 > ../logs/coordinator.log 2>&1 &
COORDINATOR_PID=$!
echo $COORDINATOR_PID > ../logs/coordinator.pid
cd ..
echo -e "${GREEN}✓ Coordinator started (PID: $COORDINATOR_PID)${NC}"
echo ""

# Wait for all services to be ready
echo -e "${YELLOW}Waiting for all services to be ready...${NC}"
sleep 3

# Health check
echo -e "${YELLOW}Running health checks...${NC}"
echo ""

# Check Phoenix
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Phoenix API: healthy (http://localhost:8001)${NC}"
else
    echo -e "${RED}✗ Phoenix API: not responding${NC}"
fi

# Check LA
if curl -s http://localhost:8002/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ LA API: healthy (http://localhost:8002)${NC}"
else
    echo -e "${RED}✗ LA API: not responding${NC}"
fi

# Check Coordinator
if curl -s http://localhost:8000/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Coordinator: healthy (http://localhost:8000)${NC}"
else
    echo -e "${RED}✗ Coordinator: not responding${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  All services started successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Service URLs:"
echo -e "  Phoenix API:    http://localhost:8001"
echo -e "  LA API:         http://localhost:8002"
echo -e "  Coordinator:    http://localhost:8000"
echo ""
echo -e "API Documentation:"
echo -e "  Phoenix Docs:   http://localhost:8001/docs"
echo -e "  LA Docs:        http://localhost:8002/docs"
echo -e "  Coordinator:    http://localhost:8000/docs"
echo ""
echo -e "Logs available in: ${YELLOW}logs/${NC}"
echo -e "  - logs/phoenix_api.log"
echo -e "  - logs/la_api.log"
echo -e "  - logs/coordinator.log"
echo ""
echo -e "To stop all services, run:"
echo -e "  ${YELLOW}./scripts/stop_all_services.sh${NC}"
echo ""
