# SecureVault — File Guide

What every source file is for, and **how** it does the job.

This is a forensic **lab appliance**: recover files from a raw disk image, pick a NIST-aligned wipe method by media type, and seal every action on a hash-linked audit chain. Evidence images are opened **read-only**. Erasure overwrites a **working COPY**, never `/dev/*`.

```
Operator (browser)
        │
        ▼
 frontend/  ──HTTP /api/v1──►  recovery/server.py
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
        recovery/carver.py      erasure/sanitizer.py    audit/blockchain_logger.py
        recovery/ai/            erasure/device_detection.py   audit/verifier.py
        recovery/report.py      erasure/nist_compliance.py
```

---

## How a case actually runs

1. **Import** — UI posts a `.img` (or `{ "demo": true }`) to `server.py`. The file is hashed (MD5/SHA-1/SHA-256) and copied under `recovery/workspace/evidence/`.
2. **Carve** — `carver.py` memory-maps the image read-only, walks JPEG/PNG/PDF/ZIP structure, then scans leftover non-zero slack with the AI fragment classifier.
3. **Erase (demo)** — operator picks a virtual HDD/SSD/NVMe file. `device_detection.py` chooses DoD 7-pass / ATA Secure Erase analogue / NVMe Format analogue. `sanitizer.py` copies the target and overwrites the copy. `verification.py` samples sectors. `nist_compliance.py` writes a labeled prototype PDF.
4. **Audit** — every import, carve, wipe, login, and classify appends a block to `audit/audit_chain.json`. `verifier.py` recomputes hashes; one edited byte → `TAMPERED`.

---

## Root

| File | What it does | How |
|------|----------------|-----|
| `README.md` | Team map, clone, how to run | Human docs. Points at `recovery/server.py` + `frontend` Vite. |
| `FILE_GUIDE.md` | This document | File-by-file map of the repo. |
| `.gitignore` | Keeps junk out of git | Ignores `node_modules`, `workspace/`, `audit_chain.json`, logs, pyc. |
| `package-lock.json` | Accidental root npm lock | Not used; frontend has its own. |

---

## `recovery/` — carving engine + HTTP API

This folder is the running backend. Start it with `python3 server.py` from inside `recovery/`.

| File | What it does | How |
|------|----------------|-----|
| `server.py` | Single HTTP API the React UI talks to | stdlib `ThreadingHTTPServer`. Routes `/api/v1/...` (and some `/api/...` aliases). Holds in-memory + `workspace/state.json` for evidence, sessions, jobs. Calls carver, sanitizer, classifier, ledger. Lab runtime: request IDs, optional Bearer sessions, localhost CORS, JSON logs. |
| `lab_runtime.py` | Lab-appliance settings | Env: `SECUREVAULT_BIND`, `SECUREVAULT_AUTH_REQUIRED`, `SECUREVAULT_ALLOW_REAL_ERASE`. Issues HMAC-free `secrets.token_urlsafe` sessions. Writes `workspace/server.jsonl`. |
| `carver.py` | Recovers files from a raw image | Opens the image **read-only** + `mmap`. Searches magic headers. Walks JPEG markers, PNG chunks, PDF `%%EOF`, ZIP EOCD. Writes carved bytes to an output dir. If `use_ai=True`, classifies 512-byte windows in unclaimed non-zero slack (confidence ≥ 0.70). Logs `RECOVERY_*` / `FILE_EXTRACTED` to the chain. |
| `report.py` | Case report JSON + HTML | After a carve, writes `case_report.json` / `.html` with image SHA-256, offsets, types, hashes, confidence. |
| `erasure.py` | Old copy-only demo wipe | 1-pass zeros (`clear`) or 3-pass (`purge`) on a **copy** of a regular file. Refuses `/dev`. Still imported by the GUI; the web path uses `erasure/sanitizer.py` instead. |
| `generate_test_image.py` | Builds the 64 MiB demo disk | Plants valid PNG/JPEG/PDF/ZIP in a zero-filled image. Writes `testdata/injection_log.json` (ground truth). Also contains `make_pdf` used for simple PDFs. |
| `main.py` | CLI carver | `python3 main.py image.img outdir/` → `carve_image` + reports. |
| `gui.py` | Tkinter UI | Same functions as CLI (carve + demo erase). Not the SIH web console. |
| `selftest.py` | Fast carve regression | 2 MiB zero image, one of each type, asserts hashes. |
| `compare_results.py` | Score carver vs ground truth | Compares recovered files to `injection_log.json`. |
| `requirements.txt` | Python deps | Core path is **stdlib**. numpy/torch optional for CNN export. |

### `recovery/ai/` — 512-byte fragment classifier

| File | What it does | How |
|------|----------------|-----|
| `fragment_classifier.py` | Predicts file type from 512 bytes | Features (histogram + entropy + magics) → 3-layer MLP softmax, mixed with a magic-byte prior. Zeros → unknown. Printable ASCII → `txt` **unless** a binary magic (`%PDF-`, `PK`, JPEG, …) is present. Threshold 0.70. |
| `features.py` | Turns bytes into a vector | Shannon entropy, 32-bin histogram, printable/zero ratios, flags for jpg/png/pdf/zip/mp4/mp3/exe/docx/xlsx. |
| `train_classifier.py` | Trains and saves weights | Builds synthetic FFT-75-style fragments (header/mid/tail/noise/trunc) for 10 types, SGD in pure Python, writes `models/fragment_classifier.json` + `.pth` pickle + `metrics.json`. Measured hold-out ≈ **88%**. |
| `confidence.py` | Maps score → high/medium/low | ≥0.80 high, ≥0.50 medium, else low. Keep if ≥0.70. |
| `explanation.py` | One-sentence forensic note | Entropy band + which magics fired. |
| `classifier.py` | Person-3 stub | `# TODO: implement` — **not used**. Live path is `fragment_classifier.py`. |
| `__init__.py` | Package exports | `classify_fragment`, `accuracy_report`. |
| `models/fragment_classifier.json` | MLP weights | Nested lists; stdlib inference, no torch required. |
| `models/fragment_classifier.pth` | Same weights, pickle | Named `.pth` for the spec; not a torch `state_dict` unless torch export ran. |
| `models/metrics.json` | Accuracy report | Train/test accuracy, per-class, dataset note. |

### `recovery/carving/` and `recovery/importer/` — planned modules

These are **ownership stubs** from the original team split. Runtime carving/import lives in `carver.py` and `server.py`.

| File | Status |
|------|--------|
| `carving/base_carver.py`, `jpeg_carver.py`, `png_carver.py` | TODO stubs |
| `importer/evidence_importer.py`, `hasher.py`, `analyzer.py` | TODO stubs (hashing is in `server.py` `_hash_file`) |

### `recovery/testdata/`

| File | What it does |
|------|----------------|
| `synthetic_disk.img` | 64 MiB demo evidence (generated, gitignored). |
| `injection_log.json` | Ground-truth offsets/hashes of planted files. |

Samples under `recovery/samples/` (jpg/png/pdf/zip) are real small files used to plant the demo image and to test classification.

Runtime junk (gitignored): `recovery/workspace/` — evidence copies, recovered files, erasure copies, certificates, `state.json`, `server.jsonl`.

---

## `erasure/` — media-aware sanitization

Imported by adding this directory to `sys.path` from `server.py` (name clash with `recovery/erasure.py`).

| File | What it does | How |
|------|----------------|-----|
| `device_detection.py` | HDD vs SSD vs NVMe | Linux: `/sys/block/{dev}/queue/rotational`. Path `/dev/nvme*` → NVMe. macOS: `diskutil`. Demo files `demo_hdd.bin` / `demo_ssd.bin` / `demo_nvme.bin` + sidecar JSON. Returns recommended method + overprovisioning risk. |
| `methods.py` | Method catalog | HDD → DoD 5220.22-M **7-pass**. SSD → ATA Secure Erase analogue. NVMe → Format NVM SES=1 analogue. `select_method("auto")` picks by drive type. `simulate_firmware_erase` = random scramble then zeros. |
| `sanitizer.py` | Runs the wipe | Always copies the target first. Refuses `/dev` unless `SECUREVAULT_ALLOW_REAL_ERASE=1` **and** not a system disk — and even then this prototype still does not shell out to `hdparm`/`nvme`. Logs `ERASURE_STARTED/COMPLETED/VERIFIED`. |
| `verification.py` | Read-back check | SHA-256 before/after must change. Samples spaced 512-byte sectors; for Purge expects zeros. Residual entropy recorded. |
| `nist_compliance.py` | Prototype certificate | Stdlib PDF 1.4 + JSON. Fields: drive type, method, hashes, operator, NIST 800-88 Rev. 2 statement. Banner: **LAB PROTOTYPE / SIMULATED**. SHA-256 of the canonical body. |
| `__init__.py` | Public exports | `detect_device`, `sanitize`, `generate_certificate`. |

---

## `audit/` — tamper-evident ledger

| File | What it does | How |
|------|----------------|-----|
| `blockchain_logger.py` | Append-only chain | Each block: `index`, `timestamp`, `action`, `details_hash`, `previous_hash`, `hash`. **Hash is SHA-256 of those five fields only** (hashing a dict that already contains `hash` can never verify). Genesis `previous_hash = "0"`. Persists `audit_chain.json` after every `log()`. Thread-safe singleton. |
| `verifier.py` | VALID / TAMPERED | Recomputes every block hash, `details_hash`, and parent link. Returns `broken_at` index on failure. |
| `blockchain.py` | Earlier Merkle-block chain | Blocks with `merkle_root` + optional simulated L1 `anchor()`. Still used for `/audit/proof` and `/audit/anchor`. The SIH explorer reads `blockchain_logger`. |
| `merkle.py` | Merkle tree helpers | Leaf/parent SHA-256, inclusion proof, verify. |
| `logger.py` | Hash-chained event log object | Structured entries (`actor`, `action`, `entry_hash`) that can feed `AuditBlockchain`. Server also keeps a parallel list in `state.json`. |
| `__init__.py` | Package exports | Logger, chain, verifier. |
| `audit_chain.json` | Live chain (gitignored) | JSON array of blocks. Edit one `action` → `GET /api/audit/verify` → `TAMPERED`. |

---

## `frontend/` — React operator console

Vite + React 19 + TypeScript + Tailwind v4. Dev server proxies `/api` → `http://127.0.0.1:8000`.

### Boot / config

| File | What it does |
|------|----------------|
| `index.html` | HTML shell; mounts `#root`. |
| `src/main.tsx` | `createRoot` + `App`. |
| `src/App.tsx` | React Router routes (dashboard, import, recovery, erasure, AI, audit, settings). |
| `src/index.css` | Design tokens (forensic dark UI), tables, badges, chain diagram, lab banner, NIST certificate frame. |
| `src/config.ts` | `VITE_API_BASE_URL` (default `/api/v1`), `VITE_USE_MOCKS`. |
| `src/types.ts` | TypeScript types matching API payloads (evidence, recovered files, jobs, ledger blocks, health). |
| `src/auth.ts` | `sessionStorage` operator id + Bearer token; `authHeaders()` for fetch. |
| `vite.config.ts` | React + Tailwind plugins; `/api` proxy to port 8000. |
| `package.json` | Scripts: `dev`, `build`, `lint`. Deps: react-router, lucide-react, recharts. |
| `tsconfig*.json` | Strict TS project refs. |

### API client

| File | What it does | How |
|------|----------------|-----|
| `src/api/client.ts` | GET/POST/upload | `fetch` with operator headers. On `VITE_USE_MOCKS=true` returns mock data. |
| `src/api/recovery.ts` | Evidence, carve, dashboard, health, login | `/evidence/import`, `/recovery/start`, `/dashboard/stats`, `/auth/login`. |
| `src/api/erasure.ts` | Devices, sanitize, certificates | `detectDriveType`, `sanitizeDrive`, `getComplianceCertificate`. |
| `src/api/ai.ts` | Classify + accuracy | Multipart file or hex/text JSON. `getAccuracyMetrics()`. |
| `src/api/audit.ts` | Chain explorer | `getAuditChain`, `verifyAuditChain`, `getBlock(index)`. |
| `src/api/mocks/*` | Offline fixtures | Used only when mocks are on. |
| `src/data/mockData.ts` | Demo ledger, drives, certificate | Development fallbacks. |

### Layout / shared UI

| File | What it does |
|------|----------------|
| `components/Layout.tsx` | Sidebar + lab banner + feature navbar + page outlet. |
| `components/Sidebar.tsx` | Left nav (Dashboard, Import, Recovery, SSD Erasure, AI, Audit, Settings). |
| `components/Navbar.tsx` | Top links: `/erasure/ssd`, `/ai/classifier`, `/audit/chain`. |
| `components/LabBanner.tsx` | Yellow strip from `/health`: lab mode, simulated firmware, chain status. |
| `components/PageHeader.tsx` | Title / subtitle / actions. |
| `components/StatusBadge.tsx` | Evidence / sanitization / outcome chips. |
| `components/StatCard.tsx`, `ProgressBar.tsx` | Dashboard/progress widgets. |
| `components/DriveTypeBadge.tsx` | HDD blue / SSD green / NVMe purple. |
| `components/ConfidenceBar.tsx` | Green/amber/red bar for 0–1 scores. |
| `components/FileUpload.tsx` | Drag-drop 512-byte (or any) file. |
| `components/AccuracyComparison.tsx` | Recharts bar: signature baseline vs **measured** model accuracy. |
| `components/BlockchainExplorer.tsx` | Horizontal block cards with arrows. |
| `components/ComplianceCertificate.tsx` | NIST field list + PDF iframe/download. |

### Pages

| Route | File | Job |
|-------|------|-----|
| `/` | `pages/Dashboard.tsx` | Counts, recent evidence, recovery progress, three innovation cards. |
| `/import` | `pages/EvidenceImport.tsx` | Upload or “Load demo image”; starts carve. |
| `/recovery/results` | `pages/RecoveryResults.tsx` | Recovered files, AI confidence column, AI badge, link to audit chain. |
| `/erasure` | `pages/ErasureFlow.tsx` | Full sanitization form + job table + certificate. |
| `/erasure/ssd` | `pages/SSDErasurePage.tsx` | Detect type → Start Secure Erasure → pass bar → PDF. |
| `/ai` | `pages/AIClassifier.tsx` | Earlier classifier screen (still routed). |
| `/ai/classifier` | `pages/AIClassifierPage.tsx` | Upload fragment, scores, entropy, 65% vs measured AI chart. |
| `/audit` | `pages/AuditLog.tsx` | Timeline of hash-chained UI events. |
| `/audit/chain` | `pages/AuditChainPage.tsx` | Table + visual chain + Verify + block detail. |
| `/reports` | `pages/Reports.tsx` | Case report summary + HTML/JSON links. |
| `/settings` | `pages/Settings.tsx` | Health, bind, mode, operator sign-in (seals `USER_LOGIN`). |
| `*` | `pages/NotFound.tsx` | 404. |

---

## `tests/`

| File | What it proves |
|------|----------------|
| `erasure/test_device_detection.py` | `/dev/nvme0n1` → NVMe; demo targets HDD/SSD/NVMe. |
| `erasure/test_sanitizer.py` | SSD copy is wiped; original bytes unchanged; PDF written. |
| `erasure/test_safety.py` | `/dev/sda` and `/dev/nvme0n1` raise `PermissionError`. |
| `ai/test_classifier.py` | Header fragments keep ≥0.70; all-zero window rejected. |
| `audit/test_blockchain_logger.py` | Genesis + append verify `VALID`; edited action → `TAMPERED`. |
| `audit/test_blockchain.py` | Older Merkle chain + proof + simulated anchor. |

Run:

```bash
python3 -m unittest tests.erasure.test_safety tests.erasure.test_sanitizer \
  tests.ai.test_classifier tests.audit.test_blockchain_logger -v
python3 recovery/selftest.py
```

---

## `docs/` (original SIH stubs)

| File | Status |
|------|--------|
| `architecture.md`, `api-contract.md`, `data-schema.md`, `standards.md`, `testing.md`, `threat-model.md` | Placeholders owned by “Person 6”. Live behavior is this guide + `server.py`. |

---

## HTTP surface (implemented)

| Method | Path | Job |
|--------|------|-----|
| GET | `/api/v1/health` | Mode, bind, chain validity, measured AI accuracy, safety flags. |
| POST | `/api/v1/auth/login` | Operator session token; `USER_LOGIN` block. |
| POST | `/api/v1/evidence/import` | Upload / path / `{ "demo": true }`; starts carve. |
| GET | `/api/v1/recovery/results/latest` | Latest session files. |
| GET | `/api/v1/erasure/detect?device=` | Drive type + recommended method. |
| POST | `/api/v1/erasure/sanitize` | Media-aware copy wipe + certificate. |
| GET | `/api/v1/erasure/compliance/{id}/file` | NIST PDF. |
| POST | `/api/v1/ai/classify` | 512-byte fragment → type, confidence, entropy. |
| GET | `/api/v1/ai/accuracy` | Hold-out metrics (~0.8815). |
| GET | `/api/audit/chain` | Full ledger. |
| GET | `/api/audit/verify` | `{ status: "VALID" \| "TAMPERED" }`. |
| GET | `/api/audit/block/{index}` | One block (genesis is `0`). |

---

## What is *not* a source file (ignore when reading the tree)

- `frontend/node_modules/` — npm packages
- `recovery/__pycache__/`, `*.pyc`
- `recovery/workspace/` — live case data
- `* 2.py` / `* 2.png` — duplicate copies, not part of the pipeline
- `audit/audit.log`, `audit_chain.json` — generated at runtime

---

## Quick start

```bash
# terminal 1
cd recovery
python3 generate_test_image.py    # once
python3 server.py                 # http://127.0.0.1:8000

# terminal 2
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Demo path: **Load demo image** → Recovery (AI badges) → `/erasure/ssd` (virtual SSD) → download PDF → `/audit/chain` → **Verify Chain**.
