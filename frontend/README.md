# Frontend — Person 4

React + Vite + TypeScript console for SecureVault.

The UI talks to the recovery backend in `../recovery` (`server.py` → `carver.py`).

```bash
# terminal 1 — recovery API
cd recovery
python3 server.py

# terminal 2 — web UI
cd frontend
npm install
npm run dev          # http://localhost:5173
```

`.env` sets `VITE_USE_MOCKS=false` and `VITE_API_BASE_URL=/api/v1`. Vite proxies `/api` to `http://127.0.0.1:8000`.

Load the synthetic demo image from the dashboard or evidence page to run a live carve.
