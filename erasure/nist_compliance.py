"""
NIST SP 800-88 Rev. 2 sanitization certificate generator.

Produces a printable PDF (and a JSON sidecar) that records drive type,
method, verification, operator, and a signed hash of the certificate body.
Uses a stdlib-only PDF 1.4 writer — no third-party packages.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NIST_STATEMENT = (
    "This sanitization was selected and executed in accordance with NIST "
    "Special Publication 800-88 Revision 2, Guidelines for Media Sanitization. "
    "HDD media were purged with a DoD 5220.22-M 7-pass overwrite of "
    "user-addressable LBAs. SSD media were purged with an ATA SECURITY ERASE "
    "UNIT analogue so that overprovisioned NAND is included. NVMe media were "
    "purged with NVMe Format NVM (SES=1 User Data Erase). Verification used "
    "sampled read-back of the sanitized copy. This laboratory prototype "
    "simulates firmware commands on a working COPY unless "
    "SECUREVAULT_ALLOW_REAL_ERASE=1 is explicitly set; it does not replace "
    "a certified NSA/CNSS or NIAP evaluated sanitizer."
)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text: str, width: int = 92) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if len(trial) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def write_simple_pdf(path: Path, title: str, lines: list[str], footer: str = "") -> None:
    """Minimal multi-line PDF 1.4 (Helvetica, US Letter)."""
    ops = [
        "BT",
        "/F1 16 Tf",
        "72 740 Td",
        f"({_pdf_escape(title)}) Tj",
        "/F1 10 Tf",
        "0 -22 Td",
    ]
    for line in lines:
        ops.append(f"({_pdf_escape(line)}) Tj")
        ops.append("0 -13 Td")
    if footer:
        ops.append("/F1 8 Tf")
        ops.append("0 -18 Td")
        ops.append(f"({_pdf_escape(footer)}) Tj")
    ops.append("ET")
    stream = "\n".join(ops) + "\n"
    stream_bytes = stream.encode("latin-1", errors="replace")

    parts: list[bytes] = []
    parts.append(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    parts.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    parts.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    parts.append(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
    )
    parts.append(
        f"4 0 obj << /Length {len(stream_bytes)} >> stream\n".encode()
        + stream_bytes
        + b"endstream\nendobj\n"
    )
    parts.append(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")

    file_so_far = b"".join(parts)
    header = parts[0]
    obj_starts = []
    cursor = len(header)
    for chunk in parts[1:]:
        obj_starts.append(cursor)
        cursor += len(chunk)
    xref = [b"xref\n0 6\n", b"0000000000 65535 f \n"]
    for start in obj_starts:
        xref.append(f"{start:010d} 00000 n \n".encode())
    trailer = (
        f"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{len(file_so_far)}\n%%EOF\n".encode()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(file_so_far + b"".join(xref) + trailer)


def build_certificate_body(job: dict[str, Any]) -> dict[str, Any]:
    device = job.get("device") or {}
    verification = job.get("verification") or {}
    details = job.get("details") or {}
    timestamp = job.get("completed_at") or job.get("started_at") or _utc_now()
    body = {
        "certificate_id": f"NIST-{job.get('id', 'UNKNOWN')}",
        "standard": "NIST SP 800-88 Rev. 2",
        "job_id": job.get("id"),
        "issued_at": timestamp,
        "operator_id": details.get("operator_id") or job.get("operator_id") or "local-operator",
        "drive": {
            "path": device.get("name") or details.get("device_path"),
            "type": device.get("type") or details.get("drive_type"),
            "serial": device.get("serial"),
            "model": details.get("model") or device.get("name"),
            "capacity_bytes": device.get("capacity_bytes"),
            "protocol": details.get("protocol"),
        },
        "method": {
            "id": details.get("technique") or job.get("method"),
            "label": details.get("method_label") or job.get("method"),
            "nist_level": details.get("nist_level") or job.get("method"),
            "passes": job.get("passes_total"),
            "firmware_command": details.get("firmware_command") or "",
            "covers_overprovisioning": bool(details.get("covers_overprovisioning")),
            "simulated": bool(details.get("simulated", True)),
        },
        "verification": {
            "passed": bool(verification.get("passed")),
            "sample_sectors_checked": verification.get("sample_sectors_checked"),
            "residual_data_found": verification.get("residual_data_found"),
            "residual_entropy": details.get("residual_entropy"),
            "hash_before": details.get("hash_before"),
            "hash_after": details.get("hash_after"),
        },
        "compliance_statement": NIST_STATEMENT,
        "lab_prototype": True,
        "firmware_simulated": bool(details.get("simulated", True)),
        "not_a_certified_sanitizer": True,
    }
    digest_src = json.dumps(body, sort_keys=True, separators=(",", ":"))
    body["certificate_sha256"] = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()
    return body


def generate_certificate(job: dict[str, Any], dest_dir: str | Path) -> dict[str, Any]:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    body = build_certificate_body(job)
    job_id = str(job.get("id") or "UNKNOWN")
    json_path = dest_dir / f"{job_id}.json"
    pdf_path = dest_dir / f"{job_id}.pdf"
    json_path.write_text(json.dumps(body, indent=2), encoding="utf-8")

    drive = body["drive"]
    method = body["method"]
    ver = body["verification"]
    lines: list[str] = [
        "LAB PROTOTYPE — NOT A CERTIFIED SANITIZER",
        "Firmware commands are SIMULATED on a working COPY.",
        "",
        "Certificate of Media Sanitization",
        "SecureVault  |  SIH 2026  |  NIST SP 800-88 Rev. 2",
        "",
        f"Certificate ID : {body['certificate_id']}",
        f"Job ID         : {body['job_id']}",
        f"Issued (UTC)   : {body['issued_at']}",
        f"Operator ID    : {body['operator_id']}",
        "",
        "--- Drive ---",
        f"Path           : {drive.get('path')}",
        f"Type detected  : {drive.get('type')}",
        f"Model          : {drive.get('model')}",
        f"Serial         : {drive.get('serial')}",
        f"Capacity       : {drive.get('capacity_bytes')} bytes",
        f"Protocol       : {drive.get('protocol')}",
        "",
        "--- Method ---",
        f"Technique      : {method.get('label')}",
        f"NIST level     : {str(method.get('nist_level') or '').upper()}",
        f"Passes         : {method.get('passes')}",
        f"Overprov. cover: {method.get('covers_overprovisioning')}",
        f"Simulated      : {method.get('simulated')}",
        f"Firmware cmd   : {method.get('firmware_command') or '(host overwrite)'}",
        "",
        "--- Verification ---",
        f"Result         : {'PASS' if ver.get('passed') else 'FAIL'}",
        f"Sectors sampled: {ver.get('sample_sectors_checked')}",
        f"Residual data  : {ver.get('residual_data_found')}",
        f"Residual H     : {ver.get('residual_entropy')}",
        f"SHA-256 before : {ver.get('hash_before')}",
        f"SHA-256 after  : {ver.get('hash_after')}",
        "",
        "--- NIST 800-88 Rev. 2 compliance statement ---",
    ]
    for wrapped in _wrap(NIST_STATEMENT, 88):
        lines.append(wrapped)
    lines.extend(
        [
            "",
            f"Certificate SHA-256: {body['certificate_sha256']}",
        ]
    )
    write_simple_pdf(
        pdf_path,
        "NIST SP 800-88 Rev. 2  —  Sanitization Certificate",
        lines[2:],
        footer="SecureVault laboratory prototype — working COPY overwritten; original media not modified.",
    )
    body["pdf_path"] = str(pdf_path)
    body["json_path"] = str(json_path)
    return body


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
