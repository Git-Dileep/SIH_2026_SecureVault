"""Rule-based explanations for fragment classifications (forensic-reportable)."""

from __future__ import annotations

from typing import Any


def explain(classification: dict[str, Any]) -> str:
    file_type = classification.get("file_type") or classification.get("display_type") or "unknown"
    confidence = float(classification.get("confidence") or 0)
    entropy = float(classification.get("entropy") or 0)
    method = classification.get("method") or "mlp"
    mag = ((classification.get("features") or {}).get("magic_flags")) or {}
    hits = [name for name, flag in mag.items() if flag]
    parts = [
        f"Classified as {file_type} with {confidence:.0%} confidence "
        f"(Shannon entropy {entropy:.2f} bits/byte, method={method})."
    ]
    if hits:
        parts.append("Signature evidence: " + ", ".join(hits) + ".")
    if entropy >= 7.2:
        parts.append("High entropy is consistent with compressed or encrypted payloads (JPEG/PNG/ZIP/MP4/MP3).")
    elif entropy <= 4.5:
        parts.append("Low entropy is consistent with text or sparse binaries.")
    if classification.get("below_threshold"):
        parts.append("Below the 0.70 keep-threshold; flagged for analyst review and not auto-recovered.")
    return " ".join(parts)
