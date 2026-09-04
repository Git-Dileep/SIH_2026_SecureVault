#!/usr/bin/env python3
"""Media-aware sanitization on a working COPY of a tiny virtual disk."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "erasure"))

from device_detection import create_demo_targets  # noqa: E402
from sanitizer import sanitize  # noqa: E402


class SanitizerTests(unittest.TestCase):
    def test_ssd_secure_erase_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            infos = create_demo_targets(tmp_path / "targets")
            ssd = next(item for item in infos if item.drive_type == "SSD")
            result = sanitize(
                ssd.path,
                job_id="SAN-TEST-001",
                work_dir=tmp_path / "work",
                cert_dir=tmp_path / "certs",
                method="auto",
                operator_id="pytest",
            )
            self.assertEqual(result.technique, "ata_secure_erase")
            self.assertEqual(result.nist_level, "purge")
            self.assertTrue(result.verification.get("passed"))
            self.assertTrue(Path(result.details["certificate_path"]).is_file())
            self.assertTrue(Path(result.details["working_copy"]).is_file())
            # Original demo image must be untouched (copy-only).
            original = Path(ssd.path).read_bytes()
            copy = Path(result.details["working_copy"]).read_bytes()
            self.assertNotEqual(original[:64], copy[:64])
            self.assertTrue(all(b == 0 for b in copy[:4096]))


if __name__ == "__main__":
    unittest.main()
