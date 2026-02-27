#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validator — Semantic Chunk Policy v2.0

Validates:
- Exactly 1 record per family in each file
- Family sets match across claim_1 / claim_set / spec
- Required metadata fields exist
- claim_1 is "clean" (no numbering prefix, no "Claims (N)" header)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Set, List


RE_BAD_CLAIM1_PREFIX = re.compile(r"(?m)^\s*1\s*[\.):]\s+")
RE_BAD_CLAIMS_HEADER = re.compile(r"(?is)^\s*claims?\s*(\(\s*\d+\s*\))")


REQUIRED_FIELDS = [
    "family_id",
    "selected_publication",
    "source",
    "chunk_type",
    "chunk_policy_version",
    "embedding_model",
    "created_at",
    "text",
]

def load_jsonl(p: Path) -> List[dict]:
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            out.append(json.loads(ln))
    return out

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_id", required=True)
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[2]
    run_dir = repo / "artifacts" / "_pipeline_runs" / args.run_id
    chunks_dir = run_dir / "chunks_v2"

    c1_p = chunks_dir / "claim_1.jsonl"
    cs_p = chunks_dir / "claim_set.jsonl"
    sp_p = chunks_dir / "spec.jsonl"

    for p in (c1_p, cs_p, sp_p):
        if not p.exists():
            raise SystemExit(f"[error] missing chunk file: {p}")

    c1 = load_jsonl(c1_p)
    cs = load_jsonl(cs_p)
    sp = load_jsonl(sp_p)

    def family_set(recs: List[dict]) -> Set[str]:
        return set((r.get("family_id") or "").strip() for r in recs if (r.get("family_id") or "").strip())

    s1, s2, s3 = family_set(c1), family_set(cs), family_set(sp)

    # 1) Family set equality
    if not (s1 == s2 == s3):
        only1 = sorted(list(s1 - s2 - s3))[:20]
        only2 = sorted(list(s2 - s1 - s3))[:20]
        only3 = sorted(list(s3 - s1 - s2))[:20]
        raise SystemExit(
            "[fail] family sets mismatch across chunk files\n"
            f" claim_1 only sample: {only1}\n"
            f" claim_set only sample: {only2}\n"
            f" spec only sample: {only3}\n"
        )

    # 2) Exactly one per family per file
    def ensure_unique(recs: List[dict], name: str) -> None:
        seen = {}
        for r in recs:
            fid = (r.get("family_id") or "").strip()
            if not fid:
                raise SystemExit(f"[fail] {name}: missing family_id")
            seen[fid] = seen.get(fid, 0) + 1
        dup = [k for k, v in seen.items() if v != 1]
        if dup:
            raise SystemExit(f"[fail] {name}: not exactly 1 record per family. sample dup: {dup[:20]}")

    ensure_unique(c1, "claim_1")
    ensure_unique(cs, "claim_set")
    ensure_unique(sp, "spec")

    # 3) Required fields
    def check_required(recs: List[dict], name: str) -> None:
        for i, r in enumerate(recs[:2000]):  # enough for validation
            for f in REQUIRED_FIELDS:
                if f not in r:
                    raise SystemExit(f"[fail] {name}: missing field '{f}' at row {i}")
                if f in ("text",) and not isinstance(r.get(f), str):
                    raise SystemExit(f"[fail] {name}: field '{f}' must be str at row {i}")
                if f in ("family_id", "selected_publication", "source", "chunk_type", "chunk_policy_version", "created_at") and not (r.get(f) or ""):
                    raise SystemExit(f"[fail] {name}: empty field '{f}' at row {i}")

    check_required(c1, "claim_1")
    check_required(cs, "claim_set")
    check_required(sp, "spec")

    # 4) claim_1 cleanliness checks
    bad_prefix = []
    bad_header = []
    empty_claim1 = []
    for r in c1:
        t = (r.get("text") or "")
        if not t.strip():
            empty_claim1.append(r.get("family_id"))
            continue
        if RE_BAD_CLAIM1_PREFIX.search(t):
            bad_prefix.append(r.get("family_id"))
        if RE_BAD_CLAIMS_HEADER.search(t):
            bad_header.append(r.get("family_id"))

    if empty_claim1:
        raise SystemExit(f"[fail] claim_1 has empty text for families (sample): {empty_claim1[:20]}")
    if bad_prefix:
        raise SystemExit(f"[fail] claim_1 not clean (still has '1.' prefix) sample: {bad_prefix[:20]}")
    if bad_header:
        raise SystemExit(f"[fail] claim_1 not clean (still has 'Claims (N)' header) sample: {bad_header[:20]}")

    # 5) Chunk type correctness
    for name, recs, expected in [
        ("claim_1", c1, "claim_1"),
        ("claim_set", cs, "claim_set"),
        ("spec", sp, "spec"),
    ]:
        wrong = [r.get("family_id") for r in recs if r.get("chunk_type") != expected]
        if wrong:
            raise SystemExit(f"[fail] {name}: wrong chunk_type sample: {wrong[:20]}")

    print("[ok] chunks_v2 validation PASS")
    print(" run_id:", args.run_id)
    print(" families:", len(s1))
    print(" files:", str(chunks_dir))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
