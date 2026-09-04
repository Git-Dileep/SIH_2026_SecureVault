#!/usr/bin/env python3
"""Fragment classifier smoke tests (magic-byte headers)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / "recovery" / "ai"
sys.path.insert(0, str(AI))

from fragment_classifier import classify_fragment  # noqa: E402
from train_classifier import GENERATORS  # noqa: E402


class ClassifierTests(unittest.TestCase):
    def test_header_types(self) -> None:
        for label in ("jpg", "png", "pdf", "txt", "exe"):
            blob = GENERATORS[label]()
            result = classify_fragment(blob[:512])
            self.assertFalse(result.below_threshold, msg=label)
            self.assertEqual(result.file_type, label, msg=f"{label} -> {result.file_type} {result.confidence}")
            self.assertGreaterEqual(result.confidence, 0.7)

    def test_zeros_rejected(self) -> None:
        result = classify_fragment(b"\x00" * 512)
        self.assertTrue(result.below_threshold)
        self.assertEqual(result.file_type, "unknown")


if __name__ == "__main__":
    unittest.main()
