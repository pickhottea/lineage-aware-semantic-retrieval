#!/usr/bin/env python3
"""
Step C -> Pre-Chroma lineage gate (Google lane)
Fail-fast if any GOOGLE row is missing required lineage fields.

Usage:
  python scripts/step_c_lineage_gate.py \
    --in artifacts/claims_representation_v3.jsonl \
    --check-files

Exit codes:
  0: PASS
  1: FAIL (lineage missing / flags missing / file missing)
  2: ERROR (input not readable / invalid JSON)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Tuple


REQUIRED_FLAGS = {"THIRD_PARTY_SOURCE", "COVERAGE_FALLBACK"}


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception as ex:
                raise ValueError(f"Invalid JSON at line {i}: {ex}") from ex
    return rows


def is_nonempty_str(x: Any) -> bool:
    return isinstance(x, str) and x.strip() != ""


def validate_google_row(row: Dict[str, Any], check_files: bool) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    if row.get("claims_source") != "GOOGLE":
        return True, reasons  # non-google rows are out of scope for this gate

    # A) required lineage fields
    if not is_nonempty_str(row.get("google_seed_publication")):
        reasons.append("MISSING google_seed_publication")

    if not is_nonempty_str(row.get("google_resolved_publication")):
        reasons.append("MISSING google_resolved_publication")

    if not is_nonempty_str(row.get("google_status")):
        reasons.append("MISSING google_status")

    if not is_nonempty_str(row.get("claims_google_text_path")):
        reasons.append("MISSING claims_google_text_path")

    # B) governance flags
    flags = row.get("governance_flags")
    if not isinstance(flags, list) or not all(isinstance(x, str) for x in flags):
        reasons.append("governance_flags is not an array[str]")
    else:
        missing = sorted(list(REQUIRED_FLAGS - set(flags)))
        if missing:
            reasons.append(f"Missing governance_flags: {','.join(missing)}")

    # C) selected_source naming convention
    selected_source = row.get("selected_source")
    if not is_nonempty_str(selected_source):
        reasons.append("MISSING selected_source")
    else:
        if not selected_source.startswith("GOOGLE_FALLBACK_"):
            reasons.append("selected_source must start with GOOGLE_FALLBACK_")

    # D) optional file existence check
    if check_files and is_nonempty_str(row.get("claims_google_text_path")):
        p = row["claims_google_text_path"]
        if not os.path.isfile(p):
            reasons.append(f"TXT file not found: {p}")

    ok = len(reasons) == 0
    return ok, reasons


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Input JSONL (claims_representation_v3.jsonl)")
    ap.add_argument("--check-files", action="store_true", help="Also check claims_google_text_path exists on disk")
    ap.add_argument("--max-errors", type=int, default=50, help="Max errors to print before truncating output")
    args = ap.parse_args()

    try:
        rows = load_jsonl(args.in_path)
    except Exception as ex:
        eprint(f"[ERROR] cannot read {args.in_path}: {ex}")
        return 2

    google_rows = [r for r in rows if r.get("claims_source") == "GOOGLE"]
    if not google_rows:
        print("PASS: no GOOGLE rows found (gate not applicable)")
        return 0

    bad: List[Tuple[str, str, List[str]]] = []
    for r in google_rows:
        ok, reasons = validate_google_row(r, check_files=args.check_files)
        if not ok:
            family_id = str(r.get("family_id", "UNKNOWN_FAMILY"))
            selected_pub = str(r.get("selected_publication", "UNKNOWN_PUBLICATION"))
            bad.append((family_id, selected_pub, reasons))

    if bad:
        eprint(f"FAIL: Google lineage gate failed ({len(bad)}/{len(google_rows)} bad rows)")
        for i, (fid, pub, reasons) in enumerate(bad[: args.max_errors], start=1):
            eprint(f"  {i}. family_id={fid} selected_publication={pub}")
            for rr in reasons:
                eprint(f"     - {rr}")
        if len(bad) > args.max_errors:
            eprint(f"  ... truncated, total bad rows: {len(bad)}")
        return 1

    print(f"PASS: Google lineage gate passed ({len(google_rows)} GOOGLE rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

