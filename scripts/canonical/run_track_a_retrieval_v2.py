#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Track A retrieval runner (retrieval-only, no LLM).
Runs: 10 queries × (2 models × 3 layers) and dumps top-k hits to JSONL.

Assumptions:
- You already built Chroma collections for Track A en95.
- Each collection stores metadata keys at least:
  family_id, publication or selected_publication, chunk_type, vector_id, embedding_version_id
- You provide a config JSON describing each model's chroma_path, embedding_model, and collection names per layer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


def read_jsonl(p: Path) -> List[Dict[str, Any]]:
    rows = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def pick(meta: Dict[str, Any], *keys: str) -> Optional[Any]:
    for k in keys:
        if k in meta and meta[k] not in (None, ""):
            return meta[k]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="Path to retrieval config JSON (see template below).")
    ap.add_argument("--query_set", required=True, help="Path to track_a_query_set_v2.jsonl")
    ap.add_argument("--top_k", type=int, default=10)
    ap.add_argument("--n_results", type=int, default=50, help="Raw chunk candidates before collapsing (>= top_k).")
    ap.add_argument("--out", default="artifacts/_pipeline_runs/trackA_eval/retrieval_runs_v2.jsonl")
    args = ap.parse_args()

    cfg_path = Path(args.config).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    repo_root = cfg_path.parent.parent.parent.resolve()  # experiments/<exp>/config.json -> repo root
    query_rows = read_jsonl(Path(args.query_set).resolve())

    out_rows: List[Dict[str, Any]] = []

    for model in cfg["models"]:
        model_name = model["name"]
        emb_model_name = model["embedding_model"]
        chroma_path_raw = Path(model["chroma_path"])
        chroma_path = chroma_path_raw if chroma_path_raw.is_absolute() else (repo_root / chroma_path_raw)
        chroma_path = chroma_path.resolve()
        collections = model["collections"]  # {"claim_1": "...", "claim_set": "...", "spec": "..."}

        st = SentenceTransformer(emb_model_name)
        try:
            # keep stable behavior; you may override in model profile later
            st.max_seq_length = int(model.get("max_seq_length", 384))
        except Exception:
            pass

        client = chromadb.PersistentClient(
            path=str(chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )

        for layer in ("claim_1", "claim_set", "spec"):
            col_name = collections[layer]
            col = client.get_collection(col_name)

            for q in query_rows:
                qid = q["query_id"]
                qtype = q["query_type"]
                qtext = q["query_text"]

                qemb = st.encode([qtext], normalize_embeddings=True).tolist()[0]

                res = col.query(
                    query_embeddings=[qemb],
                    n_results=int(args.n_results),
                    include=["documents", "metadatas", "distances"],
                )

                docs = res.get("documents", [[]])[0]
                metas = res.get("metadatas", [[]])[0]
                dists = res.get("distances", [[]])[0]

                # Collapse to unique family_id (family-level ranking)
                seen_fams = set()
                hits = []
                for doc, meta, dist in zip(docs, metas, dists):
                    meta = meta or {}
                    fam = pick(meta, "family_id")
                    if not fam:
                        continue
                    if fam in seen_fams:
                        continue
                    seen_fams.add(fam)

                    pub = pick(meta, "publication", "selected_publication")
                    chunk_type = pick(meta, "chunk_type") or layer
                    preview = (doc or "").replace("\n", " ").strip()
                    preview = preview[:260]

                    hits.append(
                        {
                            "rank": len(hits) + 1,
                            "distance": float(dist),
                            "family_id": fam,
                            "publication": pub,
                            "chunk_type": chunk_type,
                            "vector_id": pick(meta, "vector_id"),
                            "embedding_version_id": pick(meta, "embedding_version_id"),
                            "preview": preview,
                        }
                    )
                    if len(hits) >= int(args.top_k):
                        break

                out_rows.append(
                    {
                        "query_id": qid,
                        "query_type": qtype,
                        "query_text": qtext,
                        "model": model_name,
                        "layer": layer,
                        "collection": col_name,
                        "top_k": int(args.top_k),
                        "hits": hits,
                    }
                )

                print(f"[ok] {model_name} / {layer} / {qid} -> {len(hits)} hits")

    out_path_raw = Path(args.out)
    out_path = out_path_raw if out_path_raw.is_absolute() else (repo_root / out_path_raw)
    out_path = out_path.resolve()
    write_jsonl(out_path, out_rows)
    print(f"\n[DONE] wrote -> {out_path}")


if __name__ == "__main__":
    main()
