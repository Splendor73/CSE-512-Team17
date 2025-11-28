"""
2PC Consistency Test Harness (Phoenix <-> LA)

Run with:
    venv\Scripts\activate
    python test_two_phase_consistency.py
"""

from pymongo import MongoClient
from two_phase_coordinator import two_phase_handoff, PHX_URI, LA_URI, SIMULATE_PREPARE_FAILURE


def get_phx_db():
    client = MongoClient(PHX_URI)
    return client, client.av_fleet


def get_la_db():
    client = MongoClient(LA_URI)
    return client, client.av_fleet


def get_global_counts():
    phx_client, phx_db = get_phx_db()
    la_client, la_db = get_la_db()

    phx_count = phx_db.rides.count_documents({})
    la_count = la_db.rides.count_documents({})
    total = phx_count + la_count

    phx_client.close()
    la_client.close()

    return phx_count, la_count, total


def get_overlap_ride_ids():
    """Return the set of rideIds that exist in BOTH Phoenix and LA."""
    phx_client, phx_db = get_phx_db()
    la_client, la_db = get_la_db()

    phx_ids = set(doc["rideId"] for doc in phx_db.rides.find({}, {"rideId": 1}))
    la_ids = set(doc["rideId"] for doc in la_db.rides.find({}, {"rideId": 1}))

    overlap = phx_ids.intersection(la_ids)

    phx_client.close()
    la_client.close()

    return overlap


def check_no_stuck_prepared():
    """
    Ensure no ride is left in PREPARED/locked state after 2PC.
    This is a strong correctness guarantee about the protocol.
    """
    phx_client, phx_db = get_phx_db()
    la_client, la_db = get_la_db()

    stuck_phx = phx_db.rides.count_documents(
        {"handoff_status": "PREPARED", "locked": True}
    )
    stuck_la = la_db.rides.count_documents(
        {"handoff_status": "PREPARED", "locked": True}
    )

    phx_client.close()
    la_client.close()

    assert stuck_phx == 0, f"Found {stuck_phx} stuck PREPARED rides in Phoenix"
    assert stuck_la == 0, f"Found {stuck_la} stuck PREPARED rides in LA"


def check_no_new_duplicates(initial_overlap):
    """
    Ensure 2PC did not create *additional* duplicates.
    We allow duplicates that already existed in the initial synthetic dataset,
    but we assert that the protocol does not introduce new ones.
    """
    overlap_after = get_overlap_ride_ids()

    # 2PC must not increase the overlap set
    new_duplicates = overlap_after - initial_overlap

    assert len(new_duplicates) == 0, (
        "2PC introduced new duplicate rideIds across shards: "
        f"{list(new_duplicates)[:5]}"
    )


def run_successful_handoffs(n=3):
    """
    Run 2PC handoff n times in normal mode (no simulated failure)
    and check invariants:
      - global total count is preserved
      - no rides are left PREPARED/locked
      - 2PC does not create new duplicates across shards
    """
    print(f"\n=== Running {n} successful 2PC handoffs (no simulated failure) ===")

    # Capture initial global state
    phx_before, la_before, total_before = get_global_counts()
    initial_overlap = get_overlap_ride_ids()

    print(f"Initial counts -> PHX: {phx_before}, LA: {la_before}, TOTAL: {total_before}")
    print(f"Initial overlap rideIds count: {len(initial_overlap)}")

    for i in range(1, n + 1):
        print(f"\n--- Handoff {i} ---")
        two_phase_handoff()

    phx_after, la_after, total_after = get_global_counts()
    print(f"\nAfter {n} handoffs -> PHX: {phx_after}, LA: {la_after}, TOTAL: {total_after}")

    # TOTAL must stay the same (we are moving rides, not creating/deleting globally)
    assert total_before == total_after, "Total rides changed after successful 2PC handoffs"

    # No stuck PREPARED or locked rides
    check_no_stuck_prepared()

    # 2PC must not introduce new duplicates
    check_no_new_duplicates(initial_overlap)

    print("\n[OK] Successful handoff tests passed:")
    print("     - global total preserved")
    print("     - no stuck PREPARED/locked rides")
    print("     - no new duplicate rideIds created by 2PC")


def run_failure_handoffs(n=3):
    """
    Run 2PC handoff n times with SIMULATE_PREPARE_FAILURE=True
    to verify rollback keeps system consistent.
    """
    if not SIMULATE_PREPARE_FAILURE:
        print("\n[WARN] SIMULATE_PREPARE_FAILURE is False in two_phase_coordinator.py")
        print("       Set it to True to fully test rollback behavior.")
        return

    print(f"\n=== Running {n} 2PC handoffs with simulated failures ===")

    phx_before, la_before, total_before = get_global_counts()
    initial_overlap = get_overlap_ride_ids()

    print(f"Initial counts -> PHX: {phx_before}, LA: {la_before}, TOTAL: {total_before}")
    print(f"Initial overlap rideIds count: {len(initial_overlap)}")

    for i in range(1, n + 1):
        print(f"\n--- Simulated failure handoff {i} ---")
        two_phase_handoff()

    phx_after, la_after, total_after = get_global_counts()
    print(f"\nAfter {n} simulated failures -> PHX: {phx_after}, LA: {la_after}, TOTAL: {total_after}")

    # Even with failures, TOTAL must stay the same because we roll back.
    assert total_before == total_after, "Total rides changed after simulated failure runs"

    # No stuck PREPARED or locked rides
    check_no_stuck_prepared()

    # 2PC must not introduce new duplicates either
    check_no_new_duplicates(initial_overlap)

    print("\n[OK] Failure tests passed:")
    print("     - global total preserved after rollback")
    print("     - no stuck PREPARED/locked rides")
    print("     - no new duplicate rideIds created by failed 2PC")


def main():
    print("====================================================")
    print("  2PC Consistency Test Harness (Phoenix <-> LA)")
    print("====================================================")

    # 1) Run a few successful handoffs with SIMULATE_PREPARE_FAILURE=False
    run_successful_handoffs(n=3)

    # 2) If you set SIMULATE_PREPARE_FAILURE=True in two_phase_coordinator.py,
    #    uncomment the line below to run rollback tests:
    # run_failure_handoffs(n=3)

    print("\nAll configured tests completed.")


if __name__ == "__main__":
    main()

