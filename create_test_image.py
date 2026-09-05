"""
Creates a mock disk image file containing a hidden PNG for testing the carver.
"""
import os
import sys
from pathlib import Path

# Add project root to sys.path so we can import our test helper
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tests.carving.test_png_carver import generate_minimal_png

def create_test_image(filename="mock_evidence.dd"):
    print(f"[*] Generating mock disk image: {filename}")
    with open(filename, "wb") as f:
        # Write 1MB of junk data
        f.write(os.urandom(1024 * 1024))
        
        # Inject the valid PNG
        print("[-] Injecting hidden PNG file at offset 1MB...")
        f.write(generate_minimal_png())
        
        # Write another 2MB of junk data
        f.write(os.urandom(2 * 1024 * 1024))
        
    print(f"[+] Done! Created {filename} ({os.path.getsize(filename) / (1024*1024):.2f} MB)")
    print(f"[>] To test recovery, run: python recover_pendrive.py --image {filename}")

if __name__ == "__main__":
    create_test_image()
