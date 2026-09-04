#!/usr/bin/env python3
"""
compare_results.py — Check carved output against the injection log.

    python compare_results.py testdata/injection_log.json recovered/case_report.json

A planted file is a true positive when we recover the same type at the
same start offset with the same SHA-256. Anything extra is a false positive
(interesting to talk about; not always a bug).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("usage: python compare_results.py <injection_log.json> <case_report.json>")
        return 2

    truth = load(args[0])
    report = load(args[1])
    planted = truth.get("files", [])
    recovered = report.get("files", [])

    rec_by_offset = {int(item["offset_start"]): item for item in recovered}

    print(f"Planted:   {len(planted)}")
    print(f"Recovered: {len(recovered)}")
    print()

    hits = 0
    misses = []
    for item in planted:
        got = rec_by_offset.get(int(item["offset_start"]))
        if not got:
            misses.append((item, "not recovered"))
            continue
        problems = []
        if got.get("type") != item.get("type"):
            problems.append(f"type {got.get('type')} != {item.get('type')}")
        if int(got.get("size", -1)) != int(item.get("size", -2)):
            problems.append(f"size {got.get('size')} != {item.get('size')}")
        if got.get("sha256") != item.get("sha256"):
            problems.append("sha256 mismatch")
        if problems:
            misses.append((item, "; ".join(problems)))
        else:
            hits += 1
            print(
                f"  HIT  {item['type']:4s} @ {item['offset_start']:<10} "
                f"{item['source_file']}"
            )

    print()
    print(f"True positives: {hits}/{len(planted)}")
    if misses:
        print("Misses / mismatches:")
        for item, why in misses:
            print(f"  MISS {item['type']:4s} @ {item['offset_start']:<10} {why}")
        return 1

    extra = [r for r in recovered if int(r["offset_start"]) not in {int(p["offset_start"]) for p in planted}]
    if extra:
        print(f"Extra recovered files (not in injection log): {len(extra)}")
        for item in extra:
            print(f"  + {item.get('type')} @ {item.get('offset_start')} {item.get('filename')}")
    else:
        print("No extra files. Ground truth matched exactly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
