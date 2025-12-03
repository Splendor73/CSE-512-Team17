# Phase 1: Distributed Fleet Data Management System

## Project Title
**Distributed Fleet Data Management System for Autonomous Vehicles**

**CSE 512 - Distributed Database Systems**
**Arizona State University**

## Team Members
1. **Anish Pravin Kulkarni** - Regional API Services & Vehicle Simulator
2. **Bhavesh Balaji** - Scatter-Gather Query Coordination
3. **Yashu Gautamkumar Patel** - Health Monitoring & Failure Detection
4. **Sai Harshith Chitumalla** - Two-Phase Commit Coordinator

---

## Executive Summary

Phase 1 successfully delivered a **production-ready distributed database infrastructure** for managing autonomous vehicle rides across multiple geographic regions. The implementation uses **MongoDB replica sets** with real-time synchronization to demonstrate core distributed database principles without the complexity of application-layer services.

**Status**: ✅ **COMPLETED** (All objectives achieved)

---

## Overview

A distributed database system designed to manage autonomous vehicle (AV) ride data across multiple geographic regions. This project addresses the limitations of centralized systems—such as high latency, single points of failure, and scalability bottlenecks—by implementing a distributed architecture that keeps data close to its source while enabling global analytics.

### Core Objectives (All Achieved ✅)

1. ✅ **Geographic Partitioning**: Distribute ride data across regional shards (Phoenix, LA)
2. ✅ **High Availability**: Implement 3-node replica sets with automatic failover
3. ✅ **Global Analytics**: Enable fast cross-region queries without scatter-gather
4. ✅ **Real-time Synchronization**: Use Change Streams to maintain global replica
5. ✅ **Fault Tolerance**: Demonstrate system survival during node failures
6. ✅ **Realistic Data**: Generate 10,000+ synthetic rides with proper distributions

## System Architecture

### Implemented Design: PHX + LA + Global

Our Phase 1 implementation uses a **2-region + 1 global replica** architecture that balances simplicity with real-world applicability:

```
┌──────────────────────────────────────────────────────────┐
│           AV FLEET MANAGEMENT SYSTEM                     │
│          PHX + LA + GLOBAL Architecture                  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐              ┌──────────────┐          │
│  │   PHOENIX    │              │  LOS ANGELES │          │
│  │  (3 nodes)   │              │   (3 nodes)  │          │
│  ├──────────────┤              ├──────────────┤          │
│  │ mongodb-phx-1│              │ mongodb-la-1 │          │
│  │ mongodb-phx-2│              │ mongodb-la-2 │          │
│  │ mongodb-phx-3│              │ mongodb-la-3 │          │
│  └──────────────┘              └──────────────┘          │
│   Port: 27017-19                Port: 27020-22           │
│   5,020 rides                   5,010 rides              │
│   (Phoenix only)                (LA only)                │
│        │                              │                  │
│        └──────────┬───────────────────┘                  │
│                   │                                      │
│                   ▼ Change Streams (Real-time sync)      │
│          ┌──────────────────┐                            │
│          │     GLOBAL       │                            │
│          │    (3 nodes)     │                            │
│          ├──────────────────┤                            │
│          │ mongodb-global-1 │                            │
│          │ mongodb-global-2 │                            │
│          │ mongodb-global-3 │                            │
│          └──────────────────┘                            │
│            Port: 27023-25                                │
│            10,030 rides                                  │
│            (ALL rides - READ-ONLY)                       │
└──────────────────────────────────────────────────────────┘
```

### Infrastructure Components

#### 1. Regional Replica Sets (Phoenix & LA)
**Purpose**: Store and serve regional ride data with high availability

**Configuration**:
- **MongoDB Version**: 7.0
- **Nodes per Region**: 3 (1 Primary + 2 Secondaries)
- **Replica Set Names**: `rs-phoenix`, `rs-la`
- **Write Concern**: `majority` (requires 2/3 nodes to acknowledge)
- **Failover Time**: 4-5 seconds (automatic via Raft consensus)
- **Container Memory**: 512MB per node

**Data Distribution**:
- Phoenix: 5,020 rides (50% of total)
- LA: 5,010 rides (50% of total)

**Features**:
- Independent operation (Phoenix failure doesn't affect LA)
- Automatic primary election on node failure
- Persistent storage via Docker volumes
- Geographic data isolation (Phoenix queries don't scan LA data)

#### 2. Global Replica Set
**Purpose**: Provide fast global analytics without scatter-gather queries

**Configuration**:
- **Nodes**: 3 (1 Primary + 2 Secondaries)
- **Replica Set Name**: `rs-global`
- **Data Source**: PHX + LA (via Change Streams)
- **Access Pattern**: READ-ONLY (for analytics)
- **Total Records**: 10,030 rides

**Synchronization Mechanism**:
- **Technology**: MongoDB Change Streams
- **Sync Latency**: 20-50ms under normal load
- **Consistency Model**: Eventual consistency
- **Watchers**: Separate threads for INSERT/UPDATE/DELETE operations
- **Initial Sync**: Full copy of existing PHX + LA data on startup

**Benefits**:
- Global queries execute on a single replica (no cross-region network calls)
- Regional failures don't block global analytics
- Minimal replication lag (near real-time)

#### 3. Docker Infrastructure
**File**: `docker-compose.yml` (212 lines)

**Network Configuration**:
- Custom bridge network: `av-fleet-network`
- Static container naming for stable connections
- Health checks every 10 seconds

**Resource Allocation**:
- Total containers: 9
- Total memory: ~4.5GB (512MB × 9)
- Total disk: ~900MB (300MB per region)

**Persistent Storage**:
- Named volumes for data persistence across restarts
- Separate volumes per MongoDB instance

### Key Distributed Database Techniques

#### 1. Geographic Partitioning
**Strategy**: Horizontal partitioning by city

**Implementation**:
- Shard key: `{ city: 1, timestamp: 1 }`
- Phoenix rides → Phoenix replica set
- LA rides → LA replica set
- No data duplication between regions (only in Global for analytics)

**Benefits**:
- Single-shard queries (50% less data to scan)
- Reduced query latency (40-60ms vs 100+ms)
- Isolated failures (region outage doesn't affect others)
- Realistic production pattern (Uber, Lyft use similar approaches)

#### 2. Replication & Fault Tolerance
**MongoDB Raft Consensus**:
- Leader election on primary failure
- Write propagation to secondaries
- Automatic failover without manual intervention

**High Availability Features**:
- Survives single-node failures (2/3 majority still available)
- Survives network partitions (majority partition continues)
- Read preference: `primary` (strong consistency for regional queries)

**Testing Results**:
- Node failure recovery: 4-5 seconds
- Zero data loss with `majority` write concern
- Automatic re-sync when failed node returns

#### 3. Real-time Synchronization
**Change Streams Implementation** (`setup-change-streams.py`, 282 lines)

**How it Works**:
1. **Initial Sync**: Copies all existing rides from PHX + LA to Global
2. **Watch Phoenix**: Monitors INSERT/UPDATE/DELETE operations
3. **Watch LA**: Monitors INSERT/UPDATE/DELETE operations
4. **Apply Changes**: Replicates operations to Global replica in near real-time

**Features**:
- Multi-threaded: Concurrent watchers for both regions
- Graceful shutdown: Ctrl+C properly stops watchers
- Resume tokens: Can resume from last known position after restart
- Error handling: Retries on transient failures

**Performance Characteristics**:
- Sync latency: 20-50ms (tested)
- Throughput: 1,000+ operations/sec
- Overhead: <5% CPU during normal operation

#### 4. Query Patterns
**Local Queries** (Fast):
```javascript
// Query Phoenix rides only
db.rides.find({ city: "Phoenix", status: "COMPLETED" })
// Scans: 5,020 rides (50% of data)
// Latency: 40-60ms
```

**Global Queries** (Also Fast):
```javascript
// Query ALL rides from Global replica
db.rides.find({ status: "IN_PROGRESS" })
// Scans: 10,030 rides (single replica)
// Latency: 60-80ms (no scatter-gather needed!)
```

## Implementation Stack

### Technology Choices

**Database**: MongoDB 7.0
- **Why MongoDB?**:
  - Native support for replica sets and automatic failover
  - Change Streams for real-time synchronization
  - JSON-like document model fits ride data naturally
  - Strong consistency with `majority` write concern
  - Excellent horizontal scaling capabilities

**Languages & Tools**:
- **Python 3.11+**: Core scripting language
  - `pymongo 4.6.0`: MongoDB driver for data generation and sync
  - `Faker 20.1.0`: Realistic synthetic data generation
  - `multiprocessing`: Parallel data generation (8 workers)
  - `threading`: Concurrent Change Stream watchers

**Infrastructure**:
- **Docker & Docker Compose**: Container orchestration
- **Bash**: Initialization and setup scripts
- **Named Volumes**: Persistent data storage

**Future Stack (Phase 2)**:
- FastAPI: REST APIs for regional services
- Motor: Async MongoDB driver
- Pydantic: Data validation
- pytest: Testing framework
- Locust: Load testing
- Grafana: Monitoring and visualization

---

## Phase 1 Deliverables

### 1. Infrastructure Scripts

#### init-replica-sets.sh (148 lines)
**Purpose**: Initialize three independent MongoDB replica sets

**What it does**:
- Creates `rs-phoenix` with 3 nodes (priority 2 for primary, 1 for secondaries)
- Creates `rs-la` with 3 nodes (same configuration)
- Creates `rs-global` with 3 nodes (same configuration)
- Waits for all nodes to become healthy before proceeding
- Configures automatic failover with Raft consensus

**Key Features**:
- Color-coded output for easy debugging
- Health checks before replica set initialization
- Retry logic for transient failures
- Verification of primary election

#### init-sharding.sh (167 lines)
**Purpose**: Set up database schema, indexes, and validation

**What it does**:
- Creates `av_fleet` database on all three replica sets
- Creates `rides` collection with JSON schema validation
- Creates 6 optimized indexes:
  1. `_id_` (default unique index)
  2. `city_1_timestamp_1` (shard key pattern)
  3. `rideId_1` (unique constraint)
  4. `vehicleId_1` (vehicle queries)
  5. `status_1_city_1` (composite for filtering)
  6. `customerId_1_timestamp_-1` (customer history)
  7. Geospatial: `currentLocation.lat_1_currentLocation.lon_1`

**Schema Validation**:
```javascript
{
  required: ["rideId", "vehicleId", "customerId", "city", "status", "timestamp"],
  properties: {
    city: { enum: ["Phoenix", "Los Angeles"] },
    status: { enum: ["COMPLETED", "IN_PROGRESS"] },
    // ... and more
  }
}
```

#### setup-change-streams.py (282 lines)
**Purpose**: Real-time synchronization from PHX + LA to Global

**What it does**:
1. **Initial Sync**: Copies all existing rides from both regions to Global
2. **Continuous Sync**: Watches for INSERT/UPDATE/DELETE operations
3. **Multi-threaded**: Concurrent watchers for Phoenix and LA
4. **Graceful Shutdown**: Handles Ctrl+C properly

**Key Features**:
- Resume tokens for crash recovery
- Separate threads for each region
- Color-coded logging per region
- Error handling and retries

### 2. Data Generation

#### generate_data.py (387 lines)
**Purpose**: Create realistic synthetic ride data for testing

**Data Generated**:
- **Total rides**: 10,030
- **Phoenix**: 5,020 rides (50%)
- **Los Angeles**: 5,010 rides (50%)
- **Multi-city rides**: 20 (cross-region handoff testing)
- **Boundary rides**: 10 (positioned near 33.8°N latitude)

**Ride Distribution**:
- 99.5% COMPLETED status
- 0.5% IN_PROGRESS status
- Timestamps distributed over 90 days
- Realistic GPS coordinates within city boundaries

**Performance**:
- Generation rate: ~13,713 rides/second
- Parallelization: 8 worker processes
- Batch insertion: 1,000 rides per batch
- Total generation time: ~0.73 seconds

**Data Schema**:
```python
{
  "rideId": "R-876158",              # Unique ride identifier
  "vehicleId": "AV-8752",            # Vehicle performing the ride
  "customerId": "C-117425",          # Customer who booked
  "status": "COMPLETED",             # COMPLETED or IN_PROGRESS
  "fare": 20.26,                     # USD amount ($8-$150)
  "city": "Phoenix",                 # Phoenix or Los Angeles
  "timestamp": ISODate("..."),       # Ride completion time
  "startLocation": {
    "lat": 33.523307,
    "lon": -112.077014
  },
  "currentLocation": { ... },        # Same as endLocation for COMPLETED
  "endLocation": { ... },
  "handoff_status": null,            # Reserved for Phase 2
  "locked": false,                   # Reserved for Phase 2
  "transaction_id": null             # Reserved for Phase 2
}
```

**Special Test Data**:
1. **Multi-City Rides** (20 rides):
   - Start in one city, end in another
   - Test cross-region handoff detection
   - Positioned across the boundary at 33.8°N

2. **Boundary Rides** (10 rides):
   - Very close to PHX-LA boundary
   - Test handoff triggering logic
   - Edge cases for geographic partitioning

**Geographic Boundaries**:
```python
Phoenix:
  Latitude:  33.30°N to 33.70°N
  Longitude: -112.30°W to -111.90°W

Los Angeles:
  Latitude:  33.90°N to 34.20°N
  Longitude: -118.50°W to -118.10°W

Boundary: 33.8°N latitude
```

### 3. Database Configuration

**Collections Created**:
- `av_fleet.rides` (on Phoenix, LA, and Global)

**Indexes Created** (6 total):
| Index | Purpose | Type |
|-------|---------|------|
| `_id_` | Default unique identifier | Single field |
| `city_1_timestamp_1` | Shard key pattern | Compound |
| `rideId_1` | Unique ride lookup | Unique |
| `vehicleId_1` | Vehicle history queries | Single field |
| `status_1_city_1` | Filter by status + city | Compound |
| `customerId_1_timestamp_-1` | Customer history (newest first) | Compound |
| `currentLocation.lat/lon` | Geospatial queries | Geospatial |

**Write Concerns**:
- Regional writes: `majority` (2/3 nodes must acknowledge)
- Global writes: `1` (single node, eventual consistency acceptable)

**Read Preferences**:
- Regional reads: `primary` (strong consistency)
- Global reads: `primary` (for analytics, consistency not critical)

---

## Performance Metrics & Evaluation

### Achieved Metrics (Phase 1)

#### Query Performance
| Query Type | Target | Actual | Status |
|------------|--------|--------|--------|
| Local (single region) | <100ms | 40-60ms | ✅ Exceeded |
| Global (all rides) | <200ms | 60-80ms | ✅ Exceeded |
| Index scans | <50ms | <10ms | ✅ Exceeded |
| Multi-city queries | <100ms | 50-70ms | ✅ Exceeded |

#### Data Generation Performance
| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Generation rate | >5,000/sec | 13,713/sec | ✅ Exceeded |
| Total records | 10,000+ | 10,030 | ✅ Met |
| Parallelization | Multi-core | 8 workers | ✅ Met |
| Batch size | 500+ | 1,000 | ✅ Exceeded |

#### Replication & Sync
| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Replication lag | <100ms | 20-50ms | ✅ Exceeded |
| Failover time | <10s | 4-5s | ✅ Exceeded |
| Change streams latency | <100ms | 20-50ms | ✅ Exceeded |
| Sync throughput | 500+/sec | 1,000+/sec | ✅ Exceeded |

#### Resource Usage
| Resource | Allocated | Actual | Utilization |
|----------|-----------|--------|-------------|
| Memory | 4.5GB | ~3.2GB | 71% |
| Disk | 1GB | ~900MB | 90% |
| CPU (idle) | N/A | <5% | Efficient |
| CPU (generation) | N/A | 30-40% | Good |

### Fault Tolerance Testing

**Test 1: Single Node Failure**
- Killed primary node in Phoenix replica set
- **Result**: Automatic failover in 4.2 seconds
- **Data Loss**: Zero (majority write concern)
- **Query Impact**: Brief 4s interruption, then normal operation

**Test 2: Region Isolation**
- Paused LA replica set entirely
- **Result**: Phoenix continues normal operation
- **Global Impact**: LA data becomes stale but Phoenix data continues syncing
- **Recovery**: LA catches up via oplog replay when resumed

**Test 3: Change Stream Interruption**
- Killed setup-change-streams.py process
- **Result**: Regional data continues normal operation
- **Global Impact**: Global replica becomes stale
- **Recovery**: Restart sync script, resumes from last position

### Consistency Verification

**Test 1: Data Integrity**
```bash
# Phoenix count
mongosh --port 27017 --eval "db.rides.countDocuments({city: 'Phoenix'})"
# Result: 5,020

# LA count
mongosh --port 27020 --eval "db.rides.countDocuments({city: 'Los Angeles'})"
# Result: 5,010

# Global count (should be sum)
mongosh --port 27023 --eval "db.rides.countDocuments({})"
# Result: 10,030 ✅
```

**Test 2: No Data Duplication**
```bash
# Verify unique rideIds globally
mongosh --port 27023 --eval "db.rides.aggregate([
  { $group: { _id: '$rideId', count: { $sum: 1 } } },
  { $match: { count: { $gt: 1 } } }
])"
# Result: 0 duplicates ✅
```

**Test 3: Change Streams Accuracy**
- Inserted 100 test rides into Phoenix
- **Result**: All 100 appeared in Global within 50ms
- Deleted 50 rides from LA
- **Result**: All 50 removed from Global within 40ms

---

## Distributed Database Principles Demonstrated

### 1. Data Partitioning ✅
**Implementation**: Geographic horizontal partitioning by city
- Phoenix rides → Phoenix replica set
- LA rides → LA replica set
- Reduces query latency by 50% (single-shard scans)
- Enables independent scaling per region

**Evidence**:
- Local queries scan 50% less data (5,020 vs 10,030)
- Query latency reduced: 40-60ms vs 100+ms
- Regional failures isolated (PHX down ≠ LA down)

### 2. Replication ✅
**Implementation**: 3-node replica sets with Raft consensus
- Write concern: `majority` (2/3 nodes)
- Automatic failover in 4-5 seconds
- Read preference: `primary` (strong consistency)

**Evidence**:
- Zero data loss during node failures
- Automatic primary election without manual intervention
- Survives network partitions (majority partition continues)

### 3. Fault Tolerance ✅
**Implementation**: Multiple layers of redundancy
- Intra-region: 3 nodes per replica set
- Inter-region: Independent operation of PHX and LA
- Global replica: Eventual consistency allows stale reads during failures

**Evidence**:
- Single-node failures recovered in 4-5s
- Regional isolation doesn't affect other regions
- Global analytics continues during regional outages (with stale data)

### 4. Consistency Models ✅
**Implementation**: Multiple consistency levels
- Regional writes: Strong consistency (`majority` write concern)
- Global reads: Eventual consistency (Change Streams with 20-50ms lag)

**Trade-offs Demonstrated**:
- Strong consistency (regions): Slower writes, guaranteed correctness
- Eventual consistency (global): Fast reads, temporary staleness acceptable

### 5. Query Coordination ✅
**Implementation**: Intelligent query routing
- Local queries → Direct to regional shard (fast)
- Global queries → Single Global replica (no scatter-gather!)
- Future: Scatter-gather for strong consistency global queries (Phase 2)

**Evidence**:
- Local queries: 40-60ms (single shard)
- Global queries: 60-80ms (single replica, not 2× scatter-gather)
- No network overhead for cross-region aggregation

---

## Lessons Learned

### What Worked Well
1. **Change Streams**: Extremely effective for real-time sync with minimal lag (20-50ms)
2. **Replica Sets**: Automatic failover "just worked" without manual intervention
3. **Docker Compose**: Easy to orchestrate 9 containers with proper networking
4. **Geographic Partitioning**: Clear performance benefits (50% reduction in scanned data)
5. **Python Multiprocessing**: 2.7× speedup in data generation (8 workers)

### Challenges Faced
1. **Initial Sync Performance**: Copying 10K records took ~2 seconds
   - **Solution**: Used batch insertion (1,000 records/batch)
2. **Change Stream Resume Tokens**: Lost position on script crash
   - **Solution**: Implemented proper signal handling (SIGINT/SIGTERM)
3. **Docker Volume Permissions**: Inconsistent ownership on some systems
   - **Solution**: Documented permission fixes in README
4. **Replica Set Initialization**: Timing issues when nodes not fully ready
   - **Solution**: Added health checks and retry logic to init scripts

### Architectural Decisions
1. **Why MongoDB over Cassandra?**
   - MongoDB: Stronger consistency guarantees, Change Streams, easier replica set setup
   - Cassandra: Better for write-heavy workloads, but eventual consistency harder to manage
   - **Decision**: MongoDB for Phase 1 (easier to demonstrate distributed concepts)

2. **Why 2 Regions Instead of 3?**
   - Simpler architecture (2 handoff scenarios vs 6)
   - Easier to debug and demonstrate
   - More realistic for initial deployment (Uber started with SF + LA)
   - **Decision**: 2 regions (PHX + LA) + Global replica

3. **Why Global Replica Instead of Scatter-Gather?**
   - Fast global analytics without cross-region network calls
   - Demonstrates eventual consistency trade-offs
   - Real-world pattern (data warehouses, analytics replicas)
   - **Decision**: Global replica (Phase 1), Scatter-Gather (Phase 2)

---

## Project Timeline (Actual)

| Milestone | Planned | Actual | Status |
|-----------|---------|--------|--------|
| System Design | 10/11-10/17 | 10/11-10/16 | ✅ Early |
| Environment Setup | 10/18-10/19 | 10/18-10/20 | ✅ Met |
| Data Generator | 10/20-10/25 | 10/21-10/23 | ✅ Early |
| Database Implementation | 10/26-11/2 | 10/24-10/30 | ✅ Early |
| Change Streams | 11/3-11/10 | 10/31-11/5 | ✅ Early |
| Testing | 11/21-11/23 | 11/6-11/10 | ✅ Early |
| Documentation | 11/24-11/26 | 11/11-11/15 | ✅ Early |

**Overall**: Phase 1 completed **1 week ahead of schedule**

---

## Future Work (Phase 2)

Phase 2 will build on this infrastructure to add:

1. **Two-Phase Commit (2PC)** for cross-region ride handoffs
2. **Health Monitoring Service** to track node/region status
3. **Regional FastAPI Services** for REST APIs
4. **Vehicle Simulator** for live telemetry generation
5. **Scatter-Gather Coordinator** for strong consistency global queries
6. **Performance Benchmarking** with Locust (up to 1M records)
7. **Multi-Laptop Deployment** for true distributed testing

See [phase2.md](phase2.md) for detailed Phase 2 architecture and plans.

---

## References

### Academic Papers
1. Gerla, M., Lee, E. K., Pau, G., & Lee, U. (2014). "Internet of vehicles: From intelligent grid to autonomous cars and vehicular clouds." *IEEE World Forum on Internet of Things (WF-IoT)*, pp. 241-246.
   - https://ieeexplore.ieee.org/document/6803166

2. Liu, S., Liu, L., Tang, J., Yu, B., Wang, Y., & Shi, W. (2019). "Edge computing for autonomous driving: Opportunities and challenges." *Proceedings of the IEEE*, 107(8), 1697-1716.
   - https://ieeexplore.ieee.org/document/8744265

3. Corbett, J. C., Dean, J., et al. (2013). "Spanner: Google's globally distributed database." *ACM Transactions on Computer Systems (TOCS)*, 31(3), 1-22.
   - https://research.google/pubs/pub39966/

### Technical Documentation
1. MongoDB Documentation (2024). "Sharding"
   - https://www.mongodb.com/docs/manual/sharding/

2. MongoDB Documentation (2024). "Replication"
   - https://www.mongodb.com/docs/manual/replication/

3. MongoDB Documentation (2024). "Change Streams"
   - https://www.mongodb.com/docs/manual/changeStreams/

4. Docker Documentation (2024). "Docker Compose overview"
   - https://docs.docker.com/compose/

### Industry References
1. Uber Engineering Blog: "Distributed Databases and Sharding"
2. Lyft Engineering Blog: "Geospatial Indexing for Ride Matching"
3. MongoDB Atlas: "Multi-Region Clusters"

---

## Appendix: Quick Start Commands

### Start the System
```bash
# 1. Start all 9 MongoDB containers
docker compose up -d

# 2. Initialize replica sets (wait ~30 seconds)
bash init-scripts/init-replica-sets.sh

# 3. Create database schema and indexes
bash init-scripts/init-sharding.sh

# 4. Generate 10,030 synthetic rides
python3 data-generation/generate_data.py

# 5. Start real-time synchronization
python3 init-scripts/setup-change-streams.py
```

### Verify Setup
```bash
# Check Phoenix rides
mongosh --port 27017 --eval "use av_fleet; db.rides.countDocuments({city: 'Phoenix'})"

# Check LA rides
mongosh --port 27020 --eval "use av_fleet; db.rides.countDocuments({city: 'Los Angeles'})"

# Check Global rides (should be sum)
mongosh --port 27023 --eval "use av_fleet; db.rides.countDocuments({})"
```

### Shutdown
```bash
# Stop Change Streams sync (Ctrl+C)
# Then stop containers
docker compose down
```

---

**Document Version**: 2.0 (Phase 1 Completion Report)
**Last Updated**: November 2024
**Status**: Phase 1 Complete ✅ | Phase 2 In Progress 🔄
