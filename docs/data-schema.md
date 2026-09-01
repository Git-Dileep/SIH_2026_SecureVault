# Data Schema

> Owned by Person 6 (Research / Tech Lead)

## Evidence Object

TBD — owned by Person 6

```json
{
  "id": "string — unique evidence identifier",
  "filename": "string — original filename",
  "format": "string — E01 | AFF4 | raw",
  "size_bytes": "number",
  "import_timestamp": "string — ISO 8601",
  "hashes": {
    "md5": "string",
    "sha1": "string",
    "sha256": "string"
  },
  "status": "string — importing | imported | analyzing | analyzed | error",
  "metadata": {
    "TODO": "define additional metadata fields"
  }
}
```

---

## Recovered-File Object

TBD — owned by Person 6

```json
{
  "id": "string — unique recovered file identifier",
  "evidence_id": "string — parent evidence identifier",
  "filename": "string — reconstructed filename or generated name",
  "file_type": "string — JPEG | PNG | PDF | ...",
  "size_bytes": "number",
  "offset": "number — byte offset in evidence image",
  "recovery_method": "string — carved | filesystem | metadata",
  "confidence_score": "number — 0.0 to 1.0",
  "confidence_label": "string — high | medium | low",
  "ai_explanation": "string — human-readable explanation",
  "integrity_checks": {
    "header_valid": "boolean",
    "footer_valid": "boolean",
    "structure_valid": "boolean",
    "hash": "string — SHA-256 of recovered file"
  },
  "recovered_at": "string — ISO 8601"
}
```

---

## Sanitization-Result Object

TBD — owned by Person 6

```json
{
  "id": "string — unique sanitization job identifier",
  "device": {
    "name": "string — /dev/sda | \\\\.\\PhysicalDrive0",
    "type": "string — HDD | SSD | NVMe | USB",
    "serial": "string",
    "capacity_bytes": "number"
  },
  "method": "string — clear | purge | destroy",
  "passes_completed": "number",
  "passes_total": "number",
  "status": "string — pending | in_progress | verifying | completed | failed",
  "started_at": "string — ISO 8601",
  "completed_at": "string | null — ISO 8601",
  "verification": {
    "passed": "boolean",
    "sample_sectors_checked": "number",
    "residual_data_found": "boolean"
  },
  "certificate_url": "string | null — URL to download certificate"
}
```

---

## Audit-Log Entry

TBD — owned by Person 6

```json
{
  "id": "string — unique log entry identifier",
  "timestamp": "string — ISO 8601",
  "actor": "string — user or system identity",
  "action": "string — evidence.import | recovery.start | erasure.start | ...",
  "target": "string — resource identifier acted upon",
  "outcome": "string — success | failure | error",
  "details": {
    "TODO": "define per-action detail fields"
  },
  "prev_hash": "string — hash of previous log entry (chain integrity)",
  "entry_hash": "string — hash of this entry"
}
```
