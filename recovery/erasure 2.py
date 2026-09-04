#!/usr/bin/env python3
"""
erasure.py — MOCK / DEMO secure-erasure module.

This is intentionally limited. For the hackathon we show the *workflow*
of sanitization (hash → overwrite → verify) without touching real disks.

Safety rules:
  - We never operate on block devices (/dev/disk*, \\\\.\\PhysicalDrive*).
  - We work on a COPY of a regular file, never on the caller's original.
  - This is NOT a certified sanitizer (not NIST 800-88 compliant in a
    laboratory sense). It is a teaching demo.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from carver import sha256_file


FORBIDDEN_PREFIXES = (
    "/dev/",
    "\\\\.\\",
    "//./",
)


@dataclass
class ErasureResult:
    source_file: str
    working_copy: str
    method: str
    passes: int
    hash_before: str
    hash_after: str
    bytes_overwritten: int
    verified: bool
    message: str


def _is_forbidden(path: Path) -> bool:
    raw = str(path)
    if raw.startswith(FORBIDDEN_PREFIXES):
        return True
    # Refuse anything that looks like a raw disk image path used as evidence
    # only if it is a device node.
    try:
        return path.is_block_device() or path.is_char_device()
    except (OSError, NotImplementedError):
        return False


def demo_erase(
    src_file: str | Path,
    out_dir: str | Path,
    method: str = "clear",
) -> ErasureResult:
    """
    Copy `src_file` into `out_dir` and overwrite the COPY.

    method:
      clear — 1 pass of 0x00          (NIST "Clear"-style illustration)
      purge — 3 passes: 0x00, 0xFF, random   (simplified "Purge" illustration)
    """
    src_file = Path(src_file).resolve()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not src_file.is_file():
        raise FileNotFoundError(f"Not a regular file: {src_file}")
    if _is_forbidden(src_file):
        raise PermissionError(
            "Refusing to operate on a device node. Demo erasure only accepts regular files."
        )

    method = method.lower().strip()
    if method not in ("clear", "purge"):
        raise ValueError("method must be 'clear' or 'purge'")

    working = out_dir / f"erasure_copy_{src_file.name}"
    working.write_bytes(src_file.read_bytes())

    hash_before = sha256_file(working)
    size = working.stat().st_size
    chunk = 1024 * 1024

    if method == "clear":
        patterns = [b"\x00"]
    else:
        patterns = [b"\x00", b"\xff", None]  # None => cryptographic random

    with open(working, "r+b") as handle:
        for pattern in patterns:
            handle.seek(0)
            remaining = size
            while remaining > 0:
                n = min(chunk, remaining)
                blob = secrets.token_bytes(n) if pattern is None else (pattern * n)
                handle.write(blob)
                remaining -= n
            handle.flush()
            os.fsync(handle.fileno())

    hash_after = sha256_file(working)
    verified = hash_after != hash_before or size == 0

    return ErasureResult(
        source_file=str(src_file),
        working_copy=str(working),
        method=method,
        passes=len(patterns),
        hash_before=hash_before,
        hash_after=hash_after,
        bytes_overwritten=size,
        verified=verified,
        message=(
            f"Overwrote a working COPY with {len(patterns)} pass(es). "
            "Original file was not modified. Hash changed after overwrite "
            f"({verified})."
        ),
    )
