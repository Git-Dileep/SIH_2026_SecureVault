#!/usr/bin/env python3
"""
selftest.py — Tiny end-to-end check that does not need the 64 MiB demo image.

Builds a 2 MiB zero image, plants one of each type, carves, and asserts
hashes match. Run this if you change carver.py.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from carver import carve_image, sha256_bytes
from generate_test_image import make_jpeg, make_pdf, make_png, make_zip


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        samples = tmp_path / "samples"
        samples.mkdir()
        png = samples / "a.png"
        jpg = samples / "a.jpg"
        pdf = samples / "a.pdf"
        zpath = samples / "a.zip"
        make_png(png, 16, 16, lambda x, y: (255, 0, 0))
        make_jpeg(jpg, png)
        make_pdf(pdf, "Selftest", ["ok"])
        make_zip(zpath, {"n.txt": "hello carving\n"})

        blobs = [
            ("JPEG", jpg.read_bytes(), 64 * 1024),
            ("PNG", png.read_bytes(), 256 * 1024),
            ("PDF", pdf.read_bytes(), 512 * 1024),
            ("ZIP", zpath.read_bytes(), 768 * 1024),
        ]

        image = tmp_path / "tiny.img"
        with open(image, "wb") as handle:
            handle.truncate(2 * 1024 * 1024)
            for _typ, blob, offset in blobs:
                handle.seek(offset)
                handle.write(blob)

        out = tmp_path / "out"
        recovered = carve_image(image, out)
        by_type = {item.type: item for item in recovered}

        assert len(recovered) >= 4, f"expected >= 4 files, got {len(recovered)}"
        for typ, blob, offset in blobs:
            item = by_type.get(typ)
            assert item is not None, f"missing {typ}"
            assert item.offset_start == offset, f"{typ} offset {item.offset_start} != {offset}"
            assert item.sha256 == sha256_bytes(blob), f"{typ} hash mismatch"
            print(f"OK  {typ:4s} @ {offset}  {item.filename}  {item.confidence}")

        print("selftest passed")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
