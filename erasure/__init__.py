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
from erasure.verification import (
    DEFAULT_MIN_RANDOM_ENTROPY,
    DEFAULT_SAMPLE_CHUNK_SIZE,
    SampleChunkResult,
    VerificationEngine,
    VerificationReport,
    calculate_shannon_entropy,
    inspect_erasure,
    verify_erasure,
)

__all__ = [
    # Methods
    "DEFAULT_CHUNK_SIZE",
    "BinaryPatternGenerator",
    "OverwriteEngine",
    "PassDetail",
    "SanitizationAlgorithm",
    "SanitizationResult",
    "overwrite_dod_3pass",
    "overwrite_nist_clear",
    # Device Detection
    "StorageMediaType",
    "TargetScopeInfo",
    "TargetScopeValidator",
    "check_target_safety",
    "validate_sanitization_target",
    # Verification
    "DEFAULT_SAMPLE_CHUNK_SIZE",
    "DEFAULT_MIN_RANDOM_ENTROPY",
    "SampleChunkResult",
    "VerificationEngine",
    "VerificationReport",
    "calculate_shannon_entropy",
    "inspect_erasure",
    "verify_erasure",
]
