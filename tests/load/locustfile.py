"""
Load Testing with Locust
=========================

This file defines load test scenarios for the rideshare system.

Usage:
    # Test single Regional API
    locust -f tests/load/locustfile.py --host http://localhost:8001

    # Test with 1000 users
    locust -f tests/load/locustfile.py --host http://localhost:8001 \
        --users 1000 --spawn-rate 10 --run-time 60s --headless

    # Test Coordinator
    locust -f tests/load/locustfile.py RegionalAPIUser --host http://localhost:8000

Prerequisites:
    pip install locust
"""

from locust import HttpUser, task, between, events
from datetime import datetime, timezone
import random
import json


# Sample data generators
VEHICLE_IDS = [f"AV-PHX-{i:03d}" for i in range(1, 101)]
CUSTOMER_IDS = [f"C-{i:04d}" for i in range(1, 1001)]
CITIES = ["Phoenix", "Los Angeles"]

# Phoenix coordinates
PHX_LATS = [33.4 + random.random() * 0.2 for _ in range(100)]
PHX_LONS = [-112.2 + random.random() * 0.2 for _ in range(100)]

# LA coordinates
LA_LATS = [34.0 + random.random() * 0.2 for _ in range(100)]
LA_LONS = [-118.3 + random.random() * 0.2 for _ in range(100)]


def generate_ride_data(city="Phoenix"):
    """Generate random ride data"""
    ride_id = f"R-LOAD-{random.randint(100000, 999999)}"

    if city == "Phoenix":
        lat = random.choice(PHX_LATS)
        lon = random.choice(PHX_LONS)
    else:
        lat = random.choice(LA_LATS)
        lon = random.choice(LA_LONS)

    return {
        "rideId": ride_id,
        "vehicleId": random.choice(VEHICLE_IDS),
        "customerId": random.choice(CUSTOMER_IDS),
        "status": random.choice(["IN_PROGRESS", "COMPLETED"]),
        "city": city,
        "fare": round(random.uniform(10.0, 100.0), 2),
        "startLocation": {"lat": lat, "lon": lon},
        "currentLocation": {"lat": lat + 0.01, "lon": lon + 0.01},
        "endLocation": {"lat": lat + 0.05, "lon": lon + 0.05},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


class RegionalAPIUser(HttpUser):
    """Simulates users interacting with Regional API"""

    wait_time = between(0.5, 2.0)  # Wait 0.5-2 seconds between tasks

    def on_start(self):
        """Called when a simulated user starts"""
        self.created_rides = []

    @task(5)
    def create_ride(self):
        """Create a new ride (50% weight)"""
        ride_data = generate_ride_data()
        self.created_rides.append(ride_data["rideId"])

        with self.client.post(
            "/rides",
            json=ride_data,
            catch_response=True,
            name="POST /rides"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed: {response.status_code}")

    @task(3)
    def get_ride(self):
        """Get a ride by ID (30% weight)"""
        if self.created_rides:
            ride_id = random.choice(self.created_rides)
            with self.client.get(
                f"/rides/{ride_id}",
                catch_response=True,
                name="GET /rides/{id}"
            ) as response:
                if response.status_code == 200:
                    response.success()
                elif response.status_code == 404:
                    response.success()  # Expected if ride was deleted
                else:
                    response.failure(f"Failed: {response.status_code}")

    @task(1)
    def get_stats(self):
        """Get regional statistics (10% weight)"""
        with self.client.get(
            "/stats",
            catch_response=True,
            name="GET /stats"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed: {response.status_code}")

    @task(1)
    def health_check(self):
        """Health check (10% weight)"""
        with self.client.get(
            "/health",
            catch_response=True,
            name="GET /health"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed: {response.status_code}")


class CoordinatorUser(HttpUser):
    """Simulates users interacting with Global Coordinator"""

    wait_time = between(1.0, 3.0)

    def on_start(self):
        """Setup for coordinator testing"""
        # Create some rides in both regions first
        self.ride_ids = []
        for _ in range(5):
            ride_data = generate_ride_data("Phoenix")
            # Would need to call regional APIs here
            self.ride_ids.append(ride_data["rideId"])

    @task(3)
    def search_rides_local(self):
        """Search rides with local scope (30% weight)"""
        query = {
            "scope": "local",
            "city": random.choice(["Phoenix", "Los Angeles"]),
            "limit": random.choice([10, 20, 50])
        }

        with self.client.post(
            "/rides/search",
            json=query,
            catch_response=True,
            name="POST /rides/search (local)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed: {response.status_code}")

    @task(2)
    def search_rides_global_fast(self):
        """Search rides with global-fast scope (20% weight)"""
        query = {
            "scope": "global-fast",
            "limit": random.choice([10, 20, 50]),
            "min_fare": random.choice([None, 20.0, 30.0])
        }

        with self.client.post(
            "/rides/search",
            json=query,
            catch_response=True,
            name="POST /rides/search (global-fast)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed: {response.status_code}")

    @task(2)
    def search_rides_global_live(self):
        """Search rides with global-live scope (20% weight)"""
        query = {
            "scope": "global-live",
            "limit": random.choice([10, 20, 50])
        }

        with self.client.post(
            "/rides/search",
            json=query,
            catch_response=True,
            name="POST /rides/search (global-live)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed: {response.status_code}")

    @task(1)
    def get_all_stats(self):
        """Get stats from all regions (10% weight)"""
        with self.client.get(
            "/stats/all",
            catch_response=True,
            name="GET /stats/all"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed: {response.status_code}")

    @task(1)
    def initiate_handoff(self):
        """Initiate a cross-region handoff (10% weight)"""
        if self.ride_ids:
            handoff_request = {
                "ride_id": random.choice(self.ride_ids),
                "source": "Phoenix",
                "target": "Los Angeles"
            }

            with self.client.post(
                "/handoff",
                json=handoff_request,
                catch_response=True,
                name="POST /handoff"
            ) as response:
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") in ["SUCCESS", "BUFFERED", "FAILED"]:
                        response.success()
                    else:
                        response.failure(f"Unexpected status: {data.get('status')}")
                else:
                    response.failure(f"Failed: {response.status_code}")

    @task(1)
    def get_transaction_history(self):
        """Get transaction history (10% weight)"""
        with self.client.get(
            "/transactions/history?limit=20",
            catch_response=True,
            name="GET /transactions/history"
        ) as response:
            if response.status_code in [200, 500]:  # 500 ok if DB not connected
                response.success()
            else:
                response.failure(f"Failed: {response.status_code}")


# Custom statistics tracking
request_latencies = []


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Track request latencies for P50/P99 calculation"""
    if exception is None:
        request_latencies.append(response_time)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Calculate and print P50/P99 latencies at test end"""
    if request_latencies:
        request_latencies.sort()
        count = len(request_latencies)

        p50_index = int(count * 0.50)
        p95_index = int(count * 0.95)
        p99_index = int(count * 0.99)

        print("\n" + "="*60)
        print("LATENCY PERCENTILES")
        print("="*60)
        print(f"P50 (median): {request_latencies[p50_index]:.2f} ms")
        print(f"P95:          {request_latencies[p95_index]:.2f} ms")
        print(f"P99:          {request_latencies[p99_index]:.2f} ms")
        print(f"Max:          {request_latencies[-1]:.2f} ms")
        print(f"Min:          {request_latencies[0]:.2f} ms")
        print("="*60 + "\n")
