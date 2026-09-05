"""
Post-sanitization verification (NIST SP 800-88 Rev. 2 §4.8).

Reads sampled sectors back from the working copy and checks that residual
user data is gone. For Purge methods we expect zeros (the typical post-
secure-erase observation). A SHA-256 change from the pre-image is a
mandatory supporting check.
"""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SECTOR = 512


@dataclass
class VerificationResult:
    passed: bool
    sample_sectors_checked: int
    residual_data_found: bool
    residual_entropy: float
    expected_pattern: str
    hash_before: str
    hash_after: str
    hash_changed: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    entropy = 0.0
    n = len(data)
    for count in counts:
        if count:
            p = count / n
            entropy -= p * math.log2(p)
    return entropy


def sample_sectors(path: Path, count: int = 256, sector_size: int = SECTOR) -> bytes:
    size = path.stat().st_size
    if size <= 0:
        return b""
    count = max(1, min(count, max(1, size // sector_size)))
    buf = bytearray()
    with open(path, "rb") as handle:
        # Deterministic even spacing so the certificate is reproducible.
        step = max(sector_size, (size // count))
        offset = 0
        for _ in range(count):
            handle.seek(min(offset, max(0, size - sector_size)))
            buf.extend(handle.read(sector_size))
            offset += step
    return bytes(buf)


def verify_sanitization(
    path: str | Path,
    hash_before: str,
    expected: str = "zero",
    sample_sectors_count: int = 256,
) -> VerificationResult:
    path = Path(path)
    if not path.is_file():
        return VerificationResult(
            passed=False,
            sample_sectors_checked=0,
            residual_data_found=True,
            residual_entropy=0.0,
            expected_pattern=expected,
            hash_before=hash_before,
            hash_after="",
            hash_changed=False,
            notes="Working copy missing; cannot verify.",
        )

    hash_after = _sha256_file(path)
    hash_changed = hash_after != hash_before or path.stat().st_size == 0
    blob = sample_sectors(path, count=sample_sectors_count)
    entropy = _shannon_entropy(blob)
    sectors = len(blob) // SECTOR if blob else 0

    residual = False
    notes = ""
    if expected == "zero":
        # Any non-zero byte in the sample is residual user data.
        residual = any(byte != 0 for byte in blob)
        notes = (
            "Sampled sectors are all 0x00."
            if not residual
            else "Non-zero bytes remain in sampled sectors."
        )
    else:
        residual = not hash_changed
        notes = "Pre/post hash comparison used as the residual check."

    passed = (not residual) and hash_changed
    if path.stat().st_size == 0:
        passed = True
        residual = False
        notes = "Zero-length target; treated as sanitized."

    return VerificationResult(
        passed=passed,
        sample_sectors_checked=sectors,
        residual_data_found=residual,
        residual_entropy=round(entropy, 4),
        expected_pattern=expected,
        hash_before=hash_before,
        hash_after=hash_after,
        hash_changed=hash_changed,
        notes=notes,
    )


def sha256_file(path: str | Path) -> str:
    return _sha256_file(Path(path))
