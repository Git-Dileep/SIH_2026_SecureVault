"""Merkle tree for batching audit entries into a single block root."""

from __future__ import annotations

import hashlib
from typing import Iterable


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def leaf_hash(payload: str | bytes) -> str:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return _digest(b"leaf:" + payload)


def parent_hash(left: str, right: str) -> str:
    a, b = (left, right) if left <= right else (right, left)
    return _digest(f"node:{a}:{b}".encode("utf-8"))


def merkle_root(leaves: Iterable[str]) -> str:
    layer = list(leaves)
    if not layer:
        return _digest(b"empty")
    while len(layer) > 1:
        nxt: list[str] = []
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        for i in range(0, len(layer), 2):
            nxt.append(parent_hash(layer[i], layer[i + 1]))
        layer = nxt
    return layer[0]


def merkle_proof(leaves: list[str], index: int) -> list[dict[str, str]]:
    """Inclusion proof: sibling hashes from leaf to root."""
    if not leaves or index < 0 or index >= len(leaves):
        return []
    layer = list(leaves)
    proof: list[dict[str, str]] = []
    idx = index
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        sibling = idx ^ 1
        if sibling < len(layer):
            proof.append(
                {
                    "position": "left" if sibling < idx else "right",
                    "hash": layer[sibling],
                }
            )
        nxt: list[str] = []
        for i in range(0, len(layer), 2):
            nxt.append(parent_hash(layer[i], layer[i + 1]))
        layer = nxt
        idx //= 2
    return proof


def verify_proof(leaf: str, proof: list[dict[str, str]], root: str) -> bool:
    current = leaf
    for step in proof:
        sibling = step.get("hash") or ""
        current = parent_hash(current, sibling)
    return current == root
