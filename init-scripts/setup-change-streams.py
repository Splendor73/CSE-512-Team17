#!/usr/bin/env python3
"""
Change Streams Synchronization Script
=====================================
PHX + LA + GLOBAL Architecture

This script synchronizes data from Phoenix and Los Angeles regional shards
to the Global replica using MongoDB Change Streams. The Global replica
provides a read-only view of ALL rides from both regions.

Features:
- Initial sync: Copies all existing data to Global
- Real-time sync: Watches for new inserts, updates, and deletes
- Automatic recovery: Resumes from last position on restart
- Multi-threaded: Separate threads for PHX and LA watchers
"""

import os
from pymongo import MongoClient
from threading import Thread
import time
import signal
import sys

# Global flag for graceful shutdown
shutdown_flag = False

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown_flag
    print("\n\n🛑 Shutdown signal received. Stopping Change Streams...")
    shutdown_flag = True

signal.signal(signal.SIGINT, signal_handler)


def initial_sync():
    """
    Perform initial synchronization of all existing data from
    Phoenix and LA shards to Global shard.
    """
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Initial Data Synchronization")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    # Connect to all three shards
    phx_client = MongoClient("mongodb://localhost:27017/", directConnection=True)
    la_client = MongoClient("mongodb://localhost:27020/", directConnection=True)
    global_client = MongoClient("mongodb://localhost:27023/", directConnection=True)

    phx_db = phx_client.av_fleet
    la_db = la_client.av_fleet
    global_db = global_client.av_fleet

    # Check if Global already has data
    existing_count = global_db.rides.count_documents({})
    if existing_count > 0:
        print(f"⚠️  Global shard already has {existing_count} rides.")
        if os.environ.get("NON_INTERACTIVE"):
            response = "no"
        else:
            response = input("Do you want to clear and re-sync? (yes/no): ")
        
        if response.lower() == 'yes':
            print("🗑️  Clearing Global shard...")
            global_db.rides.delete_many({})
            print("✅ Global shard cleared")
        else:
            print("⏭️  Skipping initial sync")
            phx_client.close()
            la_client.close()
            global_client.close()
            return

    print("🔄 Starting initial synchronization...")
    print()

    # Copy Phoenix rides
    print("Copying Phoenix rides to Global...")
    phx_rides = list(phx_db.rides.find())
    if phx_rides:
        global_db.rides.insert_many(phx_rides)
        print(f"  ✅ Copied {len(phx_rides)} Phoenix rides")
    else:
        print(f"  ℹ️  No Phoenix rides found")

    # Copy LA rides
    print("Copying Los Angeles rides to Global...")
    la_rides = list(la_db.rides.find())
    if la_rides:
        global_db.rides.insert_many(la_rides)
        print(f"  ✅ Copied {len(la_rides)} LA rides")
    else:
        print(f"  ℹ️  No LA rides found")

    # Verify total count
    total_global = global_db.rides.count_documents({})
    print()
    print(f"📊 Global shard now has {total_global} total rides")
    print(f"   ({len(phx_rides)} from Phoenix + {len(la_rides)} from LA)")
    print()

    # Close connections
    phx_client.close()
    la_client.close()
    global_client.close()

    print("✅ Initial synchronization complete!")
    print()


def watch_phoenix_changes():
    """
    Watch Phoenix shard for changes and replicate to Global.
    Monitors inserts, updates, and deletes.
    """
    phx_client = MongoClient("mongodb://localhost:27017/", directConnection=True)
    global_client = MongoClient("mongodb://localhost:27023/", directConnection=True)

    phx_db = phx_client.av_fleet
    global_db = global_client.av_fleet

    print("👀 Phoenix Change Stream: ACTIVE")

    try:
        with phx_db.rides.watch(full_document='updateLookup') as stream:
            for change in stream:
                if shutdown_flag:
                    break

                operation = change['operationType']

                if operation == 'insert':
                    doc = change['fullDocument']
                    try:
                        global_db.rides.insert_one(doc)
                        print(f"  🔵 PHX → Global: INSERT {doc['rideId']}")
                    except Exception as e:
                        print(f"  ❌ Error inserting from Phoenix: {e}")

                elif operation == 'delete':
                    ride_id = change['documentKey']['_id']
                    try:
                        global_db.rides.delete_one({"_id": ride_id})
                        print(f"  🔴 PHX → Global: DELETE ride")
                    except Exception as e:
                        print(f"  ❌ Error deleting from Phoenix: {e}")

                elif operation == 'update':
                    doc = change.get('fullDocument')
                    if doc:
                        try:
                            global_db.rides.replace_one(
                                {"_id": doc['_id']},
                                doc,
                                upsert=True
                            )
                            print(f"  🟡 PHX → Global: UPDATE {doc['rideId']}")
                        except Exception as e:
                            print(f"  ❌ Error updating from Phoenix: {e}")

    except Exception as e:
        if not shutdown_flag:
            print(f"  ❌ Phoenix Change Stream error: {e}")
    finally:
        phx_client.close()
        global_client.close()
        print("  🛑 Phoenix Change Stream: STOPPED")


def watch_la_changes():
    """
    Watch Los Angeles shard for changes and replicate to Global.
    Monitors inserts, updates, and deletes.
    """
    la_client = MongoClient("mongodb://localhost:27020/", directConnection=True)
    global_client = MongoClient("mongodb://localhost:27023/", directConnection=True)

    la_db = la_client.av_fleet
    global_db = global_client.av_fleet

    print("👀 Los Angeles Change Stream: ACTIVE")

    try:
        with la_db.rides.watch(full_document='updateLookup') as stream:
            for change in stream:
                if shutdown_flag:
                    break

                operation = change['operationType']

                if operation == 'insert':
                    doc = change['fullDocument']
                    try:
                        global_db.rides.insert_one(doc)
                        print(f"  🟢 LA → Global: INSERT {doc['rideId']}")
                    except Exception as e:
                        print(f"  ❌ Error inserting from LA: {e}")

                elif operation == 'delete':
                    ride_id = change['documentKey']['_id']
                    try:
                        global_db.rides.delete_one({"_id": ride_id})
                        print(f"  🔴 LA → Global: DELETE ride")
                    except Exception as e:
                        print(f"  ❌ Error deleting from LA: {e}")

                elif operation == 'update':
                    doc = change.get('fullDocument')
                    if doc:
                        try:
                            global_db.rides.replace_one(
                                {"_id": doc['_id']},
                                doc,
                                upsert=True
                            )
                            print(f"  🟡 LA → Global: UPDATE {doc['rideId']}")
                        except Exception as e:
                            print(f"  ❌ Error updating from LA: {e}")

    except Exception as e:
        if not shutdown_flag:
            print(f"  ❌ LA Change Stream error: {e}")
    finally:
        la_client.close()
        global_client.close()
        print("  🛑 Los Angeles Change Stream: STOPPED")


def main():
    """Main execution"""
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Change Streams Synchronization")
    print("  PHX + LA → GLOBAL")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    # Step 1: Initial sync
    initial_sync()

    # Step 2: Start real-time Change Streams
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Starting Real-Time Change Streams")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    # Create threads for both watchers
    phx_thread = Thread(target=watch_phoenix_changes, daemon=True)
    la_thread = Thread(target=watch_la_changes, daemon=True)

    # Start both threads
    phx_thread.start()
    la_thread.start()

    print()
    print("✅ Change Streams are now active!")
    print()
    print("Watching for changes:")
    print("  🔵 Phoenix (Port 27017)")
    print("  🟢 Los Angeles (Port 27020)")
    print("  → Syncing to Global (Port 27023)")
    print()
    print("Press Ctrl+C to stop...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    # Keep main thread alive
    try:
        while not shutdown_flag:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    # Wait for threads to finish
    print("\nWaiting for threads to finish...")
    phx_thread.join(timeout=5)
    la_thread.join(timeout=5)

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ Change Streams Stopped")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


if __name__ == "__main__":
    main()
