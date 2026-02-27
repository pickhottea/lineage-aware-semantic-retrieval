#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import chromadb
from sentence_transformers import SentenceTransformer


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


Q12: List[Dict[str, str]] = [
    # A) Structural / Mechanical
    {"qid": "S1", "category": "structural", "query": "LED lamp shade structure for improving light extraction efficiency"},
    {"qid": "S2", "category": "structural", "query": "mechanical arrangement of LED module components without modifying electrode design"},
    {"qid": "S3", "category": "structural", "query": "structural connection between sensor device and lighting unit"},

    # B) Functional / Effect
    {"qid": "F1", "category": "functional", "query": "method for reducing power consumption while increasing brightness in LED luminaire"},
    {"qid": "F2", "category": "functional", "query": "lighting system that activates only when motion is detected in dark environment"},
    {"qid": "F3", "category": "functional", "query": "improving luminous efficiency through mechanical configuration"},

    # C) Electronic / Control
    {"qid": "E1", "category": "electronic", "query": "motion sensing switch for automatic lighting control"},
    {"qid": "E2", "category": "electronic", "query": "sensor-based activation mechanism for LED lighting system"},
    {"qid": "E3", "category": "electronic", "query": "power-saving lighting control circuit with object detection"},

    # D) Definition / Terminology
    {"qid": "D1", "category": "definition", "query": "definition of optical axis in LED lighting device"},
    {"qid": "D2", "category": "definition", "query": "meaning of luminous efficiency in semiconductor lighting"},
    {"qid": "D3", "category": "definition", "query": "as used herein the term LED module housing"},
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--persist_dir", default="vector_db")
    ap.add_argument("--collection", default="spec_all_A")
    ap.add_argument("--model", default="AI-Growth-Lab/PatentSBERTa")
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--out", default="artifacts/eval_spec_all_A_q12_v1.jsonl")
    args = ap.parse_args()

    persist_dir = args.persist_dir
    collection_name = args.collection
    topk = args.topk
    out_path = Path(args.out)

    client = chromadb.PersistentClient(path=persist_dir)
    col = client.get_collection(collection_name)

    model = SentenceTransformer(args.model)
    try:
        model.max_seq_length = 512
    except Exception:
        pass

    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[info] collection={collection_name} topk={topk} out={out_path}")

    with out_path.open("w", encoding="utf-8") as f:
        for q in Q12:
            qid = q["qid"]
            cat = q["category"]
            text = q["query"]

            q_emb = model.encode([text])[0]

            res = col.query(
                query_embeddings=[q_emb],
                n_results=topk,
                include=["documents", "metadatas", "distances"],
            )

            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[]])[0]

            hits: List[Dict[str, Any]] = []
            for doc, meta, dist in zip(docs, metas, dists):
                doc = doc or ""
                meta = meta or {}
                hits.append({
                    "distance": dist,
                    "selected_publication": meta.get("selected_publication"),
                    "jurisdiction": meta.get("jurisdiction"),
                    "chunk_type": meta.get("chunk_type"),
                    "spec_source": meta.get("spec_source"),
                    "family_id": meta.get("family_id"),
                    "asset_id": meta.get("asset_id"),
                    "preview": doc[:300].replace("\n", " "),
                })

            rec = {
                "run_id": "q12_spec_v1",
                "created_at": now_iso(),
                "persist_dir": persist_dir,
                "collection": collection_name,
                "model": args.model,
                "topk": topk,
                "qid": qid,
                "category": cat,
                "query": text,
                "hits": hits,
            }

            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

            # tiny console summary
            if hits:
                h0 = hits[0]
                print(f"[{qid}] {cat} -> top1={h0.get('jurisdiction')} {h0.get('selected_publication')} dist={h0.get('distance'):.4f}")
            else:
                print(f"[{qid}] {cat} -> NO HITS")

    print("[done] wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
