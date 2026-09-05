"""
Device Detection — Owner: Person 5

Detects and enumerates attached storage devices and their properties
(type, capacity, interface, partitions). Provides USB pendrive detection
and insertion monitoring.
"""

import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Callable


@dataclass
class StorageDevice:
    device_id: str
    drive_letter: str
    mount_point: str
    raw_path: str
    is_removable: bool
    volume_label: str
    file_system: str
    total_bytes: int
    free_bytes: int

    def __str__(self) -> str:
        size_gb = self.total_bytes / (1024**3)
        return (
            f"[{self.drive_letter}] '{self.volume_label}' ({self.file_system}) "
            f"- {size_gb:.2f} GB total, Removable: {self.is_removable}"
        )


def _get_windows_drives() -> List[StorageDevice]:
    """Enumerates Windows drives using kernel32 API with ctypes."""
    import ctypes

    kernel32 = ctypes.windll.kernel32
    devices = []

    # Get bitmask of logical drives
    bitmask = kernel32.GetLogicalDrives()

    for i in range(26):
        if bitmask & (1 << i):
            drive_letter = f"{chr(65 + i)}:"
            mount_point = f"{drive_letter}\\"
            drive_type = kernel32.GetDriveTypeW(mount_point)

            # DRIVE_REMOVABLE = 2, DRIVE_FIXED = 3
            is_removable = (drive_type == 2)

            # Volume Information
            vol_name = ctypes.create_unicode_buffer(261)
            fs_name = ctypes.create_unicode_buffer(261)
            serial_number = ctypes.c_ulong()
            max_component_len = ctypes.c_ulong()
            flags = ctypes.c_ulong()

            res = kernel32.GetVolumeInformationW(
                mount_point,
                vol_name,
                ctypes.sizeof(vol_name),
                ctypes.byref(serial_number),
                ctypes.byref(max_component_len),
                ctypes.byref(flags),
                fs_name,
                ctypes.sizeof(fs_name),
            )

            label = vol_name.value if res else ""
            fs = fs_name.value if res else "Unknown"

            # Disk Free Space
            free_bytes_avail = ctypes.c_ulonglong()
            total_bytes = ctypes.c_ulonglong()
            total_free_bytes = ctypes.c_ulonglong()

            res_space = kernel32.GetDiskFreeSpaceExW(
                mount_point,
                ctypes.byref(free_bytes_avail),
                ctypes.byref(total_bytes),
                ctypes.byref(total_free_bytes),
            )

            total = total_bytes.value if res_space else 0
            free = total_free_bytes.value if res_space else 0

            devices.append(
                StorageDevice(
                    device_id=drive_letter,
                    drive_letter=drive_letter,
                    mount_point=mount_point,
                    raw_path=rf"\\.\{drive_letter}",
                    is_removable=is_removable,
                    volume_label=label,
                    file_system=fs,
                    total_bytes=total,
                    free_bytes=free,
                )
            )

    return devices


def detect_all_devices() -> List[StorageDevice]:
    """Enumerates all available storage devices across the operating system."""
    if sys.platform == "win32":
        return _get_windows_drives()
    else:
        # Fallback for non-Windows (stub / standard mounts)
        return []


def detect_removable_devices() -> List[StorageDevice]:
    """Returns only removable drives (such as USB pendrives and flash drives)."""
    return [d for d in detect_all_devices() if d.is_removable]


def wait_for_pendrive(
    poll_interval: float = 1.0,
    timeout: Optional[float] = None,
    on_poll: Optional[Callable[[int], None]] = None,
) -> StorageDevice:
    """
    Blocks and continuously monitors for a newly inserted or currently connected USB pendrive.
    Returns the StorageDevice when found.
    """
    initial_drives = {d.drive_letter for d in detect_removable_devices()}
    start_time = time.time()
    ticks = 0

    # If a removable drive is already connected, return it
    current_removable = detect_removable_devices()
    if current_removable:
        return current_removable[0]

    while True:
        if timeout and (time.time() - start_time) > timeout:
            raise TimeoutError("Timed out waiting for pendrive insertion.")

        time.sleep(poll_interval)
        ticks += 1
        if on_poll:
            on_poll(ticks)

        current_drives = detect_removable_devices()
        for dev in current_drives:
            if dev.drive_letter not in initial_drives or len(current_drives) > len(initial_drives):
                return dev
            return dev
