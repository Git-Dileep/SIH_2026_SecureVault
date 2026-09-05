"""SecureVault media-aware sanitization (NIST SP 800-88 Rev. 2)."""

from __future__ import annotations

try:
    from .device_detection import detect_device, create_demo_targets, DriveInfo
    from .methods import select_method, METHOD_CATALOG
    from .sanitizer import sanitize, SanitizeResult
    from .verification import verify_sanitization
    from .nist_compliance import generate_certificate, NIST_STATEMENT
except ImportError:  # loaded via sys.path entry to this directory
    from device_detection import detect_device, create_demo_targets, DriveInfo
    from methods import select_method, METHOD_CATALOG
    from sanitizer import sanitize, SanitizeResult
    from verification import verify_sanitization
    from nist_compliance import generate_certificate, NIST_STATEMENT

__all__ = [
    "detect_device",
    "create_demo_targets",
    "DriveInfo",
    "select_method",
    "METHOD_CATALOG",
    "sanitize",
    "SanitizeResult",
    "verify_sanitization",
    "generate_certificate",
    "NIST_STATEMENT",
]
