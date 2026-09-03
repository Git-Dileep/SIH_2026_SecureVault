# SecureVault

**Forensic Recovery + Secure Erasure Prototype**

SecureVault is a forensic-grade tool that combines two core pipelines:

1. **Recovery Pipeline** — Import evidence images, carve deleted files, and use AI-assisted confidence scoring to rank recovered artifacts by likelihood of integrity.
2. **Erasure Pipeline** — Securely sanitize storage media following NIST SP 800-88 guidelines, verify the erasure, and generate auditable certificates of destruction.

Both pipelines feed into a unified **audit log** for chain-of-custody compliance, and a **web frontend** provides a single pane of glass for operators.

---

## Team Roles & Folder Ownership

| Person | Role | Folder(s) | Branch |
|--------|------|-----------|--------|
| Person 1 | Evidence Importer | `recovery/importer/` | `feature/recovery-import` |
| Person 2 | File Carving Engine | `recovery/carving/` | `feature/recovery-carving` |
| Person 3 | AI Confidence Scoring | `recovery/ai/` | `feature/recovery-ai` |
| Person 4 | Frontend / UI | `frontend/` | `feature/frontend` |
| Person 5 | Secure Erasure | `erasure/` | `feature/erasure-security` |
| Person 6 | Research / Tech Lead | `audit/`, `docs/` | `feature/research-core` |

### ⚠️ Ownership Rule

> **One owner per module.** If your work requires touching someone else's folder, flag it to them or to Person 6 (Research/Tech Lead) — don't silently edit it.

---

## Branch Strategy & PR Rules

- **Default branch:** `main`
- **No direct commits to `main`.** All work happens on `feature/*` branches.
- PRs merge in dependency order at integration checkpoints (see `docs/architecture.md`).
- **Person 6 reviews every PR** for schema compliance and cross-module consistency.
- Feature branches:
  - `feature/recovery-import` — Person 1
  - `feature/recovery-carving` — Person 2
  - `feature/recovery-ai` — Person 3
  - `feature/frontend` — Person 4
  - `feature/erasure-security` — Person 5
  - `feature/research-core` — Person 6

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- Git

### Clone & Setup

```bash
git clone https://github.com/Git-Dileep/SIH_2026_SecureVault.git
cd SIH_2026_SecureVault

# Checkout your feature branch
git checkout feature/<your-branch>

# Frontend setup (Person 4)
cd frontend
npm install
npm run dev
```

### Running locally (recovery backend + frontend)

The recovery engine lives in `recovery/` (from `file-recov`). The React console lives in `frontend/`.

```bash
# terminal 1 — Python API
cd recovery
python3 generate_test_image.py    # once: builds testdata/synthetic_disk.img
python3 server.py                 # http://127.0.0.1:8000

# terminal 2 — web UI
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

`frontend/.env` already has `VITE_USE_MOCKS=false` and `VITE_API_BASE_URL=/api/v1`. Vite proxies `/api` to the recovery server.

CLI / GUI (from `recovery/`):

```bash
python3 main.py testdata/synthetic_disk.img recovered/
python3 gui.py
```

---

## Project Structure

```
SecureVault/
├── recovery/
│   ├── importer/       # Person 1 — evidence import, hashing, analysis
│   ├── carving/        # Person 2 — file carving engine
│   └── ai/             # Person 3 — AI confidence scoring
├── frontend/           # Person 4 — React/Vite/TypeScript UI
├── erasure/            # Person 5 — secure erasure & verification
├── audit/              # Person 6 — audit logging
├── docs/               # Person 6 — architecture, API contracts, schemas
├── tests/              # mirrors module structure
├── .gitignore
└── README.md
```

---

## Documentation

See the `docs/` folder:

- [`architecture.md`](docs/architecture.md) — System overview, module boundaries, data flow
- [`api-contract.md`](docs/api-contract.md) — REST API endpoint contracts
- [`data-schema.md`](docs/data-schema.md) — JSON schemas for all data objects
- [`standards.md`](docs/standards.md) — NIST SP 800-88 compliance mapping
- [`threat-model.md`](docs/threat-model.md) — Security threat analysis
- [`testing.md`](docs/testing.md) — Test strategy per module
