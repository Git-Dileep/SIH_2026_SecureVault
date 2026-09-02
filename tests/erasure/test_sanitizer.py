"""
Unit tests for erasure.sanitizer (End-to-end forensic sanitization pipeline).
Validates pre-wipe SHA-256 hashing, pattern overwriting, independent verification,
16-character random renaming/deletion, and data-schema.md compliant certificate generation.
Compatible with unittest and pytest.
Strictly operates on temporary local dummy files.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from erasure.methods import SanitizationAlgorithm
from erasure.sanitizer import (
    SanitizationJobResult,
    Sanitizer,
    compute_file_sha256,
    generate_random_filename,
    sanitize_file,
)


class TestErasureSanitizer(unittest.TestCase):
    """Test suite for Sanitizer orchestration engine."""

    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp(prefix="securevault_san_"))
        self.cert_dir = self.test_dir / "certificates"
        self.cert_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_random_filename_generator(self) -> None:
        """Verify 16-character random alphanumeric filename generator."""
        name1 = generate_random_filename(16)
        name2 = generate_random_filename(16)

        self.assertEqual(len(name1), 16)
        self.assertEqual(len(name2), 16)
        self.assertTrue(name1.isalnum())
        self.assertNotEqual(name1, name2)

    def test_compute_file_sha256(self) -> None:
        """Verify chunked SHA-256 computation matches standard library hashlib."""
        dummy_file = self.test_dir / "sample_hash.bin"
        sample_data = b"FORENSIC CHAIN OF CUSTODY EVIDENCE SAMPLE" * 150
        dummy_file.write_bytes(sample_data)

        expected_hash = hashlib.sha256(sample_data).hexdigest()
        computed_hash = compute_file_sha256(dummy_file)

        self.assertEqual(computed_hash, expected_hash)

    def test_end_to_end_nist_clear_workflow(self) -> None:
        """Test full NIST Clear workflow: Hash -> Overwrite -> Verify -> Scramble -> Delete -> Cert."""
        dummy_file = self.test_dir / "confidential_target.docx"
        original_data = b"PATIENT MEDICAL RECORD 2026 TOP SECRET" * 50
        dummy_file.write_bytes(original_data)
        original_hash = hashlib.sha256(original_data).hexdigest()
        original_size = len(original_data)

        sanitizer = Sanitizer(
            certificates_dir=self.cert_dir,
            approved_roots=[self.test_dir],
        )

        result: SanitizationJobResult = sanitizer.sanitize(
            target_path=dummy_file,
            algorithm=SanitizationAlgorithm.NIST_800_88_CLEAR,
            operator_name="Officer Alice Smith",
        )

        # 1. Pipeline status checks
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.verification_status, "passed")
        self.assertEqual(result.pass_count, 1)
        self.assertEqual(result.pre_wipe_sha256, original_hash)
        self.assertEqual(result.size_bytes, original_size)
        self.assertEqual(result.operator_name, "Officer Alice Smith")

        # 2. File deletion check: Original file path must NO longer exist
        self.assertFalse(dummy_file.exists())

        # 3. Certificate validation (data-schema.md compliance)
        self.assertIsNotNone(result.certificate_path)
        cert_path = Path(result.certificate_path)
        self.assertTrue(cert_path.exists())

        cert_data = json.loads(cert_path.read_text(encoding="utf-8"))
        self.assertEqual(cert_data["id"], result.id)
        self.assertEqual(cert_data["target_path"], str(dummy_file.resolve()))
        self.assertEqual(cert_data["pre_wipe_sha256"], original_hash)
        self.assertEqual(cert_data["erasure_method"], SanitizationAlgorithm.NIST_800_88_CLEAR.value)
        self.assertEqual(cert_data["pass_count"], 1)
        self.assertEqual(cert_data["verification_status"], "passed")
        self.assertEqual(cert_data["operator_name"], "Officer Alice Smith")
        self.assertIn("timestamp_iso", cert_data)
        self.assertIn("device", cert_data)
        self.assertIn("verification", cert_data)
        self.assertTrue(cert_data["verification"]["passed"])

    def test_end_to_end_dod_3pass_workflow(self) -> None:
        """Test full DoD 3-pass sanitization workflow."""
        dummy_file = self.test_dir / "dod_classified.pdf"
        dummy_file.write_bytes(b"MILITARY BLUEPRINTS 2026" * 100)

        result = sanitize_file(
            target_path=dummy_file,
            algorithm=SanitizationAlgorithm.LEGACY_DOD_5220_22_M,
            operator_name="Operator Bob",
            certificates_dir=self.cert_dir,
            approved_roots=[self.test_dir],
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.verification_status, "passed")
        self.assertEqual(result.pass_count, 3)
        self.assertEqual(result.passes_total, 3)
        self.assertFalse(dummy_file.exists())
        self.assertTrue(Path(result.certificate_path).exists())

    def test_read_only_file_sanitization(self) -> None:
        """Test that read-only files are unlocked, wiped, scrambled, and deleted cleanly."""
        ro_file = self.test_dir / "locked_file.dat"
        ro_file.write_bytes(b"READ ONLY FINANCIAL TRANSACTION LOG" * 20)

        # Set read-only attribute
        os.chmod(ro_file, stat.S_IREAD)

        result = sanitize_file(
            target_path=ro_file,
            algorithm=SanitizationAlgorithm.NIST_800_88_CLEAR,
            certificates_dir=self.cert_dir,
            approved_roots=[self.test_dir],
        )

        self.assertEqual(result.status, "completed")
        self.assertFalse(ro_file.exists())

    def test_empty_0byte_file_sanitization(self) -> None:
        """Test sanitization pipeline handles 0-byte files cleanly."""
        empty_file = self.test_dir / "empty_artifact.tmp"
        empty_file.write_bytes(b"")

        empty_hash = hashlib.sha256(b"").hexdigest()

        result = sanitize_file(
            target_path=empty_file,
            algorithm=SanitizationAlgorithm.NIST_800_88_CLEAR,
            certificates_dir=self.cert_dir,
            approved_roots=[self.test_dir],
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.size_bytes, 0)
        self.assertEqual(result.pre_wipe_sha256, empty_hash)
        self.assertFalse(empty_file.exists())

    def test_safety_rejection_for_system_paths(self) -> None:
        """Validator must reject critical OS paths and abort without I/O."""
        sanitizer = Sanitizer(
            certificates_dir=self.cert_dir,
            approved_roots=[self.test_dir],
        )

        result = sanitizer.sanitize(
            target_path=r"C:\Windows\System32",
            algorithm=SanitizationAlgorithm.NIST_800_88_CLEAR,
        )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.verification_status, "skipped")
        self.assertIn("Safety Rejection", result.error_message or "")


if __name__ == "__main__":
    unittest.main()
