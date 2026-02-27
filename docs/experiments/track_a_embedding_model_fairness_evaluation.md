# Track A — Embedding Model Fairness Evaluation (English-only)

---

# 🎯 Objective

To compare embedding models for patent semantic retrieval under a controlled,
governance-aware boundary.

This track isolates embedding behavior by controlling:

- Canonical text source (Google-only)
- Chunk policy (v2.0)
- English-only family gate (95 families)
- Vector store structure (Chroma)
- Query set (frozen)

---

# 🧱 Experimental Boundary

Dataset:
- 150 seed families (OPS landscape)
- Semantic layer uses Google canonical text only
- English-only subset: 95 families (claims_lang_hint = ascii_en_like)

Chunk Policy:
- v2.0
- Exactly 3 vectors per family:
  - claim_1
  - claim_set
  - spec
- No OPS XML mixing

Embedding Models Compared:
- PatentSBERTa
- bge-m3 (multilingual)

Vector Store:
- Chroma
- Separate collection per model & layer

Retrieval Protocol:
- Top-3 retrieval per query
- Family-level collapse (no chunk-level scoring)
- Manual relevance assessment

---

# 📊 Unit of Evaluation

Evaluation is performed at:

- Query-level
- Layer-level (claim_1 / claim_set / spec)
- Family-level (after collapse)
- Top-3 precision comparison

⚠ This track does NOT compute full Recall@10.
It evaluates Top-3 retrieval robustness under semantic stress.

---

# 🔬 Semantic Stress Dimensions

Queries are designed to stress five semantic axes:

- Structural
- Functional
- Causal
- Noise
- Reversal

Each dimension isolates a different semantic weakness.

---

# 📁 Relevant Artifacts

Chunks:
artifacts/_pipeline_runs/<RUN_ID>/chunks_v2/

Embedding manifests:
artifacts/_pipeline_runs/<RUN_ID>/embedding_v2/

Evaluation outputs:
experiments/semantic_trackA_en95_v2/outputs/

---

# 🚫 Out of Scope

Track A does NOT evaluate:

- GPT reasoning stability
- Multilingual coverage robustness
- UI / RAG interface behavior

Those belong to Track B.

Track A evaluates embedding retrieval behavior only.
