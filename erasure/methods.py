"""
NIST SP 800-88 Rev. 2 sanitization methods, selected by media type.

HDD  — user-addressable overwrite is a valid Purge analogue (DoD 5220.22-M).
SSD  — overwrite leaves 20–30% of NAND in overprovisioned blocks; Purge
       requires ATA SECURITY ERASE UNIT (or SANITIZE).
NVMe — Purge requires NVMe Format NVM with Secure Erase Settings (SES=1)
       or NVMe Sanitize.

Real firmware commands are NEVER issued against block devices unless
SECUREVAULT_ALLOW_REAL_ERASE=1 is set. The default path simulates the
command semantics on a working COPY of a regular file.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Callable, Iterable


ProgressFn = Callable[[str, float], None]


# DoD 5220.22-M ECE (7-pass): zeros, ones, random, zeros, ones, random, zeros.
DOD_5220_22M_7PASS: list[bytes | None] = [
    b"\x00",
    b"\xff",
    None,  # cryptographic random
    b"\x00",
    b"\xff",
    None,
    b"\x00",
]

NIST_CLEAR_1PASS: list[bytes | None] = [b"\x00"]


@dataclass(frozen=True)
class MethodSpec:
    id: str
    label: str
    nist_level: str  # clear | purge | destroy
    media: tuple[str, ...]
    passes: int
    firmware_command: str
    description: str
    covers_overprovisioning: bool
    verification_expectation: str  # zero | changed


METHOD_CATALOG: dict[str, MethodSpec] = {
    "dod_5220_22m_7pass": MethodSpec(
        id="dod_5220_22m_7pass",
        label="DoD 5220.22-M 7-pass overwrite",
        nist_level="purge",
        media=("HDD", "USB", "FILE"),
        passes=7,
        firmware_command="",
        description=(
            "Seven-pass overwrite of user-addressable LBAs: 0x00, 0xFF, random, "
            "0x00, 0xFF, random, 0x00. Appropriate Purge analogue for HDD."
        ),
        covers_overprovisioning=False,
        verification_expectation="zero",
    ),
    "ata_secure_erase": MethodSpec(
        id="ata_secure_erase",
        label="ATA Secure Erase (SECURITY ERASE UNIT)",
        nist_level="purge",
        media=("SSD",),
        passes=1,
        firmware_command="hdparm --user-master u --security-erase NULL {device}",
        description=(
            "Firmware-level block erase of every NAND page the controller maps, "
            "including overprovisioned and retired blocks. NIST 800-88 Rev. 2 "
            "Purge for ATA SSDs. Host overwrite is NOT sufficient."
        ),
        covers_overprovisioning=True,
        verification_expectation="zero",
    ),
    "nvme_format_nvm": MethodSpec(
        id="nvme_format_nvm",
        label="NVMe Format NVM (SES=1 User Data Erase)",
        nist_level="purge",
        media=("NVMe",),
        passes=1,
        firmware_command="nvme format {device} --ses=1 --force",
        description=(
            "NVMe Format NVM with Secure Erase Settings = 1 (User Data Erase). "
            "Controller erases all user namespaces including hidden capacity. "
            "NIST 800-88 Rev. 2 Purge for NVMe."
        ),
        covers_overprovisioning=True,
        verification_expectation="zero",
    ),
    "overwrite_clear": MethodSpec(
        id="overwrite_clear",
        label="NIST Clear — single-pass zero overwrite",
        nist_level="clear",
        media=("HDD", "SSD", "NVMe", "USB", "FILE"),
        passes=1,
        firmware_command="",
        description="Single-pass 0x00 overwrite of user-addressable space (NIST Clear).",
        covers_overprovisioning=False,
        verification_expectation="zero",
    ),
    "destroy": MethodSpec(
        id="destroy",
        label="NIST Destroy — physical destruction (out of band)",
        nist_level="destroy",
        media=("HDD", "SSD", "NVMe", "USB"),
        passes=0,
        firmware_command="",
        description="Physical destruction is logged, not performed, by this software.",
        covers_overprovisioning=True,
        verification_expectation="changed",
    ),
}


def spec_for(method_id: str) -> MethodSpec:
    if method_id not in METHOD_CATALOG:
        raise ValueError(f"Unknown sanitization method: {method_id}")
    return METHOD_CATALOG[method_id]


def select_method(drive_type: str, requested: str | None = None) -> MethodSpec:
    """Pick a NIST-aligned method. 'auto' / None follows media type."""
    requested = (requested or "auto").lower().strip()
    if requested in ("auto", "media_aware", "purge"):
        mapping = {
            "HDD": "dod_5220_22m_7pass",
            "SSD": "ata_secure_erase",
            "NVMe": "nvme_format_nvm",
            "USB": "dod_5220_22m_7pass",
            "FILE": "overwrite_clear",
        }
        return spec_for(mapping.get(drive_type, "overwrite_clear"))
    if requested in ("clear", "overwrite_clear"):
        return spec_for("overwrite_clear")
    if requested in ("destroy",):
        return spec_for("destroy")
    if requested in METHOD_CATALOG:
        return spec_for(requested)
    raise ValueError(f"Unknown sanitization method: {requested}")


def _pattern_blob(pattern: bytes | None, n: int) -> bytes:
    if pattern is None:
        return secrets.token_bytes(n)
    return pattern * n


def overwrite_passes(
    handle,
    size: int,
    patterns: Iterable[bytes | None],
    progress: ProgressFn | None = None,
    chunk_size: int = 1024 * 1024,
) -> int:
    """Apply overwrite patterns to an open r+b file. Returns pass count."""
    patterns = list(patterns)
    total = max(len(patterns), 1)
    for index, pattern in enumerate(patterns, start=1):
        if progress:
            label = "random" if pattern is None else f"0x{pattern[0]:02X}"
            progress(f"Pass {index}/{total} ({label})", (index - 1) / total)
        handle.seek(0)
        remaining = size
        while remaining > 0:
            n = min(chunk_size, remaining)
            handle.write(_pattern_blob(pattern, n))
            remaining -= n
        handle.flush()
        os.fsync(handle.fileno())
    if progress:
        progress(f"Completed {total} overwrite pass(es)", 1.0)
    return total


def simulate_firmware_erase(
    handle,
    size: int,
    progress: ProgressFn | None = None,
    chunk_size: int = 1024 * 1024,
) -> None:
    """
    Approximate ATA SE / NVMe Format: crypto scramble of user LBAs
    followed by a zero fill (what most drives return after a successful Purge).
    """
    if progress:
        progress("Firmware sanitize: cryptographic scramble of user LBAs", 0.15)
    overwrite_passes(handle, size, [None], progress=None, chunk_size=chunk_size)
    if progress:
        progress("Firmware sanitize: block-erase analogue (zeros)", 0.65)
    overwrite_passes(handle, size, [b"\x00"], progress=None, chunk_size=chunk_size)
    if progress:
        progress("Firmware sanitize complete", 1.0)
