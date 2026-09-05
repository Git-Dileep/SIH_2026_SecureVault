"""
Permissioned forensic blockchain for chain-of-custody.

Each audit event is a transaction. Transactions are sealed into blocks
with a Merkle root and a SHA-256 pointer to the previous block. This is
an append-only, tamper-evident ledger — the threat model is a local
operator or compromised workstation rewriting history, not a public
miner set. Optional `anchor()` simulates publishing the latest block
hash to an external L1 (Ethereum-style tx id).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .merkle import leaf_hash, merkle_proof, merkle_root, verify_proof
except ImportError:
    from merkle import leaf_hash, merkle_proof, merkle_root, verify_proof


GENESIS_HASH = "0" * 64


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AuditBlockchain:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.chain: list[dict[str, Any]] = []
        self.anchors: list[dict[str, Any]] = []
        if self.path and self.path.is_file():
            self._load()
        if not self.chain:
            self._genesis()

    def _genesis(self) -> None:
        block = {
            "index": 0,
            "timestamp": "1970-01-01T00:00:00Z",
            "prev_hash": GENESIS_HASH,
            "entries": [
                {
                    "id": "GENESIS",
                    "action": "chain.genesis",
                    "actor": "securevault",
                    "target": "ledger",
                    "outcome": "success",
                    "details": {"note": "SecureVault forensic chain-of-custody genesis"},
                }
            ],
            "merkle_root": "",
            "nonce": 0,
            "hash": "",
        }
        block["merkle_root"] = self._root_for(block["entries"])
        block["hash"] = self._hash_block(block)
        self.chain = [block]

    def _root_for(self, entries: list[dict[str, Any]]) -> str:
        leaves = [leaf_hash(_canonical(entry)) for entry in entries]
        return merkle_root(leaves)

    def _hash_block(self, block: dict[str, Any]) -> str:
        header = {
            "index": block["index"],
            "timestamp": block["timestamp"],
            "prev_hash": block["prev_hash"],
            "merkle_root": block["merkle_root"],
            "nonce": block.get("nonce", 0),
        }
        return _sha256_text(_canonical(header))

    def height(self) -> int:
        return max(0, len(self.chain) - 1)

    def tip(self) -> dict[str, Any]:
        return self.chain[-1]

    def append_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        prev = self.tip()
        body = {
            "id": entry.get("id"),
            "timestamp": entry.get("timestamp") or _utc_now(),
            "actor": entry.get("actor"),
            "action": entry.get("action"),
            "target": entry.get("target"),
            "outcome": entry.get("outcome"),
            "details": entry.get("details") or {},
            "entry_hash": entry.get("entry_hash"),
            "prev_hash": entry.get("prev_hash"),
        }
        block = {
            "index": prev["index"] + 1,
            "timestamp": body["timestamp"],
            "prev_hash": prev["hash"],
            "entries": [body],
            "merkle_root": self._root_for([body]),
            "nonce": 0,
            "hash": "",
        }
        block["hash"] = self._hash_block(block)
        self.chain.append(block)
        self._save()
        return block

    def verify(self) -> dict[str, Any]:
        if not self.chain:
            return {"valid": False, "broken_at": 0, "reason": "empty chain", "height": 0}
        for i, block in enumerate(self.chain):
            expected = self._hash_block(block)
            if block.get("hash") != expected:
                return {
                    "valid": False,
                    "broken_at": i,
                    "reason": "block hash mismatch",
                    "height": self.height(),
                }
            if self._root_for(block.get("entries") or []) != block.get("merkle_root"):
                return {
                    "valid": False,
                    "broken_at": i,
                    "reason": "merkle root mismatch",
                    "height": self.height(),
                }
            if i == 0:
                continue
            if block.get("prev_hash") != self.chain[i - 1].get("hash"):
                return {
                    "valid": False,
                    "broken_at": i,
                    "reason": "prev_hash does not match previous block",
                    "height": self.height(),
                }
        return {
            "valid": True,
            "broken_at": None,
            "reason": "chain intact",
            "height": self.height(),
            "tip": self.tip().get("hash"),
            "anchors": len(self.anchors),
        }

    def proof_for(self, entry_id: str) -> dict[str, Any] | None:
        for block in self.chain:
            entries = block.get("entries") or []
            for idx, entry in enumerate(entries):
                if str(entry.get("id")) != str(entry_id):
                    continue
                leaves = [leaf_hash(_canonical(item)) for item in entries]
                proof = merkle_proof(leaves, idx)
                leaf = leaves[idx]
                return {
                    "entry_id": entry_id,
                    "block_index": block["index"],
                    "block_hash": block["hash"],
                    "merkle_root": block["merkle_root"],
                    "leaf": leaf,
                    "proof": proof,
                    "valid": verify_proof(leaf, proof, block["merkle_root"]),
                    "entry": entry,
                }
        return None

    def anchor(self, network: str = "simulated-ethereum") -> dict[str, Any]:
        """
        Simulate publishing the tip hash to an external chain.
        A production build would send the 32-byte hash to a smart contract.
        """
        tip = self.tip()
        tx_material = _canonical(
            {
                "network": network,
                "block_index": tip["index"],
                "block_hash": tip["hash"],
                "merkle_root": tip["merkle_root"],
                "timestamp": _utc_now(),
            }
        )
        tx_id = "0x" + _sha256_text(tx_material)
        record = {
            "network": network,
            "tx_id": tx_id,
            "block_index": tip["index"],
            "block_hash": tip["hash"],
            "anchored_at": _utc_now(),
        }
        self.anchors.append(record)
        self._save()
        return record

    def public_chain(self, limit: int = 50) -> dict[str, Any]:
        blocks = self.chain[-limit:]
        return {
            "height": self.height(),
            "tip": self.tip().get("hash"),
            "valid": self.verify().get("valid"),
            "anchors": list(reversed(self.anchors))[:10],
            "blocks": [
                {
                    "index": b["index"],
                    "timestamp": b["timestamp"],
                    "hash": b["hash"],
                    "prev_hash": b["prev_hash"],
                    "merkle_root": b["merkle_root"],
                    "entries": b.get("entries") or [],
                }
                for b in reversed(blocks)
            ],
        }

    def rebuild_from_audit(self, entries: list[dict[str, Any]]) -> None:
        """Recreate the chain from the in-memory audit log (idempotent)."""
        self.chain = []
        self._genesis()
        known = {e.get("id") for block in self.chain for e in block.get("entries") or []}
        for entry in entries:
            if entry.get("id") in known:
                continue
            self.append_entry(entry)
            known.add(entry.get("id"))

    def _load(self) -> None:
        if not self.path:
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.chain = data.get("chain") or []
        self.anchors = data.get("anchors") or []

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"chain": self.chain, "anchors": self.anchors}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
