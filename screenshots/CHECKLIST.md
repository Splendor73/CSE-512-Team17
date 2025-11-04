# Screenshot Checklist for Phase 1 Documentation

## 📸 Screenshots to Take (12 Required)

### Infrastructure & Setup
- [ ] **01-docker-ps.png** - All 9 containers running
- [ ] **02-phoenix-rs-status.png** - Phoenix replica set status
- [ ] **03-la-rs-status.png** - LA replica set status
- [ ] **04-global-rs-status.png** - Global replica set status

### Database Configuration
- [ ] **05-indexes.png** - All 6 indexes on rides collection

### Data Generation & Distribution
- [ ] **06-data-generation.png** - Complete data generation output
- [ ] **07-phoenix-count.png** - Phoenix shard: ~5,020 rides
- [ ] **08-la-count.png** - LA shard: ~5,010 rides
- [ ] **09-global-count.png** - Global shard: ~10,030 rides

### Data Verification
- [ ] **10-sample-document.png** - Full ride document with all fields
- [ ] **11-multi-city-rides.png** - Multi-city rides query results

### Tools & Integration
- [ ] **12-compass-connections.png** - MongoDB Compass with all 3 shards

---

## 🎯 Quick Commands Reference

### Screenshot 1: Docker Containers
```bash
docker ps
```

### Screenshot 2: Phoenix Replica Set
```bash
mongosh --host localhost --port 27017 --eval "rs.status()"
```

### Screenshot 3: LA Replica Set
```bash
mongosh --host localhost --port 27020 --eval "rs.status()"
```

### Screenshot 4: Global Replica Set
```bash
mongosh --host localhost --port 27023 --eval "rs.status()"
```

### Screenshot 5: Indexes
```bash
mongosh --host localhost --port 27017 --eval "use av_fleet" --eval "db.rides.getIndexes()"
```

### Screenshot 6: Data Generation
```bash
python data-generation/generate_data.py
```

### Screenshot 7: Phoenix Count
```bash
mongosh --host localhost --port 27017 --eval "use av_fleet" --eval "
print('Total:', db.rides.countDocuments({}));
print('Completed:', db.rides.countDocuments({status: 'COMPLETED'}));
print('In-Progress:', db.rides.countDocuments({status: 'IN_PROGRESS'}));
"
```

### Screenshot 8: LA Count
```bash
mongosh --host localhost --port 27020 --eval "use av_fleet" --eval "
print('Total:', db.rides.countDocuments({}));
print('Completed:', db.rides.countDocuments({status: 'COMPLETED'}));
print('In-Progress:', db.rides.countDocuments({status: 'IN_PROGRESS'}));
"
```

### Screenshot 9: Global Count
```bash
mongosh --host localhost --port 27023 --eval "use av_fleet" --eval "
print('Total:', db.rides.countDocuments({}));
print('Completed:', db.rides.countDocuments({status: 'COMPLETED'}));
print('In-Progress:', db.rides.countDocuments({status: 'IN_PROGRESS'}));
"
```

### Screenshot 10: Sample Document
```bash
mongosh --host localhost --port 27017 --eval "use av_fleet" --eval "db.rides.findOne()"
```

### Screenshot 11: Multi-City Rides
```bash
mongosh --host localhost --port 27017 --eval "
use av_fleet
db.rides.find({
  status: 'IN_PROGRESS',
  \$or: [
    {'startLocation.lat': {\$lt: 34}, 'endLocation.lat': {\$gt: 34}},
    {'startLocation.lat': {\$gt: 34}, 'endLocation.lat': {\$lt: 34}}
  ]
}).limit(3)
"
```

### Screenshot 12: MongoDB Compass
1. Open MongoDB Compass
2. Connect to:
   - `mongodb://localhost:27017/?directConnection=true` (Phoenix)
   - `mongodb://localhost:27020/?directConnection=true` (LA)
   - `mongodb://localhost:27023/?directConnection=true` (Global)
3. Screenshot the connections list

---

## 📊 Expected Values

| Shard | Total Rides | Completed | In-Progress |
|-------|-------------|-----------|-------------|
| Phoenix | ~5,020 | ~4,995 | ~25 |
| Los Angeles | ~5,010 | ~4,985 | ~25 |
| Global | ~10,030 | ~9,980 | ~50 |

---

## ✅ After Taking Screenshots

1. Save all screenshots to `screenshots/` folder
2. Name them exactly as listed above
3. Verify all screenshots are clear and readable
4. Reference them in your documentation
5. Push to GitHub:
   ```bash
   git add screenshots/
   git commit -m "Add Phase 1 screenshots"
   git push origin phase1
   ```

---

## 📄 Documentation Template

Use this structure in your report:

```
## Completed Tasks

### Task 1: Docker Infrastructure ✅
Description: [Brief description]
Evidence: ![Docker Containers](screenshots/01-docker-ps.png)

### Task 2: Replica Sets ✅
Description: [Brief description]
Evidence:
- ![Phoenix RS](screenshots/02-phoenix-rs-status.png)
- ![LA RS](screenshots/03-la-rs-status.png)
- ![Global RS](screenshots/04-global-rs-status.png)

[Continue for all tasks...]
```
