"""
PNG Carver — Owner: Person 2

Carves PNG images from raw evidence streams by detecting the PNG signature
(89 50 4E 47 0D 0A 1A 0A) and IEND chunk. Validates chunk structure and
CRC checksums of recovered images.
"""

import hashlib
import struct
import zlib
from typing import BinaryIO, Generator, Optional, Tuple, Dict, Any

from recovery.carving.base_carver import BaseCarver, CarvedFile

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
IEND_CHUNK_TYPE = b"IEND"
IHDR_CHUNK_TYPE = b"IHDR"


class PNGCarver(BaseCarver):
    """Carver specialized in extracting and validating PNG images from binary streams."""

    def __init__(self, verify_crc: bool = True, max_file_size: int = 50 * 1024 * 1024):
        self._verify_crc = verify_crc
        self._max_file_size = max_file_size

    @property
    def file_type(self) -> str:
        return "png"

    @property
    def header_signature(self) -> bytes:
        return PNG_SIGNATURE

    def parse_ihdr(self, ihdr_data: bytes) -> Dict[str, Any]:
        """Extracts resolution and color properties from the IHDR chunk data."""
        if len(ihdr_data) < 13:
            return {}
        width, height, bit_depth, color_type, comp_method, filter_method, interlace = struct.unpack(
            ">IIBBBBB", ihdr_data[:13]
        )
        return {
            "width": width,
            "height": height,
            "bit_depth": bit_depth,
            "color_type": color_type,
            "compression_method": comp_method,
            "filter_method": filter_method,
            "interlace_method": interlace,
        }

    def validate(self, data: bytes) -> bool:
        """Verifies PNG signature, well-formed chunks, and CRC checksums."""
        if not data.startswith(PNG_SIGNATURE):
            return False

        offset = len(PNG_SIGNATURE)
        total_len = len(data)
        has_ihdr = False
        has_iend = False

        while offset + 8 <= total_len:
            length, chunk_type = struct.unpack(">I4s", data[offset : offset + 8])
            offset += 8

            if offset + length + 4 > total_len:
                return False

            chunk_data = data[offset : offset + length]
            offset += length

            (chunk_crc,) = struct.unpack(">I", data[offset : offset + 4])
            offset += 4

            # Verify chunk type is valid ASCII
            if not all(65 <= b <= 90 or 97 <= b <= 122 for b in chunk_type):
                return False

            if self._verify_crc:
                calc_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
                if calc_crc != chunk_crc:
                    return False

            if chunk_type == IHDR_CHUNK_TYPE:
                has_ihdr = True
            elif chunk_type == IEND_CHUNK_TYPE:
                has_iend = True
                break

        return has_ihdr and has_iend

    def _extract_png_at_offset(
        self, stream: BinaryIO, start_offset: int
    ) -> Optional[Tuple[bytes, Dict[str, Any], bool]]:
        """
        Attempts to parse a complete PNG starting at start_offset in stream.
        Returns (data, metadata, is_valid) or None.
        """
        current_pos = stream.tell()
        try:
            stream.seek(start_offset)
            header = stream.read(8)
            if header != PNG_SIGNATURE:
                return None

            png_bytes = bytearray(header)
            metadata: Dict[str, Any] = {}
            all_crc_valid = True
            has_ihdr = False

            while len(png_bytes) < self._max_file_size:
                chunk_header = stream.read(8)
                if len(chunk_header) < 8:
                    break

                length, chunk_type = struct.unpack(">I4s", chunk_header)

                # Check if chunk length is reasonable and chunk type is valid ASCII
                if length > self._max_file_size or not all(
                    65 <= b <= 90 or 97 <= b <= 122 for b in chunk_type
                ):
                    return None

                chunk_data = stream.read(length)
                if len(chunk_data) < length:
                    return None

                crc_bytes = stream.read(4)
                if len(crc_bytes) < 4:
                    return None

                (chunk_crc,) = struct.unpack(">I", crc_bytes)

                if self._verify_crc:
                    calc_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
                    if calc_crc != chunk_crc:
                        all_crc_valid = False

                png_bytes.extend(chunk_header)
                png_bytes.extend(chunk_data)
                png_bytes.extend(crc_bytes)

                if chunk_type == IHDR_CHUNK_TYPE:
                    has_ihdr = True
                    metadata.update(self.parse_ihdr(chunk_data))

                if chunk_type == IEND_CHUNK_TYPE:
                    if has_ihdr:
                        final_data = bytes(png_bytes)
                        is_valid = all_crc_valid if self._verify_crc else True
                        return final_data, metadata, is_valid
                    return None

            return None
        finally:
            stream.seek(current_pos)

    def carve_stream(
        self,
        stream: BinaryIO,
        chunk_size: int = 1024 * 1024,
        max_file_size: int = 50 * 1024 * 1024,
    ) -> Generator[CarvedFile, None, None]:
        """
        Scans a binary stream using a sliding window for PNG headers,
        and extracts valid PNG files without loading the entire stream into memory.
        """
        self._max_file_size = max_file_size
        sig = self.header_signature
        sig_len = len(sig)

        stream.seek(0, 2)
        total_stream_size = stream.tell()
        stream.seek(0)

        current_offset = 0
        overlap = sig_len - 1
        buffer = b""

        while current_offset < total_stream_size:
            chunk = stream.read(chunk_size)
            if not chunk:
                break

            data = buffer + chunk
            search_start = 0

            while True:
                found_idx = data.find(sig, search_start)
                if found_idx == -1:
                    break

                abs_file_offset = current_offset - len(buffer) + found_idx
                extracted = self._extract_png_at_offset(stream, abs_file_offset)

                if extracted is not None:
                    png_data, meta, is_valid = extracted
                    sha256 = hashlib.sha256(png_data).hexdigest()
                    meta["sha256"] = sha256
                    carved = CarvedFile(
                        file_type=self.file_type,
                        offset=abs_file_offset,
                        size=len(png_data),
                        data=png_data,
                        sha256=sha256,
                        is_valid=is_valid,
                        metadata=meta,
                    )
                    yield carved
                    # Advance search past this extracted file if it fit within data
                    search_start = found_idx + len(png_data)
                else:
                    search_start = found_idx + 1

            if len(data) >= overlap:
                buffer = data[-overlap:]
            else:
                buffer = data

            current_offset = stream.tell()
