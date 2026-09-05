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

    def _try_parse_png_memory(self, buffer: bytearray, start_idx: int) -> Any:
        """Returns (png_data, meta, is_valid) or 'INVALID' or 'NEED_MORE'"""
        if len(buffer) - start_idx < 8:
            return "NEED_MORE"
            
        offset = start_idx + 8
        total_len = len(buffer)
        
        has_ihdr = False
        all_crc_valid = True
        metadata = {}
        
        while True:
            if offset + 8 > total_len:
                return "NEED_MORE"
                
            length, chunk_type = struct.unpack(">I4s", buffer[offset:offset+8])
            
            # Check if chunk length is reasonable and chunk type is valid ASCII
            if length > self._max_file_size or not all(65 <= b <= 90 or 97 <= b <= 122 for b in chunk_type):
                return "INVALID"
                
            if offset + 8 + length + 4 > total_len:
                return "NEED_MORE"
                
            chunk_data = buffer[offset+8 : offset+8+length]
            (chunk_crc,) = struct.unpack(">I", buffer[offset+8+length : offset+8+length+4])
            
            if self._verify_crc:
                calc_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
                if calc_crc != chunk_crc:
                    all_crc_valid = False
                    
            if chunk_type == IHDR_CHUNK_TYPE:
                has_ihdr = True
                metadata.update(self.parse_ihdr(chunk_data))
                
            offset += 8 + length + 4
            
            if chunk_type == IEND_CHUNK_TYPE:
                if has_ihdr:
                    png_data = bytes(buffer[start_idx:offset])
                    is_valid = all_crc_valid if self._verify_crc else True
                    return (png_data, metadata, is_valid)
                return "INVALID"

    def carve_stream(
        self,
        stream: BinaryIO,
        chunk_size: int = 1024 * 1024,
        max_file_size: int = 50 * 1024 * 1024,
    ) -> Generator[CarvedFile, None, None]:
        """
        Scans a binary stream using a sliding window for PNG headers,
        and extracts valid PNG files entirely in memory without seeking the physical disk.
        """
        self._max_file_size = max_file_size
        sig = self.header_signature

        buffer = bytearray()
        buffer_start_offset = 0

        while True:
            try:
                chunk = stream.read(chunk_size)
            except OSError as e:
                # Windows may throw PermissionError (Errno 13) when reading locked filesystem sectors 
                # (like MFT/FAT) if not running as Administrator. Skip the unreadable chunk!
                try:
                    # Advance the stream manually to bypass the locked region
                    stream.seek(chunk_size, 1)
                    continue
                except OSError:
                    # If we can't seek past it, we have to abort this stream
                    break

            if not chunk and len(buffer) == 0:
                break
            
            if chunk:
                buffer.extend(chunk)

            search_start = 0
            need_more_data = False

            while True:
                found_idx = buffer.find(sig, search_start)
                if found_idx == -1:
                    break

                res = self._try_parse_png_memory(buffer, found_idx)

                if res == "NEED_MORE":
                    if not chunk:  # EOF, can't get more data
                        search_start = found_idx + 1
                        continue
                    if len(buffer) - found_idx > self._max_file_size:
                        search_start = found_idx + 1
                        continue
                    
                    need_more_data = True
                    break  # Break out to read the next chunk
                
                elif res == "INVALID":
                    search_start = found_idx + 1
                
                else:
                    png_data, meta, is_valid = res
                    abs_file_offset = buffer_start_offset + found_idx
                    sha256 = hashlib.sha256(png_data).hexdigest()
                    meta["sha256"] = sha256
                    
                    yield CarvedFile(
                        file_type=self.file_type,
                        offset=abs_file_offset,
                        size=len(png_data),
                        data=png_data,
                        sha256=sha256,
                        is_valid=is_valid,
                        metadata=meta,
                    )
                    search_start = found_idx + len(png_data)

            if need_more_data:
                # Keep everything from found_idx onwards to continue parsing
                buffer_start_offset += found_idx
                buffer = buffer[found_idx:]
            else:
                # Discard processed bytes, keep overlap for cross-chunk signatures
                overlap = len(sig) - 1
                if len(buffer) > overlap:
                    buffer_start_offset += len(buffer) - overlap
                    buffer = buffer[-overlap:]
                else:
                    buffer_start_offset += len(buffer)
                    buffer = bytearray()
                    
            if not chunk:
                break
