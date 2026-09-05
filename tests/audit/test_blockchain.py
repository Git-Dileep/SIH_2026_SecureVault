#!/usr/bin/env python3
"""Permissioned audit chain: hash links, merkle proofs, tamper detection."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "audit"))

from blockchain import AuditBlockchain  # noqa: E402


class BlockchainTests(unittest.TestCase):
    def test_append_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            chain = AuditBlockchain(Path(tmp) / "chain.json")
            chain.append_entry(
                {
                    "id": "AL-001",
                    "action": "evidence.import",
                    "actor": "pytest",
                    "target": "EV-001",
                    "outcome": "success",
                    "details": {},
                }
            )
            report = chain.verify()
            self.assertTrue(report["valid"])
            proof = chain.proof_for("AL-001")
            self.assertIsNotNone(proof)
            self.assertTrue(proof["valid"])
            anchor = chain.anchor()
            self.assertTrue(anchor["tx_id"].startswith("0x"))

    def test_tamper_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            chain = AuditBlockchain(Path(tmp) / "chain.json")
            chain.append_entry({"id": "AL-009", "action": "erasure.complete", "target": "SAN-1"})
            chain.chain[-1]["entries"][0]["action"] = "tampered"
            report = chain.verify()
            self.assertFalse(report["valid"])


if __name__ == "__main__":
    unittest.main()
