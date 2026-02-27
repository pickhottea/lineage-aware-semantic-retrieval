#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Semantic Chunk Policy v2.0 — Controlled Chunk Generation (Canonical)

Inputs:
- artifacts/_pipeline_runs/<RUN_ID>/02_text/google_raw/*.json
- artifacts/raw_pub_to_family_id.json   (seed publication -> dataset_family_id mapping)

Outputs:
- artifacts/_pipeline_runs/<RUN_ID>/chunks_v2/claim_1.jsonl
- artifacts/_pipeline_runs/<RUN_ID>/chunks_v2/claim_set.jsonl
- artifacts/_pipeline_runs/<RUN_ID>/chunks_v2/spec.jsonl

Policy guarantees:
- Google-only text source
- Exactly 3 chunk records per family_id
- Deterministic extraction and ordering
- Claim 1 is "clean" (prefix/header stripped)
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Optional


CHUNK_POLICY_VERSION = "v2.0"
SOURCE = "GOOGLE"

# --- Normalization helpers ----------------------------------------------------

_RE_WS = re.compile(r"[ \t]+")
_RE_MULTIBLANK = re.compile(r"\n{3,}")

# Common Google header noise at top of claims section
# Examples:
#   Claims (
#   10
#   )
# Or:
#   Claims (10)
_RE_CLAIMS_HEADER_BLOCK = re.compile(
    r"(?is)^\s*claims?\s*(\(\s*\d+\s*\))?\s*(\n|\r\n)+\s*(\d+\s*(\n|\r\n)+\s*)?\)\s*(\n|\r\n)+"
)
_RE_CLAIMS_HEADER_INLINE = re.compile(r"(?is)^\s*claims?\s*\(\s*\d+\s*\)\s*")

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def normalize_text(t: str) -> str:
    t = (t or "").replace("\r\n", "\n").strip()
    t = _RE_WS.sub(" ", t)
    t = _RE_MULTIBLANK.sub("\n\n", t)
    return t.strip()

def strip_google_claims_header(claims_raw: str) -> str:
    txt = (claims_raw or "").replace("\r\n", "\n").strip()
    # block style
    txt2 = _RE_CLAIMS_HEADER_BLOCK.sub("", txt)
    if txt2 != txt:
        return txt2.strip()
    # inline style
    txt2 = _RE_CLAIMS_HEADER_INLINE.sub("", txt)
    return txt2.strip()

def strip_numbering_prefix(line: str) -> str:
    """
    Remove common claim numbering prefix at start of a claim body.
    E.g. "1. A lamp..." -> "A lamp..."
         "1) A lamp..." -> "A lamp..."
         "1: A lamp..." -> "A lamp..."
    """
    return re.sub(r"^\s*1\s*[\.):]\s*", "", line or "").strip()


# --- Claim parsing (deterministic, conservative) ------------------------------

# English-style numbered claim starts: "1. ", "2) ", "10: "
_RE_NUM_CLAIM_START = re.compile(r"(?m)^\s*(\d{1,4})\s*[\.):]\s+")

# CJK markers for claim starts (JP/CN/KR)
# We treat these as "claim headers" and try to segment by claim number.
_RE_JP_START = re.compile(r"(請求項\s*([0-9０-９]+))")
_RE_CN_START = re.compile(r"((?:权利要求|權利要求)\s*([0-9０-９]+))")
_RE_KR_START = re.compile(r"(청구항\s*([0-9０-９]+))")

def _to_int_digit(s: str) -> Optional[int]:
    if not s:
        return None
    # normalize full-width digits
    fw = str.maketrans("０１２３４５６７８９", "0123456789")
    s2 = s.translate(fw).strip()
    if s2.isdigit():
        return int(s2)
    return None

@dataclass
class ParsedClaims:
    method: str                  # NUMBERED / CJK_MARKER / UNNUMBERED_FALLBACK
    claims_by_no: Dict[int, str] # {1: "body", 2: "body", ...}
    raw_cleaned: str             # claims text after header stripping

def parse_claims_to_map(claims_raw: str) -> ParsedClaims:
    raw = strip_google_claims_header(claims_raw)
    txt = raw.replace("\r\n", "\n").strip()

    # 1) English-numbered segmentation
    matches = list(_RE_NUM_CLAIM_START.finditer(txt))
    if matches:
        spans: List[Tuple[int, int, int]] = []  # (no, start, end)
        for idx, m in enumerate(matches):
            no = int(m.group(1))
            start = m.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(txt)
            spans.append((no, start, end))

        claims: Dict[int, str] = {}
        for no, start, end in spans:
            seg = txt[start:end].strip()
            # remove the leading "N. " prefix
            seg = re.sub(r"^\s*\d{1,4}\s*[\.):]\s+", "", seg).strip()
            seg = normalize_text(seg)
            # keep first occurrence deterministically
            if no not in claims and seg:
                claims[no] = seg

        if claims:
            return ParsedClaims(method="NUMBERED", claims_by_no=claims, raw_cleaned=normalize_text(txt))

    # 2) CJK marker segmentation (JP/CN/KR)
    # We do a single pass looking for any marker occurrences and segment by earliest positions.
    markers: List[Tuple[int, int, str]] = []  # (claim_no, pos, marker_type)
    for m in _RE_JP_START.finditer(txt):
        no = _to_int_digit(m.group(2))
        if no is not None:
            markers.append((no, m.start(), "JP"))
    for m in _RE_CN_START.finditer(txt):
        no = _to_int_digit(m.group(2))
        if no is not None:
            markers.append((no, m.start(), "CN"))
    for m in _RE_KR_START.finditer(txt):
        no = _to_int_digit(m.group(2))
        if no is not None:
            markers.append((no, m.start(), "KR"))

    if markers:
        markers.sort(key=lambda x: x[1])  # by position in text
        claims: Dict[int, str] = {}
        for idx, (no, pos, _typ) in enumerate(markers):
            end = markers[idx + 1][1] if idx + 1 < len(markers) else len(txt)
            seg = txt[pos:end].strip()
            # strip the leading marker phrase itself, keep body
            seg = re.sub(r"^(請求項|权利要求|權利要求|청구항)\s*[0-9０-９]+\s*", "", seg).strip()
            seg = normalize_text(seg)
            if no not in claims and seg:
                claims[no] = seg

        if claims:
            return ParsedClaims(method="CJK_MARKER", claims_by_no=claims, raw_cleaned=normalize_text(txt))

    # 3) Unnumbered fallback
    # Deterministic: treat the first substantive paragraph as "claim1" body candidate,
    # and claim_set as the entire cleaned claims text.
    cleaned = normalize_text(txt)
    return ParsedClaims(method="UNNUMBERED_FALLBACK", claims_by_no={}, raw_cleaned=cleaned)


def extract_claim1_and_claimset(claims_raw: str) -> Tuple[str, str, Dict]:
    """
    Returns:
      claim1_text (clean)
      claimset_text (deterministic concatenation)
      extraction_meta (method/reason/quality flags)
    """
    parsed = parse_claims_to_map(claims_raw)
    meta = {
        "claims_parse_method": parsed.method,
        "claim1_extraction_quality": "HIGH",
        "claim1_reason_code": None,
    }

    if parsed.method in ("NUMBERED", "CJK_MARKER") and parsed.claims_by_no:
        # claimset: numeric order, separated by TWO newlines
        ordered_nos = sorted(parsed.claims_by_no.keys())
        claimset = "\n\n".join(parsed.claims_by_no[n] for n in ordered_nos if parsed.claims_by_no.get(n))
        claimset = normalize_text(claimset)

        # claim1
        c1 = parsed.claims_by_no.get(1, "")
        c1 = normalize_text(c1)
        # extra safety: strip any residual "1." prefix
        c1 = strip_numbering_prefix(c1)

        if not c1:
            # We have numbered claims but missing 1: treat as LOW quality, fallback to first claim
            meta["claim1_extraction_quality"] = "LOW"
            meta["claim1_reason_code"] = "CLAIM1_NOT_FOUND_FALLBACK_TO_FIRST"
            first_no = ordered_nos[0]
            c1 = normalize_text(parsed.claims_by_no[first_no])
            c1 = strip_numbering_prefix(c1)

        if not claimset:
            meta["claim1_extraction_quality"] = "LOW"
            meta["claim1_reason_code"] = meta["claim1_reason_code"] or "CLAIMSET_EMPTY_AFTER_PARSE"
            claimset = normalize_text(parsed.raw_cleaned)

        return c1, claimset, meta

    # UNNUMBERED_FALLBACK
    meta["claim1_extraction_quality"] = "LOW"
    meta["claim1_reason_code"] = "UNNUMBERED_FALLBACK"

    claimset = normalize_text(parsed.raw_cleaned)
    # claim1 fallback: first non-empty line / paragraph
    c1 = ""
    for para in (claimset.split("\n\n") if claimset else []):
        p = para.strip()
        if p:
            c1 = p
            break
    c1 = strip_numbering_prefix(normalize_text(c1))

    # If still empty, keep empty (validator will catch)
    return c1, claimset, meta


# --- I/O ---------------------------------------------------------------------

def load_pub_to_family(repo: Path) -> Dict[str, str]:
    p = repo / "artifacts" / "raw_pub_to_family_id.json"
    if not p.exists():
        raise SystemExit(f"[error] missing mapping file: {p}")
    j = json.loads(p.read_text(encoding="utf-8"))
    # normalize keys to uppercase raw pubs (e.g., EP3825599A1)
    out = {}
    for k, v in j.items():
        if k and v:
            out[str(k).strip().upper()] = str(v).strip()
    return out

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_id", required=True, help="pipeline run id, e.g. 20260221T200902Z__semantic_exp_v2")
    ap.add_argument("--embedding_model", default="UNSET", help="metadata placeholder; set real model at embedding time")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[2]
    run_dir = repo / "artifacts" / "_pipeline_runs" / args.run_id
    raw_dir = run_dir / "02_text" / "google_raw"
    if not raw_dir.exists():
        raise SystemExit(f"[error] missing raw dir: {raw_dir}")

    out_dir = run_dir / "chunks_v2"
    out_dir.mkdir(parents=True, exist_ok=True)

    pub_to_family = load_pub_to_family(repo)

    claim1_out = out_dir / "claim_1.jsonl"
    claimset_out = out_dir / "claim_set.jsonl"
    spec_out = out_dir / "spec.jsonl"

    # We enforce exactly 1 record per family by deterministic "first seen" selection.
    seen_family = set()

    n_total_files = 0
    n_written = 0
    n_skipped_no_family = 0
    n_skipped_duplicate_family = 0
    n_skipped_not_ok = 0

    with claim1_out.open("w", encoding="utf-8") as f_c1, \
         claimset_out.open("w", encoding="utf-8") as f_cs, \
         spec_out.open("w", encoding="utf-8") as f_sp:

        for p in sorted(raw_dir.glob("*.json")):
            n_total_files += 1
            rec = json.loads(p.read_text(encoding="utf-8"))

            if rec.get("status") != "OK":
                n_skipped_not_ok += 1
                continue

            pub = (rec.get("publication") or "").strip().upper()
            if not pub:
                n_skipped_no_family += 1
                continue

            dataset_family_id = pub_to_family.get(pub)
            if not dataset_family_id:
                n_skipped_no_family += 1
                continue

            family_id = dataset_family_id  # policy requires family_id; we use dataset family identity deterministically

            if family_id in seen_family:
                n_skipped_duplicate_family += 1
                continue
            seen_family.add(family_id)

            claims_raw = rec.get("claims_raw") or ""
            desc_raw = rec.get("description_raw") or ""

            claim1_text, claimset_text, claim_meta = extract_claim1_and_claimset(claims_raw)
            spec_text = normalize_text(desc_raw)

            created_at = utc_now_iso()
            selected_publication = pub

            base_meta = {
                "family_id": family_id,
                "dataset_family_id": dataset_family_id,
                "selected_publication": selected_publication,
                "source": SOURCE,
                "chunk_policy_version": CHUNK_POLICY_VERSION,
                "embedding_model": args.embedding_model,
                "created_at": created_at,

                # provenance / QC signals
                "claims_lang_hint": rec.get("claims_lang_hint", ""),
                "claims_script_flags": rec.get("claims_script_flags", {}),
                "html_lang": rec.get("html_lang", ""),
                "google_resolved_slug": rec.get("google_resolved_slug", ""),
                "slug_attempts": rec.get("slug_attempts", []),
            }

            # --- claim_1 record
            c1 = {
                **base_meta,
                "chunk_type": "claim_1",
                "text": claim1_text,
                "text_chars": len(claim1_text),
                **claim_meta,
            }
            # Remove numbering prefix requirement is enforced by extraction; also enforce again defensively:
            c1["text"] = strip_numbering_prefix(c1["text"])
            c1["text"] = normalize_text(c1["text"])
            c1["text_chars"] = len(c1["text"])

            # --- claim_set record
            cs = {
                **base_meta,
                "chunk_type": "claim_set",
                "text": claimset_text,
                "text_chars": len(claimset_text),
                "claims_parse_method": claim_meta.get("claims_parse_method"),
            }

            # --- spec record
            sp = {
                **base_meta,
                "chunk_type": "spec",
                "text": spec_text,
                "text_chars": len(spec_text),
                "spec_policy": "full_description",
            }

            f_c1.write(json.dumps(c1, ensure_ascii=False) + "\n")
            f_cs.write(json.dumps(cs, ensure_ascii=False) + "\n")
            f_sp.write(json.dumps(sp, ensure_ascii=False) + "\n")
            n_written += 1

    print("[ok] chunk build complete")
    print(" run_id:", args.run_id)
    print(" raw_files_total:", n_total_files)
    print(" families_written:", n_written)
    print(" skipped_not_ok:", n_skipped_not_ok)
    print(" skipped_no_family_mapping:", n_skipped_no_family)
    print(" skipped_duplicate_family:", n_skipped_duplicate_family)
    print(" out_dir:", str(out_dir))
    print("  -", str(claim1_out))
    print("  -", str(claimset_out))
    print("  -", str(spec_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
