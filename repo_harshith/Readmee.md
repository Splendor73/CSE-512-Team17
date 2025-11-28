# 🚗 Autonomous Vehicle Fleet – Distributed Database System  
### Phoenix (PHX) ↔ Los Angeles (LA) Cross-Region Architecture with Global Coordinator

This project implements a fully distributed backend for an autonomous vehicle fleet management system using **MongoDB replica sets**, **Two-Phase Commit (2PC)**, **failure-tolerant handoffs**, and a **Global Coordinator** for transaction metadata and query routing.

It demonstrates real-world distributed system features:

- Multi-region partitioning  
- Cross-region ride handoff with atomicity  
- Fault tolerance and rollback  
- Global metadata tracking  
- Query routing across regions  
- End-to-end consistency tests  

---

# 📁 Project Structure

```
ddbs_project/
│
├── docker-compose.yml                 
├── init-replica-sets.sh               
├── init-sharding.sh                   
├── setup-change-streams.py            
│
├── generate_data.py                   
│
├── two_phase_coordinator.py           
├── global_coordinator_setup.py        
├── global_coordinator.py              
├── global_query_router.py             
│
├── test_two_phase_consistency.py      
│
└── requirements.txt
```

---

# 🔧 System Architecture

## 1. Distributed Replica Sets (9 MongoDB Nodes)

We deploy:

- Phoenix Region (PHX) – 3-node replica set (`rs-phoenix`)
- Los Angeles Region (LA) – 3-node replica set (`rs-la`)
- Global Coordinator Region – 3-node replica set (`rs-global`)

All containers run MongoDB 7.0 with host port mappings:

| Region | Ports | Purpose |
|--------|--------|---------|
| Phoenix | 27017–27019 | Operational PHX rides |
| Los Angeles | 27020–27022 | Operational LA rides |
| Global | 27023–27025 | GlobalCoordinator metadata |

---

# 🌎 2. Ride Storage & Sharding Model

Rides are partitioned by **city**:

- PHX → stored only in **rs-phoenix**
- LA → stored only in **rs-la**
- Global → stores only **metadata**, not rides

---

# 🚕 3. Synthetic Ride Generation

`generate_data.py` creates:

- 10,000 regular rides  
- 20 multi-city boundary-crossing rides  
- 10 boundary rides  
- Split roughly 50/50 between PHX and LA  

Performance:  
**10k rides in ~0.7 seconds**

---

# 🔁 4. Two-Phase Commit (2PC) Handoff

`two_phase_coordinator.py` implements:

### Phase 1 – PREPARE
- Lock ride in PHX  
- Mark as PREPARED  
- Insert copy into LA  

### Phase 2 – COMMIT
- Delete PHX copy  
- Mark LA copy COMMITTED  

### Rollback
If anything fails:
- Unlock PHX ride  
- Remove tentative LA copy  
- Mark global tx ABORTED  

---

# 💥 5. Failure Simulation

Enable crash after PHX PREPARE:

```
SIMULATE_PREPARE_FAILURE = True
```

Ensures:
- No stuck locks  
- No lost rides  
- No duplicates  
- Global tx marked ABORTED  

---

# 🌐 6. Global Coordinator (rs-global)

Tracks all 2PC transactions via:

- DB: `global_coord`
- Collection: `transactions`
- Status lifecycle:
  - STARTED  
  - PREPARED  
  - COMMITTED  
  - ABORTED  

Provides auditability, recovery, and routing metadata.

---

# 🔎 7. Global Query Router

`global_query_router.py` resolves any rideId by:

1. Checking global metadata  
2. If missing, probing PHX + LA  
3. Returning whichever region owns the ride  

---

# 🧪 8. Consistency Testing

`test_two_phase_consistency.py` validates:

- No data loss  
- No new duplicates  
- No stuck PREPARED rides  
- Rollback correctness  

---

# 🚀 How to Run

### Start cluster
```
docker-compose up -d
```

### Initialize replica sets
```
./init-replica-sets.sh
```

### Init schema + indexes
```
./init-sharding.sh
```

### Generate rides
```
python generate_data.py
```

### Setup global coordinator DB
```
python global_coordinator_setup.py
```

### Run a 2PC handoff
```
python two_phase_coordinator.py
```

### Simulate failure
Set:
```
SIMULATE_PREPARE_FAILURE = True
```

### Query a ride
```
python global_query_router.py R-XXXXX
```

### Run tests
```
python test_two_phase_consistency.py
```

---

# 👥 Team Members
(Add names here)

# 📄 License
Educational / academic use.