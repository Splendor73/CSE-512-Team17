"""
Autonomous Vehicle Simulator
=============================

Simulates autonomous vehicles moving through Phoenix and LA regions.
Automatically triggers handoffs when vehicles cross the boundary at 33.8°N.

Features:
- Simulates 100+ vehicles
- Real-time location updates (every 2 seconds)
- Automatic boundary crossing detection
- Triggers 2PC handoffs via Coordinator
- Realistic movement patterns
- Configurable vehicle density

Usage:
    python services/vehicle_simulator.py --vehicles 100 --speed 2

    # Or with custom settings
    python services/vehicle_simulator.py --vehicles 50 --speed 1 --update-interval 3
"""

import asyncio
import httpx
import random
import argparse
import sys
from datetime import datetime, timezone
from typing import List, Dict, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# API endpoints
PHOENIX_API = "http://localhost:8001"
LA_API = "http://localhost:8002"
COORDINATOR_API = "http://localhost:8000"

# Geographic constants
BOUNDARY_LAT = 33.8  # Latitude boundary between Phoenix and LA
PHOENIX_CENTER = (33.4484, -112.0740)  # Phoenix coordinates
LA_CENTER = (34.0522, -118.2437)  # Los Angeles coordinates

# Movement parameters
LAT_DEGREE_KM = 111.0  # 1 degree latitude ≈ 111 km
LON_DEGREE_KM = 85.0   # 1 degree longitude ≈ 85 km (at ~34°N)


class Vehicle:
    """Represents a single autonomous vehicle"""

    def __init__(self, vehicle_id: str, start_region: str):
        self.vehicle_id = vehicle_id
        self.region = start_region
        self.ride_id = None
        self.customer_id = f"C-SIM-{random.randint(1000, 9999)}"
        self.status = "IDLE"

        # Starting location
        if start_region == "Phoenix":
            self.lat = PHOENIX_CENTER[0] + random.uniform(-0.2, 0.2)
            self.lon = PHOENIX_CENTER[1] + random.uniform(-0.2, 0.2)
            self.destination_lat = BOUNDARY_LAT + random.uniform(0.1, 0.3)  # Cross boundary
            self.destination_lon = LA_CENTER[1] + random.uniform(-0.2, 0.2)
        else:  # Los Angeles
            self.lat = LA_CENTER[0] + random.uniform(-0.2, 0.2)
            self.lon = LA_CENTER[1] + random.uniform(-0.2, 0.2)
            self.destination_lat = BOUNDARY_LAT - random.uniform(0.1, 0.3)  # Cross boundary
            self.destination_lon = PHOENIX_CENTER[1] + random.uniform(-0.2, 0.2)

        self.start_lat = self.lat
        self.start_lon = self.lon
        self.speed_kmh = random.uniform(40, 80)  # Speed in km/h
        self.handoff_triggered = False

    def calculate_movement(self, time_delta_seconds: float) -> Tuple[float, float]:
        """Calculate new position based on speed and time"""
        # Distance traveled in km
        distance_km = (self.speed_kmh / 3600) * time_delta_seconds

        # Calculate direction vector
        dlat = self.destination_lat - self.lat
        dlon = self.destination_lon - self.lon
        distance_to_dest = ((dlat * LAT_DEGREE_KM) ** 2 + (dlon * LON_DEGREE_KM) ** 2) ** 0.5

        if distance_to_dest < 0.5:  # Within 500m of destination
            return self.lat, self.lon  # Stop moving

        # Normalize direction and apply movement
        lat_movement = (dlat / distance_to_dest) * (distance_km / LAT_DEGREE_KM)
        lon_movement = (dlon / distance_to_dest) * (distance_km / LON_DEGREE_KM)

        new_lat = self.lat + lat_movement
        new_lon = self.lon + lon_movement

        return new_lat, new_lon

    def move(self, time_delta_seconds: float) -> bool:
        """Move vehicle and return True if boundary crossed"""
        old_lat = self.lat
        old_region = self.region

        # Calculate new position
        self.lat, self.lon = self.calculate_movement(time_delta_seconds)

        # Check boundary crossing
        if old_region == "Phoenix" and self.lat >= BOUNDARY_LAT and old_lat < BOUNDARY_LAT:
            # Crossed from Phoenix to LA
            self.region = "Los Angeles"
            return True
        elif old_region == "Los Angeles" and self.lat <= BOUNDARY_LAT and old_lat > BOUNDARY_LAT:
            # Crossed from LA to Phoenix
            self.region = "Phoenix"
            return True

        return False

    def get_location_dict(self):
        """Return location as dictionary"""
        return {"lat": round(self.lat, 6), "lon": round(self.lon, 6)}


class VehicleSimulator:
    """Main simulator class"""

    def __init__(self, num_vehicles: int, update_interval: int = 2, speed_multiplier: float = 1.0):
        self.num_vehicles = num_vehicles
        self.update_interval = update_interval
        self.speed_multiplier = speed_multiplier
        self.vehicles: List[Vehicle] = []
        self.http_client = None
        self.running = False
        self.stats = {
            "rides_created": 0,
            "handoffs_triggered": 0,
            "handoffs_successful": 0,
            "handoffs_failed": 0,
            "boundary_crossings": 0
        }

    async def setup(self):
        """Initialize HTTP client and create vehicles"""
        self.http_client = httpx.AsyncClient(timeout=10.0)
        logger.info(f"Creating {self.num_vehicles} vehicles...")

        # Create vehicles (50/50 split between regions)
        for i in range(self.num_vehicles):
            region = "Phoenix" if i % 2 == 0 else "Los Angeles"
            vehicle = Vehicle(f"AV-SIM-{i:03d}", region)
            vehicle.speed_kmh *= self.speed_multiplier
            self.vehicles.append(vehicle)

        logger.info(f"✓ Created {len(self.vehicles)} vehicles")
        logger.info(f"  - Phoenix: {sum(1 for v in self.vehicles if v.region == 'Phoenix')}")
        logger.info(f"  - LA:      {sum(1 for v in self.vehicles if v.region == 'Los Angeles')}")

    async def teardown(self):
        """Cleanup"""
        if self.http_client:
            await self.http_client.aclose()
        logger.info("Simulator stopped")

    async def create_ride(self, vehicle: Vehicle):
        """Create a ride for a vehicle"""
        try:
            ride_id = f"R-SIM-{vehicle.vehicle_id}-{int(datetime.now().timestamp())}"
            vehicle.ride_id = ride_id
            vehicle.status = "IN_PROGRESS"

            api_url = PHOENIX_API if vehicle.region == "Phoenix" else LA_API

            ride_data = {
                "rideId": ride_id,
                "vehicleId": vehicle.vehicle_id,
                "customerId": vehicle.customer_id,
                "status": "IN_PROGRESS",
                "city": vehicle.region,
                "fare": round(random.uniform(20.0, 80.0), 2),
                "startLocation": vehicle.get_location_dict(),
                "currentLocation": vehicle.get_location_dict(),
                "endLocation": {"lat": round(vehicle.destination_lat, 6),
                               "lon": round(vehicle.destination_lon, 6)},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            response = await self.http_client.post(f"{api_url}/rides", json=ride_data)

            if response.status_code == 200:
                self.stats["rides_created"] += 1
                logger.info(f"✓ Created ride {ride_id} in {vehicle.region}")
                return True
            else:
                logger.error(f"Failed to create ride: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error creating ride: {e}")
            return False

    async def update_ride_location(self, vehicle: Vehicle):
        """Update ride location"""
        if not vehicle.ride_id or vehicle.status != "IN_PROGRESS":
            return

        try:
            api_url = PHOENIX_API if vehicle.region == "Phoenix" else LA_API

            update_data = {
                "currentLocation": vehicle.get_location_dict(),
                "status": "IN_PROGRESS"
            }

            response = await self.http_client.put(
                f"{api_url}/rides/{vehicle.ride_id}",
                json=update_data
            )

            if response.status_code != 200:
                logger.warning(f"Failed to update location for {vehicle.ride_id}")

        except Exception as e:
            logger.error(f"Error updating location: {e}")

    async def trigger_handoff(self, vehicle: Vehicle, old_region: str, new_region: str):
        """Trigger handoff via coordinator"""
        if not vehicle.ride_id or vehicle.handoff_triggered:
            return

        try:
            self.stats["boundary_crossings"] += 1
            vehicle.handoff_triggered = True

            logger.info(f"🔄 BOUNDARY CROSSED: {vehicle.vehicle_id} ({vehicle.ride_id})")
            logger.info(f"   {old_region} → {new_region} at lat={vehicle.lat:.4f}")

            handoff_request = {
                "ride_id": vehicle.ride_id,
                "source": old_region,
                "target": new_region
            }

            self.stats["handoffs_triggered"] += 1

            response = await self.http_client.post(
                f"{COORDINATOR_API}/handoff",
                json=handoff_request
            )

            if response.status_code == 200:
                result = response.json()
                if result["status"] == "SUCCESS":
                    self.stats["handoffs_successful"] += 1
                    logger.info(f"✓ HANDOFF SUCCESS: {vehicle.ride_id}")
                    logger.info(f"   TX ID: {result['tx_id']}")
                    logger.info(f"   Latency: {result['latency_ms']:.2f} ms")
                elif result["status"] == "BUFFERED":
                    logger.warning(f"⚠ HANDOFF BUFFERED: {result['reason']}")
                else:
                    self.stats["handoffs_failed"] += 1
                    logger.error(f"✗ HANDOFF FAILED: {result.get('reason', 'Unknown')}")
            else:
                self.stats["handoffs_failed"] += 1
                logger.error(f"✗ HANDOFF REQUEST FAILED: {response.status_code}")

        except Exception as e:
            self.stats["handoffs_failed"] += 1
            logger.error(f"✗ Error during handoff: {e}")

    async def simulate_vehicle(self, vehicle: Vehicle):
        """Simulate a single vehicle's journey"""
        # Create initial ride
        await self.create_ride(vehicle)
        await asyncio.sleep(0.1)  # Small delay to avoid overwhelming the API

        while self.running and vehicle.status == "IN_PROGRESS":
            # Move vehicle
            old_region = vehicle.region
            boundary_crossed = vehicle.move(self.update_interval)

            # Update location
            await self.update_ride_location(vehicle)

            # Check for boundary crossing
            if boundary_crossed:
                await self.trigger_handoff(vehicle, old_region, vehicle.region)

            # Wait for next update
            await asyncio.sleep(self.update_interval)

    async def print_stats(self):
        """Periodically print statistics"""
        while self.running:
            await asyncio.sleep(10)
            logger.info("="*60)
            logger.info("SIMULATION STATISTICS")
            logger.info("="*60)
            logger.info(f"Rides Created:        {self.stats['rides_created']}")
            logger.info(f"Boundary Crossings:   {self.stats['boundary_crossings']}")
            logger.info(f"Handoffs Triggered:   {self.stats['handoffs_triggered']}")
            logger.info(f"Handoffs Successful:  {self.stats['handoffs_successful']}")
            logger.info(f"Handoffs Failed:      {self.stats['handoffs_failed']}")
            if self.stats['handoffs_triggered'] > 0:
                success_rate = (self.stats['handoffs_successful'] / self.stats['handoffs_triggered']) * 100
                logger.info(f"Success Rate:         {success_rate:.1f}%")
            logger.info("="*60)

    async def run(self, duration_seconds: int = None):
        """Run the simulation"""
        await self.setup()

        self.running = True
        logger.info(f"\n{'='*60}")
        logger.info("STARTING VEHICLE SIMULATION")
        logger.info(f"{'='*60}")
        logger.info(f"Vehicles:         {self.num_vehicles}")
        logger.info(f"Update Interval:  {self.update_interval} seconds")
        logger.info(f"Speed Multiplier: {self.speed_multiplier}x")
        logger.info(f"Boundary:         {BOUNDARY_LAT}°N")
        logger.info(f"{'='*60}\n")

        try:
            # Start all vehicle simulations
            vehicle_tasks = [self.simulate_vehicle(v) for v in self.vehicles]
            stats_task = self.print_stats()

            all_tasks = vehicle_tasks + [stats_task]

            if duration_seconds:
                # Run for specified duration
                await asyncio.wait_for(
                    asyncio.gather(*all_tasks, return_exceptions=True),
                    timeout=duration_seconds
                )
            else:
                # Run indefinitely
                await asyncio.gather(*all_tasks, return_exceptions=True)

        except asyncio.TimeoutError:
            logger.info(f"\n⏱️  Simulation duration ({duration_seconds}s) reached")
        except KeyboardInterrupt:
            logger.info("\n⏹️  Simulation interrupted by user")
        finally:
            self.running = False
            await self.teardown()

            # Print final stats
            logger.info("\n" + "="*60)
            logger.info("FINAL STATISTICS")
            logger.info("="*60)
            logger.info(f"Rides Created:        {self.stats['rides_created']}")
            logger.info(f"Boundary Crossings:   {self.stats['boundary_crossings']}")
            logger.info(f"Handoffs Triggered:   {self.stats['handoffs_triggered']}")
            logger.info(f"Handoffs Successful:  {self.stats['handoffs_successful']}")
            logger.info(f"Handoffs Failed:      {self.stats['handoffs_failed']}")
            if self.stats['handoffs_triggered'] > 0:
                success_rate = (self.stats['handoffs_successful'] / self.stats['handoffs_triggered']) * 100
                logger.info(f"Success Rate:         {success_rate:.1f}%")
            logger.info("="*60)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Autonomous Vehicle Simulator")
    parser.add_argument("--vehicles", type=int, default=100, help="Number of vehicles (default: 100)")
    parser.add_argument("--speed", type=float, default=1.0, help="Speed multiplier (default: 1.0)")
    parser.add_argument("--update-interval", type=int, default=2, help="Update interval in seconds (default: 2)")
    parser.add_argument("--duration", type=int, default=None, help="Simulation duration in seconds (default: infinite)")

    args = parser.parse_args()

    # Check if services are running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            phoenix_health = await client.get(f"{PHOENIX_API}/health")
            la_health = await client.get(f"{LA_API}/health")
            coord_health = await client.get(f"{COORDINATOR_API}/")

            if phoenix_health.status_code != 200 or la_health.status_code != 200 or coord_health.status_code != 200:
                logger.error("❌ Not all services are healthy!")
                logger.error("Please start services with: ./scripts/start_all_services.sh")
                sys.exit(1)

            logger.info("✓ All services are healthy")
            logger.info("✓ Phoenix API ready")
            logger.info("✓ LA API ready")
            logger.info("✓ Coordinator ready\n")

    except Exception as e:
        logger.error(f"❌ Cannot connect to services: {e}")
        logger.error("Please start services with: ./scripts/start_all_services.sh")
        sys.exit(1)

    # Run simulator
    simulator = VehicleSimulator(
        num_vehicles=args.vehicles,
        update_interval=args.update_interval,
        speed_multiplier=args.speed
    )

    await simulator.run(duration_seconds=args.duration)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Simulator stopped by user")
