#!/usr/bin/env python3
"""
Autonomous Vehicle Fleet - Synthetic Data Generation
====================================================
PHX + LA + GLOBAL Architecture

This script generates realistic synthetic ride data for testing the
distributed AV fleet management system. It creates rides distributed
across two geographic regions (Phoenix, LA) with realistic
attributes including GPS coordinates, timestamps, fares, and statuses.

Features:
- Geographic distribution: 50% Phoenix, 50% LA
- Realistic GPS coordinates within city boundaries
- Mix of completed and in-progress rides
- Special MULTI-CITY rides for cross-region handoff testing
- Special boundary rides positioned near 33.8°N
- Multiprocessing for fast generation
- Batch insertion for efficiency
"""

import random
from datetime import datetime, timedelta
from faker import Faker
from pymongo import MongoClient
from multiprocessing import Pool, cpu_count
import time
from typing import Dict, List, Tuple

# Initialize Faker
fake = Faker()

# ============================================
# GEOGRAPHIC BOUNDARIES
# ============================================

# City boundaries (lat/lon ranges)
CITY_BOUNDARIES = {
    "Phoenix": {
        "lat_range": (33.30, 33.70),
        "lon_range": (-112.30, -111.90),
        "port": 27017
    },
    "Los Angeles": {
        "lat_range": (33.90, 34.20),
        "lon_range": (-118.50, -118.10),
        "port": 27020
    }
}

# Regional boundary for handoff testing (Phoenix <-> LA boundary)
PHX_LA_BOUNDARY = 33.80  # Latitude boundary


# ============================================
# DATA GENERATION FUNCTIONS
# ============================================

def generate_gps_for_city(city: str) -> Dict[str, float]:
    """Generate random GPS coordinates within city boundaries."""
    boundaries = CITY_BOUNDARIES[city]
    lat = random.uniform(*boundaries["lat_range"])
    lon = random.uniform(*boundaries["lon_range"])
    return {"lat": round(lat, 6), "lon": round(lon, 6)}


def generate_ride(city: str, ride_type: str = "completed") -> Dict:
    """
    Generate a single synthetic ride record.

    Args:
        city: Target city (Phoenix or Los Angeles)
        ride_type: "completed", "in_progress", "boundary", or "multi_city"

    Returns:
        Dictionary containing ride data
    """
    ride_id = f"R-{fake.random_int(100000, 999999)}"
    vehicle_id = f"AV-{fake.random_int(1000, 9999)}"
    customer_id = f"C-{fake.random_int(100000, 999999)}"

    # Generate timestamps (rides from past 90 days)
    timestamp = fake.date_time_between(start_date="-90d", end_date="now")

    # Determine ride status and locations
    if ride_type == "multi_city":
        # MULTI-CITY RIDE: Crosses from one city to another
        status = "IN_PROGRESS"

        # Randomly choose direction: PHX→LA or LA→PHX
        if random.choice([True, False]):
            # Phoenix to Los Angeles
            start_location = generate_gps_for_city("Phoenix")
            end_location = generate_gps_for_city("Los Angeles")
            # Current location near boundary (in Phoenix territory for now)
            current_location = {
                "lat": round(PHX_LA_BOUNDARY - random.uniform(0.01, 0.05), 6),
                "lon": random.uniform(-112.30, -111.90)
            }
            city = "Phoenix"  # Currently in Phoenix
        else:
            # Los Angeles to Phoenix
            start_location = generate_gps_for_city("Los Angeles")
            end_location = generate_gps_for_city("Phoenix")
            # Current location near boundary (in LA territory for now)
            current_location = {
                "lat": round(PHX_LA_BOUNDARY + random.uniform(0.01, 0.05), 6),
                "lon": random.uniform(-118.50, -118.10)
            }
            city = "Los Angeles"  # Currently in LA

    elif ride_type == "boundary":
        # Special boundary ride for handoff testing (very close to boundary)
        status = "IN_PROGRESS"
        start_location = generate_gps_for_city("Phoenix")
        # Current location VERY NEAR PHX-LA boundary
        current_location = {
            "lat": round(PHX_LA_BOUNDARY - 0.02 + random.uniform(0, 0.04), 6),
            "lon": random.uniform(-112.30, -111.90)
        }
        end_location = generate_gps_for_city("Los Angeles")

    elif ride_type == "in_progress":
        status = "IN_PROGRESS"
        start_location = generate_gps_for_city(city)
        current_location = generate_gps_for_city(city)
        end_location = generate_gps_for_city(city)

    else:  # completed ride
        status = "COMPLETED"
        start_location = generate_gps_for_city(city)
        current_location = generate_gps_for_city(city)
        end_location = current_location  # Arrived at destination

    # Calculate realistic fare based on approximate distance
    distance = abs(end_location["lat"] - start_location["lat"]) + \
               abs(end_location["lon"] - start_location["lon"])
    base_fare = 8.00
    per_unit_fare = 50.0  # Approximate
    fare = round(base_fare + (distance * per_unit_fare), 2)
    fare = max(fare, 8.00)  # Minimum fare
    fare = min(fare, 150.00)  # Maximum fare

    ride = {
        "rideId": ride_id,
        "vehicleId": vehicle_id,
        "customerId": customer_id,
        "status": status,
        "fare": fare,
        "city": city,
        "timestamp": timestamp,
        "startLocation": start_location,
        "currentLocation": current_location,
        "endLocation": end_location,
        "handoff_status": None,  # For future 2PC handoff tracking
        "locked": False,  # For future transaction locking
        "transaction_id": None  # For future 2PC transaction ID
    }

    return ride


def generate_batch(args: Tuple[str, int, str]) -> List[Dict]:
    """
    Generate a batch of rides (for multiprocessing).

    Args:
        args: Tuple of (city, count, ride_type)

    Returns:
        List of ride dictionaries
    """
    city, count, ride_type = args
    return [generate_ride(city, ride_type) for _ in range(count)]


# ============================================
# DATABASE INSERTION
# ============================================

def insert_to_shard(rides: List[Dict], city: str):
    """
    Insert rides into the appropriate regional shard.

    Args:
        rides: List of ride documents
        city: City name (determines which shard)
    """
    port = CITY_BOUNDARIES[city]["port"]
    # Use directConnection=True to bypass replica set discovery
    client = MongoClient(f"mongodb://localhost:{port}/", directConnection=True)
    db = client.av_fleet

    try:
        # Insert in batches for efficiency
        batch_size = 1000
        for i in range(0, len(rides), batch_size):
            batch = rides[i:i + batch_size]
            db.rides.insert_many(batch, ordered=False)

        print(f"✅ Inserted {len(rides)} rides into {city} shard (port {port})")
        return len(rides)

    except Exception as e:
        print(f"❌ Error inserting into {city} shard: {e}")
        return 0
    finally:
        client.close()


# ============================================
# MAIN GENERATION PIPELINE
# ============================================

def main():
    """Main data generation pipeline."""
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Autonomous Vehicle Fleet - Data Generation")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    # Configuration
    TOTAL_RIDES = 10000
    PHOENIX_PERCENT = 0.50
    LA_PERCENT = 0.50
    COMPLETED_PERCENT = 0.995  # 99.5% completed
    BOUNDARY_RIDES = 10  # Special rides for handoff testing
    MULTI_CITY_RIDES = 20  # Cross-region rides (PHX ↔ LA)

    phoenix_count = int(TOTAL_RIDES * PHOENIX_PERCENT)
    la_count = int(TOTAL_RIDES * LA_PERCENT)

    print(f"Target Distribution:")
    print(f"  • Phoenix: {phoenix_count} rides (50%)")
    print(f"  • Los Angeles: {la_count} rides (50%)")
    print(f"  • Multi-City: {MULTI_CITY_RIDES} cross-region rides")
    print(f"  • Boundary: {BOUNDARY_RIDES} rides near 33.8°N")
    print(f"  • Total: {TOTAL_RIDES + MULTI_CITY_RIDES + BOUNDARY_RIDES} rides")
    print()

    start_time = time.time()

    # ============================================
    # STEP 1: Generate Regular Rides
    # ============================================
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Step 1: Generating synthetic rides")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Prepare batches for parallel processing
    num_workers = min(cpu_count(), 8)
    rides_per_worker = 1000

    tasks = []
    for city, total in [("Phoenix", phoenix_count), ("Los Angeles", la_count)]:
        completed = int(total * COMPLETED_PERCENT)
        in_progress = total - completed

        # Split into batches
        for i in range(0, completed, rides_per_worker):
            batch_size = min(rides_per_worker, completed - i)
            tasks.append((city, batch_size, "completed"))

        if in_progress > 0:
            tasks.append((city, in_progress, "in_progress"))

    # Generate rides in parallel
    print(f"Using {num_workers} worker processes...")
    with Pool(num_workers) as pool:
        results = pool.map(generate_batch, tasks)

    # Flatten results and group by city
    all_rides = {"Phoenix": [], "Los Angeles": []}
    for batch in results:
        if batch:
            city = batch[0]["city"]
            all_rides[city].extend(batch)

    generation_time = time.time() - start_time
    total_generated = sum(len(rides) for rides in all_rides.values())
    print(f"✅ Generated {total_generated} rides in {generation_time:.2f} seconds")
    print(f"   ({int(total_generated/generation_time)} rides/second)")
    print()

    # ============================================
    # STEP 2: Generate Multi-City Rides
    # ============================================
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Step 2: Generating multi-city rides (cross-region handoffs)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    multi_city_rides = [generate_ride("Phoenix", "multi_city") for _ in range(MULTI_CITY_RIDES)]
    # Distribute multi-city rides based on their current location
    for ride in multi_city_rides:
        all_rides[ride["city"]].append(ride)
    print(f"✅ Generated {MULTI_CITY_RIDES} multi-city rides (PHX ↔ LA)")
    print()

    # ============================================
    # STEP 3: Generate Boundary Rides
    # ============================================
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Step 3: Generating boundary rides for handoff testing")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    boundary_rides = [generate_ride("Phoenix", "boundary") for _ in range(BOUNDARY_RIDES)]
    all_rides["Phoenix"].extend(boundary_rides)
    print(f"✅ Generated {BOUNDARY_RIDES} boundary rides (very close to 33.8°N)")
    print()

    # ============================================
    # STEP 4: Insert into Shards
    # ============================================
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Step 4: Inserting rides into regional shards")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    insert_start = time.time()
    total_inserted = 0

    for city, rides in all_rides.items():
        if rides:
            inserted = insert_to_shard(rides, city)
            total_inserted += inserted

    insert_time = time.time() - insert_start
    print()
    print(f"✅ Inserted {total_inserted} rides in {insert_time:.2f} seconds")
    print()

    # ============================================
    # STEP 5: Verify Insertion
    # ============================================
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Step 5: Verifying data distribution")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for city, info in CITY_BOUNDARIES.items():
        port = info["port"]
        client = MongoClient(f"mongodb://localhost:{port}/", directConnection=True)
        db = client.av_fleet

        total_count = db.rides.count_documents({})
        completed_count = db.rides.count_documents({"status": "COMPLETED"})
        in_progress_count = db.rides.count_documents({"status": "IN_PROGRESS"})

        print(f"\n{city} Shard (port {port}):")
        print(f"  • Total rides: {total_count}")
        print(f"  • Completed: {completed_count}")
        print(f"  • In Progress: {in_progress_count}")

        client.close()

    # ============================================
    # SUMMARY
    # ============================================
    total_time = time.time() - start_time

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ Data Generation Complete!")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print("Summary:")
    total_rides = total_generated + MULTI_CITY_RIDES + BOUNDARY_RIDES
    print(f"  • Total rides generated: {total_rides}")
    print(f"  • Regular rides: {total_generated}")
    print(f"  • Multi-city rides: {MULTI_CITY_RIDES}")
    print(f"  • Boundary test rides: {BOUNDARY_RIDES}")
    print(f"  • Total time: {total_time:.2f} seconds")
    print(f"  • Average rate: {int(total_rides/total_time)} rides/second")
    print()
    print("Architecture:")
    print("  • Phoenix shard (Port 27017): Phoenix rides only")
    print("  • LA shard (Port 27020): LA rides only")
    print("  • Global shard (Port 27023): Will sync ALL rides via Change Streams")
    print()
    print("Next Steps:")
    print("  1. Set up Change Streams: python init-scripts/setup-change-streams.py")
    print("  2. Verify Global has all data: mongosh --port 27023 --eval 'use av_fleet' --eval 'db.rides.countDocuments({})'")
    print("  3. View multi-city rides: mongosh --port 27017 --eval 'use av_fleet' --eval 'db.rides.find({startLocation:{$exists:true}, endLocation:{$exists:true}}).limit(5)'")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    main()
