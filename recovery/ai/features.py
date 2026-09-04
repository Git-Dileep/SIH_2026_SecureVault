"""
Feature extraction for 512-byte file fragments.

Byte-histogram + entropy + printable ratio + magic-signature flags are
the standard input for file-type classification when headers may be
missing (Garfinkel FFT-75 / NIST NSRL-style fragment classification).
"""

from __future__ import annotations

import math
from typing import Any


FRAGMENT_SIZE = 512
HIST_BINS = 32  # 256-byte histogram folded into 32 bins

# Magic signatures we look for anywhere in the 512-byte window.
MAGIC: list[tuple[str, bytes]] = [
    ("jpg", b"\xff\xd8\xff"),
    ("png", b"\x89PNG\r\n\x1a\n"),
    ("pdf", b"%PDF-"),
    ("zip", b"PK\x03\x04"),
    ("mp4", b"ftyp"),
    ("mp3", b"ID3"),
    ("mp3_sync", b"\xff\xfb"),
    ("exe", b"MZ"),
    ("docx_hint", b"word/"),
    ("xlsx_hint", b"xl/"),
    ("content_types", b"[Content_Types].xml"),
]


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    n = len(data)
    entropy = 0.0
    for count in counts:
        if not count:
            continue
        p = count / n
        entropy -= p * math.log2(p)
    return entropy


def _printable_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    printable = sum(1 for b in data if 32 <= b <= 126 or b in (9, 10, 13))
    return printable / len(data)


def _chi_square_uniform(hist256: list[int], n: int) -> float:
    if n == 0:
        return 0.0
    expected = n / 256.0
    return sum((c - expected) ** 2 / expected for c in hist256)


def extract_features(data: bytes) -> dict[str, Any]:
    """Return a dict with scalar features, 32-bin histogram, and a flat vector."""
    fragment = bytes(data[:FRAGMENT_SIZE])
    if len(fragment) < FRAGMENT_SIZE:
        fragment = fragment + b"\x00" * (FRAGMENT_SIZE - len(fragment))

    hist256 = [0] * 256
    for byte in fragment:
        hist256[byte] += 1
    hist32 = [sum(hist256[i * 8 : (i + 1) * 8]) / FRAGMENT_SIZE for i in range(HIST_BINS)]

    entropy = shannon_entropy(fragment)
    printable = _printable_ratio(fragment)
    zeros = hist256[0] / FRAGMENT_SIZE
    ones = hist256[255] / FRAGMENT_SIZE
    high_bit = sum(hist256[128:]) / FRAGMENT_SIZE
    mean = sum(i * hist256[i] for i in range(256)) / FRAGMENT_SIZE
    # Unbiased-enough std for a 512-byte window.
    var = sum(hist256[i] * (i - mean) ** 2 for i in range(256)) / FRAGMENT_SIZE
    std = math.sqrt(var)
    chi = _chi_square_uniform(hist256, FRAGMENT_SIZE)

    magic_flags = [1.0 if token in fragment else 0.0 for _, token in MAGIC]
    # ZIP-based office: PK + XML names.
    is_docx = 1.0 if (b"PK\x03\x04" in fragment and (b"word/" in fragment or b"word\\" in fragment)) else 0.0
    is_xlsx = 1.0 if (b"PK\x03\x04" in fragment and (b"xl/" in fragment or b"xl\\" in fragment)) else 0.0

    scalars = [
        entropy / 8.0,
        printable,
        zeros,
        ones,
        high_bit,
        mean / 255.0,
        std / 128.0,
        min(chi / 512.0, 4.0) / 4.0,
        is_docx,
        is_xlsx,
        *magic_flags,
    ]
    vector = hist32 + scalars
    return {
        "entropy": entropy,
        "printable_ratio": printable,
        "zero_ratio": zeros,
        "vector": vector,
        "magic_flags": {name: flag for (name, _), flag in zip(MAGIC, magic_flags)},
        "is_docx": is_docx,
        "is_xlsx": is_xlsx,
        "size": len(data),
    }


def feature_dim() -> int:
    # 32 histogram bins + 8 statistical + 2 office flags + N magics
    return HIST_BINS + 8 + 2 + len(MAGIC)
