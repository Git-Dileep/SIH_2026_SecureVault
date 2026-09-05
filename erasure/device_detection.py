"""
Drive type detection for media-aware sanitization.

SSDs and NVMe devices use wear-leveling and overprovisioned NAND that
OS-visible overwrites never touch (typically 20–30% of physical flash).
NIST SP 800-88 Rev. 2 therefore requires firmware-level Purge commands
for those media, not HDD-style multi-pass overwrite.

Detection order:
  1. Linux sysfs: /sys/block/{dev}/queue/rotational
  2. NVMe path heuristic: device.startswith("/dev/nvme")
  3. macOS diskutil (Solid State / Protocol)
  4. Path / filename hints for demo images (hdd, ssd, nvme)
  5. Regular files are treated as FILE targets (copy-only demo)
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


DriveType = str  # HDD | SSD | NVMe | USB | FILE | UNKNOWN


@dataclass
class DriveCapabilities:
    overwrite: bool = True
    ata_secure_erase: bool = False
    nvme_format: bool = False
    trim: bool = False
    crypto_erase: bool = False


@dataclass
class DriveInfo:
    path: str
    drive_type: DriveType
    rotational: bool | None
    serial: str
    model: str
    capacity_bytes: int
    protocol: str
    capabilities: DriveCapabilities
    overprovisioning_risk: bool
    recommended_method: str
    recommended_nist_level: str
    nist_purge_command: str
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = asdict(self.capabilities)
        return payload


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _normalize_device(device: str | Path) -> str:
    raw = str(device).strip()
    if raw.startswith("/dev/"):
        return raw
    path = Path(raw)
    try:
        return str(path.expanduser().resolve())
    except OSError:
        return raw


def _sys_block_name(device: str) -> str | None:
    """
    /dev/sda -> sda, /dev/sda1 -> sda, /dev/nvme0n1 -> nvme0n1,
    /dev/nvme0n1p1 -> nvme0n1
    """
    if not device.startswith("/dev/"):
        return None
    name = device[5:]
    if name.startswith("nvme"):
        match = re.match(r"(nvme\d+n\d+)", name)
        return match.group(1) if match else name
    match = re.match(r"([a-z]+)", name)
    return match.group(1) if match else name


def _read_sys(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _file_size(path: str) -> int:
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


def _serial_from_name(name: str) -> str:
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:16].upper()


# ---------------------------------------------------------------------------
# Linux sysfs
# ---------------------------------------------------------------------------

def _detect_linux(device: str) -> DriveInfo | None:
    block = _sys_block_name(device)
    if not block:
        return None
    sys_dev = Path("/sys/block") / block
    if not sys_dev.is_dir():
        return None

    rotational_raw = _read_sys(sys_dev / "queue" / "rotational")
    rotational = None if rotational_raw is None else rotational_raw == "1"
    size_sectors = _read_sys(sys_dev / "size")
    # sysfs size is in 512-byte sectors
    capacity = int(size_sectors) * 512 if size_sectors and size_sectors.isdigit() else 0
    model = (
        _read_sys(sys_dev / "device" / "model")
        or _read_sys(sys_dev / "device" / "name")
        or block
    )
    serial = (
        _read_sys(sys_dev / "device" / "serial")
        or _read_sys(sys_dev / "device" / "wwid")
        or _serial_from_name(block)
    )

    is_nvme = device.startswith("/dev/nvme") or block.startswith("nvme")
    if is_nvme:
        drive_type: DriveType = "NVMe"
        protocol = "NVMe"
    elif rotational is False:
        drive_type = "SSD"
        protocol = "SATA"
    elif rotational is True:
        drive_type = "HDD"
        protocol = "SATA"
    else:
        drive_type = "UNKNOWN"
        protocol = "unknown"

    removable = _read_sys(sys_dev / "removable")
    if removable == "1" and drive_type in ("HDD", "SSD", "UNKNOWN"):
        drive_type = "USB"
        protocol = "USB"

    return _finalize(
        path=device,
        drive_type=drive_type,
        rotational=rotational,
        serial=str(serial),
        model=str(model).strip(),
        capacity_bytes=capacity,
        protocol=protocol,
        notes="Detected via Linux sysfs /sys/block.",
    )


# ---------------------------------------------------------------------------
# macOS diskutil
# ---------------------------------------------------------------------------

def _detect_macos(device: str) -> DriveInfo | None:
    if platform.system() != "Darwin":
        return None
    disk = device
    if disk.startswith("/dev/"):
        disk = disk[5:]
    if not re.match(r"disk\d+", disk):
        return None
    try:
        proc = subprocess.run(
            ["diskutil", "info", "-plist", disk],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout:
        # Fall back to human-readable output
        try:
            proc = subprocess.run(
                ["diskutil", "info", disk],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        return _parse_diskutil_text(device, proc.stdout)
    return _parse_diskutil_text(device, proc.stdout)


def _parse_diskutil_text(device: str, text: str) -> DriveInfo:
    def field(label: str) -> str | None:
        match = re.search(rf"{re.escape(label)}:\s*(.+)", text)
        return match.group(1).strip() if match else None

    solid = (field("Solid State") or "").lower()
    protocol = field("Protocol") or field("Device Protocol") or "unknown"
    media = field("Media Type") or ""
    serial = field("Disk / Partition UUID") or field("Volume UUID") or _serial_from_name(device)
    model = field("Device / Media Name") or field("Media Name") or device
    size_line = field("Disk Size") or field("Volume Total Space") or "0"
    capacity = 0
    match = re.search(r"\((\d+)\s*Bytes\)", size_line, flags=re.I)
    if match:
        capacity = int(match.group(1))

    proto_l = protocol.lower()
    is_nvme = "nvme" in proto_l or "pci-express" in proto_l or "apple fabric" in proto_l
    if is_nvme or device.startswith("/dev/nvme"):
        drive_type: DriveType = "NVMe"
        rotational = False
        protocol = "NVMe"
    elif solid.startswith("yes") or "ssd" in media.lower():
        drive_type = "SSD"
        rotational = False
        protocol = protocol or "SATA"
    elif solid.startswith("no") or "rotational" in media.lower():
        drive_type = "HDD"
        rotational = True
        protocol = protocol or "SATA"
    else:
        drive_type = "UNKNOWN"
        rotational = None

    return _finalize(
        path=device if device.startswith("/dev/") else f"/dev/{device}",
        drive_type=drive_type,
        rotational=rotational,
        serial=str(serial),
        model=str(model),
        capacity_bytes=capacity,
        protocol=protocol,
        notes="Detected via macOS diskutil.",
    )


# ---------------------------------------------------------------------------
# Path heuristics (demo images, virtual devices, Windows-style names)
# ---------------------------------------------------------------------------

def _detect_heuristic(device: str) -> DriveInfo:
    lower = device.lower()
    name = Path(device).name.lower()
    rotational: bool | None
    notes = "Inferred from device path / filename (no sysfs node)."

    if device.startswith("/dev/nvme") or "nvme" in lower:
        drive_type: DriveType = "NVMe"
        rotational = False
        protocol = "NVMe"
        notes = "NVMe detected from device path prefix /dev/nvme*."
    elif "ssd" in lower or name.startswith("demo_ssd"):
        drive_type = "SSD"
        rotational = False
        protocol = "SATA"
    elif "hdd" in lower or "rotational" in lower or name.startswith("demo_hdd"):
        drive_type = "HDD"
        rotational = True
        protocol = "SATA"
    elif any(token in lower for token in ("usb", "flash", "thumb", "removable")):
        drive_type = "USB"
        rotational = False
        protocol = "USB"
    elif device.startswith("/dev/"):
        drive_type = "UNKNOWN"
        rotational = None
        protocol = "unknown"
    else:
        drive_type = "FILE"
        rotational = None
        protocol = "file"
        notes = "Regular file target. Sanitization runs on a working COPY only."

    serial = _serial_from_name(Path(device).name)
    model = Path(device).name or device
    capacity = _file_size(device) if drive_type == "FILE" or Path(device).is_file() else 0

    sidecar = Path(device).with_suffix(Path(device).suffix + ".meta.json")
    extra: dict[str, Any] = {}
    if sidecar.is_file():
        try:
            extra = json.loads(sidecar.read_text(encoding="utf-8"))
            drive_type = str(extra.get("drive_type") or drive_type)
            serial = str(extra.get("serial") or serial)
            model = str(extra.get("model") or model)
            if extra.get("capacity_bytes"):
                capacity = int(extra["capacity_bytes"])
            notes = str(extra.get("notes") or notes)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            extra = {}

    info = _finalize(
        path=device,
        drive_type=drive_type,
        rotational=rotational,
        serial=serial,
        model=model,
        capacity_bytes=capacity,
        protocol=protocol,
        notes=notes,
    )
    info.extra.update(extra)
    return info


def _finalize(
    *,
    path: str,
    drive_type: DriveType,
    rotational: bool | None,
    serial: str,
    model: str,
    capacity_bytes: int,
    protocol: str,
    notes: str,
) -> DriveInfo:
    caps = DriveCapabilities()
    if drive_type == "HDD":
        caps = DriveCapabilities(overwrite=True, ata_secure_erase=True)
        method = "dod_5220_22m_7pass"
        nist = "purge"
        command = "DoD 5220.22-M 7-pass overwrite (user-addressable LBAs)"
        overprov = False
    elif drive_type == "SSD":
        caps = DriveCapabilities(
            overwrite=True,
            ata_secure_erase=True,
            trim=True,
            crypto_erase=True,
        )
        method = "ata_secure_erase"
        nist = "purge"
        command = "hdparm --user-master u --security-erase NULL <device>"
        overprov = True
    elif drive_type == "NVMe":
        caps = DriveCapabilities(
            overwrite=True,
            nvme_format=True,
            trim=True,
            crypto_erase=True,
        )
        method = "nvme_format_nvm"
        nist = "purge"
        command = "nvme format <device> --ses=1 --force"
        overprov = True
    elif drive_type == "USB":
        caps = DriveCapabilities(overwrite=True)
        method = "dod_5220_22m_7pass"
        nist = "clear"
        command = "DoD 5220.22-M 7-pass overwrite (flash; firmware sanitize if advertised)"
        overprov = True
    else:
        caps = DriveCapabilities(overwrite=True)
        method = "overwrite_clear"
        nist = "clear"
        command = "Single-pass overwrite of a working copy (demo / file target)"
        overprov = False

    return DriveInfo(
        path=path,
        drive_type=drive_type,
        rotational=rotational,
        serial=serial,
        model=model,
        capacity_bytes=capacity_bytes,
        protocol=protocol,
        capabilities=caps,
        overprovisioning_risk=overprov,
        recommended_method=method,
        recommended_nist_level=nist,
        nist_purge_command=command,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_device(device: str | Path) -> DriveInfo:
    """Return drive type + capabilities for a device path or demo file."""
    path = _normalize_device(device)
    if path.startswith("/dev/nvme"):
        linux = _detect_linux(path)
        if linux:
            linux.drive_type = "NVMe"
            linux.protocol = "NVMe"
            linux.rotational = False
            return _finalize(
                path=linux.path,
                drive_type="NVMe",
                rotational=False,
                serial=linux.serial,
                model=linux.model,
                capacity_bytes=linux.capacity_bytes,
                protocol="NVMe",
                notes=linux.notes or "NVMe path prefix /dev/nvme*.",
            )
        return _detect_heuristic(path)

    linux = _detect_linux(path) if path.startswith("/dev/") else None
    if linux:
        return linux
    macos = _detect_macos(path) if path.startswith("/dev/") or re.match(r"disk\d+", str(device)) else None
    if macos:
        return macos
    return _detect_heuristic(path)


def list_linux_block_devices() -> list[DriveInfo]:
    sys_block = Path("/sys/block")
    if not sys_block.is_dir():
        return []
    found: list[DriveInfo] = []
    for entry in sorted(sys_block.iterdir()):
        name = entry.name
        if name.startswith(("loop", "ram", "dm-", "sr")):
            continue
        found.append(detect_device(f"/dev/{name}"))
    return found


def create_demo_targets(root: str | Path) -> list[DriveInfo]:
    """
    Create small virtual HDD / SSD / NVMe images so the UI can demonstrate
    media-aware sanitization without touching real disks.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    specs = [
        {
            "name": "demo_hdd.bin",
            "drive_type": "HDD",
            "model": "SecureVault Virtual HDD",
            "serial": "SV-HDD-DEMO-001",
            "capacity_bytes": 2 * 1024 * 1024,
            "notes": "Virtual rotational disk for DoD 5220.22-M 7-pass demo.",
        },
        {
            "name": "demo_ssd.bin",
            "drive_type": "SSD",
            "model": "SecureVault Virtual SATA SSD",
            "serial": "SV-SSD-DEMO-001",
            "capacity_bytes": 2 * 1024 * 1024,
            "notes": "Virtual SSD. Overwrite cannot reach overprovisioned NAND; ATA Secure Erase is required for Purge.",
        },
        {
            "name": "demo_nvme.bin",
            "drive_type": "NVMe",
            "model": "SecureVault Virtual NVMe",
            "serial": "SV-NVME-DEMO-001",
            "capacity_bytes": 2 * 1024 * 1024,
            "notes": "Virtual NVMe. NIST 800-88 Rev. 2 Purge = NVMe Format NVM (SES=1).",
        },
    ]
    results: list[DriveInfo] = []
    payload = os.urandom(64 * 1024)
    for spec in specs:
        path = root / spec["name"]
        if not path.exists() or path.stat().st_size == 0:
            # Repeat a recognisable pattern so verification can prove it vanished.
            blob = (payload * ((spec["capacity_bytes"] // len(payload)) + 1))[: spec["capacity_bytes"]]
            path.write_bytes(blob)
        meta = {k: v for k, v in spec.items() if k != "name"}
        meta["path"] = str(path)
        (root / f"{spec['name']}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        results.append(detect_device(path))
    return results


def detect_drive(device: str | Path) -> DriveInfo:
    """Alias used by the sanitizer / API layer."""
    return detect_device(device)
