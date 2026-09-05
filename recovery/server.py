#!/usr/bin/env python3
"""
server.py — Local HTTP API that connects the React UI to ForensicRecover.

The CLI, Tkinter GUI, and this API all call the same functions:
  carver.carve_image, report.write_reports, erasure.demo_erase

    python3 server.py
    python3 server.py --port 8000

No third-party packages. Evidence images are opened read-only.
Erasure still only overwrites a COPY of a regular file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import shutil
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from carver import TOOL_NAME, TOOL_VERSION, carve_image, utc_now_iso
import delete_recover_demo as delete_demo
from erasure import _is_forbidden, demo_erase
from generate_test_image import make_pdf
from lab_runtime import (
    AUTH_REQUIRED,
    BIND_HOST,
    FIRMWARE_SIMULATED,
    MODE,
    cors_origin_allowed,
    issue_session,
    log_event,
    new_request_id,
    parse_bearer,
    resolve_session,
    revoke_session,
)
from report import write_reports
import users

# Top-level /erasure and /audit packages share the name `erasure` with this
# directory's demo module, so they are loaded from the repo root via sys.path.
_PARENT = Path(__file__).resolve().parent.parent
for _pkg_dir in (_PARENT / "erasure", _PARENT / "audit", Path(__file__).resolve().parent / "ai"):
    _s = str(_pkg_dir)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from device_detection import create_demo_targets, detect_device  # noqa: E402
from sanitizer import sanitize as media_sanitize  # noqa: E402
from blockchain import AuditBlockchain  # noqa: E402
from blockchain_logger import get_logger as get_ledger  # noqa: E402
from verifier import verify_chain  # noqa: E402
from fragment_classifier import accuracy_report, classify_fragment, ensure_model  # noqa: E402
from actor_context import get_actor, set_actor  # noqa: E402


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / "workspace"
STATE_PATH = WORKSPACE / "state.json"
EVIDENCE_DIR = WORKSPACE / "evidence"
RECOVERED_DIR = WORKSPACE / "recovered"
ERASURE_DIR = WORKSPACE / "erasure"
CERT_DIR = WORKSPACE / "certificates"
DEMO_IMAGE = ROOT / "testdata" / "synthetic_disk.img"
CHAIN_PATH = WORKSPACE / "blockchain.json"
TARGETS_DIR = WORKSPACE / "targets"
ERASURE_UPLOADS = WORKSPACE / "erasure_uploads"
LEDGER_PATH = ROOT.parent / "audit" / "audit_chain.json"

ACTION_TO_LEDGER = {
    "evidence.import": "EVIDENCE_IMPORTED",
    "recovery.start": "RECOVERY_STARTED",
    "recovery.complete": "RECOVERY_COMPLETED",
    "erasure.start": "ERASURE_STARTED",
    "erasure.complete": "ERASURE_COMPLETED",
    "erasure.verify": "ERASURE_VERIFIED",
    "certificate.generate": "CERTIFICATE_GENERATED",
    "audit.export": "CHAIN_ANCHORED",
    "auth.login": "USER_LOGIN",
    "auth.logout": "USER_LOGOUT",
    "auth.register": "USER_REGISTERED",
    "file.export": "FILE_EXPORTED",
    "ai.classify": "AI_CLASSIFIED",
}

HOST = BIND_HOST
DEFAULT_PORT = 8000
ACTOR = "local-operator"
UPLOAD_LIMIT = 512 * 1024 * 1024

CONFIDENCE_SCORE = {"high": 0.92, "medium": 0.64, "low": 0.28}

STATE_LOCK = threading.Lock()
_state: dict = {}
_chain: AuditBlockchain | None = None
_ledger = None


def _empty_state() -> dict:
    return {
        "counters": {"EV": 0, "RS": 0, "SAN": 0, "AL": 0},
        "evidence": [],
        "sessions": [],
        "erasure_jobs": [],
        "audit": [],
        "actor": ACTOR,
    }


def _ensure_dirs() -> None:
    for path in (WORKSPACE, EVIDENCE_DIR, RECOVERED_DIR, ERASURE_DIR, CERT_DIR, TARGETS_DIR, ERASURE_UPLOADS):
        path.mkdir(parents=True, exist_ok=True)
    create_demo_targets(TARGETS_DIR)


def _get_chain() -> AuditBlockchain:
    global _chain
    if _chain is None:
        _chain = AuditBlockchain(CHAIN_PATH)
    return _chain


def _get_ledger():
    global _ledger
    if _ledger is None:
        _ledger = get_ledger(LEDGER_PATH)
    return _ledger


def _ledger_public() -> dict:
    ledger = _get_ledger()
    blocks = ledger.get_chain()
    report = verify_chain(blocks)
    mapped = []
    for block in reversed(blocks):
        details = block.get("details") or {}
        mapped.append(
            {
                "index": block["index"],
                "timestamp": block["timestamp"],
                "hash": block["hash"],
                "prev_hash": block["previous_hash"],
                "previous_hash": block["previous_hash"],
                "merkle_root": block["details_hash"],
                "action": block["action"],
                "details_hash": block["details_hash"],
                "details": details,
                "entries": [
                    {
                        "id": f"BLK-{block['index']}",
                        "timestamp": block["timestamp"],
                        "actor": details.get("actor") or details.get("username") or details.get("operator_id") or ACTOR,
                        "action": block["action"],
                        "target": str(
                            details.get("job_id")
                            or details.get("filename")
                            or details.get("target")
                            or block["action"]
                        ),
                        "outcome": details.get("outcome") or "success",
                        "details": details,
                        "prev_hash": block["previous_hash"],
                        "entry_hash": block["hash"],
                    }
                ],
            }
        )
    return {
        "chain": [_annotate_block(b) for b in blocks],
        "blocks": mapped,
        "height": ledger.height(),
        "tip": ledger.tip()["hash"] if blocks else "",
        "valid": report["valid"],
        "status": report["status"],
        "anchors": [],
        "verify": report,
    }


_PLAIN = {
    "GENESIS": "Audit ledger started — empty chain of custody",
    "USER_LOGIN": "Operator signed in",
    "USER_LOGOUT": "Operator signed out",
    "USER_REGISTERED": "New operator account created",
    "DEMO_STAGE": "Exhibits planted on the suspect disk image",
    "DEMO_DELETE": "Folder names deleted; directory table wiped; bytes still on disk",
    "DEMO_UPLOAD": "Operator added a file to the demo",
    "DEMO_RESET": "Delete-recover demo reset",
    "EVIDENCE_IMPORTED": "Evidence image imported and hashed",
    "RECOVERY_STARTED": "File carving started on a raw image",
    "RECOVERY_COMPLETED": "Carving finished",
    "FILE_EXTRACTED": "A file was carved from unallocated space",
    "ERASURE_STARTED": "Sanitization started (working copy)",
    "ERASURE_COMPLETED": "Sanitization finished",
    "ERASURE_VERIFIED": "Read-back verification recorded",
    "CERTIFICATE_GENERATED": "NIST prototype certificate issued",
    "AI_CLASSIFIED": "A 512-byte fragment was classified",
    "FILE_EXPORTED": "A recovered file was downloaded",
    "CHAIN_ANCHORED": "Tip hash recorded as an external anchor",
}


def _current_actor() -> str:
    actor = get_actor()
    if actor and actor != "anonymous":
        return actor
    return str(_state.get("actor") or ACTOR)


def _plain_action(action: str, details: dict | None) -> str:
    details = details or {}
    who = str(details.get("actor") or details.get("username") or details.get("operator_id") or "")
    name = str(details.get("filename") or details.get("original_filename") or "")
    if action == "USER_LOGIN" and who:
        return f"{who} signed in"
    if action == "USER_LOGOUT" and who:
        return f"{who} signed out"
    if action == "USER_REGISTERED" and who:
        return f"New operator account created for {who}"
    if action == "FILE_EXTRACTED" and name:
        base = f"Recovered {name} from unallocated space"
    elif action in ("DEMO_UPLOAD",) and name:
        base = f"Queued {name} for the suspect image"
    elif action == "AI_CLASSIFIED":
        base = f"Classified fragment as {details.get('target') or details.get('file_type') or 'unknown'}"
    else:
        base = _PLAIN.get(action, action.replace("_", " ").title())
    if who and action not in ("GENESIS", "USER_LOGIN", "USER_LOGOUT", "USER_REGISTERED"):
        return f"{base} — by {who}"
    return base


def _annotate_block(block: dict) -> dict:
    out = dict(block)
    details = block.get("details") or {}
    out["plain"] = _plain_action(str(block.get("action") or ""), details)
    out["actor"] = details.get("actor") or details.get("username") or details.get("operator_id")
    return out


def _custody_receipt() -> dict:
    ledger = _get_ledger()
    blocks = [_annotate_block(b) for b in ledger.get_chain()]
    report = verify_chain(ledger.get_chain())
    events = [
        {
            "index": b["index"],
            "timestamp": b["timestamp"],
            "action": b["action"],
            "plain": b["plain"],
            "hash": b["hash"],
            "actor": (b.get("details") or {}).get("actor") or b.get("actor"),
            "details": b.get("details") or {},
        }
        for b in blocks
    ]
    return {
        "title": "SecureVault chain-of-custody receipt",
        "generated_at": utc_now_iso(),
        "operator": _current_actor(),
        "status": report.get("status"),
        "valid": report.get("valid"),
        "height": ledger.height(),
        "tip": ledger.tip()["hash"] if blocks else "",
        "blocks_checked": report.get("blocks_checked"),
        "note": (
            "Each block hashes the previous block. If this JSON and the live chain "
            "still verify as VALID, the log was not silently rewritten."
        ),
        "events": events,
    }


def _load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            base = _empty_state()
            base.update(data)
            return base
        except (OSError, json.JSONDecodeError):
            pass
    return _empty_state()


def _save_state() -> None:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(_state, indent=2), encoding="utf-8")


def _next_id(prefix: str) -> str:
    _state["counters"][prefix] = int(_state["counters"].get(prefix, 0)) + 1
    return f"{prefix}-{_state['counters'][prefix]:03d}"


def _append_audit(action: str, target: str, outcome: str = "success", details: dict | None = None) -> dict:
    prev = "0" * 64
    if _state["audit"]:
        prev = _state["audit"][-1]["entry_hash"]
    entry_id = _next_id("AL")
    timestamp = utc_now_iso()
    actor = _current_actor()
    payload = {
        "id": entry_id,
        "timestamp": timestamp,
        "actor": actor,
        "action": action,
        "target": target,
        "outcome": outcome,
        "details": {
            **(details or {}),
            "actor": actor,
            "logged_at": timestamp,
        },
        "prev_hash": prev,
    }
    digest_src = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["entry_hash"] = hashlib.sha256((prev + digest_src).encode("utf-8")).hexdigest()
    try:
        ledger_action = ACTION_TO_LEDGER.get(action, action.upper().replace(".", "_"))
        block = _get_ledger().log(
            ledger_action,
            {
                "target": target,
                "outcome": outcome,
                **(details or {}),
                "actor": actor,
                "logged_at": timestamp,
            },
        )
        payload["block_index"] = block["index"]
        payload["block_hash"] = block["hash"]
        payload["merkle_root"] = block["details_hash"]
        payload["ledger_action"] = ledger_action
    except Exception:
        payload.setdefault("block_index", None)
        try:
            block = _get_chain().append_entry(payload)
            payload["block_index"] = block["index"]
            payload["block_hash"] = block["hash"]
            payload["merkle_root"] = block["merkle_root"]
        except Exception:
            pass
    _state["audit"].append(payload)
    return payload


def _hash_file(path: Path) -> dict:
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
    return {"md5": md5.hexdigest(), "sha1": sha1.hexdigest(), "sha256": sha256.hexdigest()}


def _guess_format(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".e01"):
        return "E01"
    if lower.endswith(".aff4"):
        return "AFF4"
    return "raw"


def _public_evidence(item: dict) -> dict:
    return {
        "id": item["id"],
        "filename": item["filename"],
        "format": item["format"],
        "size_bytes": item["size_bytes"],
        "import_timestamp": item["import_timestamp"],
        "hashes": item["hashes"],
        "status": item["status"],
        "metadata": item.get("metadata") or {},
    }


def _file_to_frontend(rec: dict, evidence_id: str, recovered_at: str) -> dict:
    label = rec.get("confidence") or "medium"
    if label not in CONFIDENCE_SCORE:
        label = "medium"
    ai_score = rec.get("ai_confidence")
    if isinstance(ai_score, (int, float)):
        score = float(ai_score)
        if score >= 0.8:
            label = "high"
        elif score >= 0.5:
            label = "medium"
        else:
            label = "low"
    else:
        score = CONFIDENCE_SCORE[label]
    method = rec.get("recovery_method") or "signature"
    header_valid = method == "signature" or label in ("high", "medium")
    footer_valid = label in ("high", "medium")
    structure_valid = method == "signature" and label == "high"
    notes = rec.get("notes") or "structure-aware parse"
    if method == "ai_classified":
        explanation = notes
        recovery_method = "carved"
    else:
        explanation = (
            f"{notes}. Signature-based contiguous carve of {rec.get('type')} "
            f"at byte offset {rec.get('offset_start')}."
        )
        recovery_method = "carved"
    return {
        "id": f"{evidence_id}-{rec.get('index', 0):04d}",
        "evidence_id": evidence_id,
        "filename": rec.get("filename"),
        "file_type": rec.get("type"),
        "size_bytes": rec.get("size"),
        "offset": rec.get("offset_start"),
        "recovery_method": recovery_method,
        "confidence_score": score,
        "confidence_label": label,
        "ai_explanation": explanation,
        "ai_confidence": rec.get("ai_confidence"),
        "entropy": rec.get("entropy"),
        "classifier": "ai" if method == "ai_classified" else "signature",
        "integrity_checks": {
            "header_valid": header_valid,
            "footer_valid": footer_valid,
            "structure_valid": structure_valid,
            "hash": rec.get("sha256") or "",
        },
        "recovered_at": recovered_at,
    }


def _session_to_results(session: dict | None) -> dict:
    if not session:
        return {
            "session_id": "",
            "evidence_id": "",
            "total_files": 0,
            "files": [],
            "status": "idle",
            "progress": 0,
            "message": "No recovery has been run yet. Import a raw image to start carving.",
            "image_size_bytes": 0,
        }
    return {
        "session_id": session["id"],
        "evidence_id": session["evidence_id"],
        "total_files": session.get("total_files") or len(session.get("files") or []),
        "files": session.get("files") or [],
        "status": session.get("status"),
        "progress": session.get("progress") or 0,
        "message": session.get("message") or "",
        "image_size_bytes": session.get("image_size_bytes") or 0,
    }


def _find_evidence(evidence_id: str) -> dict | None:
    for item in _state["evidence"]:
        if item["id"] == evidence_id:
            return item
    return None


def _find_session(session_id: str) -> dict | None:
    for item in _state["sessions"]:
        if item["id"] == session_id:
            return item
    return None


def _latest_session() -> dict | None:
    if not _state["sessions"]:
        return None
    return _state["sessions"][-1]


def _dashboard_stats() -> dict:
    files: list[dict] = []
    for session in _state["sessions"]:
        if session.get("status") == "completed":
            files.extend(session.get("files") or [])
    by_type: dict[str, int] = {}
    for item in files:
        typ = item.get("file_type") or "UNK"
        by_type[typ] = by_type.get(typ, 0) + 1
    high = sum(1 for item in files if item.get("confidence_label") == "high")
    medium = sum(1 for item in files if item.get("confidence_label") == "medium")
    low = sum(1 for item in files if item.get("confidence_label") == "low")
    avg = sum(float(item.get("confidence_score") or 0) for item in files) / len(files) if files else 0.0
    erasures_done = sum(1 for job in _state["erasure_jobs"] if job.get("status") == "completed")
    sessions = [
        {
            "session_id": session["id"],
            "evidence_id": session["evidence_id"],
            "status": session.get("status"),
            "progress": session.get("progress") or 0,
            "message": session.get("message") or "",
            "total_files": session.get("total_files") or 0,
        }
        for session in reversed(_state["sessions"])
    ]
    return {
        "total_evidence": len(_state["evidence"]),
        "files_recovered": len(files),
        "erasures_completed": erasures_done,
        "audit_events": len(_state["audit"]),
        "avg_confidence": avg,
        "recovery_by_type": [{"type": name, "count": count} for name, count in sorted(by_type.items())],
        "recent_activity": list(reversed(_state["audit"]))[:8],
        "confidence_distribution": [
            {"label": "High (≥0.8)", "count": high},
            {"label": "Medium (0.5–0.8)", "count": medium},
            {"label": "Low (<0.5)", "count": low},
        ],
        "sessions": sessions,
        "innovations": {
            "ssd_aware_erasure": True,
            "ai_fragment_classifier": True,
            "blockchain_audit": True,
            "chain_height": _get_ledger().height(),
            "chain_valid": bool(verify_chain(_get_ledger().get_chain()).get("valid")),
        },
        "mode": MODE,
        "firmware_simulated": FIRMWARE_SIMULATED,
        "auth_required": AUTH_REQUIRED,
    }


def _run_recovery(evidence_id: str, session_id: str, actor: str | None = None) -> None:
    set_actor(actor)
    try:
        with STATE_LOCK:
            evidence = _find_evidence(evidence_id)
            session = _find_session(session_id)
            if not evidence or not session:
                return
            image_path = Path(evidence["source_path"])
            out_dir = RECOVERED_DIR / evidence_id
            evidence["status"] = "analyzing"
            session["status"] = "running"
            session["message"] = "Starting recovery..."
            _append_audit("recovery.start", session_id, details={"evidence_id": evidence_id})
            _save_state()

        def progress(msg: str, frac: float) -> None:
            with STATE_LOCK:
                session_live = _find_session(session_id)
                if session_live:
                    session_live["message"] = msg
                    session_live["progress"] = frac
                    _save_state()

        recovered = carve_image(image_path, out_dir, progress_cb=progress)
        json_path = out_dir / "case_report.json"
        html_path = out_dir / "case_report.html"
        write_reports(
            source_image=image_path,
            source_hash_sha256=evidence["hashes"]["sha256"],
            files=recovered,
            json_path=json_path,
            html_path=html_path,
            image_size=image_path.stat().st_size,
        )
        recovered_at = utc_now_iso()
        files = [_file_to_frontend(item.to_dict(), evidence_id, recovered_at) for item in recovered]
        with STATE_LOCK:
            evidence_live = _find_evidence(evidence_id)
            session_live = _find_session(session_id)
            if evidence_live:
                evidence_live["status"] = "analyzed"
            if session_live:
                session_live["status"] = "completed"
                session_live["progress"] = 1
                session_live["message"] = "Carving complete."
                session_live["total_files"] = len(files)
                session_live["files"] = files
                session_live["completed_at"] = recovered_at
                session_live["report_json"] = str(json_path)
                session_live["report_html"] = str(html_path)
            _append_audit(
                "recovery.complete",
                session_id,
                details={"evidence_id": evidence_id, "files_recovered": len(files)},
            )
            _save_state()
    except Exception as exc:  # noqa: BLE001 — surface in case state
        with STATE_LOCK:
            evidence_live = _find_evidence(evidence_id)
            session_live = _find_session(session_id)
            if evidence_live:
                evidence_live["status"] = "error"
            if session_live:
                session_live["status"] = "failed"
                session_live["message"] = str(exc)
            _append_audit(
                "recovery.complete",
                session_id,
                outcome="error",
                details={"error": str(exc)},
            )
            _save_state()
        traceback.print_exc()


def _start_recovery_locked(evidence: dict) -> dict:
    session_id = _next_id("RS")
    session = {
        "id": session_id,
        "evidence_id": evidence["id"],
        "status": "running",
        "progress": 0.01,
        "message": "Queued",
        "total_files": 0,
        "files": [],
        "started_at": utc_now_iso(),
        "completed_at": None,
        "image_size_bytes": evidence["size_bytes"],
        "error": None,
    }
    _state["sessions"].append(session)
    _save_state()
    thread = threading.Thread(
        target=_run_recovery,
        args=(evidence["id"], session_id, get_actor()),
        daemon=True,
    )
    thread.start()
    return session


def _import_from_path(source: Path, filename: str | None = None) -> dict:
    if not source.is_file():
        raise FileNotFoundError(f"Not a regular file: {source}")
    if _is_forbidden(source):
        raise PermissionError("Refusing to import a device node. Use a raw image file.")

    hashes = _hash_file(source)
    existing = next((item for item in _state["evidence"] if item["hashes"]["sha256"] == hashes["sha256"]), None)
    if existing and existing.get("status") in ("analyzing", "imported"):
        return existing
    if existing and existing.get("status") == "analyzed":
        running = next(
            (
                session
                for session in _state["sessions"]
                if session["evidence_id"] == existing["id"] and session.get("status") == "running"
            ),
            None,
        )
        if running:
            return existing
        existing["status"] = "analyzing"
        _start_recovery_locked(existing)
        return existing

    evidence_id = _next_id("EV")
    dest_dir = EVIDENCE_DIR / evidence_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored_name = filename or source.name
    stored_path = dest_dir / stored_name
    if source.resolve() != stored_path.resolve():
        shutil.copy2(source, stored_path)

    item = {
        "id": evidence_id,
        "filename": stored_name,
        "format": _guess_format(stored_name),
        "size_bytes": stored_path.stat().st_size,
        "import_timestamp": utc_now_iso(),
        "hashes": hashes,
        "status": "analyzing",
        "source_path": str(stored_path),
        "metadata": {
            "original_path": str(source),
            "tool": TOOL_NAME,
            "tool_version": TOOL_VERSION,
        },
    }
    _state["evidence"].insert(0, item)
    _append_audit("evidence.import", evidence_id, details={"filename": stored_name, "sha256": hashes["sha256"]})
    _start_recovery_locked(item)
    _save_state()
    return item


def _device_public(info, rel_name: str) -> dict:
    drive_type = info.drive_type if info.drive_type in ("HDD", "SSD", "NVMe", "USB") else "USB"
    return {
        "name": rel_name,
        "type": drive_type,
        "serial": info.serial,
        "capacity_bytes": info.capacity_bytes or 0,
        "drive_type": info.drive_type,
        "model": info.model,
        "protocol": info.protocol,
        "recommended_method": info.recommended_method,
        "recommended_nist_level": info.recommended_nist_level,
        "overprovisioning_risk": info.overprovisioning_risk,
        "nist_purge_command": info.nist_purge_command,
        "capabilities": info.to_dict()["capabilities"],
        "notes": info.notes,
    }


def _rel_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _import_erasure_file(data: bytes, filename: str, media: str | None = None) -> dict:
    """
    Stage a local file for sanitization the same way evidence import works:
    copy into workspace. The operator's original path is never opened for write.
    """
    if not filename or filename.endswith("/") or filename in (".", ".."):
        raise ValueError("Uploaded file has no name")
    safe_name = Path(filename).name
    ERASURE_UPLOADS.mkdir(parents=True, exist_ok=True)
    dest = ERASURE_UPLOADS / safe_name
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        dest = ERASURE_UPLOADS / f"{stem}_{utc_now_iso().replace(':', '')}{suffix}"
    dest.write_bytes(data)
    media_norm = (media or "FILE").strip().upper()
    if media_norm not in ("HDD", "SSD", "NVMe", "USB", "FILE"):
        media_norm = "FILE"
    meta = {
        "drive_type": media_norm,
        "original_filename": safe_name,
        "imported_at": utc_now_iso(),
        "notes": (
            "Operator-uploaded local file. The original on disk is not modified. "
            "Sanitization overwrites a working COPY only."
        ),
        "capacity_bytes": dest.stat().st_size,
        "model": safe_name,
        "serial": f"UPLOAD-{dest.stat().st_size}",
    }
    dest.with_suffix(dest.suffix + ".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _append_audit(
        "erasure.start",
        _rel_to_root(dest),
        details={"action": "FILE_STAGED_FOR_ERASURE", "filename": safe_name, "bytes": dest.stat().st_size},
    )
    info = detect_device(dest)
    return _device_public(info, _rel_to_root(dest))


def _erasure_devices() -> list[dict]:
    devices = []
    ERASURE_UPLOADS.mkdir(parents=True, exist_ok=True)
    for path in sorted(ERASURE_UPLOADS.iterdir(), reverse=True):
        if not path.is_file() or path.name.startswith(".") or path.name.endswith(".meta.json"):
            continue
        info = detect_device(path)
        devices.append(_device_public(info, _rel_to_root(path)))
    create_demo_targets(TARGETS_DIR)
    for path in sorted(TARGETS_DIR.glob("demo_*.bin")):
        info = detect_device(path)
        devices.append(_device_public(info, _rel_to_root(path)))
    samples = ROOT / "samples"
    if samples.is_dir():
        for path in sorted(samples.iterdir()):
            if not path.is_file() or path.name.startswith(".") or " 2." in path.name:
                continue
            info = detect_device(path)
            devices.append(_device_public(info, _rel_to_root(path)))
    return devices


def _resolve_erasure_target(device_name: str) -> Path:
    candidate = Path(device_name)
    if not candidate.is_absolute():
        candidate = (ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if not _safe_under(ROOT, candidate) and not _safe_under(TARGETS_DIR, candidate):
        raise PermissionError("Erasure targets must live inside the project directory")
    return candidate


def _write_certificate(job: dict) -> Path:
    path = CERT_DIR / f"{job['id']}.pdf"
    details = job.get("details") or {}
    make_pdf(
        path,
        f"Sanitization certificate {job['id']}",
        [
            f"Target: {job['device']['name']}",
            f"Method: {job['method']}  passes={job['passes_total']}",
            f"SHA-256 before: {details.get('hash_before', 'n/a')}",
            f"SHA-256 after:  {details.get('hash_after', 'n/a')}",
            "Working COPY overwritten. Original file was not modified.",
            f"Verified: {job['verification']['passed']}",
        ],
    )
    return path


def _public_job(job: dict) -> dict:
    return {k: v for k, v in job.items() if k not in ("certificate_path",)}


def _start_erasure(device_name: str, method: str, operator_id: str | None = None) -> dict:
    method = (method or "auto").lower().strip()
    operator_id = operator_id or _current_actor()
    devices = {item["name"]: item for item in _erasure_devices()}
    device = devices.get(device_name)
    source = _resolve_erasure_target(device_name)
    if not device:
        info = detect_device(source)
        device = _device_public(info, device_name)

    job_id = _next_id("SAN")
    _append_audit(
        "erasure.start",
        job_id,
        details={"method": method, "device": device_name, "drive_type": device.get("type")},
    )
    try:
        result = media_sanitize(
            source,
            job_id=job_id,
            work_dir=ERASURE_DIR / job_id,
            cert_dir=CERT_DIR,
            method=method,
            operator_id=operator_id,
        )
    except Exception as exc:
        job = {
            "id": job_id,
            "device": device,
            "method": method,
            "passes_completed": 0,
            "passes_total": 0,
            "status": "failed",
            "started_at": utc_now_iso(),
            "completed_at": utc_now_iso(),
            "verification": {"passed": False, "sample_sectors_checked": 0, "residual_data_found": False},
            "certificate_url": None,
            "details": {"error": str(exc), "operator_id": operator_id},
        }
        _state["erasure_jobs"].insert(0, job)
        _append_audit("erasure.complete", job_id, outcome="error", details={"error": str(exc)})
        _save_state()
        return job

    job = result.to_job_dict()
    job["certificate_path"] = result.details.get("certificate_path")
    job["compliance_url"] = f"/erasure/compliance/{job_id}"
    if not job.get("certificate_url"):
        job["certificate_url"] = f"/erasure/compliance/{job_id}/file"
    _state["erasure_jobs"].insert(0, job)
    _append_audit(
        "erasure.complete",
        job_id,
        details={
            "method": result.technique,
            "nist_level": result.nist_level,
            "drive_type": result.device.get("type"),
            "verified": result.verification.get("passed"),
        },
    )
    _append_audit(
        "erasure.verify",
        job_id,
        details={"passed": result.verification.get("passed"), "sectors": result.verification.get("sample_sectors_checked")},
    )
    _append_audit(
        "certificate.generate",
        job_id,
        details={"path": result.details.get("certificate_path"), "sha256": result.details.get("certificate_sha256")},
    )
    _save_state()
    return job


def _health_payload() -> dict:
    try:
        chain_report = verify_chain(_get_ledger().get_chain())
    except Exception as exc:  # noqa: BLE001
        chain_report = {"valid": False, "status": "ERROR", "reason": str(exc)}
    try:
        metrics = accuracy_report()
        model_loaded = bool((metrics.get("weights") or {}).get("json") or metrics.get("accuracy") is not None)
    except Exception:
        metrics = {}
        model_loaded = False
    return {
        "ok": True,
        "tool": TOOL_NAME,
        "version": TOOL_VERSION,
        "mocks": False,
        "mode": MODE,
        "bind": HOST,
        "firmware_simulated": FIRMWARE_SIMULATED,
        "auth_required": AUTH_REQUIRED,
        "chain": {
            "valid": bool(chain_report.get("valid")),
            "status": chain_report.get("status"),
            "height": chain_report.get("height"),
        },
        "classifier": {
            "loaded": model_loaded,
            "accuracy": metrics.get("accuracy"),
            "dataset": metrics.get("dataset"),
        },
        "safety": {
            "block_devices_refused": True,
            "evidence_read_only": True,
            "erasure_copy_only": FIRMWARE_SIMULATED,
        },
    }


def _safe_under(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


class ThreadedServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    server_version = f"{TOOL_NAME}/{TOOL_VERSION}"

    def log_message(self, fmt: str, *args) -> None:
        # A closed or broken stderr (orphaned process after the terminal exits)
        # must not abort the HTTP response — that shows up as Vite 502s.
        try:
            rid = getattr(self, "request_id", "-")
            log_event("info", fmt % args, request_id=rid, client=self.client_address[0])
        except Exception:
            try:
                sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))
            except Exception:
                pass

    def _cors(self) -> None:
        origin = self.headers.get("Origin") or ""
        if cors_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        elif not origin:
            self.send_header("Access-Control-Allow-Origin", "http://localhost:5174")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Operator-Id, X-Request-Id")
        self.send_header("Access-Control-Expose-Headers", "X-Request-Id")

    def _send_json(self, payload, status: int = 200) -> None:
        if status >= 400 and isinstance(payload, dict) and "request_id" not in payload:
            payload = {
                **payload,
                "request_id": getattr(self, "request_id", None),
                "code": payload.get("code") or f"http_{status}",
            }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Request-Id", getattr(self, "request_id", ""))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _send_file(self, path: Path, download_name: str | None = None) -> None:
        if not path.is_file():
            self._send_json({"error": "Not found"}, 404)
            return
        data = path.read_bytes()
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if download_name:
            self.send_header("Content-Disposition", f'inline; filename="{download_name}"')
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length > UPLOAD_LIMIT:
            raise ValueError("Upload exceeds 512 MiB limit")
        return self.rfile.read(length) if length else b""

    def _parse_json(self) -> dict:
        raw = self._read_body()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _parse_multipart(self) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
        ctype = self.headers.get("Content-Type", "")
        body = self._read_body()
        match = re.search(r"boundary=([^;]+)", ctype, flags=re.I)
        if not match:
            return {}, {}
        boundary = match.group(1).strip().strip('"')
        delim = b"--" + boundary.encode("utf-8")
        fields: dict[str, str] = {}
        files: dict[str, tuple[str, bytes]] = {}
        for chunk in body.split(delim):
            chunk = chunk.strip(b"\r\n")
            if not chunk or chunk == b"--" or chunk.startswith(b"--"):
                continue
            header_blob, sep, data = chunk.partition(b"\r\n\r\n")
            if not sep:
                continue
            if data.endswith(b"\r\n"):
                data = data[:-2]
            headers = header_blob.decode("utf-8", "replace")
            name = None
            filename = None
            for line in headers.split("\r\n"):
                if line.lower().startswith("content-disposition:"):
                    name_m = re.search(r'name="([^"]*)"', line)
                    file_m = re.search(r'filename="([^"]*)"', line)
                    if name_m:
                        name = name_m.group(1)
                    if file_m:
                        filename = file_m.group(1)
            if not name:
                continue
            if filename is not None:
                files[name] = (filename, data)
            else:
                fields[name] = data.decode("utf-8", "replace")
        return fields, files

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _begin_request(self) -> None:
        self.request_id = self.headers.get("X-Request-Id") or new_request_id()
        token = parse_bearer(self.headers.get("Authorization"))
        session = resolve_session(token)
        if session:
            set_actor(session["operator_id"])
        else:
            set_actor(None)

    def _authorize_mutation(self, path: str) -> bool:
        public = {
            "/api/v1/auth/login",
            "/api/auth/login",
            "/api/v1/auth/register",
            "/api/auth/register",
        }
        if path in public:
            return True
        token = parse_bearer(self.headers.get("Authorization"))
        session = resolve_session(token)
        if session:
            user = session["operator_id"]
            set_actor(user)
            with STATE_LOCK:
                _state["actor"] = user
            return True
        set_actor(None)
        self._send_json(
            {"error": "Sign in with username and password first", "code": "auth_required"},
            401,
        )
        return False

    def do_GET(self) -> None:  # noqa: N802
        self._begin_request()
        try:
            self._handle_get()
        except Exception as exc:  # noqa: BLE001
            try:
                traceback.print_exc()
            except Exception:
                pass
            try:
                self._send_json({"error": str(exc)}, 500)
            except Exception:
                pass

    def do_POST(self) -> None:  # noqa: N802
        self._begin_request()
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/") or "/"
        if not self._authorize_mutation(path):
            return
        try:
            self._handle_post()
        except FileNotFoundError as exc:
            self._send_json({"error": str(exc)}, 404)
        except PermissionError as exc:
            self._send_json({"error": str(exc)}, 403)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001
            try:
                traceback.print_exc()
            except Exception:
                pass
            try:
                self._send_json({"error": str(exc)}, 500)
            except Exception:
                pass

    def _handle_get(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/") or "/"
        parts = [p for p in path.split("/") if p]

        if path in ("/", "/api", "/api/v1"):
            self._send_json({"tool": TOOL_NAME, "version": TOOL_VERSION, "api": "/api/v1"})
            return
        if path == "/api/v1/health":
            with STATE_LOCK:
                self._send_json(_health_payload())
            return
        if path in ("/api/v1/auth/me", "/api/auth/me"):
            token = parse_bearer(self.headers.get("Authorization"))
            session = resolve_session(token)
            if not session:
                self._send_json({"ok": False, "signed_in": False}, 200)
                return
            self._send_json({"ok": True, "signed_in": True, "username": session["operator_id"], "operator_id": session["operator_id"]})
            return

        payload = None
        status = 200
        file_send: tuple[Path, str] | None = None

        with STATE_LOCK:
            if path == "/api/v1/dashboard/stats":
                payload = _dashboard_stats()
            elif path == "/api/v1/evidence":
                payload = [_public_evidence(item) for item in _state["evidence"]]
            elif path in ("/api/v1/recovery/results", "/api/v1/recovery/results/latest"):
                payload = _session_to_results(_latest_session())
            elif path.startswith("/api/v1/recovery/results/") and len(parts) == 5:
                session = _find_session(parts[4])
                if not session:
                    payload, status = {"error": "Unknown session"}, 404
                else:
                    payload = _session_to_results(session)
            elif path == "/api/v1/recovery/sessions":
                payload = _dashboard_stats()["sessions"]
            elif path == "/api/v1/audit/log":
                payload = list(_state["audit"])
            elif path == "/api/v1/erasure/jobs":
                payload = [
                    {k: v for k, v in job.items() if k not in ("certificate_path",)}
                    for job in _state["erasure_jobs"]
                ]
            elif path == "/api/v1/erasure/devices":
                payload = _erasure_devices()
            elif path.startswith("/api/v1/erasure/status/") and len(parts) == 5:
                job = next((item for item in _state["erasure_jobs"] if item["id"] == parts[4]), None)
                if not job:
                    payload, status = {"error": "Unknown job"}, 404
                else:
                    payload = {k: v for k, v in job.items() if k != "certificate_path"}
            elif path.startswith("/api/v1/erasure/certificate/") and len(parts) >= 5:
                job_id = parts[4]
                job = next((item for item in _state["erasure_jobs"] if item["id"] == job_id), None)
                if not job:
                    payload, status = {"error": "Unknown job"}, 404
                elif len(parts) == 6 and parts[5] == "file":
                    file_send = (Path(job.get("certificate_path") or ""), f"{job_id}.pdf")
                else:
                    payload = {"url": f"/erasure/certificate/{job_id}/file"}
            elif path.startswith("/api/v1/erasure/compliance/") or path.startswith("/api/erasure/compliance/"):
                job_id = parts[-1] if parts[-1] != "file" else parts[-2]
                want_file = parts[-1] == "file"
                job = next((item for item in _state["erasure_jobs"] if item["id"] == job_id), None)
                if not job:
                    payload, status = {"error": "Unknown job"}, 404
                elif want_file:
                    file_send = (Path(job.get("certificate_path") or ""), f"{job_id}.pdf")
                else:
                    payload = job.get("certificate") or {
                        "url": job.get("certificate_url"),
                        "job_id": job_id,
                    }
            elif path in ("/api/v1/erasure/detect", "/api/erasure/detect"):
                query = parse_qs(parsed.query)
                device = (query.get("device") or [""])[0]
                if not device:
                    payload, status = {"error": "device query parameter is required"}, 400
                else:
                    # Detection is read-only (sysfs / path heuristics). Do not require
                    # the path to be an erasure target inside the project tree.
                    if device.startswith("/dev/"):
                        payload = detect_device(device).to_dict()
                    else:
                        try:
                            target = _resolve_erasure_target(device)
                        except PermissionError:
                            payload = detect_device(device).to_dict()
                        else:
                            payload = detect_device(target).to_dict()
            elif path in ("/api/v1/demo/delete-recover", "/api/demo/delete-recover"):
                payload = delete_demo.snapshot()
            elif path.startswith("/api/v1/demo/exhibits/") or path.startswith("/api/demo/exhibits/"):
                filename = Path(parts[-1]).name
                dest = (delete_demo.EXHIBITS / filename).resolve()
                if not _safe_under(delete_demo.EXHIBITS, dest) or not dest.is_file():
                    payload, status = {"error": "Exhibit not in the live folder (deleted or missing)"}, 404
                else:
                    file_send = (dest, filename)
            elif path.startswith("/api/v1/demo/inbox/") or path.startswith("/api/demo/inbox/"):
                filename = Path(parts[-1]).name
                dest = (delete_demo.INBOX / filename).resolve()
                if not _safe_under(delete_demo.INBOX, dest) or not dest.is_file():
                    payload, status = {"error": "Not in the pick list"}, 404
                else:
                    file_send = (dest, filename)
            elif path in ("/api/v1/ai/accuracy", "/api/ai/accuracy"):
                payload = accuracy_report()
            elif path in ("/api/v1/audit/chain", "/api/audit/chain"):
                payload = _ledger_public()
            elif path in ("/api/v1/audit/verify", "/api/audit/verify"):
                payload = verify_chain(_get_ledger().get_chain())
            elif path in ("/api/v1/audit/receipt", "/api/audit/receipt"):
                payload = _custody_receipt()
            elif path.startswith("/api/v1/audit/block/") or path.startswith("/api/audit/block/"):
                try:
                    index = int(parts[-1])
                except ValueError:
                    payload, status = {"error": "block index must be an integer"}, 400
                else:
                    block = _get_ledger().get_block(index)
                    if block is None:
                        payload, status = {"error": "Unknown block"}, 404
                    else:
                        payload = _annotate_block(block)
            elif path.startswith("/api/v1/audit/proof/") or path.startswith("/api/audit/proof/"):
                entry_id = parts[-1]
                proof = _get_chain().proof_for(entry_id)
                if not proof:
                    payload, status = {"error": "Unknown audit entry"}, 404
                else:
                    payload = proof
            elif path.startswith("/api/v1/files/") and len(parts) == 5:
                evidence_id, filename = parts[3], parts[4]
                dest = (RECOVERED_DIR / evidence_id / filename).resolve()
                if not _safe_under(RECOVERED_DIR, dest):
                    payload, status = {"error": "Forbidden"}, 403
                else:
                    file_send = (dest, filename)
                    _append_audit("file.export", filename, details={"evidence_id": evidence_id})
            elif path.startswith("/api/v1/reports/") and len(parts) == 5:
                evidence_id, kind = parts[3], parts[4]
                folder = RECOVERED_DIR / evidence_id
                if kind == "html":
                    file_send = (folder / "case_report.html", "case_report.html")
                elif kind == "json":
                    file_send = (folder / "case_report.json", "case_report.json")
            if payload is None and file_send is None:
                payload, status = {"error": "Not found", "path": path}, 404

        if file_send is not None:
            self._send_file(*file_send)
            return
        self._send_json(payload, status)

    def _handle_post(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/") or "/"
        ctype = self.headers.get("Content-Type", "")

        if path == "/api/v1/evidence/import":
            if "multipart/form-data" in ctype:
                _fields, files = self._parse_multipart()
                if "file" not in files:
                    raise ValueError("multipart body must include a file field named 'file'")
                filename, data = files["file"]
                if not filename:
                    raise ValueError("Uploaded file has no name")
                tmp = WORKSPACE / "uploads"
                tmp.mkdir(parents=True, exist_ok=True)
                upload_path = tmp / Path(filename).name
                upload_path.write_bytes(data)
                with STATE_LOCK:
                    item = _import_from_path(upload_path, filename=Path(filename).name)
                    self._send_json(_public_evidence(item), 201)
                return

            body = self._parse_json()
            with STATE_LOCK:
                if body.get("demo"):
                    if not DEMO_IMAGE.is_file():
                        raise FileNotFoundError(
                            "Demo image missing. Run: python3 generate_test_image.py"
                        )
                    item = _import_from_path(DEMO_IMAGE)
                    self._send_json(_public_evidence(item), 201)
                    return
                raw_path = body.get("path")
                if not raw_path:
                    raise ValueError("Provide demo=true, path, or upload a file")
                source = Path(str(raw_path))
                if not source.is_absolute():
                    source = (ROOT / source).resolve()
                else:
                    source = source.resolve()
                if not _safe_under(ROOT, source):
                    raise PermissionError("Path import is limited to files inside the project directory")
                item = _import_from_path(source, filename=body.get("filename"))
                self._send_json(_public_evidence(item), 201)
            return

        if path in (
            "/api/v1/demo/delete-recover/upload",
            "/api/demo/delete-recover/upload",
        ):
            if "multipart/form-data" not in ctype:
                raise ValueError("Upload a file as multipart field 'file'")
            _fields, files = self._parse_multipart()
            if "file" not in files:
                raise ValueError("multipart body must include a file field named 'file'")
            filename, data = files["file"]
            with STATE_LOCK:
                snap = delete_demo.add_uploaded_file(filename, data)
                _append_audit("demo.upload", filename, details={"bytes": len(data)})
                _save_state()
                self._send_json(snap, 201)
            return

        if path in ("/api/v1/demo/delete-recover", "/api/demo/delete-recover"):
            body = self._parse_json()
            action = str(body.get("action") or "").strip().lower()
            with STATE_LOCK:
                if action == "stage":
                    snap = delete_demo.stage(use_samples=bool(body.get("use_samples")))
                    _append_audit("demo.stage", "suspect_disk.img", details={"files": [p["filename"] for p in snap.get("planted") or []]})
                    _save_state()
                    self._send_json(snap, 201)
                    return
                if action == "remove":
                    name = str(body.get("filename") or "")
                    snap = delete_demo.remove_uploaded_file(name)
                    _save_state()
                    self._send_json(snap)
                    return
                if action == "delete":
                    snap = delete_demo.delete_exhibits()
                    _append_audit("demo.delete", "suspect_disk.img", details={"directory_wiped": True, "folder_empty": True})
                    _save_state()
                    self._send_json(snap)
                    return
                if action == "reset":
                    snap = delete_demo.reset()
                    _append_audit("demo.reset", "suspect_disk.img")
                    _save_state()
                    self._send_json(snap)
                    return
                if action == "recover":
                    image = delete_demo.image_path()
                    item = _import_from_path(image, filename="suspect_disk.img")
                    snap = delete_demo.mark_recovering(item["id"])
                    _save_state()
                    snap["evidence"] = _public_evidence(item)
                    self._send_json(snap, 202)
                    return
            raise ValueError("action must be stage, delete, recover, or reset")

        if path in ("/api/v1/erasure/import", "/api/erasure/import"):
            if "multipart/form-data" not in ctype:
                raise ValueError("Upload a file as multipart field 'file' (same as evidence import)")
            fields, files = self._parse_multipart()
            if "file" not in files:
                raise ValueError("multipart body must include a file field named 'file'")
            filename, data = files["file"]
            media = fields.get("media") or fields.get("drive_type")
            with STATE_LOCK:
                item = _import_erasure_file(data, filename, media=media)
                _save_state()
                self._send_json(item, 201)
            return

        if path == "/api/v1/recovery/start":
            body = self._parse_json()
            evidence_id = body.get("evidence_id")
            if not evidence_id:
                raise ValueError("evidence_id is required")
            with STATE_LOCK:
                evidence = _find_evidence(str(evidence_id))
                if not evidence:
                    raise FileNotFoundError(f"Unknown evidence: {evidence_id}")
                running = next(
                    (
                        session
                        for session in _state["sessions"]
                        if session["evidence_id"] == evidence["id"] and session.get("status") == "running"
                    ),
                    None,
                )
                session = running or _start_recovery_locked(evidence)
                self._send_json(_session_to_results(session), 202)
            return

        if path in ("/api/v1/erasure/start", "/api/v1/erasure/sanitize", "/api/erasure/sanitize"):
            body = self._parse_json()
            device = body.get("device") or body.get("deviceName") or body.get("device_path")
            method = body.get("method") or ("auto" if "sanitize" in path else "auto")
            operator_id = _current_actor()
            if not device:
                raise ValueError("device is required")
            with STATE_LOCK:
                job = _start_erasure(str(device), str(method), operator_id=str(operator_id))
                self._send_json(_public_job(job), 201)
            return

        if path in ("/api/v1/ai/classify", "/api/ai/classify"):
            fragment = b""
            if "multipart/form-data" in ctype:
                _fields, files = self._parse_multipart()
                if files:
                    _name, fragment = next(iter(files.values()))
            else:
                body = self._parse_json()
                if body.get("hex"):
                    fragment = bytes.fromhex(re.sub(r"\s+", "", str(body["hex"])))
                elif body.get("bytes_b64") or body.get("b64"):
                    import base64

                    fragment = base64.b64decode(body.get("bytes_b64") or body.get("b64"))
                elif body.get("text"):
                    fragment = str(body["text"]).encode("utf-8")
            if not fragment:
                raise ValueError("Provide a file upload, hex, or base64 fragment")
            result = classify_fragment(fragment)
            with STATE_LOCK:
                _append_audit(
                    "ai.classify",
                    result.file_type,
                    details={"confidence": result.confidence, "entropy": result.entropy, "method": result.method},
                )
                _save_state()
            self._send_json(result.to_dict())
            return

        if path in ("/api/v1/auth/register", "/api/auth/register"):
            body = self._parse_json()
            username = str(body.get("username") or body.get("operator_id") or "").strip()
            password = str(body.get("password") or "")
            profile = users.register(username, password)
            set_actor(profile["username"])
            session = issue_session(profile["username"])
            with STATE_LOCK:
                _state["actor"] = profile["username"]
                entry = _append_audit(
                    "auth.register",
                    profile["username"],
                    details={"username": profile["username"], "created_at": profile["created_at"]},
                )
                _save_state()
            self._send_json(
                {
                    "ok": True,
                    "username": profile["username"],
                    "operator_id": profile["username"],
                    "token": session["token"],
                    "expires_at": session["expires_at"],
                    "created_at": profile["created_at"],
                    "block_index": entry.get("block_index"),
                },
                201,
            )
            return

        if path in ("/api/v1/auth/login", "/api/auth/login"):
            body = self._parse_json()
            username = str(body.get("username") or body.get("operator_id") or "").strip()
            password = str(body.get("password") or "")
            profile = users.authenticate(username, password)
            set_actor(profile["username"])
            session = issue_session(profile["username"])
            with STATE_LOCK:
                _state["actor"] = profile["username"]
                entry = _append_audit(
                    "auth.login",
                    profile["username"],
                    details={
                        "username": profile["username"],
                        "logged_in_at": profile.get("last_login_at"),
                    },
                )
                _save_state()
                self._send_json(
                    {
                        "ok": True,
                        "username": profile["username"],
                        "operator_id": profile["username"],
                        "token": session["token"],
                        "expires_at": session["expires_at"],
                        "last_login_at": profile.get("last_login_at"),
                        "block_index": entry.get("block_index"),
                        "mode": MODE,
                    }
                )
            return

        if path in ("/api/v1/auth/me", "/api/auth/me"):
            token = parse_bearer(self.headers.get("Authorization"))
            session = resolve_session(token)
            if not session:
                self._send_json({"error": "Not signed in", "code": "auth_required"}, 401)
                return
            self._send_json({"ok": True, "username": session["operator_id"], "operator_id": session["operator_id"]})
            return

        if path in ("/api/v1/auth/logout", "/api/auth/logout"):
            token = parse_bearer(self.headers.get("Authorization"))
            operator = get_actor()
            revoke_session(token)
            with STATE_LOCK:
                entry = _append_audit("auth.logout", operator, details={"username": operator})
                _save_state()
                self._send_json({"ok": True, "block_index": entry.get("block_index")})
            return

        if path in ("/api/v1/audit/anchor", "/api/audit/anchor"):
            body = self._parse_json()
            network = body.get("network") or "simulated-ethereum"
            with STATE_LOCK:
                record = _get_chain().anchor(network=str(network))
                _append_audit("audit.export", record["tx_id"], details=record)
                _save_state()
                self._send_json(record, 201)
            return

        self._send_json({"error": "Not found", "path": path}, 404)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{TOOL_NAME} API server")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    _ensure_dirs()
    global _state
    _state = _load_state()
    _get_ledger()
    chain = _get_chain()
    if _state.get("audit") and chain.height() < len(_state["audit"]):
        chain.rebuild_from_audit(_state["audit"])
    threading.Thread(target=ensure_model, daemon=True).start()

    httpd = ThreadedServer((args.host, args.port), Handler)
    log_event("info", "api.start", host=args.host, port=args.port, mode=MODE, firmware_simulated=FIRMWARE_SIMULATED)
    print(f"{TOOL_NAME} {TOOL_VERSION} API  http://{args.host}:{args.port}/api/v1")
    print(f"Mode: {MODE}  firmware={'simulated' if FIRMWARE_SIMULATED else 'LIVE-DANGER'}  auth_required={AUTH_REQUIRED}")
    print("Frontend: cd frontend && npm run dev")
    print("Demo import: POST /api/v1/evidence/import  {\"demo\": true}")
    print("SSD-aware sanitize: POST /api/v1/erasure/sanitize")
    print("AI classify:        POST /api/v1/ai/classify")
    print("Blockchain verify:  GET  /api/v1/audit/verify")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
