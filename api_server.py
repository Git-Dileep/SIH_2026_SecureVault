import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from pathlib import Path

from erasure.device_detection import detect_removable_devices, StorageDevice
from recovery.pendrive_recovery import PendrivePNGRecoverer

app = FastAPI(title="SecureVault Pendrive Recovery API")

# Allow CORS for frontend interaction during dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup output directory
OUTPUT_DIR = Path("recovered_pngs")
OUTPUT_DIR.mkdir(exist_ok=True)

# Mount static files to serve recovered images directly
app.mount("/images", StaticFiles(directory=str(OUTPUT_DIR)), name="images")

class RecoveryRequest(BaseModel):
    drive_letter: str

def get_devices_with_mock():
    """Helper to get devices and inject a mock device for testing if mock_evidence.dd exists."""
    devices = detect_removable_devices()
    
    mock_file = Path("mock_evidence.dd")
    if mock_file.exists():
        mock_dev = StorageDevice(
            device_id="MOCK",
            drive_letter="M:",
            mount_point=str(mock_file.resolve()),
            raw_path=str(mock_file.resolve()),
            is_removable=True,
            volume_label="MOCK_EVIDENCE_DD",
            file_system="RAW",
            total_bytes=mock_file.stat().st_size,
            free_bytes=0,
        )
        devices.append(mock_dev)
    return devices

@app.get("/api/devices")
def get_devices():
    """Returns a list of connected pendrives."""
    devices = get_devices_with_mock()
    return {"devices": [d.__dict__ for d in devices]}

@app.post("/api/recover")
def recover_pngs(req: RecoveryRequest):
    """Executes the PNG recovery process on the specified drive."""
    recoverer = PendrivePNGRecoverer(output_base_dir=str(OUTPUT_DIR))
    
    devices = get_devices_with_mock()
    target = None
    for d in devices:
        if d.drive_letter.upper() == req.drive_letter.upper():
            target = d
            break
            
    if not target:
        raise HTTPException(status_code=404, detail="Drive not found")
        
    try:
        summary = recoverer.recover(target)
        
        # Collect generated image URLs
        out_dir = Path(summary["output_directory"])
        image_urls = []
        if out_dir.exists():
            for file in out_dir.iterdir():
                if file.suffix.lower() == ".png":
                    # Generate URL path relative to the static mount
                    rel_path = file.relative_to(OUTPUT_DIR.resolve())
                    url = f"/images/{rel_path.as_posix()}"
                    image_urls.append(url)
                    
        summary["image_urls"] = image_urls
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
