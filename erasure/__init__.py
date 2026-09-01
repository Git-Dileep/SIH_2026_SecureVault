"""
SecureVault Erasure Module — Owner: Person 5
Sub-package for secure data sanitization, device detection, verification, and audit certification.
"""

from erasure.methods import (
    DEFAULT_CHUNK_SIZE,
    BinaryPatternGenerator,
    OverwriteEngine,
    PassDetail,
    SanitizationAlgorithm,
    SanitizationResult,
    overwrite_dod_3pass,
    overwrite_nist_clear,
)
from erasure.device_detection import (
    StorageMediaType,
    TargetScopeInfo,
    TargetScopeValidator,
    check_target_safety,
    validate_sanitization_target,
)

__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "BinaryPatternGenerator",
    "OverwriteEngine",
    "PassDetail",
    "SanitizationAlgorithm",
    "SanitizationResult",
    "overwrite_dod_3pass",
    "overwrite_nist_clear",
    "StorageMediaType",
    "TargetScopeInfo",
    "TargetScopeValidator",
    "check_target_safety",
    "validate_sanitization_target",
]

