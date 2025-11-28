import uuid  # still used for safety if needed
from copy import deepcopy

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from global_coordinator import GlobalCoordinator

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

# Direct host connections into each primary
PHX_URI = "mongodb://localhost:27017/?directConnection=true"
LA_URI = "mongodb://localhost:27020/?directConnection=true"

# Toggle this to simulate a crash AFTER Phoenix PREPARE but BEFORE
# inserting into LA. Used to demonstrate rollback / fault tolerance.
SIMULATE_PREPARE_FAILURE = False  # set True to test rollback


# -------------------------------------------------------------------
# DB HELPERS
# -------------------------------------------------------------------

def get_phx_db():
    """Return (client, db) for the Phoenix shard."""
    client = MongoClient(PHX_URI)
    return client, client.av_fleet


def get_la_db():
    """Return (client, db) for the LA shard."""
    client = MongoClient(LA_URI)
    return client, client.av_fleet


def pick_test_ride_from_phx(phx_db):
    """
    Pick one IN_PROGRESS ride from Phoenix as a candidate
    for cross-region handoff.
    """
    return phx_db.rides.find_one(
        {"status": "IN_PROGRESS", "locked": False},
        {
            "rideId": 1,
            "city": 1,
            "currentLocation": 1,
            "handoff_status": 1,
            "locked": 1,
        },
    )


# -------------------------------------------------------------------
# 2PC HANDOFF IMPLEMENTATION (now integrated with GlobalCoordinator)
# -------------------------------------------------------------------

def two_phase_handoff():
    """
    Perform a single 2PC handoff of one ride from Phoenix -> LA.

    GlobalCoordinator on rs-global is used to:
      - allocate the transaction id
      - persist status transitions: STARTED, PREPARED, COMMITTED, ABORTED

    PHASE 1 (PREPARE):
      - Lock ride in Phoenix and mark as PREPARED with transaction_id
      - Insert copy in LA marked as PREPARED (unless we simulate failure)

    PHASE 2 (COMMIT):
      - Delete original ride in Phoenix
      - Mark LA ride as COMMITTED and unlocked

    On any error during PREPARE / COMMIT, we roll back and mark the
    transaction as ABORTED in the global coordinator.
    """
    phx_client, phx_db = get_phx_db()
    la_client, la_db = get_la_db()
    gc = GlobalCoordinator()  # global coordinator backed by rs-global

    tx_id = None
    ride_id = None

    try:
        # ---------------------------------------------------
        # 1) Pick a candidate ride from Phoenix
        # ---------------------------------------------------
        ride = pick_test_ride_from_phx(phx_db)
        if not ride:
            print("No IN_PROGRESS ride found in Phoenix.")
            return

        ride_id = ride["rideId"]
        print(f"\n=== Starting 2PC handoff for ride {ride_id} ===")

        # Ask GlobalCoordinator to allocate transaction and persist STARTED
        tx_id = gc.begin_transaction(ride_id, "PHX", "LA")
        print(f"Global transaction created, tx_id={tx_id}")

        # ---------------------------------------------------
        # PHASE 1: PREPARE
        # ---------------------------------------------------
        print("\n--- PHASE 1: PREPARE ---")

        # a) Lock and mark ride as PREPARED in Phoenix
        res_phx = phx_db.rides.update_one(
            {"rideId": ride_id, "locked": False},
            {
                "$set": {
                    "locked": True,
                    "handoff_status": "PREPARED",
                    "transaction_id": tx_id,
                }
            },
        )

        if res_phx.matched_count != 1:
            raise RuntimeError("Failed to lock/prepare ride in Phoenix")

        print("Phoenix PREPARE done (locked + transaction_id set).")

        # ⛔ Optional: simulate a crash AFTER prepare in Phoenix
        if SIMULATE_PREPARE_FAILURE:
            raise RuntimeError("SIMULATED FAILURE after Phoenix PREPARE")

        # b) Fetch updated doc & insert PREPARED copy into LA
        src_doc = phx_db.rides.find_one({"rideId": ride_id})
        if not src_doc:
            raise RuntimeError("Source ride disappeared after prepare in Phoenix")

        dest_doc = deepcopy(src_doc)
        dest_doc.pop("_id", None)        # Let LA generate its own _id
        dest_doc["city"] = "Los Angeles"  # New owner city

        res_la = la_db.rides.insert_one(dest_doc)
        dest_id = res_la.inserted_id

        print("PREPARE succeeded on both Phoenix and LA.")
        gc.mark_prepared(tx_id, "Phoenix locked + LA copy inserted.")

        # ---------------------------------------------------
        # PHASE 2: COMMIT
        # ---------------------------------------------------
        print("\n--- PHASE 2: COMMIT ---")

        # a) Delete original ride from Phoenix
        res_del = phx_db.rides.delete_one(
            {"rideId": ride_id, "transaction_id": tx_id}
        )
        if res_del.deleted_count != 1:
            raise RuntimeError(
                "Commit error: could not delete source ride in Phoenix"
            )

        # b) Mark LA ride as COMMITTED + unlock
        la_db.rides.update_one(
            {"_id": dest_id},
            {
                "$set": {
                    "handoff_status": "COMMITTED",
                    "locked": False,
                    "transaction_id": None,
                }
            },
        )

        print("COMMIT complete. Ride now owned by LA only.")
        print(f"Ride {ride_id} successfully handed off PHX -> LA in tx {tx_id}.")
        gc.mark_committed(tx_id, "Commit completed in both regions.")

    except Exception as e:
        # ---------------------------------------------------
        # ROLLBACK LOGIC
        # ---------------------------------------------------
        print("\n!!! ERROR during 2PC handoff:", e)
        print("--- ROLLING BACK ---")

        try:
            if ride_id is not None and tx_id is not None:
                # Unlock ride in Phoenix if it was left PREPARED
                phx_db.rides.update_one(
                    {"rideId": ride_id, "transaction_id": tx_id},
                    {
                        "$set": {
                            "locked": False,
                            "handoff_status": "ABORTED",
                            "transaction_id": None,
                        }
                    },
                )

                # Remove tentative copies in LA for this tx
                la_db.rides.delete_many({"transaction_id": tx_id})

            if tx_id is not None:
                gc.mark_aborted(tx_id, f"2PC failed: {e}")

        except PyMongoError as rollback_err:
            print("Rollback encountered an error:", rollback_err)

    finally:
        phx_client.close()
        la_client.close()
        gc.close()
        print("=== 2PC handoff finished (success or failure) ===\n")


# -------------------------------------------------------------------
# MAIN (for manual testing)
# -------------------------------------------------------------------

def main():
    # Show counts before & after a single handoff
    phx_client, phx_db = get_phx_db()
    la_client, la_db = get_la_db()

    print("Before handoff:")
    print("  Phoenix rides:", phx_db.rides.count_documents({}))
    print("  LA rides     :", la_db.rides.count_documents({}))

    phx_client.close()
    la_client.close()

    two_phase_handoff()

    phx_client, phx_db = get_phx_db()
    la_client, la_db = get_la_db()

    print("After handoff:")
    print("  Phoenix rides:", phx_db.rides.count_documents({}))
    print("  LA rides     :", la_db.rides.count_documents({}))

    phx_client.close()
    la_client.close()


if __name__ == "__main__":
    main()




