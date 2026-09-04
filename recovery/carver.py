#!/usr/bin/env python3
"""
carver.py — Signature-based file carving engine (MVP).

Forensic rules we follow:
  1. The source image is opened READ-ONLY. We never write to it.
  2. We treat the image as a raw byte stream (no filesystem).
  3. We recover contiguous files by matching known headers/footers
     ("magic numbers") and then validating their internal structure.

Supported types (MVP): JPEG, PNG, PDF, ZIP.
"""

from __future__ import annotations

import hashlib
import mmap
import os
import struct
import sys
import zlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional


TOOL_NAME = "ForensicRecover"
TOOL_VERSION = "1.0.0-mvp"

# Safety cap so a corrupted image cannot explode into thousands of junk files.
MAX_RECOVERED_FILES = 500


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Signature:
    """How we recognise one file type in a raw byte stream."""

    name: str          # e.g. "JPEG"
    extension: str     # e.g. "jpg"
    header: bytes      # magic number at the start of the file
    max_size: int      # refuse to extract anything larger than this
    min_size: int      # refuse tiny matches (usually false positives)


@dataclass
class RecoveredFile:
    """Metadata about one carved file. This becomes a row in the case report."""

    index: int
    filename: str
    type: str
    extension: str
    offset_start: int
    offset_end: int
    size: int
    confidence: str            # high | medium | low
    sha256: str
    notes: str = ""
    ai_confidence: float | None = None
    entropy: float | None = None
    recovery_method: str = "signature"

    def to_dict(self) -> dict:
        return asdict(self)


ProgressCallback = Optional[Callable[[str, float], None]]


def _chain_log(action: str, details: dict) -> None:
    """Best-effort forensic blockchain write. Never fails a carve."""
    try:
        audit_dir = Path(__file__).resolve().parent.parent / "audit"
        if str(audit_dir) not in sys.path:
            sys.path.insert(0, str(audit_dir))
        from blockchain_logger import log_event

        log_event(action, details)
    except Exception:
        return


# File types we know how to carve. Sizes are generous for a demo image
# but small enough to keep false positives under control.
SIGNATURES: list[Signature] = [
    Signature("JPEG", "jpg", b"\xff\xd8\xff", max_size=15 * 1024 * 1024, min_size=64),
    Signature("PNG", "png", b"\x89PNG\r\n\x1a\n", max_size=15 * 1024 * 1024, min_size=64),
    Signature("PDF", "pdf", b"%PDF-", max_size=20 * 1024 * 1024, min_size=32),
    Signature("ZIP", "zip", b"PK\x03\x04", max_size=30 * 1024 * 1024, min_size=30),
]


# ---------------------------------------------------------------------------
# Integrity: SHA-256 of the evidence image (and of recovered files)
# ---------------------------------------------------------------------------

def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file in chunks so we never load a huge image into RAM twice."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Structure-aware "where does this file end?" helpers
# ---------------------------------------------------------------------------
#
# Naive carving just searches for a footer byte string. That works, but it
# also produces false positives (the footer pattern can appear inside
# compressed data). For the four MVP types we walk the *real* structure
# instead. That is the main piece of engineering depth in this module.
# ---------------------------------------------------------------------------

def _find_jpeg_end(data: bytes, start: int, max_size: int) -> Optional[int]:
    """
    Walk JPEG markers from SOI (FFD8) until EOI (FFD9).

    JPEG is a sequence of 0xFF-prefixed markers. Most markers have a
    2-byte length. After SOS (Start Of Scan, 0xDA) comes compressed
    image data, where 0xFF00 is a stuffed 0xFF (not a marker).
    """
    end_limit = min(len(data), start + max_size)
    if start + 4 > end_limit:
        return None

    i = start + 2  # skip FFD8
    while i + 1 < end_limit:
        # Markers always start with 0xFF. Skip fill bytes (FF FF ...).
        if data[i] != 0xFF:
            return None
        while i < end_limit and data[i] == 0xFF:
            i += 1
        if i >= end_limit:
            return None

        marker = data[i]
        i += 1

        # EOI — this is the real end of the JPEG.
        if marker == 0xD9:
            return i

        # Standalone markers with no length field.
        if marker in (0xD8, 0x01) or (0xD0 <= marker <= 0xD7):
            continue

        # SOS: entropy-coded payload follows. Scan until EOI, honouring stuffing.
        if marker == 0xDA:
            if i + 2 > end_limit:
                return None
            sos_len = struct.unpack_from(">H", data, i)[0]
            i += sos_len
            while i + 1 < end_limit:
                if data[i] != 0xFF:
                    i += 1
                    continue
                nxt = data[i + 1]
                if nxt == 0x00 or (0xD0 <= nxt <= 0xD7):
                    i += 2
                    continue
                if nxt == 0xD9:  # EOI
                    return i + 2
                if nxt == 0xFF:
                    i += 1
                    continue
                # Unexpected marker inside scan data — skip it if it has a length.
                i += 2
                continue
            return None

        # Regular length-prefixed marker (APP0, DQT, SOF, DHT, ...).
        if i + 2 > end_limit:
            return None
        length = struct.unpack_from(">H", data, i)[0]
        if length < 2:
            return None
        i += length

    return None


def _find_png_end(data: bytes, start: int, max_size: int) -> Optional[int]:
    """
    Walk PNG chunks from the 8-byte signature until IEND.

    Each chunk is: 4-byte length + 4-byte type + <length> data + 4-byte CRC.
    """
    end_limit = min(len(data), start + max_size)
    offset = start + 8  # skip signature
    if offset + 12 > end_limit:
        return None

    # First chunk MUST be IHDR with length 13.
    ihdr_len = struct.unpack_from(">I", data, offset)[0]
    ihdr_type = data[offset + 4 : offset + 8]
    if ihdr_len != 13 or ihdr_type != b"IHDR":
        return None

    while offset + 12 <= end_limit:
        length = struct.unpack_from(">I", data, offset)[0]
        # PNG spec: length is a 31-bit unsigned int.
        if length > 0x7FFFFFFF:
            return None
        chunk_end = offset + 12 + length  # len + type + data + crc
        if chunk_end > end_limit:
            return None

        chunk_type = data[offset + 4 : offset + 8]
        # Type bytes should be ASCII letters.
        if not all(65 <= b <= 122 for b in chunk_type):
            return None

        # Optional CRC check — if it fails we still return the offset but
        # the caller can mark confidence as medium.
        crc_stored = struct.unpack_from(">I", data, offset + 8 + length)[0]
        crc_ok = (zlib.crc32(data[offset + 4 : offset + 8 + length]) & 0xFFFFFFFF) == crc_stored
        if chunk_type == b"IEND":
            return chunk_end if crc_ok else -chunk_end  # negative => CRC mismatch

        offset = chunk_end

    return None


def _consume_pdf_eof_whitespace(data: bytes, end: int, end_limit: int) -> int:
    """Include the CR/LF that many PDFs put immediately after %%EOF."""
    consumed = 0
    while end < end_limit and data[end] in (0x0D, 0x0A, 0x20) and consumed < 4:
        end += 1
        consumed += 1
    return end


def _find_pdf_end(data: bytes, start: int, max_size: int) -> Optional[int]:
    """
    PDFs start with %PDF- and end with %%EOF (possibly followed by CR/LF).

    Incremental updates can contain several %%EOF markers. We keep extending
    to later %%EOF markers only while the bytes in between look like more
    PDF content. A long run of zeros means we have hit slack space (or the
    next planted file on our synthetic disk), so we stop.
    """
    if start + 8 > len(data):
        return None
    version = data[start + 5 : start + 8]
    # Expect "1.x" or "2.x".
    if version[:2] not in (b"1.", b"2."):
        return None

    end_limit = min(len(data), start + max_size)
    window = data[start:end_limit]

    chosen_end: Optional[int] = None
    search_from = 0
    while True:
        rel = window.find(b"%%EOF", search_from)
        if rel == -1:
            break
        candidate = _consume_pdf_eof_whitespace(data, start + rel + 5, end_limit)

        if chosen_end is not None:
            gap = data[chosen_end:start + rel]
            if len(gap) >= 64:
                zero_ratio = gap.count(0) / len(gap)
                if zero_ratio > 0.90:
                    break  # slack / next file, not an incremental update

        chosen_end = candidate
        search_from = rel + 5

    return chosen_end


def _find_zip_end(data: bytes, start: int, max_size: int) -> Optional[int]:
    """
    A ZIP file starts with a local file header (PK\\x03\\x04) and ends with
    the End Of Central Directory record (PK\\x05\\x06).

    We look for EOCD records and accept the first one whose Central Directory
    offset, *relative to this ZIP's start*, actually points at PK\\x01\\x02.
    That extra check rejects random 'PK\\x05\\x06' hits in other data.
    """
    end_limit = min(len(data), start + max_size)
    # Quick sanity on the local file header.
    if start + 30 > len(data):
        return None
    compression = struct.unpack_from("<H", data, start + 8)[0]
    if compression not in (0, 8, 9, 12, 14):  # store, deflate, deflate64, bzip2, lzma
        return None

    needle = b"PK\x05\x06"
    pos = start + 22
    while pos < end_limit:
        pos = data.find(needle, pos, end_limit)
        if pos == -1:
            return None
        if pos + 22 > len(data):
            return None
        comment_len = struct.unpack_from("<H", data, pos + 20)[0]
        zip_end = pos + 22 + comment_len
        if zip_end > end_limit:
            pos += 1
            continue
        cd_offset = struct.unpack_from("<I", data, pos + 16)[0]
        cd_abs = start + cd_offset
        if cd_abs + 4 <= len(data) and data[cd_abs : cd_abs + 4] == b"PK\x01\x02":
            return zip_end
        pos += 1
    return None


def _locate_file_end(sig: Signature, data: bytes, start: int) -> tuple[Optional[int], str, str]:
    """
    Return (end_offset, confidence, notes).

    confidence:
      high   — structure walked successfully (and CRC/CD checks passed)
      medium — structure walked but a check was weak/failed
      low    — should not normally be returned; caller skips None ends
    """
    finder = {
        "JPEG": _find_jpeg_end,
        "PNG": _find_png_end,
        "PDF": _find_pdf_end,
        "ZIP": _find_zip_end,
    }[sig.name]

    end = finder(data, start, sig.max_size)
    if end is None:
        return None, "low", "no valid footer/structure found"

    notes = "structure-aware parse"
    confidence = "high"

    # PNG uses a negative end to signal CRC mismatch (see _find_png_end).
    if sig.name == "PNG" and end < 0:
        end = -end
        confidence = "medium"
        notes = "PNG IEND found but CRC mismatch"

    size = end - start
    if size < sig.min_size or size > sig.max_size:
        return None, "low", f"size {size} outside [{sig.min_size}, {sig.max_size}]"

    return end, confidence, notes


# ---------------------------------------------------------------------------
# Core carving algorithm
# ---------------------------------------------------------------------------

def _open_readonly_view(path: Path):
    """
    Open the evidence image read-only and memory-map it.

    mmap lets us search with data.find() without copying 50–200 MB into a
    second Python bytes object. The OS pages the file in on demand.
    """
    handle = open(path, "rb")  # never "r+b" — evidence stays untouched
    try:
        view = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
    except (ValueError, OSError):
        # Empty file or mmap not supported — fall back to a full read.
        handle.seek(0)
        view = handle.read()
    return handle, view


def _overlaps(start: int, end: int, ranges: list[tuple[int, int, str]], same_type: str) -> bool:
    """Skip a header that sits inside an already-recovered file of the same type."""
    for r_start, r_end, r_type in ranges:
        if r_type == same_type and start < r_end and end > r_start:
            return True
    return False


def _ai_scan_unclaimed(
    data,
    claimed: list[tuple[int, int, str]],
    out_dir: Path,
    recovered: list[RecoveredFile],
    progress_cb: ProgressCallback = None,
) -> None:
    """
    When signature matching misses a fragment (no header), classify 512-byte
    windows with the MLP and keep predictions at confidence >= 0.70.
    """
    try:
        from ai.fragment_classifier import MIN_CONFIDENCE, classify_fragment
        from ai.confidence import label_for
        from ai.explanation import explain
    except Exception:
        return

    image_size = len(data)
    stride = 4096
    max_ai = 40
    added = 0
    if progress_cb:
        progress_cb("AI fragment classifier scanning unclaimed regions...", 0.92)

    def claimed_at(pos: int) -> bool:
        for start, end, _typ in claimed:
            if start <= pos < end:
                return True
        return False

    pos = 0
    while pos + 512 <= image_size and added < max_ai and len(recovered) < MAX_RECOVERED_FILES:
        if claimed_at(pos):
            pos += stride
            continue
        window = bytes(data[pos : pos + 512])
        if window.count(0) >= 460:
            pos += stride
            continue
        result = classify_fragment(window)
        if result.below_threshold or result.confidence < MIN_CONFIDENCE:
            pos += stride
            continue
        if result.file_type == "unknown":
            pos += stride
            continue

        # Expand to the surrounding non-zero run, capped per type.
        start = pos
        while start > 0 and not claimed_at(start - 1) and data[start - 1] != 0:
            start -= 1
            if pos - start > 64 * 1024:
                break
        end = pos + 512
        cap = 256 * 1024
        while end < image_size and not claimed_at(end) and data[end] != 0 and (end - start) < cap:
            end += 1
        if end - start < 32:
            pos += stride
            continue
        if _overlaps(start, end, claimed, result.display_type):
            pos += stride
            continue

        payload = bytes(data[start:end])
        file_index = len(recovered) + 1
        ext = result.file_type if result.file_type != "jpg" else "jpg"
        filename = f"{file_index:04d}_AI_{result.display_type}_{start:08x}.{ext}"
        dest = out_dir / filename
        dest.write_bytes(payload)
        notes = explain(result.to_dict())
        rec = RecoveredFile(
            index=file_index,
            filename=filename,
            type=result.display_type,
            extension=ext,
            offset_start=start,
            offset_end=end,
            size=len(payload),
            confidence=label_for(result.confidence),
            sha256=sha256_bytes(payload),
            notes=notes,
            ai_confidence=result.confidence,
            entropy=result.entropy,
            recovery_method="ai_classified",
        )
        recovered.append(rec)
        claimed.append((start, end, result.display_type))
        _chain_log(
            "FILE_EXTRACTED",
            {
                "filename": filename,
                "type": result.display_type,
                "offset": start,
                "size": len(payload),
                "sha256": rec.sha256,
                "method": "ai_classified",
                "confidence": result.confidence,
            },
        )
        added += 1
        pos = end

    if progress_cb:
        progress_cb(f"AI classifier recovered {added} additional fragment(s).", 0.98)


def carve_image(
    image_path: str | Path,
    out_dir: str | Path,
    progress_cb: ProgressCallback = None,
    use_ai: bool = True,
) -> list[RecoveredFile]:
    """
    Scan `image_path` for known file signatures and write recovered files
    into `out_dir`. Returns a list of RecoveredFile metadata.

    Complexity (high level):
      Time   — O(N * K) where N is image size and K is number of signatures
               (K = 4). Each `find` walks the byte stream once per type.
      Space  — O(1) extra besides the mmap and the recovered files we write.
    For images up to ~200 MB this is comfortably interactive on a laptop.
    """
    image_path = Path(image_path)
    out_dir = Path(out_dir)
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")
    out_dir.mkdir(parents=True, exist_ok=True)

    if progress_cb:
        progress_cb("Opening image (read-only)...", 0.02)

    handle, view = _open_readonly_view(image_path)
    recovered: list[RecoveredFile] = []
    claimed_ranges: list[tuple[int, int, str]] = []
    _chain_log(
        "RECOVERY_STARTED",
        {"image": str(image_path), "out_dir": str(out_dir), "use_ai": use_ai},
    )

    try:
        data = view  # bytes-like
        image_size = len(data)
        n_sigs = len(SIGNATURES)

        for sig_index, sig in enumerate(SIGNATURES):
            if progress_cb:
                progress_cb(f"Scanning for {sig.name} signatures...", (sig_index + 1) / (n_sigs + 1))

            pos = 0
            while pos < image_size:
                pos = data.find(sig.header, pos)
                if pos == -1:
                    break

                end, confidence, notes = _locate_file_end(sig, data, pos)
                if end is None or _overlaps(pos, end, claimed_ranges, sig.name):
                    pos += 1
                    continue

                payload = bytes(data[pos:end])  # copy only the carved slice
                file_index = len(recovered) + 1
                filename = f"{file_index:04d}_{sig.name}_{pos:08x}.{sig.extension}"
                dest = out_dir / filename
                dest.write_bytes(payload)

                rec = RecoveredFile(
                    index=file_index,
                    filename=filename,
                    type=sig.name,
                    extension=sig.extension,
                    offset_start=pos,
                    offset_end=end,
                    size=len(payload),
                    confidence=confidence,
                    sha256=sha256_bytes(payload),
                    notes=notes,
                )
                recovered.append(rec)
                claimed_ranges.append((pos, end, sig.name))
                _chain_log(
                    "FILE_EXTRACTED",
                    {
                        "filename": filename,
                        "type": sig.name,
                        "offset": pos,
                        "size": len(payload),
                        "sha256": rec.sha256,
                        "method": "signature",
                    },
                )

                if len(recovered) >= MAX_RECOVERED_FILES:
                    if progress_cb:
                        progress_cb("Reached recovery cap.", 1.0)
                    return recovered

                # Jump to the end of this file so we don't re-hit its header.
                pos = end

        if use_ai and len(recovered) < MAX_RECOVERED_FILES:
            _ai_scan_unclaimed(data, claimed_ranges, out_dir, recovered, progress_cb)

        _chain_log(
            "RECOVERY_COMPLETED",
            {
                "image": str(image_path),
                "files": len(recovered),
                "by_type": count_by_type(recovered),
            },
        )
        if progress_cb:
            progress_cb("Carving complete.", 1.0)
        return recovered
    finally:
        # mmap must be closed before the file handle.
        if hasattr(view, "close"):
            view.close()
        handle.close()


def count_by_type(files: list[RecoveredFile]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in files:
        counts[item.type] = counts.get(item.type, 0) + 1
    return counts


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
