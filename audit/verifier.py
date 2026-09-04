"""
Independent chain verifier.

Recomputes every block hash and previous_hash link. A single rewritten
byte in audit_chain.json yields status TAMPERED plus the broken index.
"""

from __future__ import annotations

from typing import Any

try:
    from .blockchain_logger import (
        GENESIS_PREV,
        compute_block_hash,
        details_digest,
        get_logger,
    )
except ImportError:
    from blockchain_logger import (
        GENESIS_PREV,
        compute_block_hash,
        details_digest,
        get_logger,
    )


def verify_chain(chain: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    blocks = list(chain) if chain is not None else get_logger().get_chain()
    if not blocks:
        return {
            "status": "TAMPERED",
            "valid": False,
            "broken_at": 0,
            "reason": "empty chain (genesis missing)",
            "blocks_checked": 0,
            "height": 0,
        }

    for i, block in enumerate(blocks):
        expected = compute_block_hash(block)
        if block.get("hash") != expected:
            return {
                "status": "TAMPERED",
                "valid": False,
                "broken_at": i,
                "reason": f"hash mismatch at index {i}",
                "blocks_checked": i + 1,
                "height": max(0, len(blocks) - 1),
            }
        if "details" in block:
            recomputed = details_digest(block.get("details") or {})
            if recomputed != block.get("details_hash"):
                return {
                    "status": "TAMPERED",
                    "valid": False,
                    "broken_at": i,
                    "reason": f"details_hash mismatch at index {i}",
                    "blocks_checked": i + 1,
                    "height": max(0, len(blocks) - 1),
                }
        if i == 0:
            if block.get("previous_hash") not in (GENESIS_PREV, "0" * 64):
                return {
                    "status": "TAMPERED",
                    "valid": False,
                    "broken_at": 0,
                    "reason": "genesis previous_hash is not the well-known origin",
                    "blocks_checked": 1,
                    "height": max(0, len(blocks) - 1),
                }
            continue
        previous = blocks[i - 1]
        if block.get("previous_hash") != previous.get("hash"):
            return {
                "status": "TAMPERED",
                "valid": False,
                "broken_at": i,
                "reason": f"previous_hash does not match block {i - 1}",
                "blocks_checked": i + 1,
                "height": max(0, len(blocks) - 1),
            }
        if block.get("index") != i:
            return {
                "status": "TAMPERED",
                "valid": False,
                "broken_at": i,
                "reason": f"index field {block.get('index')} != position {i}",
                "blocks_checked": i + 1,
                "height": max(0, len(blocks) - 1),
            }

    tip = blocks[-1]
    return {
        "status": "VALID",
        "valid": True,
        "broken_at": None,
        "reason": "chain intact",
        "blocks_checked": len(blocks),
        "height": max(0, len(blocks) - 1),
        "tip": tip.get("hash"),
    }
