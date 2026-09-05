"""
Base Carver — Owner: Person 2

Abstract base class for all file carvers. Defines the interface that
format-specific carvers (JPEG, PNG, etc.) must implement: header/footer
signature matching, fragment reassembly, and validation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO, Generator, Optional, List, Dict, Any
from pathlib import Path


@dataclass
class CarvedFile:
    file_type: str
    offset: int
    size: int
    data: bytes
    sha256: str
    is_valid: bool
    metadata: Dict[str, Any]


class BaseCarver(ABC):
    """Abstract base class for raw stream file carving."""

    @property
    @abstractmethod
    def file_type(self) -> str:
        """Returns the file extension / type name (e.g. 'png', 'jpg')."""
        pass

    @property
    @abstractmethod
    def header_signature(self) -> bytes:
        """Returns the magic header bytes for this file format."""
        pass

    @abstractmethod
    def validate(self, data: bytes) -> bool:
        """Validates the extracted file data integrity."""
        pass

    @abstractmethod
    def carve_stream(
        self, stream: BinaryIO, chunk_size: int = 4 * 1024 * 1024, max_file_size: int = 100 * 1024 * 1024
    ) -> Generator[CarvedFile, None, None]:
        """Carves files from a binary stream using buffered sliding-window scanning."""
        pass

    def carve_file_or_device(
        self, source_path: str, output_dir: Optional[str] = None
    ) -> List[CarvedFile]:
        """Carves files from a source file, disk image, or raw volume device."""
        results: List[CarvedFile] = []
        out_path = Path(output_dir) if output_dir else None
        if out_path:
            out_path.mkdir(parents=True, exist_ok=True)

        with open(source_path, "rb") as stream:
            for idx, carved in enumerate(self.carve_stream(stream), start=1):
                results.append(carved)
                if out_path and carved.is_valid:
                    filename = f"recovered_{idx:04d}_offset_{carved.offset}.{self.file_type}"
                    file_path = out_path / filename
                    file_path.write_bytes(carved.data)
        return results
