#!/usr/bin/env python3
"""
report.py — Case report writers (JSON + HTML).

A forensic tool is only as useful as its paper trail. These reports record:
  - which evidence image we scanned
  - the SHA-256 of that image (integrity / chain of custody)
  - every recovered file with offsets, size, type, hash, and confidence
"""

from __future__ import annotations

import json
from pathlib import Path

from carver import (
    TOOL_NAME,
    TOOL_VERSION,
    RecoveredFile,
    count_by_type,
    utc_now_iso,
)


def build_report_dict(
    source_image: str | Path,
    source_hash_sha256: str,
    files: list[RecoveredFile],
    image_size: int | None = None,
) -> dict:
    """Assemble the canonical JSON report structure."""
    source_image = str(Path(source_image).resolve())
    by_type = count_by_type(files)
    return {
        "case_info": {
            "tool": TOOL_NAME,
            "tool_version": TOOL_VERSION,
            "timestamp": utc_now_iso(),
            "source_image": source_image,
            "source_hash_sha256": source_hash_sha256,
            "source_size_bytes": image_size,
            "notes": (
                "Source image was opened read-only. "
                "Carving is signature-based and filesystem-independent."
            ),
        },
        "recovery_summary": {
            "total_files": len(files),
            "by_type": by_type,
            "confidence_counts": {
                level: sum(1 for f in files if f.confidence == level)
                for level in ("high", "medium", "low")
            },
        },
        "files": [f.to_dict() for f in files],
    }


def write_json_report(report: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def write_html_report(report: dict, path: str | Path) -> Path:
    """Self-contained HTML report — open it in any browser, no extra files."""
    path = Path(path)
    info = report["case_info"]
    summary = report["recovery_summary"]
    files = report["files"]

    by_type_html = "".join(
        f"<li><strong>{name}</strong>: {count}</li>"
        for name, count in sorted(summary.get("by_type", {}).items())
    ) or "<li>None</li>"

    rows = []
    for item in files:
        conf = item.get("confidence", "")
        rows.append(
            "<tr>"
            f"<td>{item.get('index', '')}</td>"
            f"<td class='mono'>{_esc(item.get('filename', ''))}</td>"
            f"<td>{_esc(item.get('type', ''))}</td>"
            f"<td class='mono'>{item.get('offset_start', '')}</td>"
            f"<td class='mono'>{item.get('offset_end', '')}</td>"
            f"<td>{item.get('size', '')}</td>"
            f"<td><span class='pill {conf}'>{_esc(conf)}</span></td>"
            f"<td class='mono hash'>{_esc(item.get('sha256', ''))}</td>"
            "</tr>"
        )
    table_body = "\n".join(rows) or "<tr><td colspan='8'>No files recovered.</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{_esc(info.get('tool', 'ForensicRecover'))} — Case Report</title>
  <style>
    :root {{
      --bg: #0f1419;
      --card: #1a2332;
      --ink: #e8eef7;
      --muted: #93a1b5;
      --accent: #3d9cf0;
      --line: #2a3548;
      --high: #3dd68c;
      --medium: #f0c14d;
      --low: #e57373;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 32px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg); color: var(--ink);
    }}
    h1 {{ margin: 0 0 8px; font-size: 22px; }}
    .sub {{ color: var(--muted); margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .card {{
      background: var(--card); border: 1px solid var(--line);
      border-radius: 10px; padding: 16px 18px;
    }}
    h2 {{ margin: 0 0 10px; font-size: 14px; color: var(--accent); letter-spacing: .04em; text-transform: uppercase; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
    .hash {{ word-break: break-all; }}
    ul {{ margin: 0; padding-left: 18px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }}
    th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 600; font-size: 12px; }}
    .pill {{ padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }}
    .pill.high {{ background: #143325; color: var(--high); }}
    .pill.medium {{ background: #3a3014; color: var(--medium); }}
    .pill.low {{ background: #3a1818; color: var(--low); }}
    .footer {{ margin-top: 24px; color: var(--muted); font-size: 12px; }}
  </style>
</head>
<body>
  <h1>Forensic Case Report</h1>
  <p class="sub">{_esc(info.get('tool'))} v{_esc(info.get('tool_version'))} · {_esc(info.get('timestamp'))}</p>

  <div class="grid">
    <div class="card">
      <h2>Evidence</h2>
      <p><strong>Source image</strong><br><span class="mono">{_esc(info.get('source_image'))}</span></p>
      <p><strong>SHA-256</strong><br><span class="mono hash">{_esc(info.get('source_hash_sha256'))}</span></p>
      <p><strong>Size</strong> {info.get('source_size_bytes') or 'n/a'} bytes</p>
    </div>
    <div class="card">
      <h2>Recovery summary</h2>
      <p><strong>Total files recovered:</strong> {summary.get('total_files', 0)}</p>
      <ul>{by_type_html}</ul>
    </div>
  </div>

  <div class="card" style="margin-top:16px; overflow-x:auto;">
    <h2>Recovered files</h2>
    <table>
      <thead>
        <tr>
          <th>#</th><th>Filename</th><th>Type</th>
          <th>Start</th><th>End</th><th>Size</th>
          <th>Confidence</th><th>SHA-256</th>
        </tr>
      </thead>
      <tbody>
        {table_body}
      </tbody>
    </table>
  </div>

  <p class="footer">
    The source image was opened read-only. Offsets are byte positions in the raw image.
    This report is a hackathon prototype and is not a substitute for a validated forensic tool.
  </p>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def write_reports(
    source_image: str | Path,
    source_hash_sha256: str,
    files: list[RecoveredFile],
    json_path: str | Path,
    html_path: str | Path | None = None,
    image_size: int | None = None,
) -> tuple[Path, Path | None]:
    report = build_report_dict(source_image, source_hash_sha256, files, image_size)
    json_out = write_json_report(report, json_path)
    html_out = write_html_report(report, html_path) if html_path else None
    return json_out, html_out


def _esc(value) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
