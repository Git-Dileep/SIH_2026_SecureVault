#!/usr/bin/env python3
"""
SecureVault - Pendrive PNG Recovery Tool
Attempts to auto-detect inserted USB pendrive and recover/carve PNG images from it.
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from erasure.device_detection import detect_all_devices, detect_removable_devices
from recovery.pendrive_recovery import PendrivePNGRecoverer
from recovery.carving.png_carver import PNGCarver


def main():
    parser = argparse.ArgumentParser(
        description="SecureVault: Forensic Pendrive PNG File Recovery Tool",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--drive",
        "-d",
        type=str,
        help="Target drive letter (e.g. 'E:' or 'E') or raw device path (e.g. r'\\\\.\\E:').",
    )
    parser.add_argument(
        "--image",
        "-i",
        type=str,
        help="Carve PNGs directly from a raw disk image file (e.g. evidence.dd / backup.img).",
    )
    parser.add_argument(
        "--watch",
        "-w",
        action="store_true",
        help="Wait actively and monitor for a new USB pendrive to be plugged in.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="recovered_pngs",
        help="Directory where recovered PNG images will be saved (default: 'recovered_pngs').",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List all detected storage devices and exit.",
    )
    parser.add_argument(
        "--no-crc-check",
        action="store_true",
        help="Disable strict CRC32 chunk verification (useful for recovering partially corrupted PNGs).",
    )

    args = parser.parse_args()

    print("==================================================")
    print("      SecureVault Forensic PNG Recovery Tool      ")
    print("==================================================")

    # If --list is requested
    if args.list:
        print("[*] Enumerating storage devices:")
        all_devs = detect_all_devices()
        if not all_devs:
            print("    No devices found.")
        for d in all_devs:
            tag = "[USB/REMOVABLE]" if d.is_removable else "[FIXED/LOCAL]"
            print(f"    {tag} {d}")
        sys.exit(0)

    recoverer = PendrivePNGRecoverer(
        output_base_dir=args.output,
        verify_crc=not args.no_crc_check,
    )

    # Disk Image file mode
    if args.image:
        img_path = Path(args.image)
        if not img_path.exists():
            print(f"[!] Error: Disk image file '{args.image}' not found.")
            sys.exit(1)

        print(f"[+] Carving PNG files directly from image: {img_path.resolve()}")
        carver = PNGCarver(verify_crc=not args.no_crc_check)
        out_path = Path(args.output) / f"recovered_{img_path.stem}"
        results = carver.carve_file_or_device(str(img_path), output_dir=str(out_path))
        print(f"\n[+] Recovery finished! Saved {len(results)} PNG(s) to: {out_path.resolve()}")
        sys.exit(0)

    # Pendrive mode
    try:
        device = recoverer.select_or_wait_device(
            specific_drive=args.drive,
            watch=args.watch,
        )
        recoverer.recover(device)
    except KeyboardInterrupt:
        print("\n[*] Operation cancelled by user.")
    except Exception as e:
        print(f"\n[!] Error during recovery: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
