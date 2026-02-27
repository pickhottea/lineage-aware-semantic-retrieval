---

# Track A — Release Gate Definition

## 1. Purpose

This document defines the minimum conditions required to declare Track A (Embedding Fairness Test — en95) as **complete and valid**.

Track A is not considered complete unless all gate conditions below are satisfied.

---

## 2. Gate 1 — Canonical Chunk Integrity

Source run must be:

```
20260221T200902Z__semantic_exp_v2
```

Required conditions:

- `claim_1.jsonl` line count = 150
- `claim_set.jsonl` line count = 150
- `spec.jsonl` line count = 150
- All three files contain identical family_id sets
- Each family produces exactly one chunk per asset type

Failure of any condition invalidates downstream embeddings.

---

## 3. Gate 2 — en95 Filter Integrity

Track A must apply:

```
claims_lang_hint == "ascii_en_like"
```

Required result:

```
expected_families = 95
```

Verification rule:

- After filtering, exactly 95 families remain
- No non-ascii_en_like records present
- Filter logic must be deterministic and documented

---

## 4. Gate 3 — Embedding Build Integrity

For each model:

- PatentSBERTa
- BGE-M3

Required collections (3 per model):

```
claim_1__<model>__v2_0__trackA__en95
claim_set__<model>__v2_0__trackA__en95
spec__<model>__v2_0__trackA__en95
```

Each collection must satisfy:

- count == 95
- unique family_id values
- correct embedding_version_id
- chunk_policy_version == v2.0

Chroma path must match canonical experiment directory:

```
experiments/semantic_trackA_en95_v2/outputs/chroma/<model>/<model>_v2_trackA_en95/
```

Partial, `_old_`, or `_partial_` directories are not valid release artifacts.

---

## 5. Gate 4 — Retrieval Reproducibility

Required artifacts under:

```
trackA_eval/
```

Must include:

- retrieval_runs_v2.jsonl
- top3_scoring.jsonl

Re-run must produce identical top-K ordering when:

- same query set
- same embedding_version_id
- same en95 filter

---

## 6. Gate 5 — Evaluation Scope Clarity

Track A baseline uses:

- claim_1
- claim_set
- spec.jsonl

The following are NOT part of baseline:

- spec__short6000.jsonl
- spec__full.jsonl
- experimental spec variants

These are archived operational artifacts only.

---

## 7. Completion Declaration

Track A may be declared complete when:

- All 5 gates pass
- Both models have identical family set
- Evaluation outputs are archived
- Lineage document exists

Only then may results be cited publicly.

---
