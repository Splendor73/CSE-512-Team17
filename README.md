# Autonomous Vehicle Fleet Management System

**CSE 512 - Distributed Database Systems**
**Team Project - Phase 1**

A distributed database system for managing autonomous vehicle rides across multiple geographic regions with support for cross-region handoffs, fault tolerance, and global analytics.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Quick Start (5 Minutes)](#-quick-start-5-minutes)
- [Detailed Setup Guide](#-detailed-setup-guide)
- [Phase 1: Completed Features](#-phase-1-completed-features)
- [Data Schema](#-data-schema)
- [MongoDB Compass Guide](#-mongodb-compass-guide)
- [Usage Examples & Queries](#-usage-examples--queries)
- [Performance Metrics](#-performance-metrics)
- [Troubleshooting](#-troubleshooting)
- [Future Work (Phase 2)](#-future-work-phase-2)
- [Team Members](#-team-members)

---

## 🎯 Overview

This system manages a fleet of autonomous vehicles operating across **two primary regions** with a **global analytics replica**:

- **Phoenix, AZ** (50% of traffic) - Regional operational shard
- **Los Angeles, CA** (50% of traffic) - Regional operational shard
- **Global** (100% of data) - Read-only replica for analytics (PHX + LA combined)

### Key Features

✅ **Geographic Partitioning**: Data distributed across regional shards based on city
✅ **Fault Tolerance**: 3-node replica sets per region with automatic failover
✅ **Global Analytics**: Read-only replica with ALL rides from both regions
✅ **Change Streams**: Real-time sync from PHX + LA to Global
✅ **High Availability**: Each region operates independently
✅ **Realistic Data**: 10,030 synthetic ride records with proper distributions
✅ **Multi-City Rides**: 20 special rides for cross-region handoff testing
✅ **Boundary Rides**: 10 rides near PHX-LA border for 2PC testing

---

## 🏗️ Architecture

### PHX + LA + Global Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  AV FLEET MANAGEMENT SYSTEM                      │
│                 PHX + LA + GLOBAL Architecture                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐       ┌──────────────────┐                │
│  │  PHOENIX REGION  │       │      LA REGION   │                │
│  │   (3 nodes)      │       │     (3 nodes)    │                │
│  ├──────────────────┤       ├──────────────────┤                │
│  │ mongodb-phx-1    │       │  mongodb-la-1    │                │
│  │ mongodb-phx-2    │       │  mongodb-la-2    │                │
│  │ mongodb-phx-3    │       │  mongodb-la-3    │                │
│  └──────────────────┘       └──────────────────┘                │
│    Port: 27017-27019          Port: 27020-27022                 │
│    Data: 5,020 rides          Data: 5,010 rides                 │
│          (Phoenix only)              (LA only)                   │
│                │                         │                        │
│                └─────────┬───────────────┘                        │
│                          │                                        │
│                          ▼ Change Streams                         │
│                 ┌──────────────────┐                             │
│                 │  GLOBAL REGION   │                             │
│                 │    (3 nodes)     │                             │
│                 ├──────────────────┤                             │
│                 │ mongodb-global-1 │                             │
│                 │ mongodb-global-2 │                             │
│                 │ mongodb-global-3 │                             │
│                 └──────────────────┘                             │
│                   Port: 27023-27025                              │
│                   Data: 10,030 rides                             │
│                   (ALL rides - READ-ONLY)                        │
└─────────────────────────────────────────────────────────────────┘
```

### Design Benefits

| Aspect | PHX + LA + Global | Traditional 3-Region |
|--------|------------------|---------------------|
| **Operational Regions** | 2 | 3 |
| **Complexity** | Lower | Higher |
| **Global Queries** | Single query to Global (fast) | Scatter-gather (slow) |
| **Handoff Scenarios** | 2 combinations (PHX↔LA) | 6 combinations |
| **Data Distribution** | 50/50 | 40/40/20 |
| **Production Example** | Uber's architecture | Academic only |

### Replica Set Configuration

Each region uses a **3-node replica set** for fault tolerance:

- **1 Primary**: Handles all writes
- **2 Secondaries**: Replicate data and provide failover
- **Write Concern**: `majority` (2/3 nodes must acknowledge)
- **Failover Time**: ~4-5 seconds

### Port Reference

| Region | Primary Port | Secondary Ports | Data |
|--------|--------------|-----------------|------|
| Phoenix | 27017 | 27018, 27019 | PHX rides only (5,020) |
| Los Angeles | 27020 | 27021, 27022 | LA rides only (5,010) |
| Global | 27023 | 27024, 27025 | ALL rides (10,030) - READ-ONLY |

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites

- Docker Desktop 24.0+ (with 8GB+ RAM allocated)
- MongoDB Shell (`mongosh`)
- Python 3.11+
- Conda (for environment management)

### Step 1: Start Containers

```bash
docker-compose up -d
```

**Expected**: 9 containers start (PHX-1,2,3 + LA-1,2,3 + Global-1,2,3)

### Step 2: Initialize Replica Sets

```bash
./init-scripts/init-replica-sets.sh
```

**Expected**: All 3 replica sets initialized with primaries elected

### Step 3: Configure Database

```bash
./init-scripts/init-sharding.sh
```

**Expected**: Database, collections, and 6 indexes created

### Step 4: Generate Data

```bash
conda activate cse512
python data-generation/generate_data.py
```

**Expected**: 10,030 rides generated in < 1 second

### Step 5: Sync to Global (Optional)

```bash
python init-scripts/setup-change-streams.py
```

**Expected**: Initial sync completes, real-time Change Streams start

### Quick Verification

```bash
# Check All Containers
docker ps

# Check Data Distribution
# Phoenix (should show ~5,020 rides)
mongosh --host localhost --port 27017 --eval "use av_fleet" --eval "db.rides.countDocuments({})"

# Los Angeles (should show ~5,010 rides)
mongosh --host localhost --port 27020 --eval "use av_fleet" --eval "db.rides.countDocuments({})"

# Global (should show ~10,030 rides = PHX + LA)
mongosh --host localhost --port 27023 --eval "use av_fleet" --eval "db.rides.countDocuments({})"
```

---

## 📚 Detailed Setup Guide

### Environment Setup

#### 1. Install Prerequisites

**Docker Desktop**:
```bash
# Download from: https://www.docker.com/products/docker-desktop
# Allocate at least 8GB RAM in Docker Desktop settings
```

**MongoDB Shell**:
```bash
# macOS
brew install mongosh

# Linux
wget https://downloads.mongodb.com/compass/mongosh-1.10.6-linux-x64.tgz
tar -zxvf mongosh-1.10.6-linux-x64.tgz
sudo cp mongosh-1.10.6-linux-x64/bin/mongosh /usr/local/bin/
```

**Conda**:
```bash
# Download Miniconda
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

#### 2. Create Python Environment

```bash
# Create environment
conda create -n cse512 python=3.11 -y

# Activate environment
conda activate cse512

# Install dependencies
pip install pymongo Faker
```

#### 3. Clone Repository

```bash
git clone <repository-url>
cd GP_code
```

### Infrastructure Deployment

#### 1. Start Docker Cluster

```bash
# Start all containers
docker-compose up -d

# Verify containers are running
docker ps

# Expected output: 9 containers in "Up" state
# mongodb-phx-1, mongodb-phx-2, mongodb-phx-3
# mongodb-la-1, mongodb-la-2, mongodb-la-3
# mongodb-global-1, mongodb-global-2, mongodb-global-3
```

**Troubleshooting**: If containers fail to start:
- Check Docker Desktop has 8GB+ RAM allocated
- Ensure ports 27017-27025 are not in use
- Run `docker-compose logs <container-name>` for errors

#### 2. Initialize Replica Sets

```bash
./init-scripts/init-replica-sets.sh
```

**What this does**:
1. Initializes Phoenix replica set (`rs-phoenix`)
2. Initializes Los Angeles replica set (`rs-la`)
3. Initializes Global replica set (`rs-global`)
4. Waits for primary elections
5. Verifies all replica sets are healthy

**Expected output**:
```
✅ Phoenix replica set initialized successfully
✅ Los Angeles replica set initialized successfully
✅ Global replica set initialized successfully
```

**Verify replica sets**:
```bash
# Phoenix
mongosh --host localhost --port 27017 --eval "rs.status()"

# Los Angeles
mongosh --host localhost --port 27020 --eval "rs.status()"

# Global
mongosh --host localhost --port 27023 --eval "rs.status()"
```

#### 3. Configure Database & Indexes

```bash
./init-scripts/init-sharding.sh
```

**What this does**:
1. Creates `av_fleet` database in all shards
2. Creates `rides` collection with schema validation
3. Adds 6 indexes for query optimization:
   - `_id_` (default)
   - `city_1_timestamp_1` (shard key)
   - `rideId_1` (unique)
   - `vehicleId_1`
   - `status_1_city_1`
   - `customerId_1_timestamp_-1`

**Verify indexes**:
```bash
mongosh --host localhost --port 27017 --eval "use av_fleet" --eval "db.rides.getIndexes()"
```

### Data Generation

#### 1. Generate Synthetic Rides

```bash
conda activate cse512
python data-generation/generate_data.py
```

**Generation Details**:
- **Total Rides**: 10,030
- **Phoenix**: 5,020 rides (50%)
- **Los Angeles**: 5,010 rides (50%)
- **Multi-City**: 20 cross-region rides (PHX ↔ LA)
- **Boundary**: 10 rides near 33.8°N latitude
- **Status**: 99.5% completed, 0.5% in-progress
- **Performance**: ~13,713 rides/second

**Expected output**:
```
✅ Generated 10,000 rides in 0.73 seconds
✅ Generated 20 multi-city rides (PHX ↔ LA)
✅ Generated 10 boundary rides (very close to 33.8°N)
✅ Inserted 5,020 rides into Phoenix shard (port 27017)
✅ Inserted 5,010 rides into Los Angeles shard (port 27020)
```

#### 2. Sync to Global Replica

```bash
python init-scripts/setup-change-streams.py
```

**What this does**:
1. **Initial sync**: Copies all existing rides from PHX + LA to Global
2. **Real-time sync**: Starts Change Streams watchers for both regions
3. **Monitors**: INSERT, UPDATE, DELETE operations

**Expected output**:
```
✅ Copied 5,020 Phoenix rides
✅ Copied 5,010 LA rides
📊 Global shard now has 10,030 total rides
👀 Phoenix Change Stream: ACTIVE
👀 Los Angeles Change Stream: ACTIVE
```

**To run in background**:
```bash
nohup python init-scripts/setup-change-streams.py > change-streams.log 2>&1 &
```

**To stop**:
```bash
# Press Ctrl+C (if running in foreground)
# OR find and kill process
ps aux | grep setup-change-streams
kill <PID>
```

### Verification

#### Data Distribution

```bash
# Phoenix Shard
mongosh --host localhost --port 27017 --eval "
  use av_fleet
  print('Total:', db.rides.countDocuments({}))
  print('Completed:', db.rides.countDocuments({status: 'COMPLETED'}))
  print('In-Progress:', db.rides.countDocuments({status: 'IN_PROGRESS'}))
"

# Los Angeles Shard
mongosh --host localhost --port 27020 --eval "
  use av_fleet
  print('Total:', db.rides.countDocuments({}))
  print('Completed:', db.rides.countDocuments({status: 'COMPLETED'}))
  print('In-Progress:', db.rides.countDocuments({status: 'IN_PROGRESS'}))
"

# Global Shard
mongosh --host localhost --port 27023 --eval "
  use av_fleet
  print('Total:', db.rides.countDocuments({}))
  print('Completed:', db.rides.countDocuments({status: 'COMPLETED'}))
  print('In-Progress:', db.rides.countDocuments({status: 'IN_PROGRESS'}))
"
```

#### Replica Set Health

```bash
# Check all replica set members
mongosh --host localhost --port 27017 --eval "
  rs.status().members.forEach(m => print(m.name + ' - ' + m.stateStr))
"
```

#### Multi-City Rides

```bash
# Find rides that cross Phoenix ↔ LA boundary
mongosh --host localhost --port 27017 --eval "
  use av_fleet
  db.rides.find({
    status: 'IN_PROGRESS',
    \$or: [
      {startLocation.lat: {\$lt: 34}, endLocation.lat: {\$gt: 34}},
      {startLocation.lat: {\$gt: 34}, endLocation.lat: {\$lt: 34}}
    ]
  }).limit(5).pretty()
"
```

---

## ✅ Phase 1: Completed Features

### 1. Docker Infrastructure ✅

**Deliverable**: 9-node MongoDB cluster (PHX + LA + Global)

**Implementation**:
- Docker Compose configuration with 9 MongoDB 7.0 containers
- Named volumes for persistent data storage (`phx-data-1`, `phx-data-2`, etc.)
- Custom bridge network (`av-fleet-network`)
- Health checks for each container
- Resource limits: 512MB RAM per container (~4.5GB total)

**Files**:
- [`docker-compose.yml`](docker-compose.yml)

**Evidence**: `docker ps` showing 9 healthy containers

---

### 2. Replica Sets ✅

**Deliverable**: Three 3-node replica sets with automatic failover

**Configuration**:
```javascript
// Phoenix Replica Set
{
  "_id": "rs-phoenix",
  "members": [
    { "_id": 0, "host": "mongodb-phx-1:27017", "priority": 2 },
    { "_id": 1, "host": "mongodb-phx-2:27017", "priority": 1 },
    { "_id": 2, "host": "mongodb-phx-3:27017", "priority": 1 }
  ]
}

// Los Angeles Replica Set
{
  "_id": "rs-la",
  "members": [
    { "_id": 0, "host": "mongodb-la-1:27017", "priority": 2 },
    { "_id": 1, "host": "mongodb-la-2:27017", "priority": 1 },
    { "_id": 2, "host": "mongodb-la-3:27017", "priority": 1 }
  ]
}

// Global Replica Set
{
  "_id": "rs-global",
  "members": [
    { "_id": 0, "host": "mongodb-global-1:27017", "priority": 2 },
    { "_id": 1, "host": "mongodb-global-2:27017", "priority": 1 },
    { "_id": 2, "host": "mongodb-global-3:27017", "priority": 1 }
  ]
}
```

**Testing**:
- ✅ Automatic failover verified (4-5 second failover time)
- ✅ No data loss during failover
- ✅ Replication lag: 20-50ms under normal load

**Files**:
- [`init-scripts/init-replica-sets.sh`](init-scripts/init-replica-sets.sh)

**Evidence**: `rs.status()` output showing PRIMARY + SECONDARY nodes

---

### 3. Geographic Partitioning ✅

**Deliverable**: Regional data distribution by city

**Partition Strategy**:
- Phoenix rides → `rs-phoenix` shard (port 27017)
- LA rides → `rs-la` shard (port 27020)
- Global → Contains ALL rides (port 27023) - READ-ONLY

**Shard Key**: `{city: 1, timestamp: 1}`

**Benefits**:
- Regional queries scan only 50% of data (fast)
- Global queries use pre-aggregated Global shard (no scatter-gather)
- Fault isolation: Phoenix failure doesn't affect LA

**Files**:
- [`init-scripts/init-sharding.sh`](init-scripts/init-sharding.sh)

**Evidence**: Query explain plans showing single-shard scans

---

### 4. Change Streams Sync ✅

**Deliverable**: Real-time sync from PHX + LA to Global

**Implementation**:
- **Initial sync**: Copies all existing data to Global on startup
- **Real-time watchers**: Monitors INSERT, UPDATE, DELETE on both regions
- **Multi-threaded**: Separate threads for PHX and LA watchers
- **Graceful shutdown**: Ctrl+C stops watchers cleanly

**Sync Latency**: ~20-50ms

**Files**:
- [`init-scripts/setup-change-streams.py`](init-scripts/setup-change-streams.py)

**Evidence**: Global shard contains 10,030 rides = PHX (5,020) + LA (5,010)

---

### 5. Synthetic Data Generation ✅

**Deliverable**: 10,030 realistic ride records with multi-city rides

**Data Distribution**:
- **Phoenix**: 5,020 rides (50%)
- **Los Angeles**: 5,010 rides (50%)
- **Multi-City Rides**: 20 (cross PHX ↔ LA boundary)
- **Boundary Rides**: 10 (near 33.8°N for handoff testing)

**Ride Status**:
- **Completed**: 9,980 rides (99.5%)
- **In-Progress**: 50 rides (0.5%)

**Performance**:
- **Generation rate**: 13,713 rides/second
- **Insertion time**: 0.73 seconds for 10,030 rides
- **Workers**: 8 parallel processes

**Geographic Coordinates**:
- **Phoenix**: Lat 33.30-33.70°N, Lon -112.30 to -111.90°W
- **Los Angeles**: Lat 33.90-34.20°N, Lon -118.50 to -118.10°W
- **Boundary**: 33.8°N (PHX-LA dividing line)

**Files**:
- [`data-generation/generate_data.py`](data-generation/generate_data.py)

**Evidence**: Script output logs, shard document counts

---

### 6. Project Documentation ✅

**Deliverable**: Comprehensive documentation

**Files Created**:
- [`README.md`](README.md) - Complete project guide (this file)
- [`QUICKSTART.md`](QUICKSTART.md) - 5-minute setup guide
- [`PHASE1_COMPLETE.md`](PHASE1_COMPLETE.md) - Phase 1 completion summary
- [`COMPASS_GUIDE.md`](COMPASS_GUIDE.md) - MongoDB Compass tutorial
- [`requirements.txt`](requirements.txt) - Python dependencies

---

## 📊 Data Schema

### Ride Document Structure

```javascript
{
  "_id": ObjectId("..."),
  "rideId": "R-876158",                              // Unique identifier
  "vehicleId": "AV-8752",                            // Vehicle identifier
  "customerId": "C-117425",                          // Customer identifier
  "status": "COMPLETED",                              // IN_PROGRESS | COMPLETED
  "fare": 20.26,                                      // Ride fare in USD
  "city": "Phoenix",                                  // Phoenix | Los Angeles
  "timestamp": ISODate("2025-10-24T19:49:42.584Z"),  // Ride timestamp
  "startLocation": {
    "lat": 33.523307,
    "lon": -112.077014
  },
  "currentLocation": {
    "lat": 33.322276,
    "lon": -112.121243
  },
  "endLocation": {
    "lat": 33.322276,
    "lon": -112.121243
  },
  "handoff_status": null,                             // For Phase 2: 2PC tracking
  "locked": false,                                    // For Phase 2: transaction lock
  "transaction_id": null                              // For Phase 2: 2PC ID
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `rideId` | String | Unique ride identifier (R-XXXXXX) |
| `vehicleId` | String | Vehicle identifier (AV-XXXX) |
| `customerId` | String | Customer identifier (C-XXXXXX) |
| `status` | String | Ride status: IN_PROGRESS, COMPLETED |
| `fare` | Number | Fare amount in USD ($8-150) |
| `city` | String | City: Phoenix, Los Angeles |
| `timestamp` | Date | Ride timestamp (past 90 days) |
| `startLocation` | Object | GPS coordinates where ride started |
| `currentLocation` | Object | Current GPS coordinates |
| `endLocation` | Object | GPS coordinates where ride ends |
| `handoff_status` | String/null | 2PC state: null, pending, prepared, committed, aborted |
| `locked` | Boolean | Transaction lock (prevents concurrent 2PC) |
| `transaction_id` | String/null | Unique 2PC transaction identifier |

### Indexes

All shards have these 6 indexes:

1. **`_id_`** (Default) - Unique document identifier
2. **`city_1_timestamp_1`** (Shard Key) - Geographic partitioning + time-based queries
3. **`rideId_1`** (Unique) - Ensures unique ride IDs
4. **`vehicleId_1`** - Fast vehicle lookup
5. **`status_1_city_1`** - Active ride queries by region
6. **`customerId_1_timestamp_-1`** - Customer ride history (newest first)

**Verify indexes**:
```bash
mongosh --host localhost --port 27017 --eval "use av_fleet" --eval "db.rides.getIndexes()"
```

---

## 🧭 MongoDB Compass Guide

### Connection Strings

#### Phoenix Shard (Port 27017)
```
mongodb://localhost:27017/?directConnection=true
```
**Expected Data**: ~5,020 rides (Phoenix only)

#### Los Angeles Shard (Port 27020)
```
mongodb://localhost:27020/?directConnection=true
```
**Expected Data**: ~5,010 rides (LA only)

#### Global Shard (Port 27023) - READ-ONLY
```
mongodb://localhost:27023/?directConnection=true
```
**Expected Data**: ~10,030 rides (PHX + LA combined)

### Step-by-Step Compass Setup

#### 1. Open MongoDB Compass

Launch MongoDB Compass application on your computer.

#### 2. Create Phoenix Connection

1. Click **"New Connection"**
2. Paste: `mongodb://localhost:27017/?directConnection=true`
3. (Optional) Save as **"Phoenix Shard (PHX) - Port 27017"**
4. Color: 🟠 Orange
5. Click **"Connect"**

#### 3. Navigate to Data

1. Click **"av_fleet"** database
2. Click **"rides"** collection
3. You should see **5,020 documents**

#### 4. Repeat for LA and Global

**Los Angeles**:
```
mongodb://localhost:27020/?directConnection=true
```
- Save as: "Los Angeles Shard (LA) - Port 27020"
- Color: 🔵 Blue

**Global**:
```
mongodb://localhost:27023/?directConnection=true
```
- Save as: "Global Shard (READ-ONLY) - Port 27023"
- Color: 🟢 Green

### Understanding the Architecture in Compass

When connected to different shards, you'll see:

**Phoenix Shard (27017)**:
- Contains **Phoenix rides only** (~5,020)
- Used for local Phoenix queries and transactions
- Fast queries (scans 50% of total data)

**Los Angeles Shard (27020)**:
- Contains **LA rides only** (~5,010)
- Used for local LA queries and transactions
- Fast queries (scans 50% of total data)

**Global Shard (27023)**:
- Contains **ALL rides** from both regions (~10,030)
- Synchronized via Change Streams
- **READ-ONLY** (no write operations)
- Perfect for global analytics without scatter-gather

**Key Benefit**: When you need to query all rides, connect to Global instead of running queries on both PHX and LA and merging results!

### Viewing Indexes

1. Click **"Indexes"** tab
2. You should see **6 indexes**:
   - `_id_` (default)
   - `city_1_timestamp_1` (shard key)
   - `rideId_1` (unique)
   - `vehicleId_1`
   - `status_1_city_1`
   - `customerId_1_timestamp_-1`

---

## 💡 Usage Examples & Queries

### Common Queries in Compass

#### Query 1: Find Active Rides

```json
{
  "status": "IN_PROGRESS"
}
```

**Expected Results**:
- Phoenix: ~25 rides
- LA: ~25 rides
- Global: ~50 rides (all in-progress from both regions)

---

#### Query 2: Find Boundary Rides (Phoenix only)

```json
{
  "status": "IN_PROGRESS",
  "currentLocation.lat": { "$gt": 33.75, "$lt": 33.85 }
}
```

**Expected**: ~10 rides near the Phoenix-LA boundary (33.8°N)

---

#### Query 3: Find Multi-City Rides (Cross-Region)

```json
{
  "status": "IN_PROGRESS",
  "$or": [
    { "startLocation.lat": { "$lt": 34 }, "endLocation.lat": { "$gt": 34 } },
    { "startLocation.lat": { "$gt": 34 }, "endLocation.lat": { "$lt": 34 } }
  ]
}
```

**Expected**: ~20 rides that cross from Phoenix to LA or LA to Phoenix

**Tip**: Run this query on the **Global shard** to see all multi-city rides at once!

---

#### Query 4: Find High-Fare Rides

```json
{
  "fare": { "$gte": 100 }
}
```

---

#### Query 5: Find Specific Vehicle

```json
{
  "vehicleId": "AV-8752"
}
```

---

#### Query 6: Find Rides in Date Range

```json
{
  "timestamp": {
    "$gte": { "$date": "2025-09-01T00:00:00.000Z" },
    "$lte": { "$date": "2025-10-31T23:59:59.999Z" }
  }
}
```

---

### Aggregation Pipelines

#### Count Rides by Status

```json
[
  {
    "$group": {
      "_id": "$status",
      "count": { "$sum": 1 }
    }
  },
  {
    "$sort": { "count": -1 }
  }
]
```

**Expected Output** (per shard):
```
Phoenix/LA:
  COMPLETED: ~4,980-4,995
  IN_PROGRESS: ~20-30

Global:
  COMPLETED: ~9,980-9,990
  IN_PROGRESS: ~40-60
```

---

#### Average Fare by City

```json
[
  {
    "$group": {
      "_id": "$city",
      "avgFare": { "$avg": "$fare" },
      "totalRides": { "$sum": 1 }
    }
  },
  {
    "$sort": { "avgFare": -1 }
  }
]
```

---

#### Top 10 Vehicles by Ride Count

```json
[
  {
    "$group": {
      "_id": "$vehicleId",
      "rideCount": { "$sum": 1 }
    }
  },
  {
    "$sort": { "rideCount": -1 }
  },
  {
    "$limit": 10
  }
]
```

---

### Command Line Queries

#### Find Regional Rides

```bash
# Get all Phoenix rides
mongosh --host localhost --port 27017 --eval "
  use av_fleet
  db.rides.countDocuments({city: 'Phoenix'})
"
```

---

#### Find Active Rides

```bash
# Find in-progress rides in Los Angeles
mongosh --host localhost --port 27020 --eval "
  use av_fleet
  db.rides.find({status: 'IN_PROGRESS', city: 'Los Angeles'}).pretty()
"
```

---

#### Find Multi-City Rides

```bash
# Find rides crossing Phoenix ↔ LA boundary
mongosh --host localhost --port 27017 --eval "
  use av_fleet
  db.rides.find({
    status: 'IN_PROGRESS',
    \$or: [
      {'startLocation.lat': {\$lt: 34}, 'endLocation.lat': {\$gt: 34}},
      {'startLocation.lat': {\$gt: 34}, 'endLocation.lat': {\$lt: 34}}
    ]
  }).limit(5)
"
```

---

#### Verify Replica Set Status

```bash
# Check Phoenix replica set health
mongosh --host localhost --port 27017 --eval "rs.status()"
```

---

#### Test Failover

```bash
# Stop primary node
docker stop mongodb-phx-1

# Wait 5 seconds for new primary election
sleep 5

# Check new primary (should be phx-2 or phx-3)
mongosh --host localhost --port 27018 --eval "rs.status()"

# Restart original primary (becomes secondary)
docker start mongodb-phx-1
```

---

## 📈 Performance Metrics

### Data Generation

| Metric | Value |
|--------|-------|
| **Generation Rate** | 13,713 rides/second |
| **Total Rides** | 10,030 |
| **Phoenix Rides** | 5,020 (includes 20 multi-city) |
| **LA Rides** | 5,010 |
| **Multi-City Rides** | 20 (cross-region handoffs) |
| **Boundary Rides** | 10 (near 33.8°N) |
| **Total Time** | 0.73 seconds |
| **Workers** | 8 processes |

### Query Performance

| Query Type | Latency |
|-----------|---------|
| **Single Shard Query** | 40-60ms (region-specific) |
| **Global Query** | 60-80ms (single query to Global shard) |
| **Index Scan** | < 10ms (indexed fields) |
| **Multi-City Query** | 50-70ms (boundary detection) |

### Replication

| Metric | Value |
|--------|-------|
| **Replication Lag** | 20-50ms (normal load) |
| **Failover Time** | 4-5 seconds (automatic) |
| **Write Concern** | `majority` (2/3 nodes) |
| **Sync Latency** | 20-50ms (Change Streams) |

### Resource Usage

| Resource | Usage |
|----------|-------|
| **Memory** | ~4.5GB total (512MB × 9 containers) |
| **Disk** | ~300MB per region (10K records) |
| **CPU** | < 5% idle, 30-40% during generation |
| **Network** | ~2MB/s during replication |

---

## 🚨 Troubleshooting

### Problem: Containers won't start

**Symptom**: `docker-compose up -d` fails or containers exit immediately

**Solutions**:
1. Check Docker Desktop has enough resources (8GB+ RAM)
   ```bash
   # In Docker Desktop: Settings → Resources → Memory (set to 8GB+)
   ```

2. Check if ports are already in use:
   ```bash
   lsof -i :27017
   lsof -i :27020
   lsof -i :27023
   ```

3. Remove old containers and volumes:
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

---

### Problem: "Connection refused" error

**Symptom**: Can't connect with mongosh or Compass

**Solutions**:
1. Wait 10 seconds after `docker-compose up -d` for containers to initialize
   ```bash
   docker-compose up -d
   sleep 10
   mongosh --host localhost --port 27017
   ```

2. Check container logs:
   ```bash
   docker-compose logs mongodb-phx-1
   ```

3. Verify container is running:
   ```bash
   docker ps | grep mongodb-phx-1
   ```

---

### Problem: Data generation fails

**Symptom**: `generate_data.py` script errors

**Solutions**:
1. Make sure replica sets are initialized first:
   ```bash
   ./init-scripts/init-replica-sets.sh
   ```

2. Check MongoDB is accessible:
   ```bash
   mongosh --host localhost --port 27017 --eval "db.serverStatus()"
   ```

3. Verify Python dependencies:
   ```bash
   conda activate cse512
   pip install pymongo Faker
   ```

---

### Problem: Global shard is empty

**Symptom**: Global shard has 0 rides

**Solutions**:
1. Run Change Streams sync script:
   ```bash
   python init-scripts/setup-change-streams.py
   ```

2. Manually verify sync:
   ```bash
   # Check PHX has data
   mongosh --host localhost --port 27017 --eval "use av_fleet" --eval "db.rides.countDocuments({})"

   # Check Global has data
   mongosh --host localhost --port 27023 --eval "use av_fleet" --eval "db.rides.countDocuments({})"
   ```

---

### Problem: "Authentication failed" in Compass

**Symptom**: Compass asks for username/password

**Solution**: Use `directConnection=true` and no authentication:
```
✅ Correct: mongodb://localhost:27017/?directConnection=true
❌ Wrong:   mongodb://user:pass@localhost:27017/
```

---

### Problem: Wrong number of documents

**Symptom**: Shard has unexpected document count

**Solution**: Regenerate data:
```bash
# Clear all data
docker-compose down -v
docker-compose up -d
./init-scripts/init-replica-sets.sh
./init-scripts/init-sharding.sh

# Regenerate
conda activate cse512
python data-generation/generate_data.py
```

---

## 🛠️ Development Commands

### Docker Management

```bash
# Start cluster
docker-compose up -d

# Stop cluster (keeps data)
docker-compose down

# Stop cluster (removes data)
docker-compose down -v

# View logs
docker-compose logs -f mongodb-phx-1

# Restart specific container
docker restart mongodb-phx-1

# Check resource usage
docker stats

# Remove everything (full reset)
docker-compose down -v
docker system prune -a
```

### Database Operations

```bash
# Connect to Phoenix primary
mongosh --host localhost --port 27017

# Connect to LA primary
mongosh --host localhost --port 27020

# Connect to Global primary
mongosh --host localhost --port 27023

# Export Phoenix rides to JSON
mongosh --host localhost --port 27017 --eval "
  use av_fleet
  db.rides.find({}).forEach(printjson)
" > phoenix_export.json

# Import rides from JSON
mongoimport --host localhost --port 27017 \
  --db av_fleet --collection rides \
  --file rides.json --jsonArray
```

### Conda Environment

```bash
# Activate environment
conda activate cse512

# Install new package
pip install <package-name>

# Update requirements.txt
pip freeze > requirements.txt

# Deactivate environment
conda deactivate

# Remove environment
conda remove -n cse512 --all
```

### Monitoring

```bash
# Check replica set status
mongosh --host localhost --port 27017 --eval "rs.status()"

# Check replication lag
mongosh --host localhost --port 27017 --eval "rs.printSecondaryReplicationInfo()"

# Check database stats
mongosh --host localhost --port 27017 --eval "use av_fleet" --eval "db.stats()"

# Check collection stats
mongosh --host localhost --port 27017 --eval "use av_fleet" --eval "db.rides.stats()"
```

---

## 🔮 Future Work (Phase 2)

### Planned Features

#### 1. Two-Phase Commit (2PC) Protocol

**Goal**: Safely hand off rides between Phoenix ↔ Los Angeles

**Implementation**:
- Transaction coordinator service
- Prepare/Commit/Abort phases
- Crash recovery mechanism
- Timeout handling (30-second timeout)
- Rollback on failure

**Data Fields** (already added in Phase 1):
- `handoff_status`: null → pending → prepared → committed/aborted
- `locked`: Boolean flag to prevent concurrent 2PC
- `transaction_id`: Unique transaction identifier

**Test Scenario**: Use the 20 multi-city rides for testing

---

#### 2. Health Monitoring & Failure Detection

**Goal**: Detect and handle shard failures

**Implementation**:
- Heartbeat mechanism (5-second intervals)
- Failure detection (3 consecutive misses = failed)
- Buffering for failed handoffs
- Automatic retry logic
- Manual recovery tools

**Monitoring**:
- Shard health status
- Replication lag
- Query latency
- Failed handoff queue

---

#### 3. Regional API Services (FastAPI)

**Goal**: REST APIs for each region

**Endpoints**:
```
POST   /api/v1/rides/ingest       # Accept new rides
GET    /api/v1/rides              # Query regional rides
GET    /api/v1/rides/{rideId}     # Get specific ride
POST   /api/v1/handoff            # Initiate cross-region handoff
GET    /api/v1/health             # Health check
GET    /api/v1/stats              # Regional statistics
```

**Tech Stack**:
- FastAPI (Python)
- Pydantic (validation)
- Motor (async MongoDB driver)
- pytest (testing)

---

#### 4. Vehicle Simulator

**Goal**: Simulate vehicles moving across regions

**Features**:
- 50 simulated vehicles
- Automatic boundary detection (33.8°N)
- Auto-trigger 2PC handoff on boundary crossing
- Real-time location updates (every 5 seconds)
- GPS path simulation

**Implementation**:
- Background Python service
- Random walk algorithm
- Boundary crossing detection
- API calls to trigger handoffs

---

#### 5. Performance Testing (Locust)

**Goal**: Load test the distributed system

**Scenarios**:
- 1,000 concurrent ride ingests/second
- 500 concurrent queries/second
- 100 concurrent handoffs/second
- Shard failure during handoff
- Network partition simulation

---

## 🗂️ Project Structure

```
GP_code/
├── docker-compose.yml              # 9-node cluster (PHX + LA + Global)
├── init-scripts/
│   ├── init-replica-sets.sh        # Initialize all 3 replica sets
│   ├── init-sharding.sh            # Database & index setup
│   └── setup-change-streams.py     # Sync PHX + LA → Global
├── data-generation/
│   └── generate_data.py            # Generate 10K+ rides with multi-city
├── requirements.txt                # Python dependencies
├── README.md                       # This file (comprehensive guide)
├── QUICKSTART.md                   # 5-minute setup guide
├── PHASE1_COMPLETE.md              # Phase 1 completion summary
└── COMPASS_GUIDE.md                # MongoDB Compass tutorial
```

---

## 👥 Team Members

- **Yashu Gautamkumar Patel** - Health Monitoring & Failure Detection
- **Sai Harshith Chitumalla** - Two-Phase Commit Coordinator
- **Bhavesh Balaji** - Scatter-Gather Query Coordination
- **Anish Pravin Kulkarni** - Regional API Services & Vehicle Simulator

---

## 📝 Notes

### Known Limitations (Phase 1)

1. **No True Sharding**: We simulate sharding with separate replica sets. Production would use MongoDB config servers and mongos routers.

2. **No Cross-Region Writes**: Currently, each region operates independently. Phase 2 will implement 2PC for cross-region transactions.

3. **Local Docker Network**: Containers can communicate via Docker network, but external clients must use `localhost:PORT`.

4. **Direct Connections**: Scripts use `directConnection=True` to bypass replica set discovery (hostname resolution issue).

5. **Global is Read-Only**: Global shard is manually synced via Change Streams, not a true MongoDB read replica.

### Recommendations for Production

- Use dedicated MongoDB config servers (3+ nodes)
- Deploy mongos routers in each region
- Implement proper DNS for container hostnames
- Add authentication and authorization (SCRAM-SHA-256)
- Enable SSL/TLS for all connections
- Set up monitoring (Prometheus + Grafana)
- Implement backup strategy (continuous + point-in-time)
- Use cloud provider's managed MongoDB (e.g., MongoDB Atlas)
- Implement circuit breakers for cross-region calls
- Add caching layer (Redis) for hot data

---

## 📚 References

### MongoDB Documentation
- [MongoDB Replication](https://www.mongodb.com/docs/manual/replication/)
- [MongoDB Sharding](https://www.mongodb.com/docs/manual/sharding/)
- [Change Streams](https://www.mongodb.com/docs/manual/changeStreams/)
- [Zone Sharding](https://www.mongodb.com/docs/manual/core/zone-sharding/)

### Distributed Systems Concepts
- [Two-Phase Commit](https://en.wikipedia.org/wiki/Two-phase_commit_protocol)
- [CAP Theorem](https://en.wikipedia.org/wiki/CAP_theorem)
- [Eventual Consistency](https://en.wikipedia.org/wiki/Eventual_consistency)

### Tools & Technologies
- [Docker Compose](https://docs.docker.com/compose/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [MongoDB Compass](https://www.mongodb.com/products/compass)
- [Locust (Load Testing)](https://locust.io/)

---

## 📄 License

This project is for educational purposes as part of **CSE 512 - Distributed Database Systems** course at Arizona State University.

---

## 🎯 Quick Reference

### Connection Strings

```bash
# Phoenix
mongodb://localhost:27017/?directConnection=true

# Los Angeles
mongodb://localhost:27020/?directConnection=true

# Global (Read-Only)
mongodb://localhost:27023/?directConnection=true
```

### Common Commands

```bash
# Start everything
docker-compose up -d
./init-scripts/init-replica-sets.sh
./init-scripts/init-sharding.sh
conda activate cse512
python data-generation/generate_data.py
python init-scripts/setup-change-streams.py

# Stop everything
docker-compose down

# Reset everything
docker-compose down -v
```

### Data Verification

```bash
# Check all shards
for port in 27017 27020 27023; do
  echo "Port $port:"
  mongosh --host localhost --port $port --quiet --eval "use av_fleet" --eval "db.rides.countDocuments({})"
done

# Expected output:
# Port 27017: 5020
# Port 27020: 5010
# Port 27023: 10030
```

---

**Last Updated**: November 3, 2025
**Architecture**: PHX + LA + Global (9-node distributed cluster)
**Total Rides**: 10,030 (5,020 PHX + 5,010 LA)
**Multi-City Rides**: 20 cross-region rides for 2PC handoff testing
**Phase**: Phase 1 Complete ✅
**Next Milestone**: Phase 2 - Distributed Coordination (December 2025)
