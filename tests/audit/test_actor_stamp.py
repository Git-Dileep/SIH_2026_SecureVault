#!/usr/bin/env python3
"""Ledger blocks record the signed-in operator and a UTC timestamp."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "audit"))

from actor_context import set_actor  # noqa: E402
from blockchain_logger import BlockchainLogger  # noqa: E402
from verifier import verify_chain  # noqa: E402


class ActorStampTests(unittest.TestCase):
    def tearDown(self) -> None:
        set_actor(None)

    def test_log_records_actor_and_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit_chain.json"
            set_actor("examiner-01")
            ledger = BlockchainLogger(path)
            block = ledger.log("RECOVERY_STARTED", {"image": "disk.img"})
            self.assertEqual(block["details"]["actor"], "examiner-01")
            self.assertIn("logged_at", block["details"])
            self.assertTrue(str(block["details"]["logged_at"]))
            self.assertTrue(str(block["timestamp"]))
            report = verify_chain(ledger.get_chain())
            self.assertTrue(report["valid"])

    def test_anonymous_when_no_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit_chain.json"
            set_actor(None)
            ledger = BlockchainLogger(path)
            block = ledger.log("DEMO_RESET", {})
            self.assertEqual(block["details"]["actor"], "anonymous")


if __name__ == "__main__":
    unittest.main()
