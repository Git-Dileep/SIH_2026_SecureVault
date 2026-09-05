"""
Unit tests for PNG Carver.
"""

import io
import struct
import zlib
import unittest

from recovery.carving.png_carver import PNGCarver, PNG_SIGNATURE


def generate_minimal_png() -> bytes:
    """Generates a minimal valid 1x1 PNG in bytes with proper CRC."""
    # Signature
    out = bytearray(PNG_SIGNATURE)

    # IHDR chunk: width=1, height=1, bit_depth=8, color_type=2 (Truecolor), comp=0, filt=0, inter=0
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    out.extend(struct.pack(">I4s", len(ihdr_data), b"IHDR"))
    out.extend(ihdr_data)
    out.extend(struct.pack(">I", ihdr_crc))

    # IDAT chunk: 1x1 raw pixel data compressed with zlib
    raw_scanline = b"\x00\xff\x00\x00"  # filter type 0 + RGB (255, 0, 0)
    compressed = zlib.compress(raw_scanline)
    idat_crc = zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF
    out.extend(struct.pack(">I4s", len(compressed), b"IDAT"))
    out.extend(compressed)
    out.extend(struct.pack(">I", idat_crc))

    # IEND chunk
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    out.extend(struct.pack(">I4s", 0, b"IEND"))
    out.extend(struct.pack(">I", iend_crc))

    return bytes(out)


class TestPNGCarver(unittest.TestCase):
    def setUp(self):
        self.carver = PNGCarver(verify_crc=True)
        self.valid_png = generate_minimal_png()

    def test_validate_valid_png(self):
        self.assertTrue(self.carver.validate(self.valid_png))

    def test_carve_from_simulated_raw_drive(self):
        # Simulate disk sector: 1024 bytes junk + PNG + 2048 bytes junk
        garbage_before = b"\xaa" * 1024
        garbage_after = b"\x55" * 2048
        simulated_disk = garbage_before + self.valid_png + garbage_after

        stream = io.BytesIO(simulated_disk)
        carved_files = list(self.carver.carve_stream(stream))

        self.assertEqual(len(carved_files), 1)
        carved = carved_files[0]
        self.assertEqual(carved.offset, 1024)
        self.assertEqual(carved.size, len(self.valid_png))
        self.assertEqual(carved.data, self.valid_png)
        self.assertTrue(carved.is_valid)
        self.assertEqual(carved.metadata["width"], 1)
        self.assertEqual(carved.metadata["height"], 1)

    def test_corrupted_crc_rejected_or_flagged(self):
        # Corrupt one byte in IDAT
        corrupted = bytearray(self.valid_png)
        corrupted[35] = (corrupted[35] + 1) % 256
        self.assertFalse(self.carver.validate(bytes(corrupted)))


if __name__ == "__main__":
    unittest.main()
