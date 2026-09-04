#!/usr/bin/env python3
"""Production safety: never sanitize a block device / system disk."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "erasure"))

from sanitizer import sanitize  # noqa: E402


class SafetyTests(unittest.TestCase):
    def test_refuses_dev_sda(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):
                sanitize(
                    "/dev/sda",
                    job_id="SAN-SAFE-001",
                    work_dir=Path(tmp) / "work",
                    cert_dir=Path(tmp) / "certs",
                    method="auto",
                    operator_id="pytest",
                )

    def test_refuses_nvme_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):
                sanitize(
                    "/dev/nvme0n1",
                    job_id="SAN-SAFE-002",
                    work_dir=Path(tmp) / "work",
                    cert_dir=Path(tmp) / "certs",
                    method="auto",
                    operator_id="pytest",
                )


if __name__ == "__main__":
    unittest.main()
