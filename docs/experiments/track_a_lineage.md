---

# Track A — Data Lineage & Experiment Traceability

## 1. Source Run

All Track A artifacts are derived from the following canonical pipeline run:

```
artifacts/_pipeline_runs/20260221T200902Z__semantic_exp_v2
```

This run is the authoritative source for:

- Canonical chunk packs
- Embedding manifests (PatentSBERTa / BGE-M3)
- Track A evaluation outputs

No earlier `_semantic_exp_v2` runs are considered canonical.

---

## 2. Canonical Chunk Pack (Full Set)

The pipeline produced a full semantic chunk pack for:

**150 patent families**

For each family, exactly three asset-level chunks were generated:

- `claim_1`
- `claim_set`
- `spec`

Location:

```
artifacts/_pipeline_runs/20260221T200902Z__semantic_exp_v2/chunks_v2/
```

Line counts (verified):

- `claim_1.jsonl` → 150
- `claim_set.jsonl` → 150
- `spec.jsonl` → 150

This chunk pack represents the full landscape selection (OPS family-based).

---

## 3. Language Distribution (claims_lang_hint)

Chunk metadata includes `claims_lang_hint`.

Distribution (verified from chunk files):

| claims_lang_hint | Count |
| --- | --- |
| ascii_en_like | 95 |
| nonascii_other | 29 |
| ja_like | 21 |
| cjk_like | 2 |
| ko_like | 3 |

Total: **150**

---

## 4. Track A Experimental Filter (en95)

Track A fairness testing uses a filtered subset:

```
claims_lang_hint == "ascii_en_like"
```

This produces:

**95 English-like families (en95)**

All embeddings and retrieval comparisons in Track A are based on this filtered subset.

The full 150-chunk pack remains the canonical semantic warehouse baseline.

---

## 5. Embedding Indices (Track A en95)

For the filtered en95 subset, two embedding indices were built:

### Models

- PatentSBERTa
- BGE-M3

### Asset Layers (per model)

- `claim_1`
- `claim_set`
- `spec`

Each collection contains:

```
95 vectors
```

Collection naming convention:

```
claim_1__<model>__v2_0__trackA__en95
claim_set__<model>__v2_0__trackA__en95
spec__<model>__v2_0__trackA__en95
```

Chroma persistence location:

```
experiments/semantic_trackA_en95_v2/outputs/chroma/<model>/<model>_v2_trackA_en95/
```

Both models have verified collections with count = 95.

---

## 6. Retrieval & Evaluation Outputs

Offline Track A retrieval results are stored under:

```
artifacts/_pipeline_runs/20260221T200902Z__semantic_exp_v2/trackA_eval/
```

Artifacts include:

- `retrieval_runs_v2.jsonl`
- `top3_scoring.jsonl`
- comparison Excel files
- merged fulltext inspection outputs

These outputs were generated using:

- Fixed chunk policy (v2.0)
- en95 filter
- Identical query set (`track_a_query_set_v2.jsonl`)
- Family-level evaluation logic

---

## 7. Spec Truncation Variant (Operational Incident)

Additional files present in the chunk directory:

- `spec__short6000.jsonl`
- `spec__full.jsonl`

Reason:

During BGE-M3 embedding, full spec input caused resource pressure.

A truncated spec variant (~6000 length cap) was generated as an operational mitigation.

Governance decision:

- Track A fairness baseline uses `spec.jsonl`
- Truncated variant is archived for operational fallback
- It is not used in official model comparison

---

## 8. Summary

- Canonical chunk pack: 150 families
- Track A filter: en95 (95 families)
- Two embedding models built
- 3 asset layers per model
- 95 vectors per layer
- Retrieval evaluation completed offline
- All artifacts traceable to run: `20260221T200902Z__semantic_exp_v2`

This document defines the authoritative lineage for Track A.

---
