"""Request-scoped operator name so every ledger write records who acted."""

from __future__ import annotations

import threading

_tls = threading.local()


def set_actor(username: str | None) -> None:
    _tls.username = (username or "").strip() or None


def get_actor() -> str:
    return getattr(_tls, "username", None) or "anonymous"
