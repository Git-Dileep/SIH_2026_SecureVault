#!/usr/bin/env python3
"""
generate_test_image.py — Build a synthetic raw disk image with planted files.

What this does:
  1. Creates a handful of *valid* sample files (PNG, JPEG, PDF, ZIP).
  2. Creates a sparse-ish raw image filled with zeros (default 64 MiB).
  3. Injects the sample files at known offsets.
  4. Writes testdata/injection_log.json — the ground truth we later compare
     against the carver's output.

Why zeros? Random bytes can accidentally contain magic numbers (false
positives). Zeros never look like JPEG/PNG/PDF/ZIP headers.

The "lost to care" analogue here: these files represent data that was
deleted from a filesystem. The directory entry is gone, but the raw bytes
are still on disk. Carving finds them without needing FAT/NTFS/HFS metadata.
"""

from __future__ import annotations

import json
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

from carver import sha256_bytes, utc_now_iso


ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"
TESTDATA = ROOT / "testdata"

DEFAULT_IMAGE_SIZE = 64 * 1024 * 1024  # 64 MiB — bump with --size-mb


# ---------------------------------------------------------------------------
# Sample file builders (stdlib only; JPEG may use macOS `sips` if present)
# ---------------------------------------------------------------------------

def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def make_png(path: Path, width: int, height: int, rgb_at) -> None:
    """Write a valid 8-bit RGB PNG. rgb_at(x, y) -> (r, g, b)."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type None
        for x in range(width):
            r, g, b = rgb_at(x, y)
            raw.extend((r & 255, g & 255, b & 255))
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    body = (
        signature
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(body)


def make_pdf(path: Path, title: str, lines: list[str]) -> None:
    """Write a minimal but valid PDF 1.4 with Helvetica text."""
    text_ops = [f"BT /F1 16 Tf 72 720 Td ({_pdf_escape(title)}) Tj"]
    for i, line in enumerate(lines):
        # Move down 22 points per line.
        text_ops.append(f"0 -22 Td ({_pdf_escape(line)}) Tj")
    stream = "\n".join(text_ops) + "\nET\n"
    stream_bytes = stream.encode("latin-1", errors="replace")

    # We build the file piece by piece so xref offsets are exact.
    parts: list[bytes] = []

    def add(obj: bytes) -> None:
        parts.append(obj)

    add(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")  # binary marker comment
    add(f"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n".encode())
    add(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    add(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
    )
    add(
        f"4 0 obj << /Length {len(stream_bytes)} >> stream\n".encode()
        + stream_bytes
        + b"endstream\nendobj\n"
    )
    add(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")

    file_so_far = b"".join(parts)
    # Object 0 is the free xref head. Objects 1-5 start after the header.
    header = parts[0]
    obj_starts = []
    cursor = len(header)
    for chunk in parts[1:]:
        obj_starts.append(cursor)
        cursor += len(chunk)

    xref = [b"xref\n0 6\n", b"0000000000 65535 f \n"]
    for start in obj_starts:
        xref.append(f"{start:010d} 00000 n \n".encode())
    xref_block = b"".join(xref)
    trailer = (
        f"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{len(file_so_far)}\n%%EOF\n".encode()
    )
    path.write_bytes(file_so_far + xref_block + trailer)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_zip(path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def _try_png_to_jpeg(png_path: Path, jpeg_path: Path) -> bool:
    """On macOS, `sips` can convert PNG → JPEG. Returns True on success."""
    sips = Path("/usr/bin/sips")
    if not sips.exists():
        return False
    try:
        subprocess.run(
            [str(sips), "-s", "format", "jpeg", str(png_path), "--out", str(jpeg_path)],
            check=True,
            capture_output=True,
        )
        return jpeg_path.is_file() and jpeg_path.stat().st_size > 0
    except (OSError, subprocess.CalledProcessError):
        return False


# Structurally valid JPEG (SOI + APP0 + SOS + EOI). Used only if `sips`
# is unavailable. On macOS the generator converts a real PNG so recovered
# JPEGs open in Preview.
_FALLBACK_JPEG = (
    b"\xff\xd8"
    b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00"
    b"\x00"
    b"\xff\xd9"
)


def make_jpeg(path: Path, source_png: Path | None = None) -> None:
    if source_png and _try_png_to_jpeg(source_png, path):
        return
    path.write_bytes(_FALLBACK_JPEG)


# ---------------------------------------------------------------------------
# Image construction
# ---------------------------------------------------------------------------

def build_samples() -> list[dict]:
    """Create sample files and return a list of {path, type} dicts."""
    SAMPLES.mkdir(parents=True, exist_ok=True)

    png_red = SAMPLES / "badge_red.png"
    png_blue = SAMPLES / "chart_blue.png"
    png_green = SAMPLES / "logo_green.png"
    make_png(png_red, 96, 96, lambda x, y: (200, 30, 30) if 20 < x < 76 and 20 < y < 76 else (40, 0, 0))
    make_png(png_blue, 80, 80, lambda x, y: (20, 40, 180) if (x - 40) ** 2 + (y - 40) ** 2 < 900 else (5, 8, 30))
    make_png(png_green, 64, 64, lambda x, y: (20, 160, 70) if (x // 8 + y // 8) % 2 == 0 else (10, 80, 30))

    jpg_a = SAMPLES / "photo_scene.jpg"
    jpg_b = SAMPLES / "photo_id.jpg"
    jpg_c = SAMPLES / "photo_lab.jpg"
    make_jpeg(jpg_a, png_red)
    make_jpeg(jpg_b, png_blue)
    make_jpeg(jpg_c, png_green)

    pdf_a = SAMPLES / "case_summary.pdf"
    pdf_b = SAMPLES / "chain_of_custody.pdf"
    make_pdf(
        pdf_a,
        "Case 2026-SIH-01 — Summary",
        [
            "Suspect workstation seized 2026-03-12.",
            "Raw image acquired with write-blocker (mock).",
            "This PDF is planted inside the synthetic disk image.",
        ],
    )
    make_pdf(
        pdf_b,
        "Chain of Custody Log",
        [
            "Item: 64 MiB synthetic raw image",
            "Handler: ForensicRecover MVP",
            "Hash recorded at acquisition time.",
        ],
    )

    zip_a = SAMPLES / "notes.zip"
    zip_b = SAMPLES / "exports.zip"
    make_zip(
        zip_a,
        {
            "readme.txt": "Investigator notes for SIH 2026.\nDo not modify the evidence image.\n",
            "todo.txt": "- Hash image\n- Carve files\n- Write report\n",
        },
    )
    make_zip(
        zip_b,
        {
            "hashes.txt": "placeholder hashes\n",
            "manifest.txt": "export bundle created for demo\n",
        },
    )

    return [
        {"path": jpg_a, "type": "JPEG"},
        {"path": png_red, "type": "PNG"},
        {"path": pdf_a, "type": "PDF"},
        {"path": zip_a, "type": "ZIP"},
        {"path": jpg_b, "type": "JPEG"},
        {"path": png_blue, "type": "PNG"},
        {"path": pdf_b, "type": "PDF"},
        {"path": zip_b, "type": "ZIP"},
        {"path": jpg_c, "type": "JPEG"},
        {"path": png_green, "type": "PNG"},
    ]


# Known offsets (bytes). Chosen so files do not overlap and sit on round
# numbers that are easy to point at during a live demo.
DEFAULT_OFFSETS = [
    1 * 1024 * 1024,       # 1 MiB
    3 * 1024 * 1024,       # 3 MiB
    5 * 1024 * 1024 + 512 * 1024,  # 5.5 MiB
    8 * 1024 * 1024,       # 8 MiB
    11 * 1024 * 1024,      # 11 MiB
    14 * 1024 * 1024,      # 14 MiB
    18 * 1024 * 1024,      # 18 MiB
    22 * 1024 * 1024,      # 22 MiB
    26 * 1024 * 1024,      # 26 MiB
    30 * 1024 * 1024,      # 30 MiB
]


def inject_image(image_size: int = DEFAULT_IMAGE_SIZE) -> Path:
    samples = build_samples()
    if image_size <= max(DEFAULT_OFFSETS) + 2 * 1024 * 1024:
        raise ValueError("Image is too small for the planned injection offsets.")

    TESTDATA.mkdir(parents=True, exist_ok=True)
    image_path = TESTDATA / "synthetic_disk.img"

    print(f"Creating zero-filled image ({image_size} bytes) at {image_path}")
    with open(image_path, "wb") as handle:
        handle.truncate(image_size)

        log_files = []
        for offset, sample in zip(DEFAULT_OFFSETS, samples):
            blob = Path(sample["path"]).read_bytes()
            handle.seek(offset)
            handle.write(blob)
            entry = {
                "id": len(log_files) + 1,
                "type": sample["type"],
                "source_file": str(Path(sample["path"]).relative_to(ROOT)),
                "offset_start": offset,
                "offset_end": offset + len(blob),
                "size": len(blob),
                "sha256": sha256_bytes(blob),
            }
            log_files.append(entry)
            print(
                f"  planted {entry['type']:4s} at offset {offset} "
                f"({len(blob)} bytes) from {entry['source_file']}"
            )

    from carver import sha256_file

    image_hash = sha256_file(image_path)

    log = {
        "created_at": utc_now_iso(),
        "image_path": str(image_path.relative_to(ROOT)),
        "image_size_bytes": image_size,
        "image_sha256": image_hash,
        "fill": "0x00",
        "how_label_is_generated": (
            "Each planted file is a contiguous byte run at a known offset. "
            "There is no filesystem. A correct carver must report the same "
            "type, start offset, and SHA-256 as this log."
        ),
        "files": log_files,
    }
    log_path = TESTDATA / "injection_log.json"
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"Wrote ground truth: {log_path}")
    print(f"Image SHA-256: {image_hash}")
    return image_path


def main(argv: list[str] | None = None) -> int:
    size = DEFAULT_IMAGE_SIZE
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "--size-mb":
        size = int(args[1]) * 1024 * 1024
    elif args and args[0].startswith("--size-mb="):
        size = int(args[0].split("=", 1)[1]) * 1024 * 1024
    inject_image(size)
    print("\nNext steps:")
    print("  python main.py testdata/synthetic_disk.img recovered/")
    print("  python compare_results.py testdata/injection_log.json recovered/case_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
