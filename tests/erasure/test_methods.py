"""
Unit tests for erasure.methods and erasure.device_detection.
Ensures tests strictly run on local dummy test files.
"""

import os
import tempfile
from pathlib import Path
import pytest

from erasure.methods import (
    DEFAULT_CHUNK_SIZE,
    BinaryPatternGenerator,
    OverwriteEngine,
    SanitizationAlgorithm,
    overwrite_dod_3pass,
    overwrite_nist_clear,
)
from erasure.device_detection import (
    StorageMediaType,
    TargetScopeValidator,
    validate_sanitization_target,
)


@pytest.fixture
def temp_dummy_dir():
    """Create a temporary directory for local dummy files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_chunk_size_enforced():
    """Ensure standard 4096-byte chunk size is enforced."""
    assert DEFAULT_CHUNK_SIZE == 4096


def test_binary_pattern_generator():
    """Verify binary patterns generate correct byte sequences."""
    zeros = BinaryPatternGenerator.zeros(16)
    assert zeros == b"\x00" * 16

    ones = BinaryPatternGenerator.ones(16)
    assert ones == b"\xFF" * 16

    rand_bytes = BinaryPatternGenerator.random(32)
    assert len(rand_bytes) == 32
    # Probability of 32 random bytes being all 0x00 is 1/(256^32)
    assert rand_bytes != b"\x00" * 32


def test_nist_clear_overwrite_dummy_file(temp_dummy_dir):
    """Test 1-pass NIST Clear on a local dummy file."""
    dummy_file = temp_dummy_dir / "dummy_nist.txt"
    original_data = b"CONFIDENTIAL FORENSIC EVIDENCE" * 100
    dummy_file.write_bytes(original_data)
    original_size = len(original_data)

    res = overwrite_nist_clear(dummy_file)

    assert res.success is True
    assert res.passes_completed == 1
    assert res.passes_total == 1
    assert res.total_bytes_sanitized == original_size
    assert dummy_file.stat().st_size == original_size

    # Verify content was overwritten and no longer matches original
    new_data = dummy_file.read_bytes()
    assert new_data != original_data


def test_dod_3pass_overwrite_dummy_file(temp_dummy_dir):
    """Test legacy DoD 3-pass overwrite on a local dummy file."""
    dummy_file = temp_dummy_dir / "dummy_dod.bin"
    original_data = b"SECRET FORENSIC ARTIFACT RECORD" * 500
    dummy_file.write_bytes(original_data)
    original_size = len(original_data)

    res = overwrite_dod_3pass(dummy_file)

    assert res.success is True
    assert res.passes_completed == 3
    assert res.passes_total == 3
    assert len(res.pass_details) == 3
    assert res.total_bytes_sanitized == original_size

    # Verify final overwritten data is changed
    assert dummy_file.read_bytes() != original_data


def test_empty_dummy_file(temp_dummy_dir):
    """Test sanitization handles 0-byte files gracefully without crashing."""
    empty_file = temp_dummy_dir / "empty_dummy.bin"
    empty_file.write_bytes(b"")

    res = overwrite_nist_clear(empty_file)

    assert res.success is True
    assert res.total_bytes_sanitized == 0
    assert empty_file.stat().st_size == 0


def test_device_detection_rejects_system_paths():
    """Verify safety validator rejects critical system directories."""
    validator = TargetScopeValidator()

    # Reject Windows system directory
    res_win = validator.evaluate_target(r"C:\Windows\System32")
    assert res_win.is_safe is False
    assert "REJECTED" in (res_win.rejection_reason or "") or "protected" in (res_win.rejection_reason or "").lower()

    # Reject root drive device
    res_drive = validator.evaluate_target(r"\\.\PhysicalDrive0")
    assert res_drive.is_safe is False
    assert res_drive.is_block_device is True


def test_device_detection_approves_local_dummy_file(temp_dummy_dir):
    """Verify local dummy test file in approved path is marked safe."""
    dummy_file = temp_dummy_dir / "dummy_test_sample.dat"
    dummy_file.write_bytes(b"TEST DUMMY DATA")

    validator = TargetScopeValidator(approved_roots=[temp_dummy_dir])
    res = validator.evaluate_target(dummy_file)

    assert res.is_safe is True
    assert res.media_type == StorageMediaType.DUMMY_TEST_FILE
    assert res.size_bytes == len(b"TEST DUMMY DATA")
