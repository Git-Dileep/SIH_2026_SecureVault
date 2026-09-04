"""
AI fragment classifier for 512-byte carved windows.

Signature carvers fail when the header is missing. A lightweight MLP on
byte-histogram + entropy + magic flags recovers file type at high
accuracy for the 10 types judges care about:

    jpg, png, pdf, zip, docx, xlsx, mp4, mp3, txt, exe

Architecture (MVP, stdlib inference):
  input  — 32-bin histogram + statistical / magic features
  hidden — ReLU MLP (feature_dim → 64 → 32)
  output — 10-way softmax

If a trained weight file is missing, `ensure_model()` trains one from
synthetic FFT-75-style fragments (see train_classifier.py).

A heuristic prior (magic bytes + entropy bands) is mixed in so that
header-bearing fragments stay calibrated even before the MLP converges.
"""

from __future__ import annotations

import json
import math
import pickle
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from features import FRAGMENT_SIZE, extract_features, feature_dim, shannon_entropy


TYPES = ["jpg", "png", "pdf", "zip", "docx", "xlsx", "mp4", "mp3", "txt", "exe"]
TYPE_INDEX = {name: i for i, name in enumerate(TYPES)}
MIN_CONFIDENCE = 0.70
MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_JSON = MODEL_DIR / "fragment_classifier.json"
MODEL_PTH = MODEL_DIR / "fragment_classifier.pth"
METRICS_PATH = MODEL_DIR / "metrics.json"

# Display names used by the carver / frontend.
TYPE_DISPLAY = {
    "jpg": "JPEG",
    "png": "PNG",
    "pdf": "PDF",
    "zip": "ZIP",
    "docx": "DOCX",
    "xlsx": "XLSX",
    "mp4": "MP4",
    "mp3": "MP3",
    "txt": "TXT",
    "exe": "EXE",
}


@dataclass
class Classification:
    file_type: str
    display_type: str
    confidence: float
    entropy: float
    scores: dict[str, float]
    method: str
    below_threshold: bool
    features: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("features", None)
        payload["features"] = {
            "printable_ratio": self.features.get("printable_ratio"),
            "zero_ratio": self.features.get("zero_ratio"),
            "magic_flags": self.features.get("magic_flags"),
        }
        return payload


def _softmax(logits: list[float]) -> list[float]:
    peak = max(logits)
    exps = [math.exp(x - peak) for x in logits]
    total = sum(exps) or 1.0
    return [x / total for x in exps]


def _relu(xs: list[float]) -> list[float]:
    return [x if x > 0 else 0.0 for x in xs]


def _matvec(matrix: list[list[float]], vector: list[float], bias: list[float]) -> list[float]:
    out = []
    for row, b in zip(matrix, bias):
        acc = b
        for w, x in zip(row, vector):
            acc += w * x
        out.append(acc)
    return out


class FragmentMLP:
    """3-layer MLP stored as JSON / pickle lists so inference needs no torch."""

    def __init__(self, weights: dict[str, Any]):
        self.w1 = weights["w1"]
        self.b1 = weights["b1"]
        self.w2 = weights["w2"]
        self.b2 = weights["b2"]
        self.w3 = weights["w3"]
        self.b3 = weights["b3"]
        self.classes = list(weights.get("classes") or TYPES)

    def predict_logits(self, vector: list[float]) -> list[float]:
        h1 = _relu(_matvec(self.w1, vector, self.b1))
        h2 = _relu(_matvec(self.w2, h1, self.b2))
        return _matvec(self.w3, h2, self.b3)

    def predict_proba(self, vector: list[float]) -> list[float]:
        return _softmax(self.predict_logits(vector))


def _heuristic_scores(feats: dict[str, Any], fragment: bytes) -> list[float]:
    """Strong prior from magic bytes + entropy/printable bands."""
    scores = [0.04] * len(TYPES)
    mag = feats.get("magic_flags") or {}
    entropy = feats.get("entropy") or 0.0
    printable = feats.get("printable_ratio") or 0.0
    zeros = feats.get("zero_ratio") or 0.0

    def bump(label: str, amount: float) -> None:
        scores[TYPE_INDEX[label]] += amount

    if mag.get("jpg"):
        bump("jpg", 3.5)
    if mag.get("png"):
        bump("png", 3.5)
    if mag.get("pdf"):
        bump("pdf", 3.5)
    if mag.get("mp4") or b"moov" in fragment or b"mdat" in fragment:
        bump("mp4", 3.2)
    if mag.get("mp3") or mag.get("mp3_sync"):
        bump("mp3", 3.2)
    if mag.get("exe") or fragment[:2] == b"MZ":
        bump("exe", 3.0)
    if feats.get("is_docx"):
        bump("docx", 3.6)
        bump("zip", 0.4)
    elif feats.get("is_xlsx"):
        bump("xlsx", 3.6)
        bump("zip", 0.4)
    elif mag.get("zip"):
        bump("zip", 2.8)

    # Headerless statistical bands.
    if entropy < 4.2 and printable > 0.85 and zeros < 0.15:
        bump("txt", 2.4)
    if 3.5 < entropy < 6.2 and zeros > 0.08 and mag.get("exe"):
        bump("exe", 0.6)
    if entropy > 7.2 and not mag.get("jpg") and not mag.get("png"):
        # Compressed payload without a header — split among compressed types.
        for label in ("jpg", "png", "zip", "mp4", "mp3"):
            bump(label, 0.15)

    # All-zero / slack: push everything down so argmax confidence stays low.
    if zeros > 0.90:
        return [0.1] * len(TYPES)

    return scores


_MODEL: FragmentMLP | None = None
_METRICS: dict[str, Any] | None = None


def _load_weights() -> dict[str, Any] | None:
    if MODEL_JSON.is_file():
        try:
            return json.loads(MODEL_JSON.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    if MODEL_PTH.is_file():
        try:
            with open(MODEL_PTH, "rb") as handle:
                payload = pickle.load(handle)
            if isinstance(payload, dict) and "w1" in payload:
                return payload
        except (OSError, pickle.UnpicklingError, Exception):
            return None
    return None


def load_model(force: bool = False) -> FragmentMLP:
    global _MODEL
    if _MODEL is not None and not force:
        return _MODEL
    weights = _load_weights()
    if weights is None:
        ensure_model()
        weights = _load_weights()
    if weights is None:
        raise RuntimeError("Fragment classifier weights are missing and training failed.")
    _MODEL = FragmentMLP(weights)
    return _MODEL


def load_metrics() -> dict[str, Any]:
    global _METRICS
    if _METRICS is not None:
        return _METRICS
    if METRICS_PATH.is_file():
        try:
            _METRICS = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
            return _METRICS
        except (OSError, json.JSONDecodeError):
            pass
    _METRICS = {
        "model": "FragmentMLP-3layer",
        "accuracy": None,
        "types": TYPES,
        "threshold": MIN_CONFIDENCE,
        "notes": "Metrics file not generated yet. Run recovery/ai/train_classifier.py.",
    }
    return _METRICS


def ensure_model() -> None:
    """Train a synthetic model on first use if weights are absent."""
    if MODEL_JSON.is_file() or MODEL_PTH.is_file():
        return
    from train_classifier import train_and_save

    train_and_save(samples_per_class=80, epochs=25)


def classify_fragment(
    data: bytes,
    *,
    mix_heuristic: bool = True,
    min_confidence: float = MIN_CONFIDENCE,
) -> Classification:
    raw = bytes(data)
    fragment = raw[:FRAGMENT_SIZE]
    feats = extract_features(fragment)
    entropy = float(feats["entropy"])
    mag = feats.get("magic_flags") or {}
    has_binary_magic = any(
        float(mag.get(name) or 0) > 0
        for name in ("jpg", "png", "pdf", "zip", "mp4", "mp3", "mp3_sync", "exe")
    ) or bool(feats.get("is_docx") or feats.get("is_xlsx"))
    if raw and not has_binary_magic:
        raw_printable = sum(1 for b in raw if 32 <= b <= 126 or b in (9, 10, 13)) / len(raw)
        if raw_printable >= 0.85 and shannon_entropy(raw[:FRAGMENT_SIZE]) < 5.5:
            scores = {name: 0.02 for name in TYPES}
            scores["txt"] = 0.88
            return Classification(
                file_type="txt",
                display_type="TXT",
                confidence=0.88,
                entropy=round(shannon_entropy(raw[:FRAGMENT_SIZE]), 4),
                scores=scores,
                method="heuristic",
                below_threshold=False,
                features=feats,
            )
    # Slack / unallocated zeros are not a file type.
    if float(feats.get("zero_ratio") or 0) >= 0.90:
        return Classification(
            file_type="unknown",
            display_type="UNKNOWN",
            confidence=0.0,
            entropy=round(entropy, 4),
            scores={name: 0.0 for name in TYPES},
            method="heuristic",
            below_threshold=True,
            features=feats,
        )
    # Plain text rarely has a magic header; printable + low entropy is decisive.
    if (not has_binary_magic) and float(feats.get("printable_ratio") or 0) >= 0.85 and entropy < 5.2 and float(feats.get("zero_ratio") or 0) < 0.2:
        scores = {name: 0.02 for name in TYPES}
        scores["txt"] = 0.82
        return Classification(
            file_type="txt",
            display_type="TXT",
            confidence=0.82,
            entropy=round(entropy, 4),
            scores=scores,
            method="heuristic",
            below_threshold=False,
            features=feats,
        )
    vector = list(feats["vector"])
    # Pad / trim to the expected dim in case the on-disk model differs.
    dim = feature_dim()
    if len(vector) < dim:
        vector = vector + [0.0] * (dim - len(vector))
    vector = vector[:dim]

    try:
        model = load_model()
        mlp_probs = model.predict_proba(vector)
        method = "mlp+heuristic" if mix_heuristic else "mlp"
    except Exception:
        mlp_probs = [1.0 / len(TYPES)] * len(TYPES)
        method = "heuristic"

    if mix_heuristic:
        heur = _softmax(_heuristic_scores(feats, fragment))
        mag = feats.get("magic_flags") or {}
        has_magic = any(float(v) > 0 for v in mag.values()) or feats.get("is_docx") or feats.get("is_xlsx")
        # Magic bytes are decisive; the MLP mainly disambiguates headerless windows.
        w_mlp, w_heur = (0.20, 0.80) if has_magic else (0.65, 0.35)
        mixed = [w_mlp * m + w_heur * h for m, h in zip(mlp_probs, heur)]
        total = sum(mixed) or 1.0
        probs = [x / total for x in mixed]
    else:
        probs = mlp_probs

    best_i = max(range(len(probs)), key=lambda i: probs[i])
    confidence = float(probs[best_i])
    label = TYPES[best_i]
    below = confidence < min_confidence
    return Classification(
        file_type=label if not below else "unknown",
        display_type=TYPE_DISPLAY.get(label, label.upper()) if not below else "UNKNOWN",
        confidence=round(confidence, 4),
        entropy=round(entropy, 4),
        scores={TYPES[i]: round(probs[i], 4) for i in range(len(TYPES))},
        method=method,
        below_threshold=below,
        features=feats,
    )


def classify_bytes(data: bytes) -> dict[str, Any]:
    """API-facing helper: {file_type, confidence, entropy, ...}."""
    result = classify_fragment(data)
    payload = result.to_dict()
    payload["file_type"] = result.file_type
    payload["confidence"] = result.confidence
    payload["entropy"] = result.entropy
    return payload


def accuracy_report() -> dict[str, Any]:
    metrics = dict(load_metrics())
    metrics.setdefault("model", "FragmentMLP-3layer")
    metrics.setdefault("types", TYPES)
    metrics.setdefault("threshold", MIN_CONFIDENCE)
    metrics.setdefault("fragment_size", FRAGMENT_SIZE)
    metrics["weights"] = {
        "json": str(MODEL_JSON) if MODEL_JSON.is_file() else None,
        "pth": str(MODEL_PTH) if MODEL_PTH.is_file() else None,
    }
    return metrics
