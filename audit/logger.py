"""
Append-only, hash-chained audit logger.

Every pipeline action (import, carve, sanitize, certify) is recorded with
actor, target, outcome, and a SHA-256 pointer to the previous entry. The
same record is sealed into the permissioned blockchain so a rewritten
JSON file is detectable via `verify()`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .blockchain import AuditBlockchain
except ImportError:
    from blockchain import AuditBlockchain


GENESIS_PREV = "0" * 64


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class AuditLogger:
    def __init__(
        self,
        *,
        entries: list[dict[str, Any]] | None = None,
        chain_path: str | Path | None = None,
        actor: str = "local-operator",
    ) -> None:
        self.entries = entries if entries is not None else []
        self.actor = actor
        self.chain = AuditBlockchain(chain_path)
        if self.entries and self.chain.height() < len(self.entries):
            self.chain.rebuild_from_audit(self.entries)

    def _next_id(self) -> str:
        n = sum(1 for item in self.entries if str(item.get("id", "")).startswith("AL-"))
        return f"AL-{n + 1:03d}"

    def append(
        self,
        action: str,
        target: str,
        outcome: str = "success",
        details: dict[str, Any] | None = None,
        actor: str | None = None,
        entry_id: str | None = None,
    ) -> dict[str, Any]:
        prev = GENESIS_PREV
        if self.entries:
            prev = self.entries[-1].get("entry_hash") or GENESIS_PREV
        payload = {
            "id": entry_id or self._next_id(),
            "timestamp": _utc_now(),
            "actor": actor or self.actor,
            "action": action,
            "target": target,
            "outcome": outcome,
            "details": details or {},
            "prev_hash": prev,
        }
        digest_src = _canonical({k: v for k, v in payload.items() if k != "entry_hash"})
        payload["entry_hash"] = hashlib.sha256((prev + digest_src).encode("utf-8")).hexdigest()
        self.entries.append(payload)
        block = self.chain.append_entry(payload)
        payload["block_index"] = block["index"]
        payload["block_hash"] = block["hash"]
        payload["merkle_root"] = block["merkle_root"]
        return payload

    def verify_hash_chain(self) -> dict[str, Any]:
        for i, entry in enumerate(self.entries):
            prev = GENESIS_PREV if i == 0 else self.entries[i - 1].get("entry_hash")
            if entry.get("prev_hash") != prev:
                return {"valid": False, "broken_at": i, "reason": "prev_hash mismatch"}
            body = {k: v for k, v in entry.items() if k not in ("entry_hash", "block_index", "block_hash", "merkle_root")}
            expected = hashlib.sha256((prev + _canonical(body)).encode("utf-8")).hexdigest()
            if entry.get("entry_hash") != expected:
                return {"valid": False, "broken_at": i, "reason": "entry_hash mismatch"}
        chain = self.chain.verify()
        return {
            "valid": bool(chain.get("valid")),
            "hash_chain_valid": True,
            "blockchain": chain,
            "entries": len(self.entries),
        }
