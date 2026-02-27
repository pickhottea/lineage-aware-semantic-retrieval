#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
INP = ROOT / "artifacts" / "ops_family_members.jsonl"
OUT = ROOT / "artifacts" / "global_publications_v1.ndjson"

# 你指定的 landscape merge key（只在 landscape 合併，claim interpretation 仍分離）
COLLIDE = {"71103201", "78817222"}
COLLIDE_KEY = "LC_71103201_78817222"

def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def as_str(x):
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    if isinstance(x, (int, float, bool)):
        return str(x)
    if isinstance(x, dict):
        # OPS 常見可能長這樣 {"$":"WO"} 或 {"@country":"WO"} 或 {"country":"WO"}
        for k in ("$", "country", "@country", "cc", "jurisdiction", "value"):
            v = x.get(k)
            if isinstance(v, str):
                return v
        return ""
    return ""


def main() -> int:
    if not INP.exists():
        raise SystemExit(f"missing input: {INP}")

    OUT.parent.mkdir(parents=True, exist_ok=True)

    seen = set()
    rows = 0
    pubs = 0

    with OUT.open("w", encoding="utf-8") as fo:
        for line in INP.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)

            seed_pub = rec.get("seed_publication_number")
            seed_docdb = rec.get("seed_publication_docdb")
            ops_family_id = rec.get("ops_family_id")
            members = rec.get("family_members") or []
            fetched_at = rec.get("fetched_at")

            # IMPORTANT: 你 dataset 的 family_id 在 Step B 沒有帶過來
            # 所以 global 展開這一步用 ops_family_id 當 family_key
            # 後面要回接 dataset family_id，我們會用 patents_v3 / raw_pub_to_family_id_v2.json 去 join
            family_key = str(ops_family_id or "")

            for m in members:
                pubno = as_str(m.get("publication_number")).strip()
                docdb = as_str(m.get("publication_docdb")).strip()
                jur = as_str(m.get("jurisdiction")).strip()


                if not pubno or not docdb or not jur:
                    continue

                # 以 publication_docdb 為唯一鍵去重（同一 family 內可能重複）
                uniq_key = docdb
                if uniq_key in seen:
                    continue
                seen.add(uniq_key)

                # ES _id：global pub-level 唯一
                _id = sha1("globalpub|" + docdb)

                doc = {
                    "doc_id": _id,
                    "publication_number": pubno,
                    "publication_docdb": docdb,
                    "jurisdiction": jur,
                    "ops_family_id": family_key,
                    "seed_publication_number": seed_pub,
                    "seed_publication_docdb": seed_docdb,
                    "is_seed": bool(m.get("is_seed")),
                    "fetched_at": fetched_at or now(),
                }

                # bulk ndjson: action + source
                fo.write(json.dumps({"index": {"_index": "global_publications_v1", "_id": _id}}, ensure_ascii=False) + "\n")
                fo.write(json.dumps(doc, ensure_ascii=False) + "\n")
                pubs += 1

            rows += 1

    print(json.dumps({"rows": rows, "unique_publications": pubs, "out": str(OUT)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
