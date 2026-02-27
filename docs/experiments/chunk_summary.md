cat > CHUNK_SUMMARY.md <<'MD'
# CHUNK_SUMMARY — semantic_exp_v2 (20260221T200902Z)

This folder contains **canonical chunk outputs** for the pipeline run:
`artifacts/_pipeline_runs/20260221T200902Z__semantic_exp_v2/`

## What is "canonical" here?

Canonical = the chunk artifacts that are intended to be consumed by:
- embedding ingestion (Chroma)
- Track A retrieval evaluation
- reproducible / auditable runs

Canonical artifacts must respect:
- **Fixed chunk policy v2.0**
- **Per-family, per-asset-type cap**
- **Stable identifiers (family_id / vector_id / embedding_version_id)**
- Governance constraints (e.g., language hint gating for Track A)

---

## Files in this folder (canonical)

### `claim_1.jsonl`
- One record per family for Claim 1 representation.
- Total lines: **150** (seed families)
- `claims_lang_hint` distribution:
  - `ascii_en_like`: **95**
  - `nonascii_other`: 29
  - `ja_like`: 21
  - `cjk_like`: 2
  - `ko_like`: 3
- Track A uses **only `ascii_en_like` (95)** for fairness / model comparison.

### `claim_set.jsonl`
- One record per family for claim-set representation.
- Same family coverage and language distribution as `claim_1.jsonl`.
- Track A uses **only `ascii_en_like` (95)**.

### `spec.jsonl`
- Canonical specification-focused chunks under **chunk policy v2.0**.
- Same family coverage and language distribution as claim chunks.
- Track A uses **only `ascii_en_like` (95)**.

---

## Deprecated / non-canonical artifacts

All non-canonical or debugging artifacts are moved into:

`_deprecated/`

These are kept only for traceability, not for ingestion/evaluation.

### `_deprecated/spec__full.jsonl`
- Full specification dump (unbounded).
- Not policy-controlled.
- Excluded to prevent breaking the "fixed chunk policy" boundary.

### `_deprecated/spec__short6000.jsonl`
- Crash / resource workaround artifact created during a multi-machine run.
- Not canonical.
- Excluded for the same reason (not the intended stable policy output).

---

## Why do we keep 150 lines but evaluate 95?

This run preserves the full **seed set of 150 families** in chunk output for traceability.
However, Track A is a **model-fairness test** scoped to English-only families to avoid:
- language bias in embeddings
- cross-office OCR / extraction asymmetry
- confounds introduced by mixed-script claims/specs

Therefore:
- chunks are generated for all seeds (150)
- evaluation is performed on the gated subset (95, `ascii_en_like`)

---

## Related artifacts (outside this folder)

- Google text acquisition and validation:
  - `../02_text/`
  - `google_text_validation_report.json`
  - `google_language_distribution.json`
- Embedding manifests (collection counts should match 95 for Track A):
  - `../embedding_manifest_patentsberta.json`
  - `../embedding_manifest_bge-m3.json`

MD
