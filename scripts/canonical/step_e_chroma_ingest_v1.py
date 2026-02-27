#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from sentence_transformers import SentenceTransformer


# -----------------------------
# Utilities
# -----------------------------

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def base_id(r: Dict[str, Any], collection_name: str) -> str:
    """
    Deterministic base id.
    Might collide if identical text appears multiple times.
    """
    cid = r.get("chunk_id")
    if isinstance(cid, str) and cid.strip():
        return cid.strip()

    pub = str(r.get("selected_publication") or "")
    ctype = str(r.get("chunk_type") or "")
    jur = str(r.get("jurisdiction") or "")
    text = str(r.get("text") or "")
    th = sha1(text)

    return sha1(f"{collection_name}|{jur}|{pub}|{ctype}|{th}")


# -----------------------------
# Main
# -----------------------------

def resolve_model_name(model_arg: str) -> str:
    """
    Allow both aliases and full HuggingFace model names.
    """
    alias_map = {
        "patentsberta": "AI-Growth-Lab/PatentSBERTa",
        "bge-m3": "BAAI/bge-m3",
    }

    return alias_map.get(model_arg, model_arg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument(
        "--model",
        required=True,
        help="Embedding model alias (patentsberta, bge-m3) or full HF model name",
    )
    ap.add_argument("--collection", required=True)
    ap.add_argument("--persist_dir", default="vector_db")
    ap.add_argument("--batch_size", type=int, default=32)
    args = ap.parse_args()

    input_path = args.input
    persist_dir = args.persist_dir
    collection_name = args.collection
    batch_size = args.batch_size

    Path(persist_dir).mkdir(parents=True, exist_ok=True)

    print(f"[info] loading chunks from {input_path}")
    rows = load_jsonl(input_path)
    print(f"[info] total chunks: {len(rows)}")

    model_name = resolve_model_name(args.model)

    print(f"[info] loading embedding model: {model_name}")
    model = SentenceTransformer(model_name)

    try:
        model.max_seq_length = 512
    except Exception:
        pass

    print(f"[info] initializing Chroma PersistentClient (path={persist_dir})")
    client = chromadb.PersistentClient(path=persist_dir)

    # delete existing collection to avoid id collision issues
    try:
        client.delete_collection(collection_name)
        print(f"[info] deleted existing collection {collection_name}")
    except Exception:
        pass

    collection = client.get_or_create_collection(name=collection_name)

    print("[info] embedding and inserting...")

    total = len(rows)

    # global id collision guard (跨 batch)
    global_counts = {}

    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]

        texts = [str(r.get("text") or "") for r in batch]
        embeddings = model.encode(texts, show_progress_bar=False)

        ids = []
        for r in batch:
            bid = base_id(r, collection_name)
            n = global_counts.get(bid, 0) + 1
            global_counts[bid] = n
            ids.append(bid if n == 1 else f"{bid}__{n}")

        metadatas = []
        for r in batch:
            meta = {
                "family_id": r.get("family_id"),
                "asset_id": r.get("asset_id"),
                "selected_publication": r.get("selected_publication"),
                "jurisdiction": r.get("jurisdiction"),
                "chunk_type": r.get("chunk_type"),
                "spec_source": r.get("spec_source"),
                "claims_source": r.get("claims_source"),
            }
            metadatas.append(meta)

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        print(f"[progress] {min(i + batch_size, total)}/{total}")

    print("[done] ingestion complete")


if __name__ == "__main__":
    main()
