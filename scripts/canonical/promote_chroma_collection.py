#!/usr/bin/env python3
"""
Promote a built Chroma persist directory by writing SUCCESS.flag
only after passing minimal governance checks based on collection counts.

Usage:
  python scripts/canonical/promote_chroma_collection.py \
    --persist_dir <CHROMA_PERSIST_DIR> \
    --expected_families 95 \
    --collections <COL1> <COL2> <COL3>
"""
import argparse
from pathlib import Path

def _get_collection_count(client, name: str) -> int:
    col = client.get_collection(name=name)
    data = col.get(include=[])
    return len(data.get("ids", []))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persist_dir", required=True, help="Chroma persist directory (contains chroma.sqlite3)")
    ap.add_argument("--expected_families", type=int, required=True)
    ap.add_argument("--collections", nargs="+", required=True, help="Exact Chroma collection names to validate")
    args = ap.parse_args()

    p = Path(args.persist_dir).resolve()
    if not p.exists():
        raise SystemExit(f"persist_dir not found: {p}")

    sqlite = p / "chroma.sqlite3"
    if not sqlite.exists():
        raise SystemExit(f"Refuse to promote: chroma.sqlite3 not found in {p}")

    try:
        import chromadb
    except Exception as e:
        raise SystemExit(f"Refuse to promote: chromadb import failed: {e}")

    client = chromadb.PersistentClient(path=str(p))

    counts = {}
    for cname in args.collections:
        try:
            counts[cname] = _get_collection_count(client, cname)
        except Exception as e:
            raise SystemExit(f"Refuse to promote: cannot read collection '{cname}': {e}")

    bad = {k: v for k, v in counts.items() if v != args.expected_families}
    if bad:
        lines = "\n".join([f"- {k}: {v} (expected {args.expected_families})" for k, v in bad.items()])
        raise SystemExit("Refuse to promote: collection counts mismatch:\n" + lines)

    flag = p / "SUCCESS.flag"
    flag.write_text("ok\n", encoding="utf-8")
    print(f"PROMOTED: {flag}")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
