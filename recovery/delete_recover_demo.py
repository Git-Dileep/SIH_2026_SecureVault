#!/usr/bin/env python3
"""
Delete-then-recover demo (safe, workspace-only).

Theatre for judges:
  1. STAGE  — copy exhibits into a visible folder AND plant the same bytes
              on a raw disk image. A tiny directory table at byte 0 lists them
              (filename + offset), like a filesystem index.
  2. DELETE — remove the folder files AND zero the directory table.
              Payloads stay on the image (unallocated). The folder looks empty.
  3. RECOVER — carve the image. Files come back without the directory.

Never touches the operator's Desktop/Documents. Everything lives under
recovery/workspace/demo_delete_recover/.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
from pathlib import Path

from carver import sha256_bytes, utc_now_iso


ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"
DEMO_ROOT = ROOT / "workspace" / "demo_delete_recover"
EXHIBITS = DEMO_ROOT / "exhibits"
INBOX = DEMO_ROOT / "inbox"
IMAGE = DEMO_ROOT / "suspect_disk.img"
STATE = DEMO_ROOT / "state.json"

DIR_MAGIC = b"SVDIR001"
DIR_REGION = 64 * 1024
MIN_IMAGE_SIZE = 16 * 1024 * 1024
MAX_FILES = 12
MAX_FILE_BYTES = 12 * 1024 * 1024

EXHIBIT_SPECS = [
    ("photo_id.jpg", "JPEG"),
    ("logo_green.png", "PNG"),
    ("case_summary.pdf", "PDF"),
    ("notes.zip", "ZIP"),
]

TYPE_BY_EXT = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".pdf": "PDF",
    ".zip": "ZIP",
    ".docx": "ZIP",
    ".xlsx": "ZIP",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_samples() -> None:
    missing = [name for name, _typ in EXHIBIT_SPECS if not (SAMPLES / name).is_file()]
    if missing:
        from generate_test_image import build_samples

        build_samples()


def _pack_directory(entries: list[dict]) -> bytes:
    blob = bytearray(DIR_MAGIC + struct.pack("<I", len(entries)))
    for item in entries:
        name = item["filename"].encode("utf-8")[:64].ljust(64, b"\x00")
        digest = bytes.fromhex(item["sha256"])
        blob.extend(name)
        blob.extend(struct.pack("<QQ", int(item["offset"]), int(item["size"])))
        blob.extend(digest)
    if len(blob) > DIR_REGION:
        raise ValueError("Directory table larger than reserved region")
    return bytes(blob).ljust(DIR_REGION, b"\x00")


def parse_directory(image_path: Path | None = None) -> list[dict]:
    path = image_path or IMAGE
    if not path.is_file():
        return []
    with open(path, "rb") as handle:
        header = handle.read(DIR_REGION)
    if not header.startswith(DIR_MAGIC):
        return []
    count = struct.unpack_from("<I", header, 8)[0]
    entries = []
    cursor = 12
    record = 64 + 8 + 8 + 32
    for _ in range(count):
        if cursor + record > len(header):
            break
        name = header[cursor : cursor + 64].split(b"\x00", 1)[0].decode("utf-8", "replace")
        offset, size = struct.unpack_from("<QQ", header, cursor + 64)
        digest = header[cursor + 80 : cursor + 112].hex()
        entries.append(
            {
                "filename": name,
                "offset": offset,
                "size": size,
                "sha256": digest,
            }
        )
        cursor += record
    return entries


def _type_for(name: str) -> str:
    return TYPE_BY_EXT.get(Path(name).suffix.lower(), "BIN")


def _list_dir(folder: Path, url_prefix: str) -> list[dict]:
    if not folder.is_dir():
        return []
    rows = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        rows.append(
            {
                "filename": path.name,
                "type": _type_for(path.name),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
                "url": f"{url_prefix}/{path.name}",
                "carvable": _type_for(path.name) in {"JPEG", "PNG", "PDF", "ZIP"},
            }
        )
    return rows


def _folder_listing() -> list[dict]:
    return _list_dir(EXHIBITS, "/demo/exhibits")


def _inbox_listing() -> list[dict]:
    return _list_dir(INBOX, "/demo/inbox")


def _load_state() -> dict:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"phase": "empty"}


def _save_state(data: dict) -> None:
    DEMO_ROOT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def snapshot() -> dict:
    state = _load_state()
    directory = parse_directory()
    folder = _folder_listing()
    return {
        "phase": state.get("phase") or "empty",
        "updated_at": state.get("updated_at"),
        "image_path": str(IMAGE) if IMAGE.is_file() else None,
        "image_size": IMAGE.stat().st_size if IMAGE.is_file() else 0,
        "exhibits_folder": folder,
        "directory": directory,
        "planted": state.get("planted") or [],
        "inbox": _inbox_listing(),
        "source": state.get("source") or "samples",
        "deleted_at": state.get("deleted_at"),
        "evidence_id": state.get("evidence_id"),
        "note": (
            "Pick your own jpg/png/pdf/zip files, or use the built-in case files. "
            "Plant writes them onto a raw image. Delete wipes names. Recover carves bytes back."
        ),
    }


def add_uploaded_file(filename: str, data: bytes) -> dict:
    """Queue an operator-chosen file to plant on the next disk image."""
    safe = Path(filename).name
    if not safe or safe in (".", ".."):
        raise ValueError("File has no name")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"{safe} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MiB")
    INBOX.mkdir(parents=True, exist_ok=True)
    if len(_inbox_listing()) >= MAX_FILES:
        raise ValueError(f"At most {MAX_FILES} files in one demo image")
    dest = INBOX / safe
    dest.write_bytes(data)
    state = _load_state()
    if state.get("phase") in (None, "empty"):
        state["phase"] = "picking"
        state["updated_at"] = utc_now_iso()
        _save_state(state)
    return snapshot()


def remove_uploaded_file(filename: str) -> dict:
    dest = (INBOX / Path(filename).name).resolve()
    try:
        dest.relative_to(INBOX.resolve())
    except ValueError as exc:
        raise PermissionError("Invalid filename") from exc
    if dest.is_file():
        dest.unlink()
    return snapshot()


def stage(use_samples: bool = False) -> dict:
    """Create visible exhibits + raw image with a live directory table."""
    DEMO_ROOT.mkdir(parents=True, exist_ok=True)
    sources: list[tuple[str, bytes, str]] = []
    inbox = list(INBOX.iterdir()) if INBOX.is_dir() else []
    inbox_files = [p for p in inbox if p.is_file() and not p.name.startswith(".")]
    if use_samples:
        source = "samples"
        _ensure_samples()
        for name, typ in EXHIBIT_SPECS:
            sources.append((name, (SAMPLES / name).read_bytes(), typ))
    elif inbox_files:
        source = "upload"
        for path in sorted(inbox_files):
            sources.append((path.name, path.read_bytes(), _type_for(path.name)))
    else:
        raise ValueError("Drop jpg/png/pdf/zip files first, or click Use built-in case files.")

    if not sources:
        raise ValueError("Add at least one file, or use the built-in case files.")

    if EXHIBITS.exists():
        shutil.rmtree(EXHIBITS)
    EXHIBITS.mkdir(parents=True, exist_ok=True)

    planted: list[dict] = []
    offset = 1 * 1024 * 1024
    layout: list[tuple[int, bytes, dict]] = []
    for name, blob, typ in sources:
        dest = EXHIBITS / name
        dest.write_bytes(blob)
        meta = {
            "filename": name,
            "type": typ,
            "offset": offset,
            "size": len(blob),
            "sha256": sha256_bytes(blob),
            "carvable": typ in {"JPEG", "PNG", "PDF", "ZIP"},
        }
        planted.append(meta)
        layout.append((offset, blob, meta))
        offset = ((offset + len(blob) + 1024 * 1024 - 1) // (1024 * 1024)) * (1024 * 1024)

    image_size = max(MIN_IMAGE_SIZE, offset + 1024 * 1024)
    with open(IMAGE, "wb") as handle:
        handle.truncate(image_size)
        for off, blob, _meta in layout:
            handle.seek(off)
            handle.write(blob)
        handle.seek(0)
        handle.write(_pack_directory(planted))

    state = {
        "phase": "staged",
        "updated_at": utc_now_iso(),
        "planted": planted,
        "source": source,
        "deleted_at": None,
        "evidence_id": None,
    }
    _save_state(state)
    return snapshot()


def delete_exhibits() -> dict:
    """Wipe the folder listing and the on-image directory. Payloads stay."""
    if not IMAGE.is_file():
        raise FileNotFoundError("Stage the demo first.")
    if EXHIBITS.is_dir():
        for path in EXHIBITS.iterdir():
            if path.is_file():
                path.unlink()
    with open(IMAGE, "r+b") as handle:
        handle.seek(0)
        handle.write(b"\x00" * DIR_REGION)
        handle.flush()
    state = _load_state()
    state["phase"] = "deleted"
    state["updated_at"] = utc_now_iso()
    state["deleted_at"] = state["updated_at"]
    _save_state(state)
    return snapshot()


def reset() -> dict:
    if DEMO_ROOT.exists():
        shutil.rmtree(DEMO_ROOT)
    return snapshot()


def image_path() -> Path:
    if not IMAGE.is_file():
        raise FileNotFoundError("Stage the demo first.")
    return IMAGE


def mark_recovering(evidence_id: str) -> dict:
    state = _load_state()
    state["phase"] = "recovering"
    state["evidence_id"] = evidence_id
    state["updated_at"] = utc_now_iso()
    _save_state(state)
    return snapshot()
