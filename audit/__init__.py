"""SecureVault append-only audit log + permissioned blockchain."""

from __future__ import annotations

try:
    from .logger import AuditLogger
    from .blockchain import AuditBlockchain
    from .merkle import merkle_root, merkle_proof, verify_proof
    from .blockchain_logger import BlockchainLogger, get_logger, log_event
    from .verifier import verify_chain
except ImportError:
    from logger import AuditLogger
    from blockchain import AuditBlockchain
    from merkle import merkle_root, merkle_proof, verify_proof
    from blockchain_logger import BlockchainLogger, get_logger, log_event
    from verifier import verify_chain

__all__ = [
    "AuditLogger",
    "AuditBlockchain",
    "BlockchainLogger",
    "get_logger",
    "log_event",
    "verify_chain",
    "merkle_root",
    "merkle_proof",
    "verify_proof",
]
