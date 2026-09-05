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
from urllib.parse import unquote, urlparse

from carver import TOOL_NAME, TOOL_VERSION, carve_image, utc_now_iso
from erasure import _is_forbidden, demo_erase
from generate_test_image import make_pdf
from report import write_reports


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT / "workspace"
STATE_PATH = WORKSPACE / "state.json"
EVIDENCE_DIR = WORKSPACE / "evidence"
RECOVERED_DIR = WORKSPACE / "recovered"
ERASURE_DIR = WORKSPACE / "erasure"
CERT_DIR = WORKSPACE / "certificates"
DEMO_IMAGE = ROOT / "testdata" / "synthetic_disk.img"

HOST = "127.0.0.1"
DEFAULT_PORT = 8000
ACTOR = "local-operator"
UPLOAD_LIMIT = 512 * 1024 * 1024

CONFIDENCE_SCORE = {"high": 0.92, "medium": 0.64, "low": 0.28}

STATE_LOCK = threading.Lock()
_state: dict = {}


def _empty_state() -> dict:
    return {
        "counters": {"EV": 0, "RS": 0, "SAN": 0, "AL": 0},
        "evidence": [],
        "sessions": [],
        "erasure_jobs": [],
        "audit": [],
    }


def _ensure_dirs() -> None:
    for path in (WORKSPACE, EVIDENCE_DIR, RECOVERED_DIR, ERASURE_DIR, CERT_DIR):
        path.mkdir(parents=True, exist_ok=True)


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
    payload = {
        "id": entry_id,
        "timestamp": timestamp,
        "actor": ACTOR,
        "action": action,
        "target": target,
        "outcome": outcome,
        "details": details or {},
        "prev_hash": prev,
    }
    digest_src = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["entry_hash"] = hashlib.sha256((prev + digest_src).encode("utf-8")).hexdigest()
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
    header_valid = True
    footer_valid = label in ("high", "medium")
    structure_valid = label == "high"
    notes = rec.get("notes") or "structure-aware parse"
    explanation = (
        f"{notes}. Signature-based contiguous carve of {rec.get('type')} "
        f"at byte offset {rec.get('offset_start')}."
    )
    return {
        "id": f"{evidence_id}-{rec.get('index', 0):04d}",
        "evidence_id": evidence_id,
        "filename": rec.get("filename"),
        "file_type": rec.get("type"),
        "size_bytes": rec.get("size"),
        "offset": rec.get("offset_start"),
        "recovery_method": "carved",
        "confidence_score": CONFIDENCE_SCORE[label],
        "confidence_label": label,
        "ai_explanation": explanation,
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
    }


def _run_recovery(evidence_id: str, session_id: str) -> None:
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
        args=(evidence["id"], session_id),
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


def _erasure_devices() -> list[dict]:
    devices = []
    samples = ROOT / "samples"
    if samples.is_dir():
        for path in sorted(samples.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            devices.append(
                {
                    "name": str(path.relative_to(ROOT)),
                    "type": "USB",
                    "serial": hashlib.sha256(path.name.encode()).hexdigest()[:12],
                    "capacity_bytes": path.stat().st_size,
                }
            )
    if not devices:
        fallback = WORKSPACE / "targets"
        fallback.mkdir(parents=True, exist_ok=True)
        demo = fallback / "demo_note.txt"
        if not demo.exists():
            demo.write_text("ForensicRecover erasure demo target.\n", encoding="utf-8")
        devices.append(
            {
                "name": str(demo.relative_to(ROOT)),
                "type": "USB",
                "serial": "DEMO-TARGET",
                "capacity_bytes": demo.stat().st_size,
            }
        )
    return devices


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


def _start_erasure(device_name: str, method: str) -> dict:
    method = (method or "clear").lower().strip()
    devices = {item["name"]: item for item in _erasure_devices()}
    device = devices.get(device_name)
    if not device:
        raise FileNotFoundError(f"Unknown erasure target: {device_name}")

    job_id = _next_id("SAN")
    started = utc_now_iso()
    if method == "destroy":
        job = {
            "id": job_id,
            "device": device,
            "method": method,
            "passes_completed": 0,
            "passes_total": 0,
            "status": "failed",
            "started_at": started,
            "completed_at": utc_now_iso(),
            "verification": {"passed": False, "sample_sectors_checked": 0, "residual_data_found": False},
            "certificate_url": None,
            "details": {"error": "Physical destruction is out of scope. Demo supports clear/purge on a file copy."},
        }
        _state["erasure_jobs"].insert(0, job)
        _append_audit("erasure.start", job_id, outcome="failure", details={"method": method, "device": device_name})
        _save_state()
        return job

    source = (ROOT / device_name).resolve()
    _append_audit("erasure.start", job_id, details={"method": method, "device": device_name})
    try:
        result = demo_erase(source, ERASURE_DIR / job_id, method=method)
    except Exception as exc:
        job = {
            "id": job_id,
            "device": device,
            "method": method,
            "passes_completed": 0,
            "passes_total": 1 if method == "clear" else 3,
            "status": "failed",
            "started_at": started,
            "completed_at": utc_now_iso(),
            "verification": {"passed": False, "sample_sectors_checked": 0, "residual_data_found": False},
            "certificate_url": None,
            "details": {"error": str(exc)},
        }
        _state["erasure_jobs"].insert(0, job)
        _append_audit("erasure.complete", job_id, outcome="error", details={"error": str(exc)})
        _save_state()
        return job
    job = {
        "id": job_id,
        "device": device,
        "method": result.method,
        "passes_completed": result.passes,
        "passes_total": result.passes,
        "status": "completed",
        "started_at": started,
        "completed_at": utc_now_iso(),
        "verification": {
            "passed": bool(result.verified),
            "sample_sectors_checked": 1,
            "residual_data_found": not result.verified,
        },
        "certificate_url": None,
        "details": {
            "hash_before": result.hash_before,
            "hash_after": result.hash_after,
            "working_copy": result.working_copy,
            "bytes_overwritten": result.bytes_overwritten,
            "message": result.message,
        },
    }
    cert = _write_certificate(job)
    job["certificate_url"] = f"/erasure/certificate/{job_id}/file"
    job["certificate_path"] = str(cert)
    _state["erasure_jobs"].insert(0, job)
    _append_audit("erasure.complete", job_id, details={"method": result.method, "verified": result.verified})
    _append_audit("erasure.verify", job_id, details={"passed": result.verified})
    _append_audit("certificate.generate", job_id, details={"path": str(cert)})
    _save_state()
    return job


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
            sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))
        except Exception:
            pass

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
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

    def do_GET(self) -> None:  # noqa: N802
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
            self._send_json({"ok": True, "tool": TOOL_NAME, "version": TOOL_VERSION, "mocks": False})
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
            elif path.startswith("/api/v1/files/") and len(parts) == 5:
                evidence_id, filename = parts[3], parts[4]
                dest = (RECOVERED_DIR / evidence_id / filename).resolve()
                if not _safe_under(RECOVERED_DIR, dest):
                    payload, status = {"error": "Forbidden"}, 403
                else:
                    file_send = (dest, filename)
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

        if path == "/api/v1/erasure/start":
            body = self._parse_json()
            device = body.get("device") or body.get("deviceName")
            method = body.get("method") or "clear"
            if not device:
                raise ValueError("device is required")
            with STATE_LOCK:
                job = _start_erasure(str(device), str(method))
                public = {k: v for k, v in job.items() if k != "certificate_path"}
                self._send_json(public, 201)
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

    httpd = ThreadedServer((args.host, args.port), Handler)
    print(f"{TOOL_NAME} {TOOL_VERSION} API  http://{args.host}:{args.port}/api/v1")
    print("Frontend: cd frontend && npm run dev")
    print("Demo import: POST /api/v1/evidence/import  {\"demo\": true}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
