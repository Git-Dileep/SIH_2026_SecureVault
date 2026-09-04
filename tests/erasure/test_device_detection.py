#!/usr/bin/env python3
"""Drive-type detection tests (virtual demo targets, no real disks)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "erasure"))

from device_detection import create_demo_targets, detect_device  # noqa: E402


class DeviceDetectionTests(unittest.TestCase):
    def test_nvme_path_prefix(self) -> None:
        info = detect_device("/dev/nvme0n1")
        self.assertEqual(info.drive_type, "NVMe")
        self.assertTrue(info.capabilities.nvme_format)
        self.assertTrue(info.overprovisioning_risk)
        self.assertEqual(info.recommended_method, "nvme_format_nvm")

    def test_demo_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            infos = create_demo_targets(tmp)
            types = {item.drive_type for item in infos}
            self.assertEqual(types, {"HDD", "SSD", "NVMe"})
            ssd = next(item for item in infos if item.drive_type == "SSD")
            self.assertEqual(ssd.recommended_method, "ata_secure_erase")
            hdd = next(item for item in infos if item.drive_type == "HDD")
            self.assertEqual(hdd.recommended_method, "dod_5220_22m_7pass")


if __name__ == "__main__":
    unittest.main()
