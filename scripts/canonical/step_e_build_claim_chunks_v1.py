#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def first_existing_path(row: Dict[str, Any], keys: List[str]) -> Optional[Path]:
    for k in keys:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            p = Path(v)
            if p.exists() and p.is_file():
                return p
    return None


def guess_jurisdiction(selected_publication: str) -> str:
    p = (selected_publication or "").upper()
    if p.startswith("US."):
        return "US"
    if p.startswith("EP."):
        return "EP"
    if p.startswith("WO."):
        return "WO"
    return "UNK"


# ---- Parsing helpers ----

_claim_line_re = re.compile(r"^\s*(\d{1,3})\s*[\.\)]\s+(.*\S)\s*$")


def parse_claims_from_google_txt(txt: str) -> List[Tuple[int, str]]:
    """
    Google fallback cache is plain text extracted from HTML claims section.
    We try to split into numbered claims like:
      1. ...
      2. ...
    If numbering is missing, fallback to whole text as claim 1.
    """
    lines = (txt or "").splitlines()
    claims: List[Tuple[int, str]] = []
    buf_no: Optional[int] = None
    buf: List[str] = []

    def flush():
        nonlocal buf_no, buf
        if buf_no is None:
            return
        t = " ".join(x.strip() for x in buf if x.strip()).strip()
        if t:
            claims.append((buf_no, t))
        buf_no, buf = None, []

    for ln in lines:
        m = _claim_line_re.match(ln)
        if m:
            flush()
            buf_no = int(m.group(1))
            buf = [m.group(2)]
        else:
            if buf_no is not None:
                buf.append(ln)

    flush()
    if not claims:
        t = " ".join(x.strip() for x in lines if x.strip()).strip()
        if t:
            claims = [(1, t)]
    return claims


def parse_claims_from_ops_claims_xml(xml_text: str) -> List[Tuple[int, str]]:
    """
    Best-effort OPS claims XML parsing:
    Find <claim ...> blocks, read claim-number if available, else enumerate.
    """
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []

    claims: List[Tuple[int, str]] = []

    claim_nodes = root.findall(".//{*}claim")
    if not claim_nodes:
        return []

    for idx, c in enumerate(claim_nodes, start=1):
        # try claim number from attributes or nested tags
        no = None
        for k in ["num", "id", "claim-num", "number"]:
            v = c.attrib.get(k)
            if v and str(v).isdigit():
                no = int(v)
                break

        # Some XML uses <claim-number> or <number>
        if no is None:
            n1 = c.find(".//{*}claim-number")
            if n1 is not None:
                t = "".join(n1.itertext()).strip()
                if t.isdigit():
                    no = int(t)
            if no is None:
                n2 = c.find(".//{*}number")
                if n2 is not None:
                    t = "".join(n2.itertext()).strip()
                    if t.isdigit():
                        no = int(t)

        if no is None:
            no = idx

        text = " ".join("".join(c.itertext()).split())
        text = text.strip()
        if text:
            claims.append((no, text))

    # de-dup by claim_no keep first
    seen = set()
    out: List[Tuple[int, str]] = []
    for no, t in claims:
        if no in seen:
            continue
        seen.add(no)
        out.append((no, t))
    return out


_dep_re = re.compile(r"\bclaim\s+(\d{1,3})\b", re.I)


def infer_dependency(claim_text: str) -> Optional[int]:
    """
    Conservative: detect explicit 'claim N' reference.
    If multiple, pick the first.
    """
    m = _dep_re.search(claim_text or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def claim_type(no: int, depends_on: Optional[int]) -> str:
    if no == 1:
        return "independent"
    return "dependent" if depends_on is not None else "independent"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default="artifacts/claims_representation_v3.jsonl")
    ap.add_argument("--out", default="artifacts/chunks_claims_all_v1.jsonl")
    args = ap.parse_args()

    rows = load_jsonl(args.in_path)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Candidate path keys (be tolerant to schema drift)
    TXT_KEYS = [
        "claims_google_text_path",
        "claims_text_path",
        "claims_raw_text_path",
        "claims_path",
    ]
    XML_KEYS = [
        "claims_raw_xml_path",
        "claims_xml_path",
    ]

    total_docs = 0
    wrote = 0
    miss = 0

    with out_path.open("w", encoding="utf-8") as out:
        for r in rows:
            selected_pub = str(r.get("selected_publication") or "")
            if not selected_pub:
                continue

            total_docs += 1
            jurisdiction = guess_jurisdiction(selected_pub)

            family_id = r.get("family_id")
            asset_id = r.get("asset_id")

            claims_source = r.get("claims_source")
            selected_source = r.get("selected_source")
            governance_flags = r.get("governance_flags") or []

            # Google lineage fields (optional)
            google_seed = r.get("google_seed_publication")
            google_resolved = r.get("google_resolved_publication")
            google_status = r.get("google_status")

            # Load claims content from cache path
            txt_path = first_existing_path(r, TXT_KEYS)
            xml_path = first_existing_path(r, XML_KEYS)

            claims: List[Tuple[int, str]] = []

            if txt_path is not None:
                txt = txt_path.read_text(encoding="utf-8", errors="ignore")
                claims = parse_claims_from_google_txt(txt)
            elif xml_path is not None:
                xml = xml_path.read_text(encoding="utf-8", errors="ignore")
                claims = parse_claims_from_ops_claims_xml(xml)

            if not claims:
                miss += 1
                continue

            for no, text in claims:
                depends_on = infer_dependency(text)
                ctype = claim_type(no, depends_on)

                chunk_id = sha1(f"claim|{selected_pub}|{no}|{sha1(text)}")
                rec = {
                    "chunk_id": chunk_id,
                    "chunk_type": "claim",
                    "family_id": family_id,
                    "asset_id": asset_id,
                    "selected_publication": selected_pub,
                    "jurisdiction": jurisdiction,
                    "claim_no": no,
                    "claim_type": ctype,
                    "depends_on": depends_on,
                    "claims_source": claims_source,
                    "selected_source": selected_source,
                    "governance_flags": governance_flags,
                    # Google lane (carry through if exists)
                    "google_seed_publication": google_seed,
                    "google_resolved_publication": google_resolved,
                    "google_status": google_status,
                    # provenance (paths if present)
                    "claims_google_text_path": str(txt_path) if txt_path else None,
                    "claims_raw_xml_path": str(xml_path) if xml_path else None,
                    "text": text,
                    "created_at": now_iso(),
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                wrote += 1

    print(f"[done] wrote {out_path}")
    print(f"  total_docs={total_docs} docs_with_no_claims={miss} claim_chunks={wrote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
