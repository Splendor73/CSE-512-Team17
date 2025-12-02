"""
Performance Benchmarking Script
================================

Measures and reports key performance metrics for the rideshare system.

Metrics measured:
- Query latency (P50, P95, P99)
- Handoff latency
- Write throughput
- Data consistency
- Failover time

Usage:
    python tests/benchmark.py --all
    python tests/benchmark.py --query-latency
    python tests/benchmark.py --handoff-latency
    python tests/benchmark.py --throughput
"""

import asyncio
import time
import statistics
import argparse
import httpx
from datetime import datetime, timezone
from typing import List, Dict
import json
from motor.motor_asyncio import AsyncIOMotorClient


# Configuration
PHOENIX_API = "http://localhost:8001"
LA_API = "http://localhost:8002"
COORDINATOR_API = "http://localhost:8000"
MONGODB_URI = "mongodb://localhost:27017"


class PerformanceBenchmark:
    """Performance benchmarking suite"""

    def __init__(self):
        self.http_client = None
        self.mongo_client = None
        self.results = {}

    async def setup(self):
        """Initialize clients"""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.mongo_client = AsyncIOMotorClient(MONGODB_URI)
        print("✓ Benchmark setup complete")

    async def teardown(self):
        """Cleanup clients"""
        if self.http_client:
            await self.http_client.aclose()
        if self.mongo_client:
            self.mongo_client.close()
        print("✓ Benchmark teardown complete")

    async def benchmark_query_latency(self, num_queries=100):
        """Benchmark query latency for different scopes"""
        print("\n" + "="*60)
        print("BENCHMARK: Query Latency")
        print("="*60)

        latencies = {
            "local": [],
            "global-fast": [],
            "global-live": []
        }

        # Test local scope
        print(f"Testing local scope ({num_queries} queries)...")
        for _ in range(num_queries):
            start = time.time()
            response = await self.http_client.post(
                f"{COORDINATOR_API}/rides/search",
                json={"scope": "local", "city": "Phoenix", "limit": 10}
            )
            latency = (time.time() - start) * 1000  # Convert to ms
            if response.status_code == 200:
                latencies["local"].append(latency)

        # Test global-fast scope
        print(f"Testing global-fast scope ({num_queries} queries)...")
        for _ in range(num_queries):
            start = time.time()
            response = await self.http_client.post(
                f"{COORDINATOR_API}/rides/search",
                json={"scope": "global-fast", "limit": 10}
            )
            latency = (time.time() - start) * 1000
            if response.status_code == 200:
                latencies["global-fast"].append(latency)

        # Test global-live scope (scatter-gather)
        print(f"Testing global-live scope ({num_queries} queries)...")
        for _ in range(num_queries):
            start = time.time()
            response = await self.http_client.post(
                f"{COORDINATOR_API}/rides/search",
                json={"scope": "global-live", "limit": 10}
            )
            latency = (time.time() - start) * 1000
            if response.status_code == 200:
                latencies["global-live"].append(latency)

        # Calculate statistics
        results = {}
        for scope, values in latencies.items():
            if values:
                results[scope] = {
                    "p50": statistics.median(values),
                    "p95": statistics.quantiles(values, n=20)[18],  # 95th percentile
                    "p99": statistics.quantiles(values, n=100)[98],  # 99th percentile
                    "mean": statistics.mean(values),
                    "min": min(values),
                    "max": max(values)
                }

        # Print results
        print("\nResults:")
        print(f"{'Scope':<15} {'P50':>10} {'P95':>10} {'P99':>10} {'Mean':>10}")
        print("-" * 60)
        for scope, stats in results.items():
            print(f"{scope:<15} {stats['p50']:>9.2f}ms {stats['p95']:>9.2f}ms "
                  f"{stats['p99']:>9.2f}ms {stats['mean']:>9.2f}ms")

        self.results['query_latency'] = results
        return results

    async def benchmark_handoff_latency(self, num_handoffs=50):
        """Benchmark 2PC handoff latency"""
        print("\n" + "="*60)
        print("BENCHMARK: Handoff Latency (Two-Phase Commit)")
        print("="*60)

        latencies = []
        successes = 0
        failures = 0
        buffered = 0

        print(f"Testing {num_handoffs} handoffs...")

        for i in range(num_handoffs):
            # Create a ride in Phoenix first
            ride_id = f"R-BENCH-{int(time.time()*1000)}-{i}"
            ride_data = {
                "rideId": ride_id,
                "vehicleId": f"AV-BENCH-{i}",
                "customerId": f"C-BENCH-{i}",
                "status": "IN_PROGRESS",
                "city": "Phoenix",
                "fare": 50.0,
                "startLocation": {"lat": 33.4484, "lon": -112.0740},
                "currentLocation": {"lat": 33.9, "lon": -112.5},
                "endLocation": {"lat": 34.0522, "lon": -118.2437},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            await self.http_client.post(f"{PHOENIX_API}/rides", json=ride_data)

            # Wait a bit for write to complete
            await asyncio.sleep(0.1)

            # Initiate handoff
            start = time.time()
            response = await self.http_client.post(
                f"{COORDINATOR_API}/handoff",
                json={
                    "ride_id": ride_id,
                    "source": "Phoenix",
                    "target": "Los Angeles"
                }
            )
            latency = (time.time() - start) * 1000

            if response.status_code == 200:
                result = response.json()
                if result["status"] == "SUCCESS":
                    latencies.append(latency)
                    successes += 1
                elif result["status"] == "BUFFERED":
                    buffered += 1
                else:
                    failures += 1

            # Small delay between handoffs
            await asyncio.sleep(0.05)

        # Calculate statistics
        if latencies:
            results = {
                "p50": statistics.median(latencies),
                "p95": statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies),
                "p99": statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies),
                "mean": statistics.mean(latencies),
                "min": min(latencies),
                "max": max(latencies),
                "success_rate": (successes / num_handoffs) * 100,
                "buffered_rate": (buffered / num_handoffs) * 100,
                "failure_rate": (failures / num_handoffs) * 100
            }

            # Print results
            print("\nLatency Results:")
            print(f"P50:  {results['p50']:.2f} ms")
            print(f"P95:  {results['p95']:.2f} ms")
            print(f"P99:  {results['p99']:.2f} ms")
            print(f"Mean: {results['mean']:.2f} ms")
            print(f"Min:  {results['min']:.2f} ms")
            print(f"Max:  {results['max']:.2f} ms")
            print(f"\nSuccess Rate:  {results['success_rate']:.1f}%")
            print(f"Buffered Rate: {results['buffered_rate']:.1f}%")
            print(f"Failure Rate:  {results['failure_rate']:.1f}%")

            self.results['handoff_latency'] = results
            return results
        else:
            print("No successful handoffs to measure!")
            return None

    async def benchmark_write_throughput(self, duration_seconds=10):
        """Benchmark write throughput (rides/second)"""
        print("\n" + "="*60)
        print("BENCHMARK: Write Throughput")
        print("="*60)

        print(f"Testing write throughput for {duration_seconds} seconds...")

        write_count = 0
        start_time = time.time()
        end_time = start_time + duration_seconds

        # Create concurrent write tasks
        async def write_ride(i):
            ride_data = {
                "rideId": f"R-THROUGHPUT-{int(time.time()*1000)}-{i}",
                "vehicleId": f"AV-THRU-{i % 100}",
                "customerId": f"C-THRU-{i % 500}",
                "status": "COMPLETED",
                "city": "Phoenix",
                "fare": 25.0,
                "startLocation": {"lat": 33.4484, "lon": -112.0740},
                "currentLocation": {"lat": 33.5, "lon": -112.1},
                "endLocation": {"lat": 33.5, "lon": -112.1},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            try:
                response = await self.http_client.post(f"{PHOENIX_API}/rides", json=ride_data)
                return response.status_code == 200
            except:
                return False

        i = 0
        tasks = []
        while time.time() < end_time:
            # Launch batches of 10 concurrent writes
            batch_tasks = [write_ride(i + j) for j in range(10)]
            results = await asyncio.gather(*batch_tasks)
            write_count += sum(results)
            i += 10

        elapsed = time.time() - start_time
        throughput = write_count / elapsed

        results = {
            "total_writes": write_count,
            "duration_seconds": elapsed,
            "writes_per_second": throughput
        }

        print(f"\nResults:")
        print(f"Total Writes:       {write_count}")
        print(f"Duration:           {elapsed:.2f} seconds")
        print(f"Throughput:         {throughput:.2f} writes/second")

        self.results['write_throughput'] = results
        return results

    async def benchmark_data_consistency(self):
        """Check data consistency across regions"""
        print("\n" + "="*60)
        print("BENCHMARK: Data Consistency")
        print("="*60)

        db = self.mongo_client["rideshare"]

        # Count rides in each collection
        phoenix_count = await db["phoenix_rides"].count_documents({})
        la_count = await db["la_rides"].count_documents({})
        global_count = await db["global_rides"].count_documents({})

        # Check for duplicates (same rideId in multiple collections)
        phoenix_ids = set([doc["rideId"] async for doc in db["phoenix_rides"].find({}, {"rideId": 1})])
        la_ids = set([doc["rideId"] async for doc in db["la_rides"].find({}, {"rideId": 1})])

        duplicates = phoenix_ids.intersection(la_ids)
        duplication_rate = (len(duplicates) / max(1, phoenix_count + la_count)) * 100

        # Check global consistency
        global_expected = phoenix_count + la_count
        consistency_rate = (global_count / max(1, global_expected)) * 100

        results = {
            "phoenix_rides": phoenix_count,
            "la_rides": la_count,
            "global_rides": global_count,
            "duplicates": len(duplicates),
            "duplication_rate": duplication_rate,
            "consistency_rate": consistency_rate
        }

        print(f"\nResults:")
        print(f"Phoenix Rides:      {phoenix_count}")
        print(f"LA Rides:           {la_count}")
        print(f"Global Rides:       {global_count}")
        print(f"Expected Global:    {global_expected}")
        print(f"Duplicates:         {len(duplicates)}")
        print(f"Duplication Rate:   {duplication_rate:.2f}% (target: 0%)")
        print(f"Consistency Rate:   {consistency_rate:.2f}% (target: 100%)")

        self.results['data_consistency'] = results
        return results

    async def run_all_benchmarks(self):
        """Run all benchmark tests"""
        print("\n" + "="*70)
        print(" "*15 + "PERFORMANCE BENCHMARK SUITE")
        print("="*70)

        await self.setup()

        try:
            await self.benchmark_query_latency(num_queries=100)
            await self.benchmark_handoff_latency(num_handoffs=20)
            await self.benchmark_write_throughput(duration_seconds=10)
            await self.benchmark_data_consistency()

            # Print summary
            print("\n" + "="*70)
            print(" "*25 + "SUMMARY")
            print("="*70)

            if 'query_latency' in self.results:
                print("\nQuery Latency (P50):")
                for scope, stats in self.results['query_latency'].items():
                    print(f"  {scope:<15}: {stats['p50']:.2f} ms")

            if 'handoff_latency' in self.results:
                print(f"\nHandoff Latency (P50): {self.results['handoff_latency']['p50']:.2f} ms")
                print(f"Handoff Success Rate:  {self.results['handoff_latency']['success_rate']:.1f}%")

            if 'write_throughput' in self.results:
                print(f"\nWrite Throughput:      {self.results['write_throughput']['writes_per_second']:.2f} writes/sec")

            if 'data_consistency' in self.results:
                print(f"\nData Consistency:      {self.results['data_consistency']['consistency_rate']:.1f}%")
                print(f"Duplication Rate:      {self.results['data_consistency']['duplication_rate']:.2f}%")

            print("\n" + "="*70)

            # Save results to file
            with open("benchmark_results.json", "w") as f:
                json.dump(self.results, f, indent=2)
            print("\n✓ Results saved to benchmark_results.json")

        finally:
            await self.teardown()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run performance benchmarks")
    parser.add_argument("--all", action="store_true", help="Run all benchmarks")
    parser.add_argument("--query-latency", action="store_true", help="Benchmark query latency")
    parser.add_argument("--handoff-latency", action="store_true", help="Benchmark handoff latency")
    parser.add_argument("--throughput", action="store_true", help="Benchmark write throughput")
    parser.add_argument("--consistency", action="store_true", help="Check data consistency")

    args = parser.parse_args()

    benchmark = PerformanceBenchmark()
    await benchmark.setup()

    try:
        if args.all or (not any([args.query_latency, args.handoff_latency, args.throughput, args.consistency])):
            await benchmark.run_all_benchmarks()
        else:
            if args.query_latency:
                await benchmark.benchmark_query_latency()
            if args.handoff_latency:
                await benchmark.benchmark_handoff_latency()
            if args.throughput:
                await benchmark.benchmark_write_throughput()
            if args.consistency:
                await benchmark.benchmark_data_consistency()

            # Save results
            with open("benchmark_results.json", "w") as f:
                json.dump(benchmark.results, f, indent=2)
            print("\n✓ Results saved to benchmark_results.json")

    finally:
        await benchmark.teardown()


if __name__ == "__main__":
    asyncio.run(main())
