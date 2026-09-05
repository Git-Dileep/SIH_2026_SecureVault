#!/usr/bin/env python3
"""
main.py — Command-line interface for ForensicRecover.

Example:
    python main.py testdata/synthetic_disk.img recovered/
    python main.py testdata/synthetic_disk.img recovered/ --report recovered/case_report.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from carver import carve_image, sha256_file, count_by_type, TOOL_NAME, TOOL_VERSION
from report import write_reports


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=f"{TOOL_NAME} {TOOL_VERSION} — signature-based file carving from a raw disk image.",
    )
    parser.add_argument("image", help="Path to the forensic image (.img / .dd / any raw bytes file)")
    parser.add_argument("out_dir", help="Folder where recovered files and reports will be written")
    parser.add_argument(
        "--report",
        default=None,
        help="JSON report path (default: <out_dir>/case_report.json)",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Do not write the HTML report",
    )
    return parser.parse_args(argv)


def run(image: str, out_dir: str, report_path: str | None = None, write_html: bool = True) -> dict:
    image_path = Path(image)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"[{TOOL_NAME}] Opening evidence READ-ONLY: {image_path}")
    print(f"[{TOOL_NAME}] Computing SHA-256 of source image...")
    source_hash = sha256_file(image_path)
    image_size = image_path.stat().st_size
    print(f"[{TOOL_NAME}] SHA-256: {source_hash}")
    print(f"[{TOOL_NAME}] Size:    {image_size} bytes")
    print(f"[{TOOL_NAME}] Carving contiguous JPEG/PNG/PDF/ZIP files...")

    def progress(msg: str, _frac: float) -> None:
        print(f"    {msg}")

    recovered = carve_image(image_path, out_path, progress_cb=progress)
    by_type = count_by_type(recovered)

    json_path = Path(report_path) if report_path else out_path / "case_report.json"
    html_path = None if not write_html else json_path.with_suffix(".html")
    json_out, html_out = write_reports(
        source_image=image_path,
        source_hash_sha256=source_hash,
        files=recovered,
        json_path=json_path,
        html_path=html_path,
        image_size=image_size,
    )

    print()
    print("=" * 60)
    print(f" Recovered {len(recovered)} file(s)")
    for name, count in sorted(by_type.items()):
        print(f"   {name:6s} {count}")
    print(f" JSON report: {json_out}")
    if html_out:
        print(f" HTML report: {html_out}")
    print("=" * 60)
    return {
        "recovered": recovered,
        "source_hash": source_hash,
        "json_report": json_out,
        "html_report": html_out,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run(args.image, args.out_dir, args.report, write_html=not args.no_html)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
