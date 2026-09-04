"""Local username + password store (PBKDF2-SHA256). Not a cloud IdP."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


USERS_PATH = Path(__file__).resolve().parent / "workspace" / "users.json"
_LOCK = threading.Lock()
_USER_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
_PBKDF2_ROUNDS = 180_000


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load() -> dict[str, Any]:
    if not USERS_PATH.is_file():
        return {"users": []}
    try:
        data = json.loads(USERS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("users"), list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"users": []}


def _save(data: dict[str, Any]) -> None:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = USERS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(USERS_PATH)


def _hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return digest.hex()


def _find(users: list[dict[str, Any]], username: str) -> dict[str, Any] | None:
    key = username.lower()
    for item in users:
        if str(item.get("username") or "").lower() == key:
            return item
    return None


def public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "username": row.get("username"),
        "created_at": row.get("created_at"),
        "last_login_at": row.get("last_login_at"),
    }


def register(username: str, password: str) -> dict[str, Any]:
    username = (username or "").strip()
    if not _USER_RE.match(username):
        raise ValueError("Username must be 3–32 letters, numbers, dot, underscore, or hyphen.")
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    if len(password) > 128:
        raise ValueError("Password is too long.")
    with _LOCK:
        data = _load()
        if _find(data["users"], username):
            raise ValueError("That username is already registered.")
        salt = secrets.token_bytes(16)
        row = {
            "username": username,
            "salt": salt.hex(),
            "password_hash": _hash_password(password, salt),
            "created_at": _utc_now(),
            "last_login_at": None,
        }
        data["users"].append(row)
        _save(data)
    return public_user(row)


def authenticate(username: str, password: str) -> dict[str, Any]:
    username = (username or "").strip()
    if not username or not password:
        raise ValueError("Username and password are required.")
    with _LOCK:
        data = _load()
        row = _find(data["users"], username)
        if not row:
            raise PermissionError("Unknown user or wrong password.")
        salt = bytes.fromhex(str(row.get("salt") or ""))
        expected = str(row.get("password_hash") or "")
        got = _hash_password(password, salt)
        if not secrets.compare_digest(got, expected):
            raise PermissionError("Unknown user or wrong password.")
        row["last_login_at"] = _utc_now()
        _save(data)
        return public_user(row)
