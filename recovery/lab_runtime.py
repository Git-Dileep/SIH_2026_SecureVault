"""
Lab-appliance runtime: config, operator sessions, request IDs, JSON logs.

This is a single-workstation forensic console, not a multi-tenant SaaS.
Default bind is loopback. Firmware sanitization stays simulated unless
SECUREVAULT_ALLOW_REAL_ERASE=1 — and even then block devices are refused
by the sanitizer unless they pass extra checks.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "workspace" / "server.jsonl"

# Loopback-only by default. Set SECUREVAULT_BIND=0.0.0.0 only on an isolated NIC.
BIND_HOST = os.environ.get("SECUREVAULT_BIND", "127.0.0.1")
AUTH_REQUIRED = os.environ.get("SECUREVAULT_AUTH_REQUIRED", "0") == "1"
SESSION_TTL_SEC = int(os.environ.get("SECUREVAULT_SESSION_TTL", "43200"))
MODE = os.environ.get("SECUREVAULT_MODE", "lab")  # lab | appliance
FIRMWARE_SIMULATED = os.environ.get("SECUREVAULT_ALLOW_REAL_ERASE", "0") != "1"

_LOCK = threading.Lock()
_sessions: dict[str, dict[str, Any]] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_request_id() -> str:
    return secrets.token_hex(8)


def log_event(level: str, message: str, **fields: Any) -> None:
    record = {
        "ts": utc_now(),
        "level": level,
        "message": message,
        **fields,
    }
    line = json.dumps(record, default=str)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with open(LOG_PATH, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except OSError:
        pass
    try:
        sys_stderr_write = __import__("sys").stderr.write
        sys_stderr_write(line + "\n")
    except Exception:
        pass


def issue_session(operator_id: str) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    session = {
        "token": token,
        "operator_id": operator_id.strip() or "local-operator",
        "issued_at": utc_now(),
        "expires_at": int(time.time()) + SESSION_TTL_SEC,
    }
    with _LOCK:
        _sessions[token] = session
    return session


def resolve_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    with _LOCK:
        session = _sessions.get(token)
        if not session:
            return None
        if session["expires_at"] < time.time():
            _sessions.pop(token, None)
            return None
        return dict(session)


def revoke_session(token: str | None) -> None:
    if not token:
        return
    with _LOCK:
        _sessions.pop(token, None)


def parse_bearer(header: str | None) -> str | None:
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return header.strip()


def cors_origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    return origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
