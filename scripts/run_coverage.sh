#!/bin/bash
# =============================================================================
# Code Coverage Analysis Script
# =============================================================================
# This script runs all unit tests with code coverage analysis.
#
# Usage:
#   ./scripts/run_coverage.sh
#
# Output:
#   - Terminal coverage report
#   - HTML report in htmlcov/
# =============================================================================

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Code Coverage Analysis${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if pytest-cov is installed
if ! python -c "import pytest_cov" 2>/dev/null; then
    echo -e "${YELLOW}Installing pytest-cov...${NC}"
    pip install pytest-cov
fi

# Run tests with coverage
echo -e "${YELLOW}Running unit tests with coverage...${NC}"
echo ""

pytest tests/ \
    --cov=services \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-config=.coveragerc \
    -v

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Coverage Analysis Complete${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "HTML report available at: ${BLUE}htmlcov/index.html${NC}"
echo ""
echo -e "To view the HTML report:"
echo -e "  ${YELLOW}open htmlcov/index.html${NC}"
echo ""
