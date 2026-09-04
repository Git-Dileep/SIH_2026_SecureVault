#!/usr/bin/env python3
"""Delete-then-recover demo: folder empties, directory dies, carve still finds files."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "recovery"))

import delete_recover_demo as demo  # noqa: E402
from carver import carve_image  # noqa: E402


class DeleteRecoverDemoTests(unittest.TestCase):
    def tearDown(self) -> None:
        demo.reset()

    def test_delete_wipes_index_carve_restores(self) -> None:
        demo.reset()
        staged = demo.stage(use_samples=True)
        self.assertEqual(staged["phase"], "staged")
        self.assertGreaterEqual(len(staged["exhibits_folder"]), 4)
        self.assertGreaterEqual(len(staged["directory"]), 4)

        deleted = demo.delete_exhibits()
        self.assertEqual(deleted["phase"], "deleted")
        self.assertEqual(deleted["exhibits_folder"], [])
        self.assertEqual(deleted["directory"], [])

        out = Path(demo.DEMO_ROOT) / "carved"
        recovered = carve_image(demo.IMAGE, out, use_ai=False)
        types = {item.type for item in recovered}
        self.assertTrue({"JPEG", "PNG", "PDF", "ZIP"}.issubset(types), types)

    def test_custom_file_is_planted(self) -> None:
        demo.reset()
        png = Path(__file__).resolve().parents[2] / "recovery" / "samples" / "logo_green.png"
        demo.add_uploaded_file("my_logo.png", png.read_bytes())
        staged = demo.stage(use_samples=False)
        names = [item["filename"] for item in staged["planted"]]
        self.assertEqual(names, ["my_logo.png"])
        self.assertEqual(staged["source"], "upload")
        self.assertEqual(len(staged["exhibits_folder"]), 1)


if __name__ == "__main__":
    unittest.main()
