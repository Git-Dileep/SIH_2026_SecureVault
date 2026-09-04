#!/usr/bin/env python3
"""Spec blockchain: genesis, hash links, details_hash, tamper detection."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "audit"))

from blockchain_logger import BlockchainLogger  # noqa: E402
from verifier import verify_chain  # noqa: E402


class BlockchainLoggerTests(unittest.TestCase):
    def test_genesis_and_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit_chain.json"
            ledger = BlockchainLogger(path)
            self.assertEqual(ledger.get_chain()[0]["action"], "GENESIS")
            block = ledger.log("RECOVERY_STARTED", {"image": "disk.img"})
            self.assertEqual(block["index"], 1)
            self.assertEqual(block["previous_hash"], ledger.get_chain()[0]["hash"])
            self.assertTrue(path.is_file())
            report = verify_chain(ledger.get_chain())
            self.assertEqual(report["status"], "VALID")
            self.assertTrue(report["valid"])

    def test_tamper_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit_chain.json"
            ledger = BlockchainLogger(path)
            ledger.log("FILE_EXPORTED", {"filename": "photo.jpg"})
            chain = json.loads(path.read_text(encoding="utf-8"))
            chain[-1]["action"] = "TAMPERED"
            path.write_text(json.dumps(chain), encoding="utf-8")
            tainted = BlockchainLogger(path)
            report = verify_chain(tainted.get_chain())
            self.assertEqual(report["status"], "TAMPERED")
            self.assertFalse(report["valid"])


if __name__ == "__main__":
    unittest.main()
