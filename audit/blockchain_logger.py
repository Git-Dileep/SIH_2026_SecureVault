"""
Tamper-evident forensic blockchain logger.

Each block is hash-linked to the previous one. Courts can re-run
`verifier.verify_chain()` and reject the log if any field was rewritten.

Hash construction (important): the block `hash` is SHA-256 of the canonical
fields *excluding* `hash` itself. Hashing a dict that already contains
`hash` can never verify. Canonical fields:

    index, timestamp, action, details_hash, previous_hash

`details` is stored alongside the block for the UI but is committed only
via `details_hash`, so a later rewrite of the narrative is still detected.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHAIN_FILE = Path(__file__).resolve().parent / "audit_chain.json"
LOG_FILE = Path(__file__).resolve().parent / "audit.log"
GENESIS_PREV = "0"
CANONICAL_KEYS = ("index", "timestamp", "action", "details_hash", "previous_hash")

_LOCK = threading.Lock()
_INSTANCE: "BlockchainLogger | None" = None

logger = logging.getLogger("securevault.audit")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(payload: dict[str, Any]) -> str:
    body = {key: payload[key] for key in CANONICAL_KEYS}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def details_digest(details: dict[str, Any] | str | None) -> str:
    if isinstance(details, str):
        raw = details
    else:
        raw = json.dumps(details or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_block_hash(block: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(block).encode("utf-8")).hexdigest()


class BlockchainLogger:
    def __init__(self, chain_file: str | Path | None = None) -> None:
        self.chain_file = Path(chain_file) if chain_file else CHAIN_FILE
        self.chain: list[dict[str, Any]] = []
        self._load_or_create_chain()

    def _load_or_create_chain(self) -> None:
        if self.chain_file.is_file():
            try:
                data = json.loads(self.chain_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    self.chain = data
                    return
                if isinstance(data, dict) and isinstance(data.get("chain"), list) and data["chain"]:
                    self.chain = data["chain"]
                    return
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Could not load audit chain (%s); recreating genesis.", exc)
        self.chain = []
        genesis = self._create_block("GENESIS", {"message": "System initialized"})
        self.chain = [genesis]
        self._save_chain()
        logger.info("Wrote genesis block to %s", self.chain_file)

    def _create_block(self, action: str, details: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(details, str):
            details = {"message": details}
        previous_hash = self.chain[-1]["hash"] if self.chain else GENESIS_PREV
        block: dict[str, Any] = {
            "index": len(self.chain),
            "timestamp": _utc_now(),
            "action": action,
            "details_hash": details_digest(details),
            "previous_hash": previous_hash,
        }
        block["hash"] = compute_block_hash(block)
        # Narrative payload for operators / UI. Integrity is via details_hash.
        block["details"] = details
        return block

    def log(self, action: str, details: dict[str, Any] | str | None = None) -> dict[str, Any]:
        if isinstance(details, str):
            payload: dict[str, Any] = {"message": details}
        else:
            payload = dict(details or {})
        try:
            from actor_context import get_actor

            payload.setdefault("actor", get_actor())
        except Exception:
            payload.setdefault("actor", "anonymous")
        payload.setdefault("logged_at", _utc_now())
        with _LOCK:
            block = self._create_block(action, payload)
            self.chain.append(block)
            self._save_chain()
        logger.info("block %s %s actor=%s %s", block["index"], action, payload.get("actor"), block["hash"][:16])
        return block

    def get_chain(self) -> list[dict[str, Any]]:
        return list(self.chain)

    def get_block(self, index: int) -> dict[str, Any] | None:
        if index < 0 or index >= len(self.chain):
            return None
        return dict(self.chain[index])

    def height(self) -> int:
        return max(0, len(self.chain) - 1)

    def tip(self) -> dict[str, Any]:
        return self.chain[-1]

    def _save_chain(self) -> None:
        self.chain_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.chain_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.chain, indent=2), encoding="utf-8")
        tmp.replace(self.chain_file)


def get_logger(chain_file: str | Path | None = None) -> BlockchainLogger:
    """Process-wide singleton so recovery, erasure, and the API share one chain."""
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None or (chain_file and Path(chain_file) != _INSTANCE.chain_file):
            _INSTANCE = BlockchainLogger(chain_file)
        return _INSTANCE


def log_event(action: str, details: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Best-effort helper for carver / sanitizer (never raises into the pipeline)."""
    try:
        return get_logger().log(action, details or {})
    except Exception as exc:  # noqa: BLE001 — audit must not fail a carve
        logger.warning("blockchain log failed for %s: %s", action, exc)
        return None
