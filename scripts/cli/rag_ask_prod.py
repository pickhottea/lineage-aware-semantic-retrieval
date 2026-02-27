# scripts/rag_ask_prod.py
from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import chromadb
from chromadb.config import Settings
import requests
from sentence_transformers import SentenceTransformer

PROD_REGISTRY = "artifacts/PROD_EMBEDDING_REGISTRY.json"

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral:latest")


def load_registry() -> dict:
    if os.path.exists(PROD_REGISTRY):
        with open(PROD_REGISTRY, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_collection_from_registry():
    reg = load_registry()
    chroma_dir = reg.get("chroma_dir") or reg.get("path") or "artifacts/chroma_patents_patentsberta_v1"
    collection_name = reg.get("collection") or reg.get("collection_name") or "patent_chunks_patentsberta_v1"
    emb_model = reg.get("embedding_model") or "AI-Growth-Lab/PatentSBERTa"

    client = chromadb.PersistentClient(path=chroma_dir, settings=Settings(anonymized_telemetry=False))
    col = client.get_collection(collection_name)
    return col, emb_model, chroma_dir, collection_name


def get_embedder(model_name: str):
    m = SentenceTransformer(model_name)
    try:
        m.max_seq_length = 256
    except Exception:
        pass
    return m


def ollama_run(prompt: str, *, timeout_s: int = 120, num_predict: int = 220, num_ctx: int = 1536) -> str:
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": int(num_predict), "num_ctx": int(num_ctx), "temperature": 0.2},
        },
        timeout=int(timeout_s),
    )
    r.raise_for_status()
    data = r.json()
    return (data.get("response") or "").strip()


def scope_where(scope: str) -> Dict[str, Any] | None:
    s = (scope or "all").strip().lower()
    if s == "claim":
        return {"chunk_type": "claim"}
    if s == "spec":
        return {"chunk_type": "spec_fulltext"}
    return None


def retrieve_grouped_fast(
    query: str,
    *,
    scope: str = "spec",
    n_results: int = 18,
    top_pubs: int = 3,
    per_pub_topk: int = 1,
    doc_cap_chars: int = 520,
) -> Tuple[List[dict], List[str], Dict[str, float]]:
    timings: Dict[str, float] = {}
    col, emb_model, _, _ = get_collection_from_registry()
    model = get_embedder(emb_model)

    t0 = time.perf_counter()
    qemb = model.encode([query], normalize_embeddings=True).tolist()[0]
    timings["embed_s"] = time.perf_counter() - t0

    t1 = time.perf_counter()
    res = col.query(
        query_embeddings=[qemb],
        n_results=int(n_results),
        where=scope_where(scope),
        include=["documents", "metadatas", "distances"],
    )
    timings["chroma_s"] = time.perf_counter() - t1

    t2 = time.perf_counter()
    by_pub: Dict[str, List[Tuple[float, str, Dict[str, Any]]]] = defaultdict(list)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, dists):
        meta = meta or {}
        pub = meta.get("publication") or meta.get("selected_publication") or "UNKNOWN"
        by_pub[pub].append((float(dist), doc or "", meta))

    pub_items: List[Tuple[float, str, List[Tuple[float, str, Dict[str, Any]]]]] = []
    for pub, lst in by_pub.items():
        lst_sorted = sorted(lst, key=lambda x: x[0])
        top_chunks = lst_sorted[: int(per_pub_topk)]
        best_dist = float(top_chunks[0][0])
        pub_items.append((best_dist, pub, top_chunks))

    pub_items.sort(key=lambda x: x[0])
    chosen = pub_items[: int(top_pubs)]

    ctx: List[str] = []
    pubs: List[dict] = []
    chunk_id = 0

    for best_dist, pub, chunks in chosen:
        pubs.append({"publication": pub, "best_distance": float(best_dist)})
        for dist, doc, meta in chunks:
            chunk_id += 1
            doc = (doc or "")[: int(doc_cap_chars)]
            ctype = meta.get("chunk_type")
            claim_no = meta.get("claim_no")
            src = meta.get("claims_source") or meta.get("spec_source")
            flags = meta.get("flags", "")
            ctx.append(
                f"[{chunk_id}] pub={pub} dist={float(dist):.4f} type={ctype} claim_no={claim_no} src={src} flags={flags}\n"
                f"{doc}\n"
            )

    timings["group_s"] = time.perf_counter() - t2
    return pubs, ctx, timings


def build_prompt_why_top3(query: str, pubs: List[dict], ctx: List[str]) -> str:
    top_lines = "\n".join([f"- {p['publication']} (best_distance={p['best_distance']:.4f})" for p in pubs])
    return f"""
You are a patent analyst assistant.

User query:
{query}

Top publications (retrieval result):
{top_lines}

Evidence chunks (cite [chunk_id]):
{chr(10).join(ctx)}

Explain:
1) Why these Top-3 match the query (1-2 sentences each, MUST cite chunk IDs).
2) For each publication:
   - technical problem
   - technical means
   - 2 short evidence snippets (<=15 words) with chunk citations.

Rules:
- Cite evidence using [1], [2]...
- Distance is retrieval distance: higher = less similar (lower is better).
Return in English.
""".strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["spec", "claim", "all"], default="spec")
    ap.add_argument("--query", default="")
    ap.add_argument("--n_results", type=int, default=18)
    ap.add_argument("--top_pubs", type=int, default=3)
    ap.add_argument("--per_pub_topk", type=int, default=1)
    ap.add_argument("--timeout_s", type=int, default=120)
    args = ap.parse_args()

    q = (args.query or "").strip()
    if not q:
        q = input("Query: ").strip()
    if not q:
        return

    pubs, ctx, timings = retrieve_grouped_fast(
        q,
        scope=args.scope,
        n_results=args.n_results,
        top_pubs=args.top_pubs,
        per_pub_topk=args.per_pub_topk,
    )

    print("\n=== Top publications ===\n")
    for i, p in enumerate(pubs, 1):
        print(f"{i}. {p['publication']}  best_distance={p['best_distance']:.4f}")

    prompt = build_prompt_why_top3(q, pubs, ctx)

    print("\n=== RAG Answer ===\n")
    t0 = time.perf_counter()
    ans = ollama_run(prompt, timeout_s=args.timeout_s)
    t1 = time.perf_counter() - t0
    print(ans)

    print(
        f"\n[timing] embed={timings.get('embed_s',0):.2f}s chroma={timings.get('chroma_s',0):.2f}s group={timings.get('group_s',0):.2f}s ollama={t1:.2f}s"
    )


if __name__ == "__main__":
    main()
