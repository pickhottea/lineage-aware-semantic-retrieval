#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Step B+ Coverage Report (v2)
---------------------------
Input:
  artifacts/representation_selection_report_v2_ids.jsonl

Output:
  artifacts/family_coverage_v2.jsonl

Purpose:
- Compute coverage flags for required jurisdictions/versions:
  WO A1; US A* + B*; EP A* + B*
- Compare LANDSCAPE universe (family_members_all) vs PROCESSING universe (family_publications)
- No OPS calls. Pure audit/analytics. Governance-safe.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


ROOT = Path(__file__).resolve().parents[1]
IN_JSONL = ROOT / "artifacts" / "representation_selection_report_v2_ids.jsonl"
OUT_JSONL = ROOT / "artifacts" / "family_coverage_v2.jsonl"


# ----------------------------
# Docdb parsing helpers
# ----------------------------
_DOCDB_KIND_RE = re.compile(r"([A-Z]\d?)$", re.I)

def parse_docdb(pub: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse 'WO2025201951A1' -> ('WO', '2025201951', 'A1')
    Returns (None,None,None) if cannot parse.
    """
    p = (pub or "").strip().upper()
    if len(p) < 4:
        return None, None, None
    cc = p[:2]
    m = _DOCDB_KIND_RE.search(p)
    if not m:
        return None, None, None
    kind = m.group(1).upper()
    number = p[2:-len(kind)]
    if not cc.isalpha():
        return None, None, None
    if not number:
        return None, None, None
    # number may not be digits for some doc-ids; allow non-digit here for LANDSCAPE,
    # but mark "publication-like" only if digits.
    return cc, number, kind

def kind_group(kind: str) -> str:
    k = (kind or "").upper()
    if k.startswith("A"):
        return "A"
    if k.startswith("B"):
        return "B"
    return "OTHER"

def is_wo_a1(cc: str, kind: str) -> bool:
    return (cc == "WO" and (kind or "").upper() == "A1")

def is_us_a(cc: str, kind: str) -> bool:
    return (cc == "US" and (kind or "").upper().startswith("A"))

def is_us_b(cc: str, kind: str) -> bool:
    return (cc == "US" and (kind or "").upper().startswith("B"))

def is_ep_a(cc: str, kind: str) -> bool:
    return (cc == "EP" and (kind or "").upper().startswith("A"))

def is_ep_b(cc: str, kind: str) -> bool:
    return (cc == "EP" and (kind or "").upper().startswith("B"))

def safe_docdb_list(rows: Any) -> List[str]:
    out: List[str] = []
    if isinstance(rows, list):
        for x in rows:
            if isinstance(x, dict):
                d = (x.get("docdb") or "").strip().upper()
                if d:
                    out.append(d)
    return out


def summarize_set(docdb_list: List[str]) -> Dict[str, Any]:
    """
    Summarize jurisdiction/kind coverage from a list of docdb strings.
    """
    jurs = set()
    by_jur = {}
    wo_a1 = False
    us_a = False
    us_b = False
    ep_a = False
    ep_b = False

    for d in docdb_list:
        cc, number, kind = parse_docdb(d)
        if not cc or not kind:
            continue
        jurs.add(cc)
        by_jur.setdefault(cc, {"A": 0, "B": 0, "OTHER": 0, "examples": []})
        g = kind_group(kind)
        by_jur[cc][g] += 1
        if len(by_jur[cc]["examples"]) < 5:
            by_jur[cc]["examples"].append(d)

        if is_wo_a1(cc, kind): wo_a1 = True
        if is_us_a(cc, kind): us_a = True
        if is_us_b(cc, kind): us_b = True
        if is_ep_a(cc, kind): ep_a = True
        if is_ep_b(cc, kind): ep_b = True

    return {
        "jurisdictions": sorted(jurs),
        "by_jurisdiction": by_jur,
        "flags": {
            "has_wo_a1": wo_a1,
            "has_us_a": us_a,
            "has_us_b": us_b,
            "has_ep_a": ep_a,
            "has_ep_b": ep_b,
            "meets_required_set": bool(wo_a1 and us_a and us_b and ep_a and ep_b),
        },
    }


def main() -> None:
    if not IN_JSONL.exists():
        raise SystemExit(f"Missing input: {IN_JSONL}")

    rows = [json.loads(l) for l in IN_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in rows:
            seed = (r.get("seed_publication_number") or "").strip().upper()
            asset_id = r.get("asset_id")
            event_id = r.get("event_id")
            created_at = r.get("created_at")

            landscape_docdbs = safe_docdb_list(r.get("family_members_all"))
            processing_docdbs = safe_docdb_list(r.get("family_publications"))

            land = summarize_set(landscape_docdbs)
            proc = summarize_set(processing_docdbs)

            # Required-set missing details (based on LANDSCAPE view)
            miss = []
            lf = land["flags"]
            if not lf["has_wo_a1"]: miss.append("WO_A1")
            if not lf["has_us_a"]:  miss.append("US_A*")
            if not lf["has_us_b"]:  miss.append("US_B*")
            if not lf["has_ep_a"]:  miss.append("EP_A*")
            if not lf["has_ep_b"]:  miss.append("EP_B*")

            # Diff signal: LANDSCAPE sees something but PROCESSING doesn't include it
            diff_notes = []
            land_j = set(land["jurisdictions"])
            proc_j = set(proc["jurisdictions"])
            extra_in_land = sorted(land_j - proc_j)
            if extra_in_land:
                diff_notes.append({
                    "type": "LANDSCAPE_HAS_MORE_JURISDICTIONS_THAN_PROCESSING",
                    "jurisdictions_only_in_landscape": extra_in_land
                })

            # Also warn if LANDSCAPE meets required-set but PROCESSING does not
            if lf["meets_required_set"] and not proc["flags"]["meets_required_set"]:
                diff_notes.append({
                    "type": "REQUIRED_SET_VISIBLE_IN_LANDSCAPE_BUT_NOT_IN_PROCESSING",
                    "note": "Likely Step B publication-only extraction is missing some publication references, or OPS family response lacks them under publication-reference."
                })

            out: Dict[str, Any] = {
                "policy_version": "coverage_policy_v2_required_WO_US_EP_AB",
                "seed_publication_number": seed,
                "asset_id": asset_id,
                "event_id": event_id,
                "created_at": created_at,
                "landscape": {
                    "counts": {
                        "members_all_docdb": len(landscape_docdbs),
                    },
                    **land,
                },
                "processing": {
                    "counts": {
                        "publications_docdb": len(processing_docdbs),
                    },
                    **proc,
                },
                "required_set_missing": miss,
                "diff_notes": diff_notes,
            }

            f.write(json.dumps(out, ensure_ascii=False) + "\n")

    print(f"[ok] wrote {len(rows)} rows -> {OUT_JSONL}")


if __name__ == "__main__":
    main()
