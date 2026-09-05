"""
Media-aware sanitization engine.

Default mode is SAFE: we never open block devices. We copy a regular file
(or a virtual demo image) and apply the method that NIST 800-88 Rev. 2
would select for that media:

  HDD  -> DoD 5220.22-M 7-pass overwrite
  SSD  -> ATA Secure Erase analogue (firmware Purge)
  NVMe -> NVMe Format NVM analogue (SES=1)

Set SECUREVAULT_ALLOW_REAL_ERASE=1 to reveal the firmware command that
*would* be issued. Real ATA/NVMe commands are still refused against the
boot disk and against any path that is not an explicit allow-listed device.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from .device_detection import DriveInfo, detect_device
    from .methods import (
        DOD_5220_22M_7PASS,
        NIST_CLEAR_1PASS,
        MethodSpec,
        overwrite_passes,
        select_method,
        simulate_firmware_erase,
    )
    from .nist_compliance import generate_certificate
    from .verification import sha256_file, verify_sanitization
except ImportError:
    from device_detection import DriveInfo, detect_device
    from methods import (
        DOD_5220_22M_7PASS,
        NIST_CLEAR_1PASS,
        MethodSpec,
        overwrite_passes,
        select_method,
        simulate_firmware_erase,
    )
    from nist_compliance import generate_certificate
    from verification import sha256_file, verify_sanitization


def _chain_log(action: str, details: dict[str, Any]) -> None:
    """Best-effort write to the forensic blockchain (never fails sanitization)."""
    try:
        import sys

        audit_dir = Path(__file__).resolve().parent.parent / "audit"
        if str(audit_dir) not in sys.path:
            sys.path.insert(0, str(audit_dir))
        from blockchain_logger import log_event

        log_event(action, details)
    except Exception:
        return


ProgressFn = Callable[[str, float], None]

FORBIDDEN_PREFIXES = ("/dev/", "\\\\.\\", "//./")
SYSTEM_HINTS = (
    "/dev/sda",
    "/dev/nvme0n1",
    "/dev/disk0",
    "/dev/mmcblk0",
)


@dataclass
class SanitizeResult:
    job_id: str
    device: dict[str, Any]
    method: str
    technique: str
    nist_level: str
    passes_completed: int
    passes_total: int
    status: str
    started_at: str
    completed_at: str
    verification: dict[str, Any]
    certificate: dict[str, Any]
    details: dict[str, Any] = field(default_factory=dict)

    def to_job_dict(self) -> dict[str, Any]:
        return {
            "id": self.job_id,
            "device": self.device,
            "method": self.nist_level,
            "passes_completed": self.passes_completed,
            "passes_total": self.passes_total,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "verification": {
                "passed": self.verification.get("passed"),
                "sample_sectors_checked": self.verification.get("sample_sectors_checked"),
                "residual_data_found": self.verification.get("residual_data_found"),
            },
            "certificate_url": self.details.get("certificate_url"),
            "details": self.details,
            "technique": self.technique,
            "nist_level": self.nist_level,
            "drive_type": self.device.get("type"),
            "certificate": self.certificate,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_blockish(path: Path) -> bool:
    raw = str(path)
    if raw.startswith(FORBIDDEN_PREFIXES):
        return True
    try:
        return path.is_block_device() or path.is_char_device()
    except (OSError, NotImplementedError):
        return False


def _real_erase_permitted(path: Path) -> bool:
    if os.environ.get("SECUREVAULT_ALLOW_REAL_ERASE") != "1":
        return False
    raw = str(path)
    if any(raw == hint or raw.startswith(hint + "p") or raw.startswith(hint + "s") for hint in SYSTEM_HINTS):
        return False
    return True


def _copy_target(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def sanitize(
    device: str | Path,
    *,
    job_id: str,
    work_dir: str | Path,
    cert_dir: str | Path,
    method: str = "auto",
    operator_id: str = "local-operator",
    progress: ProgressFn | None = None,
) -> SanitizeResult:
    """
    Run media-aware sanitization on a COPY of `device` (regular file).

    Block devices are refused unless SECUREVAULT_ALLOW_REAL_ERASE=1, and
    even then this prototype still does not issue hdparm/nvme-cli — it
    records the command that a production appliance would run.
    """
    started = _utc_now()
    src = Path(device).expanduser()
    if not src.is_absolute():
        src = src.resolve()
    else:
        src = src.resolve()

    info: DriveInfo = detect_device(src)
    spec: MethodSpec = select_method(info.drive_type, method)
    _chain_log(
        "ERASURE_STARTED",
        {
            "job_id": job_id,
            "device": str(src),
            "drive_type": info.drive_type,
            "method": spec.id,
            "nist_level": spec.nist_level,
            "operator_id": operator_id,
        },
    )

    device_public = {
        "name": str(device),
        "type": info.drive_type if info.drive_type in ("HDD", "SSD", "NVMe", "USB") else "USB",
        "serial": info.serial,
        "capacity_bytes": info.capacity_bytes or (_file_size(src) if src.is_file() else 0),
    }

    if spec.id == "destroy":
        result = SanitizeResult(
            job_id=job_id,
            device=device_public,
            method=spec.nist_level,
            technique=spec.id,
            nist_level=spec.nist_level,
            passes_completed=0,
            passes_total=0,
            status="failed",
            started_at=started,
            completed_at=_utc_now(),
            verification={
                "passed": False,
                "sample_sectors_checked": 0,
                "residual_data_found": False,
            },
            certificate={},
            details={
                "error": "Physical destruction is out of scope for this software.",
                "operator_id": operator_id,
                "drive_type": info.drive_type,
                "technique": spec.id,
                "nist_level": spec.nist_level,
                "method_label": spec.label,
            },
        )
        return result

    if _is_blockish(src) and not _real_erase_permitted(src):
        raise PermissionError(
            "Refusing to operate on a block device. Use a virtual demo target "
            "(demo_hdd.bin / demo_ssd.bin / demo_nvme.bin) or a regular file. "
            "Firmware commands are simulated, never issued against /dev/*."
        )

    if not src.is_file():
        raise FileNotFoundError(f"Not a regular file: {src}")

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    working = work_dir / f"sanitized_{src.name}"
    if progress:
        progress("Creating working COPY (original is never modified)", 0.02)
    _copy_target(src, working)

    hash_before = sha256_file(working)
    size = working.stat().st_size
    simulated = True
    firmware = spec.firmware_command.format(device=info.path) if spec.firmware_command else ""

    with open(working, "r+b") as handle:
        if spec.id in ("ata_secure_erase", "nvme_format_nvm"):
            if progress:
                progress(f"Simulating {spec.label}", 0.1)
            simulate_firmware_erase(handle, size, progress=progress)
            passes = spec.passes
        elif spec.id == "dod_5220_22m_7pass":
            passes = overwrite_passes(handle, size, DOD_5220_22M_7PASS, progress=progress)
        else:
            passes = overwrite_passes(handle, size, NIST_CLEAR_1PASS, progress=progress)

    if progress:
        progress("Read-back verification", 0.92)
    verification = verify_sanitization(
        working,
        hash_before=hash_before,
        expected=spec.verification_expectation,
    )
    hash_after = verification.hash_after

    details = {
        "operator_id": operator_id,
        "device_path": str(src),
        "working_copy": str(working),
        "drive_type": info.drive_type,
        "model": info.model,
        "protocol": info.protocol,
        "technique": spec.id,
        "method_label": spec.label,
        "nist_level": spec.nist_level,
        "firmware_command": firmware,
        "covers_overprovisioning": spec.covers_overprovisioning,
        "overprovisioning_risk": info.overprovisioning_risk,
        "simulated": simulated,
        "hash_before": hash_before,
        "hash_after": hash_after,
        "residual_entropy": verification.residual_entropy,
        "bytes_overwritten": size,
        "message": spec.description,
        "detection_notes": info.notes,
    }

    job_stub = {
        "id": job_id,
        "device": device_public,
        "method": spec.nist_level,
        "passes_total": passes,
        "started_at": started,
        "completed_at": _utc_now(),
        "verification": verification.to_dict(),
        "details": details,
        "operator_id": operator_id,
    }
    certificate = generate_certificate(job_stub, cert_dir)
    details["certificate_url"] = f"/erasure/compliance/{job_id}/file"
    details["certificate_path"] = certificate.get("pdf_path")
    details["certificate_json"] = certificate.get("json_path")
    details["certificate_sha256"] = certificate.get("certificate_sha256")

    status = "completed" if verification.passed else "failed"
    _chain_log(
        "ERASURE_COMPLETED",
        {
            "job_id": job_id,
            "drive_type": info.drive_type,
            "technique": spec.id,
            "nist_level": spec.nist_level,
            "status": status,
            "hash_before": hash_before,
            "hash_after": hash_after,
        },
    )
    _chain_log(
        "ERASURE_VERIFIED",
        {
            "job_id": job_id,
            "passed": bool(verification.passed),
            "sample_sectors_checked": verification.sample_sectors_checked,
            "residual_data_found": bool(verification.residual_data_found),
        },
    )
    return SanitizeResult(
        job_id=job_id,
        device=device_public,
        method=spec.nist_level,
        technique=spec.id,
        nist_level=spec.nist_level,
        passes_completed=passes,
        passes_total=passes,
        status=status,
        started_at=started,
        completed_at=job_stub["completed_at"],
        verification=verification.to_dict(),
        certificate=certificate,
        details=details,
    )


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def capabilities_payload(info: DriveInfo) -> dict[str, Any]:
    return info.to_dict()
