# SecureVault — SIH presentation brief

Use this as the **source of truth** for slides. Two decks exist in SIH:

| Deck | When | Limit | Rule |
|------|------|--------|------|
| **Idea PPT** | College internal + sih.gov.in upload | **Exactly 6 slides**, PDF | Official AICTE template. Do not add a 7th slide. |
| **Live pitch** | Internal jury / finale | **~8–10 min + Q&A** | Demo-heavy. Same story, more screenshots. |

Fill **PS ID, PS title, theme, category, Team ID, team name, institute** on slide 1 from the **official problem statement you registered**. Do not invent a PS number.

Live demo URL (this workstation): **http://localhost:5174/**  
API: `http://127.0.0.1:8000/api/v1`

---

## One-sentence pitch (memorize)

> **SecureVault is a lab workstation that carves deleted files from a raw disk dump, chooses the right NIST wipe method for HDD vs SSD vs NVMe, and seals every action on a hash-linked custody log — so a rewritten notepad is not your chain of custody.**

Follow-on (if they ask “is it production?”):

> **It is a working lab prototype. Firmware erase is simulated on a copy. The AI is an MLP on 512-byte fragments with measured ~88% hold-out, not a 94% Transformer paper. The ledger is tamper-evident hashing, not a public blockchain.**

Honesty scores higher than 94% on a slide.

---

## The problem (put numbers + sources on the slide)

**Who:** Cybercrime cells, forensic labs, incident-response teams, agencies disposing of seized media.

**Pain (three gaps, three USPs):**

1. **Deleted ≠ gone.** After a filesystem delete, directory entries vanish; file bytes often remain. Signature carvers miss **headerless 512-byte fragments**. Literature: fragment classification (FFT-75 / similar) — signature-only often ~60–65%; learned models much higher in papers.
2. **SSD ≠ HDD.** Wear-leveling and overprovisioning mean a host overwrite can leave **~20–30% of NAND** outside user LBAs. NIST SP 800-88 Rev. 2: HDD overwrite can be Purge-class; SSD/NVMe Purge needs **firmware sanitize** (ATA Secure Erase / NVMe Format NVM).
3. **Plain-text logs get challenged.** Electronic evidence needs an **append-only, verifiable** trail (hashes, operator, time). A `.txt` audit file can be edited.

**Existing tools (name them, don’t trash them):** Autopsy / PhotoRec / Scalpel (carve, little media-aware wipe + CoC). `hdparm` / `nvme-cli` (real wipe, no recovery UI). Commercial suites (EnCase, FTK, Blancco) — costly, not an integrated student-accessible lab console.

**Your gap:** one operator console: **carve + media-aware method selection + sealed log**.

---

## What you actually built (facts you may put on slides)

| Capability | What is real | What you must not claim |
|------------|----------------|-------------------------|
| Recovery | Structure-aware carve of JPEG/PNG/PDF/ZIP from a raw `.img`. Read-only evidence. | “Undelete from macOS Trash / live APFS.” |
| Delete→recover demo | Plant your files → wipe folder + directory table → carve bytes back. Workspace only. | “We recover any deleted file on the judge’s laptop.” |
| AI | 512-byte MLP + magic prior. **Measured hold-out ≈ 88.15%** on synthetic fragments. 10 types. Threshold 0.70. | “94–96% Transformer / FFT-75 trained.” That number is **research**, not this model. |
| Erasure | Detect HDD/SSD/NVMe. HDD → DoD 5220.22-M 7-pass **on a copy**. SSD/NVMe → firmware **analogue** (scramble+zero). NIST-style PDF, labeled **LAB PROTOTYPE**. | “NIST certified.” “We ATA-erase your real SSD.” `/dev` is **refused**. Original files **unchanged**. |
| Blockchain | SHA-256 hash chain (`previous_hash` + `details_hash`). Verify → VALID/TAMPERED. Downloadable custody receipt. | “On Ethereum.” “Immutable public ledger.” Say **tamper-evident custody chain**. |

**Stack:** Python 3.10+ stdlib HTTP API, React + TypeScript + Vite UI, no cloud required, binds `127.0.0.1`.

**Safety (put on feasibility slide):** evidence read-only; erasure copy-only; block devices refused; firmware simulated unless a dangerous env flag (do not demo that).

---

## Official 6-slide IDEA PPT (fill the AICTE template)

Keep **one idea per slide**, bullets, one diagram. Font ≥ 18–24pt. PDF upload.

### Slide 1 — Title

- **Solution name:** SecureVault  
- **Tagline:** Forensic recovery + media-aware sanitization + sealed custody log  
- PS ID / PS title / Theme (Cybersecurity / Blockchain as on portal) / Software  
- Team ID, team name, institute, 6 members (incl. 1 woman if required)  
- Visual: dark console screenshot (Dashboard or Delete→Recover)

### Slide 2 — Proposed solution + uniqueness

**Solution:** Single lab console for seized **raw images**.

- Recover deleted exhibits by **carving** (and AI when headers are gone).  
- **Sanitize by media type** (NIST 800-88 Rev. 2 Clear vs Purge).  
- **Hash-chain every action**; Verify = VALID or TAMPERED; export a receipt.

**Uniqueness (3 bullets only):**

1. Media-aware method **selection** (HDD overwrite vs SSD/NVMe firmware path) — most student tools treat all disks as HDD.  
2. Fragment AI as **fallback**, not a black box instead of carving.  
3. Custody log is **part of the product**, not a notepad afterthought.

**Do not** write a paragraph of marketing.

### Slide 3 — Technical approach (architecture)

Draw this left-to-right:

```
Operator UI (React)
    → API (Python)
        → Carver (mmap, magic + structure walk)
        → Fragment MLP (512 B)
        → Detector → Sanitizer (copy) → Verify → PDF
        → Blockchain logger (SHA-256 linked blocks)
```

**Methodology (demo story):**

1. Plant files on a raw image (or load dump).  
2. Delete directory/folder (bytes remain).  
3. Carve + optional AI.  
4. Optional: sanitize a **copy**; certificate.  
5. Verify chain; download receipt.

**Tech:** Python, React/TS, SHA-256, NIST 800-88 mapping, DoD 5220.22-M (HDD).

Tiny screenshot strip: Delete→Recover UI + VALID badge.

### Slide 4 — Feasibility, risks, mitigation

| Risk | Mitigation (what you already do) |
|------|-----------------------------------|
| Wiping the wrong disk | Refuse `/dev/*`; copy-only; loopback bind |
| Overclaiming AI | Show **88% measured**, cite papers separately |
| SSD overwrite myth | Method table: HDD vs ATA SE vs NVMe Format |
| Log tampering | Hash chain + Verify + receipt |
| No GPU / no internet | Stdlib inference; local-only |

**Cost:** ₹0 for prototype (own laptop).  
**TRL:** 4 — working lab appliance, not NIAP/NSA sanitizer.  
**Roadmap:** FFT-75 training; write-blocker ingest; E01/AFF4; real firmware on an **air-gapped appliance** with dual-operator confirm.

### Slide 5 — Impact

- **Users:** I4C / state cyber cells / campus DFIR / e-waste disposal officers.  
- **Social:** Faster reconstruction of deleted photos/PDFs in crime cases.  
- **Economic:** Open lab stack vs imported suites.  
- **Process:** Same console for **recover then dispose** (don’t mix leftover data on reused SSDs).  
- **Measurable (demo):** 4 exhibits planted → directory empty → carve restores JPEG/PNG/PDF/ZIP; chain stays VALID.

Avoid fake “crores saved” unless you have a source.

### Slide 6 — References (real, citable)

1. Kissel, Regenscheid, Scholl, Stine — **NIST SP 800-88 Rev. 2**, *Guidelines for Media Sanitization*, 2014.  
2. **DoD 5220.22-M** — National Industrial Security Program (overwrite patterns; HDD context).  
3. Garfinkel, S. — file carving / digital forensics literature (e.g. *Digital Investigation*).  
4. Fitzgerald et al. / related — **FFT-75** file fragment classification (512-byte windows; learned models vs magic).  
5. Indian Evidence Act — **Section 65B** (electronic records; integrity/process — do not play lawyer; “supports hash + custody log”).  
6. Project: `https://github.com/Git-Dileep/SIH_2026_SecureVault`

---

## 10-minute live jury talk (internal / finale)

**Clock (practice with a phone):**

| Min | What |
|-----|------|
| 0:00–0:45 | Problem + one sentence. |
| 0:45–2:00 | Gaps vs Autopsy / PhotoRec / hdparm. |
| 2:00–7:00 | **Demo** (this is the win). |
| 7:00–8:30 | Architecture + honest limits. |
| 8:30–10:00 | Impact, roadmap, “ask”. Then Q&A. |

### Demo script (rehearse until it never fails)

Open **http://localhost:5174/**

1. **Delete → Recover** (`/demo/delete-recover`)  
   - Browse files (or built-in case files).  
   - Build disk image — show folder + directory table.  
   - **Delete** — both empty. Say: *“Names gone. Bytes still on the dump.”*  
   - **Recover** — pictures/PDFs come back.  
   - Point at **Live custody chain** → VALID.

2. **Erasure** (`/erasure/ssd`) — 30 seconds  
   - Virtual SSD: ATA Secure Erase analogue.  
   - *“Copy only. We will not brick a judge’s laptop.”*  
   - Certificate says LAB PROTOTYPE.

3. **Chain** (`/audit/chain`) — 30 seconds  
   - Filter “Delete → recover”.  
   - Verify now. Download receipt.  
   - Optional nuclear: mention editing `audit_chain.json` flips TAMPERED (do this **before** the talk once, then restore, or skip live).

If demo breaks: screenshots in backup slides (not in the 6-slide PDF).

---

## Speaker lines that work

- “Carving is filesystem-independent. We don’t need the folder.”  
- “NIST does not say ‘overwrite everything 7 times.’ It says **match method to media**.”  
- “Our AI is a **fallback** for 512-byte windows when magic fails. Accuracy **88% on our hold-out**, not the 94% Transformer papers.”  
- “This is not Bitcoin. It is **hash(prev ∥ event)**. That’s what custody needs.”  
- “We refuse `/dev/sda` on purpose. That’s a feature.”

---

## Q&A you will get (answer in one breath)

**Q: Can it recover files I deleted from this PC?**  
A: No. It carves a **raw image**. The demo *simulates* delete by wiping the directory table.

**Q: Do you really secure-erase SSDs?**  
A: We **select** ATA SE / NVMe Format. Execution is a **firmware analogue on a copy**. Real `hdparm` is the appliance roadmap.

**Q: Is this a blockchain?**  
A: Permissioned **hash chain**. Same property courts care about: detect rewrite. No miners, no gas.

**Q: Why 88% not 94%?**  
A: 94–96% is published Transformers on FFT-75. We shipped a lightweight MLP + magics so it runs offline. Next: train on FFT-75.

**Q: Legal admissibility?**  
A: We provide **hash, operator, time, verify**. Admissibility is for the court under 65B. We don’t overclaim.

**Q: Why Python stdlib server?**  
A: Zero-dependency lab box. FastAPI is a production hardening step, not required for the prototype.

---

## Visuals to screenshot (dark UI, crop tightly)

1. Delete→Recover: files visible + directory offsets.  
2. Same page **after delete**: empty folder.  
3. Recovered thumbnails.  
4. Live custody chain VALID.  
5. SSD page: drive badge + certificate banner LAB PROTOTYPE.  
6. Audit: plain-English table + receipt JSON.

No walls of code on slides.

---

## What loses SIH (do not)

- Slide 7 on the official idea PDF.  
- “94% AI”, “NIST certified”, “on Ethereum”, “wipes your SSD”.  
- Paragraphs. Clipart padlocks. Unsourced “₹1000 crore impact”.  
- Demo from a different laptop without `python3 server.py` + `npm run dev` on **5174**.  
- Arguing with a forensic practitioner. Agree, show the **method table** and **lab TRL**.

---

## Team slide (if internal round allows names)

Map 6 people to: Importer, Carver, AI, Frontend, Erasure, Research/audit. Even if work was shared, **show roles**. Mandatory woman member if SIH rule applies — list her.

---

## Checklist the night before

- [ ] PS ID/title copied from portal, not guessed  
- [ ] 6-slide PDF, official template, no extra slides  
- [ ] References have real titles  
- [ ] Demo path works on the presentation laptop: plant → delete → recover → VALID  
- [ ] Backup: recorded 90s screen capture  
- [ ] One person demos, one person talks, one watches time  
- [ ] Printed one-pager: architecture + safety table  

---

## Suggested 10-min slide titles (live deck, not the 6-slide PDF)

1. Title  
2. Three failures of today’s toolkit  
3. SecureVault in one picture  
4. Demo: delete then recover  
5. Media-aware sanitization (HDD vs SSD vs NVMe table)  
6. Custody chain = VALID / TAMPERED  
7. Honest limits + roadmap  
8. Impact + ask (pilot with a cyber cell / college DFIR lab)

Keep the **6-slide PDF** as the upload. Use this longer set only if the jury allows a live deck plus demo.
