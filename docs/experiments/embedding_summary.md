— semantic_exp_v2 (20260221T200902Z)

This document summarizes the embedding layer for Track A fairness evaluation.

---

## Chunk Policy

- chunk_policy_version: v2.0
- Per-family, per-asset cap enforced
- Canonical chunk source: chunks_v2/

---

## Track A Language Gate

- Only `ascii_en_like` families embedded
- Total embedded families: 95

---

## Models Compared

### PatentSBERTa

- embedding_version_id: patentsberta__v2.0__A__ascii_en_like
- embedding_dim: 768
- collections:
    - claim_1 → 95
    - claim_set → 95
    - spec → 95

### bge-m3

- embedding_version_id: bge-m3__v2.0__A__ascii_en_like
- embedding_dim: 1024
- collections:
    - claim_1 → 95
    - claim_set → 95
    - spec → 95

---

## Fairness Guarantees

- Same chunks
- Same corpus
- Same language subset
- Same evaluation query set
- No OPS/EPO semantic mixing
