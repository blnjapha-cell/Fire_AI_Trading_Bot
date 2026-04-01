"""
firebase_client.py
Handles all Firestore read/write operations for the Forex bot.
"""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def init_firebase(service_account_path: str = "serviceAccountKey.json"):
    """Initialize Firebase app (call once at startup)."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized.")
    return firestore.client()


class FirestoreClient:
    def __init__(self, db):
        self.db = db

    # ── Config ────────────────────────────────────────────────
    def get_config(self) -> dict:
        """Read bot config from Firestore."""
        doc = self.db.collection("config").document("bot").get()
        if doc.exists:
            return doc.to_dict()
        raise ValueError("Bot config document not found in Firestore.")

    def update_config(self, updates: dict):
        self.db.collection("config").document("bot").update(updates)

    # ── Trades ────────────────────────────────────────────────
    def log_trade(self, trade: dict) -> str:
        """Insert a new trade record. Returns the Firestore doc ID."""
        doc_ref = self.db.collection("trades").add({
            **trade,
            "status": "pending",
            "timestamp": firestore.SERVER_TIMESTAMP,
        })
        return doc_ref[1].id

    def update_trade(self, trade_id: str, updates: dict):
        self.db.collection("trades").document(trade_id).update(updates)

    def close_trade(self, trade_id: str, exit_price: float, pnl: float):
        self.update_trade(trade_id, {
            "status": "closed",
            "exit_price": exit_price,
            "pnl": pnl,
            "closed_at": firestore.SERVER_TIMESTAMP,
        })

    def get_open_trades(self) -> list:
        docs = (
            self.db.collection("trades")
            .where("status", "in", ["pending", "open"])
            .stream()
        )
        return [{"id": d.id, **d.to_dict()} for d in docs]

    # ── Signals ───────────────────────────────────────────────
    def log_signal(self, signal: dict) -> str:
        doc_ref = self.db.collection("signals").add({
            **signal,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })
        return doc_ref[1].id

    # ── Performance snapshots ─────────────────────────────────
    def snapshot_performance(self, stats: dict):
        self.db.collection("performance").add({
            **stats,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })
