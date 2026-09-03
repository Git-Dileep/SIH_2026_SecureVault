# Recovery backend

This folder is the working recovery engine (from `file-recov`).

Run commands from **this directory**:

```bash
cd recovery

# demo disk image (once)
python3 generate_test_image.py

# API for the React UI
python3 server.py                 # http://127.0.0.1:8000/api/v1

# CLI
python3 main.py testdata/synthetic_disk.img recovered/

# Tkinter GUI
python3 gui.py

# smoke test
python3 selftest.py
```

The web console lives in `../frontend`. Start the API first, then `npm run dev` there.
