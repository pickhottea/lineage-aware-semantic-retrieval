#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

import chromadb
from sentence_transformers import SentenceTransformer


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def fail(msg: str):
    print(f"[FATAL] {msg}")
    sys.exit(1)


# -------------------------------------------------
# Main
# -------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_id", required=True)
    ap.add_argument("--model_key", required=True,
                    help="patentsberta or bge-m3")
    ap.add_argument("--persist_root",
                    default="artifacts/_prod_semantic")
    ap.add_argument("--track", default="trackA")
    ap.add_argument("--expected_families", type=int, default=95)
    args = ap.parse_args()

    run_id = args.run_id
    model_key = args.model_key
    expected_families = args.expected_families

    alias_map = {
        "patentsberta": "AI-Growth-Lab/PatentSBERTa",
        "bge-m3": "BAAI/bge-m3",
    }

    if model_key not in alias_map:
        fail(f"Unknown model_key: {model_key}")

    hf_model = alias_map[model_key]

    embedding_version_id = (
        f"{model_key}__v2.0__{args.track}__ascii_en_like"
    )

    chunk_dir = Path(
        f"artifacts/_pipeline_runs/{run_id}/chunks_v2"
    )

    if not chunk_dir.exists():
        fail("chunks_v2 directory not found")

    files = {
        "claim_1": chunk_dir / "claim_1.jsonl",
        "claim_set": chunk_dir / "claim_set.jsonl",
        "spec": chunk_dir / "spec.jsonl",
    }

    # -------------------------------------------------
    # Step 1: Load + Track A filter
    # -------------------------------------------------

    filtered_rows = {}
    family_sets = {}

    for chunk_type, path in files.items():
        rows = load_jsonl(path)
        rows = [
            r for r in rows
            if r.get("claims_lang_hint") == "ascii_en_like"
        ]

        fams = sorted({r["family_id"] for r in rows})

        if len(fams) != expected_families:
            fail(
                f"{chunk_type} families={len(fams)} "
                f"!= expected {expected_families}"
            )

        filtered_rows[chunk_type] = rows
        family_sets[chunk_type] = set(fams)

    # family consistency gate
    fam_base = family_sets["claim_1"]
    for k in family_sets:
        if family_sets[k] != fam_base:
            fail("Family sets mismatch across chunk types")

    print("[OK] Track A gate passed (95 families consistent)")

    # -------------------------------------------------
    # Step 2: Initialize model
    # -------------------------------------------------

    print(f"[info] loading model {hf_model}")
    model = SentenceTransformer(hf_model)

    dim = model.get_sentence_embedding_dimension()

    # -------------------------------------------------
    # Step 3: Create output dir (NO overwrite)
    # -------------------------------------------------

    persist_dir = Path(args.persist_root) / f"{model_key}_v2_trackA_en95"

    if persist_dir.exists():
        fail(
            f"Persist dir already exists: {persist_dir} "
            "(no overwrite allowed)"
        )

    persist_dir.mkdir(parents=True)

    client = chromadb.PersistentClient(path=str(persist_dir))

    # -------------------------------------------------
    # Step 4: Embed per chunk_type → separate collection
    # -------------------------------------------------

    manifest = {
        "run_id": run_id,
        "embedding_version_id": embedding_version_id,
        "model": hf_model,
        "embedding_dim": dim,
        "chunk_policy_version": "v2.0",
        "track": args.track,
        "created_at": utc_now(),
        "collections": {}
    }

    for chunk_type, rows in filtered_rows.items():

        collection_name = (
            f"{chunk_type}__{model_key}__v2_0__trackA__en95"
        )

        collection = client.get_or_create_collection(
            name=collection_name
        )

        texts = [r["text"] for r in rows]

        embeddings = model.encode(
            texts,
            show_progress_bar=True
        )

        ids = []
        metadatas = []

        for r in rows:
            vector_id = (
                f"{r['family_id']}#"
                f"{chunk_type}#"
                f"{embedding_version_id}"
            )

            ids.append(vector_id)

            meta = {
                "vector_id": vector_id,
                "family_id": r["family_id"],
                "selected_publication": r["selected_publication"],
                "source": "GOOGLE",
                "chunk_type": chunk_type,
                "chunk_policy_version": "v2.0",
                "embedding_version_id": embedding_version_id,
                "run_id": run_id,
                "embedded_at": utc_now(),
                "claims_lang_hint": r.get("claims_lang_hint"),
            }

            metadatas.append(meta)

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        manifest["collections"][collection_name] = {
            "count": len(ids)
        }

        print(f"[OK] {collection_name} → {len(ids)} vectors")

    # -------------------------------------------------
    # Step 5: Write manifest
    # -------------------------------------------------

    manifest_path = (
        Path(f"artifacts/_pipeline_runs/{run_id}")
        / f"embedding_manifest_{model_key}.json"
    )

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("[DONE] Embedding complete + manifest written")


if __name__ == "__main__":
    main()
