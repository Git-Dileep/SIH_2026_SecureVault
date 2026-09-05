#!/usr/bin/env python3
"""Username/password register and authenticate."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "recovery"))

import users  # noqa: E402


class UserStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        users.USERS_PATH = Path(self.tmp.name) / "users.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_register_and_login(self) -> None:
        users.register("examiner-01", "secret1")
        profile = users.authenticate("examiner-01", "secret1")
        self.assertEqual(profile["username"], "examiner-01")
        self.assertIsNotNone(profile["last_login_at"])

    def test_wrong_password(self) -> None:
        users.register("examiner-01", "secret1")
        with self.assertRaises(PermissionError):
            users.authenticate("examiner-01", "nope")

    def test_duplicate(self) -> None:
        users.register("examiner-01", "secret1")
        with self.assertRaises(ValueError):
            users.register("examiner-01", "other99")

    def test_short_password(self) -> None:
        with self.assertRaises(ValueError):
            users.register("examiner-01", "123")

    def test_username_rules(self) -> None:
        with self.assertRaises(ValueError):
            users.register("ab", "secret1")
        with self.assertRaises(ValueError):
            users.register("bad user", "secret1")


if __name__ == "__main__":
    unittest.main()
