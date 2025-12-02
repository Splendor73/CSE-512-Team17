#!/bin/bash
# =============================================================================
# Stop All Services Script
# =============================================================================
# This script stops all running microservices.
#
# Usage:
#   ./scripts/stop_all_services.sh
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  Rideshare System - Stopping Services${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Function to stop a service
stop_service() {
    local service_name=$1
    local pid_file=$2

    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${YELLOW}Stopping $service_name (PID: $PID)...${NC}"
            kill $PID
            sleep 1

            # Force kill if still running
            if ps -p $PID > /dev/null 2>&1; then
                echo -e "${YELLOW}Force stopping $service_name...${NC}"
                kill -9 $PID 2>/dev/null || true
            fi

            echo -e "${GREEN}✓ $service_name stopped${NC}"
        else
            echo -e "${YELLOW}! $service_name (PID: $PID) not running${NC}"
        fi
        rm -f "$pid_file"
    else
        echo -e "${YELLOW}! $service_name PID file not found${NC}"
    fi
}

# Stop all services
stop_service "Phoenix API" "logs/phoenix_api.pid"
stop_service "LA API" "logs/la_api.pid"
stop_service "Coordinator" "logs/coordinator.pid"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  All services stopped${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
