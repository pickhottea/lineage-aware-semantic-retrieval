#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# -----------------------------
# Canonical config
# -----------------------------
SRC_DIR = "artifacts/chroma_patents_v1__LEGACY_MINILM_NO_METADATA"
SRC_COLLECTION = "patent_chunks_v1"

DST_DIR = "artifacts/chroma_patents_patentsberta_v1"
DST_COLLECTION = "patent_chunks_patentsberta_v1"

EMB_MODEL = "AI-Growth-Lab/PatentSBERTa"

BATCH = 128


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    print("[info] source:", SRC_DIR, SRC_COLLECTION)
    print("[info] target:", DST_DIR, DST_COLLECTION)
    print("[info] embedding model:", EMB_MODEL)

    # Source
    src_client = chromadb.PersistentClient(path=SRC_DIR, settings=Settings(anonymized_telemetry=False))
    src = src_client.get_collection(SRC_COLLECTION)

    total = src.count()
    print("[info] source count:", total)

    # IMPORTANT: Chroma get() include does NOT accept "ids"
    got = src.get(include=["documents", "metadatas"])
    ids = got["ids"]
    docs = got["documents"]
    metas = got["metadatas"]

    if not (len(ids) == len(docs) == len(metas)):
        raise RuntimeError(f"length mismatch: ids={len(ids)} docs={len(docs)} metas={len(metas)}")

    print("[info] fetched:", len(ids))

    # Embedder
    model = SentenceTransformer(EMB_MODEL)
    try:
        model.max_seq_length = 512
    except Exception:
        pass

    # Target
    dst_client = chromadb.PersistentClient(path=DST_DIR, settings=Settings(anonymized_telemetry=False))

    # drop existing collection if any
    try:
        dst_client.delete_collection(DST_COLLECTION)
        print("[warn] deleted existing target collection:", DST_COLLECTION)
    except Exception:
        pass

    dst = dst_client.create_collection(
        name=DST_COLLECTION,
        metadata={
            "embedding_model": EMB_MODEL,
            "embedding_version": "v1",
            "built_at": utc_now(),
            "source_collection": f"{SRC_DIR}/{SRC_COLLECTION}",
            "status": "PRODUCTION_CANONICAL",
            "note": "Rebuilt from legacy Chroma docs/metadatas; embeddings recomputed with PatentSBERTa.",
        },
    )

    # Rebuild
    t0 = time.time()
    for i in range(0, len(ids), BATCH):
        batch_ids = ids[i : i + BATCH]
        batch_docs = docs[i : i + BATCH]
        batch_metas = metas[i : i + BATCH]

        safe_docs = [(d or "") for d in batch_docs]
        embs = model.encode(safe_docs, normalize_embeddings=True).tolist()

        dst.add(ids=batch_ids, documents=safe_docs, metadatas=batch_metas, embeddings=embs)
        print(f"[info] wrote {min(i+BATCH, len(ids))}/{len(ids)}")

    elapsed = round(time.time() - t0, 2)
    print("[ok] done. target count:", dst.count(), "elapsed_s:", elapsed)

    # Registry (external audit)
    reg = {
        "status": "PRODUCTION_CANONICAL",
        "embedding_model": EMB_MODEL,
        "embedding_version": "v1",
        "built_at": utc_now(),
        "target": {"chroma_dir": DST_DIR, "collection": DST_COLLECTION, "count": dst.count()},
        "source": {"chroma_dir": SRC_DIR, "collection": SRC_COLLECTION, "count": total},
        "note": "Chroma collection metadata + registry file both recorded to prevent drift.",
    }
    with open("artifacts/PROD_EMBEDDING_REGISTRY.json", "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)

    print("[ok] wrote artifacts/PROD_EMBEDDING_REGISTRY.json")


if __name__ == "__main__":
    main()
