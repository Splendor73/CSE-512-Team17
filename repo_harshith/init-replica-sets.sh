#!/bin/bash

# ============================================
# MongoDB Replica Set Initialization Script
# PHX + LA + GLOBAL Architecture
# ============================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Initializing MongoDB Replica Sets"
echo "PHX + LA + Global Architecture"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Wait for MongoDB containers to be fully ready
echo ""
echo "Waiting for MongoDB containers to be ready..."
sleep 5

# ============================================
# PHOENIX REGION (rs-phoenix)
# ============================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Initializing PHOENIX replica set (rs-phoenix)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mongosh --host localhost --port 27017 --quiet --eval "
rs.initiate({
  _id: 'rs-phoenix',
  members: [
    { _id: 0, host: 'mongodb-phx-1:27017', priority: 2 },
    { _id: 1, host: 'mongodb-phx-2:27017', priority: 1 },
    { _id: 2, host: 'mongodb-phx-3:27017', priority: 1 }
  ]
})
"

if [ $? -eq 0 ]; then
    echo "✅ Phoenix replica set initialized successfully"
else
    echo "❌ Failed to initialize Phoenix replica set"
    exit 1
fi

# Wait for primary election
echo "Waiting for primary election..."
sleep 5

# ============================================
# LOS ANGELES REGION (rs-la)
# ============================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Initializing LOS ANGELES replica set (rs-la)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mongosh --host localhost --port 27020 --quiet --eval "
rs.initiate({
  _id: 'rs-la',
  members: [
    { _id: 0, host: 'mongodb-la-1:27017', priority: 2 },
    { _id: 1, host: 'mongodb-la-2:27017', priority: 1 },
    { _id: 2, host: 'mongodb-la-3:27017', priority: 1 }
  ]
})
"

if [ $? -eq 0 ]; then
    echo "✅ Los Angeles replica set initialized successfully"
else
    echo "❌ Failed to initialize Los Angeles replica set"
    exit 1
fi

# Wait for primary election
echo "Waiting for primary election..."
sleep 5

# ============================================
# GLOBAL REGION (rs-global)
# ============================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Initializing GLOBAL replica set (rs-global)"
echo "This replica will contain ALL rides from PHX + LA"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mongosh --host localhost --port 27023 --quiet --eval "
rs.initiate({
  _id: 'rs-global',
  members: [
    { _id: 0, host: 'mongodb-global-1:27017', priority: 2 },
    { _id: 1, host: 'mongodb-global-2:27017', priority: 1 },
    { _id: 2, host: 'mongodb-global-3:27017', priority: 1 }
  ]
})
"

if [ $? -eq 0 ]; then
    echo "✅ Global replica set initialized successfully"
else
    echo "❌ Failed to initialize Global replica set"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ALL REPLICA SETS INITIALIZED SUCCESSFULLY!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Waiting for replica sets to stabilize..."
sleep 10

# ============================================
# VERIFY REPLICA SETS
# ============================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Verifying Replica Set Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "Phoenix Replica Set Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
mongosh --host localhost --port 27017 --quiet --eval "rs.status().members.forEach(m => print('  ' + m.name + ' - ' + m.stateStr))"

echo ""
echo "Los Angeles Replica Set Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
mongosh --host localhost --port 27020 --quiet --eval "rs.status().members.forEach(m => print('  ' + m.name + ' - ' + m.stateStr))"

echo ""
echo "Global Replica Set Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
mongosh --host localhost --port 27023 --quiet --eval "rs.status().members.forEach(m => print('  ' + m.name + ' - ' + m.stateStr))"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Replica Set Initialization Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Architecture Summary:"
echo "  • Phoenix Region: Stores Phoenix rides only (Port 27017)"
echo "  • Los Angeles Region: Stores LA rides only (Port 27020)"
echo "  • Global Region: READ-ONLY replica with ALL rides (Port 27023)"
echo ""
echo "Next Step: Run ./init-scripts/init-sharding.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
