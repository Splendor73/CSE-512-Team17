import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from pymongo import MongoClient, ReturnDocument

# From the host, we hit the primary of rs-global on port 27023
GLOBAL_URI = "mongodb://localhost:27023/?directConnection=true"


class GlobalCoordinator:
    """
    Global coordinator backed by the rs-global replica set.

    Responsibilities:
      - Allocate transaction IDs for cross-region operations
      - Persist transaction metadata and status transitions
      - Provide a single source of truth for recovery / debugging
    """

    def __init__(self) -> None:
        self.client = MongoClient(GLOBAL_URI)
        self.db = self.client.global_coord
        self.tx = self.db.transactions

    # --------------- lifecycle helpers ----------------

    def _now(self) -> datetime:
        return datetime.utcnow()

    def close(self) -> None:
        self.client.close()

    # --------------- public API -----------------------

    def begin_transaction(
        self,
        ride_id: str,
        source_region: str,
        target_region: str,
    ) -> str:
        """
        Create a new transaction record and return tx_id.
        """
        tx_id = str(uuid.uuid4())
        doc = {
            "tx_id": tx_id,
            "rideId": ride_id,
            "source_region": source_region,
            "target_region": target_region,
            "status": "STARTED",
            "created_at": self._now(),
            "last_updated": self._now(),
            "history": [
                {
                    "status": "STARTED",
                    "timestamp": self._now(),
                    "note": "Transaction created by coordinator.",
                }
            ],
        }
        self.tx.insert_one(doc)
        return tx_id

    def mark_prepared(self, tx_id: str, note: str = "") -> None:
        self._append_status(tx_id, "PREPARED", note)

    def mark_committed(self, tx_id: str, note: str = "") -> None:
        self._append_status(tx_id, "COMMITTED", note)

    def mark_aborted(self, tx_id: str, note: str = "") -> None:
        self._append_status(tx_id, "ABORTED", note)

    def get_transaction(self, tx_id: str) -> Optional[Dict[str, Any]]:
        return self.tx.find_one({"tx_id": tx_id})

    # --------------- internal helpers -----------------

    def _append_status(self, tx_id: str, new_status: str, note: str = "") -> None:
        """
        Atomically update status and append to history array.
        """
        update = {
            "$set": {
                "status": new_status,
                "last_updated": self._now(),
            },
            "$push": {
                "history": {
                    "status": new_status,
                    "timestamp": self._now(),
                    "note": note,
                }
            },
        }

        updated = self.tx.find_one_and_update(
            {"tx_id": tx_id},
            update,
            return_document=ReturnDocument.AFTER,
        )

        if updated is None:
            raise RuntimeError(f"GlobalCoordinator: tx_id {tx_id} not found")
