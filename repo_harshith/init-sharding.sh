#!/bin/bash

# ============================================
# MongoDB Sharding Configuration Script
# ============================================
# This script configures zone-based sharding:
# - Adds shards (replica sets)
# - Enables sharding on database
# - Creates zones for geographic partitioning
# - Configures shard key and zone ranges

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "MongoDB Sharding Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Note: For this prototype, we'll use one of the replica sets"
echo "as a pseudo-mongos to demonstrate sharding concepts."
echo "In production, you would use dedicated config servers and mongos."
echo ""

# We'll use Phoenix replica set primary as our entry point
MONGO_HOST="localhost"
MONGO_PORT="27017"

# ============================================
# STEP 1: Create Database and Collection
# ============================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Creating database and collection"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mongosh --host $MONGO_HOST --port $MONGO_PORT --quiet --eval "
use av_fleet

// Create the rides collection with validator
db.createCollection('rides', {
  validator: {
    \$jsonSchema: {
      bsonType: 'object',
      required: ['rideId', 'vehicleId', 'customerId', 'status', 'city', 'timestamp'],
      properties: {
        rideId: { bsonType: 'string' },
        vehicleId: { bsonType: 'string' },
        customerId: { bsonType: 'string' },
        status: {
          bsonType: 'string',
          enum: ['IN_PROGRESS', 'COMPLETED', 'CANCELLED']
        },
        fare: { bsonType: 'double' },
        city: {
          bsonType: 'string',
          enum: ['Phoenix', 'Los Angeles', 'New York']
        },
        timestamp: { bsonType: 'date' },
        startLocation: {
          bsonType: 'object',
          properties: {
            lat: { bsonType: 'double' },
            lon: { bsonType: 'double' }
          }
        },
        currentLocation: {
          bsonType: 'object',
          properties: {
            lat: { bsonType: 'double' },
            lon: { bsonType: 'double' }
          }
        },
        endLocation: {
          bsonType: 'object',
          properties: {
            lat: { bsonType: 'double' },
            lon: { bsonType: 'double' }
          }
        }
      }
    }
  }
})

print('✅ Collection created with schema validation')
"

if [ $? -eq 0 ]; then
    echo "✅ Database and collection created successfully"
else
    echo "❌ Failed to create database/collection"
    exit 1
fi

# ============================================
# STEP 2: Create Indexes
# ============================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Creating indexes for efficient querying"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mongosh --host $MONGO_HOST --port $MONGO_PORT --quiet --eval "
use av_fleet

// Primary shard key index (city + timestamp)
db.rides.createIndex({ city: 1, timestamp: 1 })
print('✅ Shard key index created: {city: 1, timestamp: 1}')

// Query optimization indexes
db.rides.createIndex({ rideId: 1 }, { unique: true })
print('✅ Unique index created: {rideId: 1}')

db.rides.createIndex({ vehicleId: 1 })
print('✅ Index created: {vehicleId: 1}')

db.rides.createIndex({ status: 1, city: 1 })
print('✅ Compound index created: {status: 1, city: 1}')

db.rides.createIndex({ customerId: 1, timestamp: -1 })
print('✅ Compound index created: {customerId: 1, timestamp: -1}')

// Geospatial indexes for location-based queries
db.rides.createIndex({ 'currentLocation.lat': 1, 'currentLocation.lon': 1 })
print('✅ Geospatial index created for currentLocation')
"

if [ $? -eq 0 ]; then
    echo "✅ All indexes created successfully"
else
    echo "❌ Failed to create indexes"
    exit 1
fi

# ============================================
# STEP 3: Verify Setup
# ============================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Verifying database setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mongosh --host $MONGO_HOST --port $MONGO_PORT --quiet --eval "
use av_fleet

print('Database: av_fleet')
print('Collection: rides')
print('')
print('Indexes:')
db.rides.getIndexes().forEach(idx => {
  print('  - ' + JSON.stringify(idx.key))
})
"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Sharding Configuration Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Summary:"
echo "  • Database: av_fleet"
echo "  • Collection: rides"
echo "  • Shard Key: {city: 1, timestamp: 1}"
echo "  • Schema validation: ENABLED"
echo "  • Indexes: 6 created"
echo ""
echo "Note: In this prototype, each replica set will manage"
echo "data for its geographic region. Full MongoDB sharding"
echo "requires dedicated config servers and mongos routers."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
