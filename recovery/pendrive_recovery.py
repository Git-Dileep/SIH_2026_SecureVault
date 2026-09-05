"""
Pendrive Recovery Module — Integrates Device Detection & PNG File Carving.
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from erasure.device_detection import StorageDevice, detect_removable_devices, wait_for_pendrive
from recovery.carving.png_carver import PNGCarver
from recovery.carving.base_carver import CarvedFile


class PendrivePNGRecoverer:
    """Manages detection of pendrives and executes forensic PNG carving."""

    def __init__(self, output_base_dir: str = "recovered_pngs", verify_crc: bool = True):
        self.output_base_dir = Path(output_base_dir)
        self.carver = PNGCarver(verify_crc=verify_crc)

    def select_or_wait_device(
        self,
        specific_drive: Optional[str] = None,
        watch: bool = False,
        timeout: Optional[float] = None,
    ) -> StorageDevice:
        """Finds or waits for a pendrive."""
        if specific_drive:
            drive_clean = specific_drive.strip().rstrip("\\/").upper()
            if not drive_clean.endswith(":"):
                drive_clean += ":"
            from erasure.device_detection import detect_all_devices

            for dev in detect_all_devices():
                if dev.drive_letter.upper() == drive_clean:
                    if not dev.is_removable:
                        raise ValueError(f"Security Exception: Drive {drive_clean} is a FIXED/LOCAL drive. This tool strictly allows access to removable pendrives only.")
                    return dev
            
            # Refuse access if the drive cannot be verified as removable
            raise ValueError(f"Device {drive_clean} not found or could not be verified as a removable pendrive.")

        removables = detect_removable_devices()
        if removables and not watch:
            return removables[0]

        print("[*] Monitoring for inserted pendrive (plug in your USB drive now)...")
        return wait_for_pendrive(
            poll_interval=1.0,
            timeout=timeout,
            on_poll=lambda tick: print(f"[*] Waiting for pendrive... ({tick}s)", end="\r"),
        )

    def recover(
        self,
        device: StorageDevice,
        max_scan_bytes: Optional[int] = None,
        chunk_size: int = 4 * 1024 * 1024,
    ) -> Dict[str, Any]:
        """
        Executes PNG recovery on the given storage device.
        Attempts raw volume reading, with a fallback to cluster file scanning if permissions restrict raw access.
        """
        if not device.is_removable:
            raise PermissionError(f"Security Policy Violation: Drive {device.drive_letter} is a FIXED/LOCAL disk. Recovery is strictly limited to removable USB pendrives.")
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = device.drive_letter.replace(":", "")
        out_dir = self.output_base_dir / f"recovery_{safe_name}_{timestamp}"
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[+] Target Device: {device}")
        print(f"[+] Output Directory: {out_dir.resolve()}")

        recovered_files: List[CarvedFile] = []
        raw_target = device.raw_path

        # Attempt raw sector carving first
        can_read_raw = False
        try:
            with open(raw_target, "rb") as test_f:
                # Read 512 bytes (boot sector), then a full chunk to ensure we truly have bulk read permissions.
                # Windows often allows reading the boot sector without Admin, but denies bulk reads.
                test_f.read(512)
                test_f.read(chunk_size)
                can_read_raw = True
        except PermissionError:
            print("[!] Raw sector access requires Administrator privileges.")
            print("[*] Falling back to direct volume file structure scan...")
        except Exception as e:
            print(f"[!] Could not open raw device {raw_target}: {e}")

        if can_read_raw:
            print(f"[+] Scanning raw disk sectors at {raw_target}...")
            with open(raw_target, "rb") as stream:
                for carved in self.carver.carve_stream(stream, chunk_size=chunk_size):
                    recovered_files.append(carved)
                    idx = len(recovered_files)
                    filename = f"carved_{idx:04d}_offset_{carved.offset}.png"
                    (out_dir / filename).write_bytes(carved.data)
                    dim = f"{carved.metadata.get('width', '?')}x{carved.metadata.get('height', '?')}"
                    print(
                        f"    -> [Recovered #{idx:03d}] Offset {carved.offset:#010x} | "
                        f"Size: {carved.size:,} bytes | Dim: {dim} | CRC: {'VALID' if carved.is_valid else 'INVALID'}"
                    )
                    if max_scan_bytes and stream.tell() >= max_scan_bytes:
                        break
        else:
            # Filesystem level scan for PNGs (including corrupted, hidden, or deleted headers)
            print(f"[+] Scanning filesystem tree and files on {device.mount_point}...")
            count = 0
            for root, _, files in os.walk(device.mount_point):
                for f in files:
                    full_path = os.path.join(root, f)
                    try:
                        with open(full_path, "rb") as file_stream:
                            for carved in self.carver.carve_stream(file_stream, chunk_size=chunk_size):
                                count += 1
                                recovered_files.append(carved)
                                filename = f"carved_{count:04d}_{Path(f).stem}_offset_{carved.offset}.png"
                                (out_dir / filename).write_bytes(carved.data)
                                print(f"    -> [Extracted #{count:03d}] From {f} | Size: {carved.size:,} bytes")
                    except Exception:
                        continue

        summary = {
            "device": str(device),
            "target": raw_target if can_read_raw else device.mount_point,
            "raw_access": can_read_raw,
            "output_directory": str(out_dir.resolve()),
            "total_recovered": len(recovered_files),
            "valid_png_count": sum(1 for f in recovered_files if f.is_valid),
            "total_recovered_bytes": sum(f.size for f in recovered_files),
        }
        print("\n" + "=" * 50)
        print("RECOVERY COMPLETE")
        print(f"Total PNGs Recovered: {summary['total_recovered']}")
        print(f"Verified CRC PNGs : {summary['valid_png_count']}")
        print(f"Output Saved To   : {summary['output_directory']}")
        print("=" * 50)
        return summary
