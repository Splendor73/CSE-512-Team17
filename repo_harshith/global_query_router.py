"""
Global Query Router

Given a rideId, this script:
  1) Consults the GlobalCoordinator metadata (on rs-global)
  2) If metadata exists, decides the owning region from transaction status
  3) If metadata is missing, probes BOTH regions and picks the one
     that actually has the ride
  4) Fetches the ride from the chosen shard and prints it

Usage:
    venv\Scripts\activate
    python global_query_router.py R-123456
"""

import sys
from typing import Optional, Tuple

from pymongo import MongoClient

from global_coordinator import GlobalCoordinator
from two_phase_coordinator import PHX_URI, LA_URI


def get_phx_db():
    client = MongoClient(PHX_URI)
    return client, client.av_fleet


def get_la_db():
    client = MongoClient(LA_URI)
    return client, client.av_fleet


def decide_region_for_ride(ride_id: str) -> Tuple[Optional[str], str]:
    """
    Decide which region should own the latest version of this ride.

    Priority:
      1) Use global_coord.transactions metadata if present.
      2) If no metadata, probe PHX and LA to see where the ride actually lives.
    """
    gc = GlobalCoordinator()

    # Get the most recent transaction for this ride, if any
    doc = gc.tx.find_one(
        {"rideId": ride_id},
        sort=[("created_at", -1)],
    )

    # Case 1: we have metadata -> use it
    if doc is not None:
        status = doc.get("status")
        src = doc.get("source_region")
        tgt = doc.get("target_region")

        if status == "COMMITTED":
            gc.close()
            return tgt, f"Last tx is COMMITTED from {src} -> {tgt}."
        elif status == "ABORTED":
            gc.close()
            return src, f"Last tx is ABORTED; using source region {src}."
        else:
            gc.close()
            return src, f"Last tx status is {status}; conservatively using source region {src}."

    # Case 2: no metadata -> fall back to probing both regions
    gc.close()

    phx_client, phx_db = get_phx_db()
    la_client, la_db = get_la_db()

    phx_doc = phx_db.rides.find_one({"rideId": ride_id}, {"rideId": 1})
    la_doc = la_db.rides.find_one({"rideId": ride_id}, {"rideId": 1})

    phx_client.close()
    la_client.close()

    if phx_doc and not la_doc:
        return "PHX", "No global tx; ride found only in PHX."
    elif la_doc and not phx_doc:
        return "LA", "No global tx; ride found only in LA."
    elif phx_doc and la_doc:
        # Should not normally happen; log ambiguous case.
        return None, "Ride exists in BOTH PHX and LA; data is inconsistent."
    else:
        # Not found anywhere
        return None, "Ride not found in either region."


def fetch_ride_from_region(ride_id: str, region: str):
    """
    Actually fetch the ride document from the chosen region.
    """
    if region is None:
        return None

    if region.upper() == "PHX":
        client, db = get_phx_db()
    elif region.upper() == "LA":
        client, db = get_la_db()
    else:
        raise ValueError(f"Unknown region: {region}")

    doc = db.rides.find_one({"rideId": ride_id})
    client.close()
    return doc


def main():
    if len(sys.argv) != 2:
        print("Usage: python global_query_router.py <rideId>")
        sys.exit(1)

    ride_id = sys.argv[1]

    region, reason = decide_region_for_ride(ride_id)
    print(f"\n[Router] Decision for ride {ride_id}: {region}")
    print(f"[Router] Reason: {reason}")

    doc = fetch_ride_from_region(ride_id, region)

    if region is None:
        print("\n[Router] Could not determine a unique owning region.")
        if doc is None:
            print("[Router] Ride not found in either region.")
        return

    if doc is None:
        print(f"\n[Router] Ride {ride_id} not found in region {region}.")
    else:
        print(f"\n[Router] Ride document from {region}:")
        print(doc)


if __name__ == "__main__":
    main()


