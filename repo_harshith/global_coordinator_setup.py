from pymongo import MongoClient, ASCENDING
from datetime import datetime

# Global replica set primary is exposed on host port 27023
GLOBAL_URI = "mongodb://localhost:27023/?directConnection=true"


def main():
    client = MongoClient(GLOBAL_URI)
    db = client.global_coord

    tx_coll = db.transactions

    # Create indexes for fast lookup and status queries
    tx_coll.create_index([("tx_id", ASCENDING)], unique=True, name="tx_id_unique")
    tx_coll.create_index([("rideId", ASCENDING)], name="rideId_idx")
    tx_coll.create_index([("status", ASCENDING)], name="status_idx")
    tx_coll.create_index([("created_at", ASCENDING)], name="created_at_idx")

    # Insert a tiny test document so we can verify everything works
    sample_tx = {
        "tx_id": "bootstrap-test",
        "rideId": None,
        "source_region": None,
        "target_region": None,
        "status": "BOOTSTRAP_OK",
        "created_at": datetime.utcnow(),
        "last_updated": datetime.utcnow(),
        "notes": "Global coordinator metadata store initialized.",
    }

    # upsert so running twice is safe
    tx_coll.update_one({"tx_id": "bootstrap-test"}, {"$set": sample_tx}, upsert=True)

    print("✅ Global coordinator DB initialized on rs-global.")
    print("   Database : global_coord")
    print("   Collection: transactions")
    print("   Indexes   : tx_id, rideId, status, created_at")
    client.close()


if __name__ == "__main__":
    main()
