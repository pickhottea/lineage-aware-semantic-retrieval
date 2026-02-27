#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import json, hashlib
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
IN_JSONL = ROOT / "artifacts" / "representation_selection_report.jsonl"
OUT_JSONL = ROOT / "artifacts" / "representation_selection_report_v2_ids.jsonl"

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def main() -> None:
    if not IN_JSONL.exists():
        raise SystemExit(f"Missing input: {IN_JSONL}")

    rows = [json.loads(l) for l in IN_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for r in rows:
            seed = (r.get("seed_publication_number") or "").strip().upper()
            created_at = (r.get("created_at") or "").strip()

            # 1) event_id: identifies this Step B record
            r["event_id"] = sha1("step_b|" + seed + "|" + created_at)

            # 2) asset_id: keep your existing logic, but ensure it exists
            fam_id = r.get("family_id")
            r["asset_id"] = sha1("family|" + (str(fam_id).strip() if fam_id else seed))

            # 3) pub_id for each publication record (publication-level stable ID)
            pubs = r.get("family_publications") or []
            if isinstance(pubs, list):
                for p in pubs:
                    docdb = (p.get("docdb") or "").strip().upper()
                    if docdb:
                        p["pub_id"] = sha1("pub|" + docdb)

            # optional: also tag selected publication pub_id
            sel = (r.get("selected_publication_number") or "").strip().upper()
            if sel:
                r["selected_pub_id"] = sha1("pub|" + sel)

            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[ok] wrote {len(rows)} rows -> {OUT_JSONL}")

if __name__ == "__main__":
    main()
