---

# 📘 Semantic Embedding Layer Policy v2.0

Status: Approved (Release-gated)

Supersedes: v1.0

Applies to: `scripts/canonical/` only

Scope boundary: From chunk artifacts → vector persistence

Excludes: Retrieval / Rerank / RAG / Evaluation metrics

---

# 0) Version Upgrade Note (Delta from v1.0)

v2.0 introduces:

1. **Spec Length Control Policy integration (mandatory logging)**
2. **Atomic Collection Build rule (no partial collections allowed)**
3. **Track A family-set hash enforcement**
4. **Embedding resource profile logging**
5. **Fail-fast gates expanded**

No structural change to:

- 3 semantic units
- Google-only source rule
- ID matrix
- Metadata contract

---

# 1) Why this policy exists (post-mortem driven)

We previously failed because we implicitly assumed:

> “If chunks exist, embeddings will be fine.”
> 

That assumption is false.

Without strict embedding controls, the system can silently drift due to:

- lane/source asymmetry (OPS vs Google)
- unequal chunk counts (density bias)
- missing metadata (non-auditable vectors)
- silent model substitution
- OOM-driven spec truncation
- partial collection persistence

Embedding is now a governed, reproducible, auditable stage.

---

# 2) Scope & Preconditions

## 2.1 Canonical text source (non-negotiable)

All semantic embeddings MUST originate from:

```
artifacts/_pipeline_runs/<RUN_ID>/02_text/google_raw/*.json
```

Forbidden:

- OPS XML claims
- multi-source merge
- legacy chunk reuse

---

## 2.2 Chunk policy dependency

Embedding allowed only if chunks produced under:

```
Semantic Chunk Policy v2.0
```

Directory:

```
artifacts/_pipeline_runs/<RUN_ID>/chunks_v2/
```

Files:

- claim_1.jsonl
- claim_set.jsonl
- spec.jsonl

---

## 2.3 Track A English isolation (when active)

If Track A:

```
claims_lang_hint == "ascii_en_like"
```

Expected:

```
95 families across all 3 files
```

Fail condition:

Counts mismatch → STOP.

---

# 3) Semantic Units (unchanged from v1.0)

Exactly three units per family:

| Unit | Purpose |
| --- | --- |
| claim_1 | scope anchor |
| claim_set | structured context |
| spec | recall expansion |

No additional units allowed.

---

# 4) ID Matrix (Embedding Boundary)

## 4.1 Upstream Required Fields (must exist)

- family_id
- selected_publication
- source = "GOOGLE"
- chunk_type ∈ {claim_1, claim_set, spec}
- chunk_policy_version = "v2.0"
- claims_lang_hint
- created_at

Missing field → FAIL FAST.

---

## 4.2 embedding_version_id (deterministic global ID)

Format:

```
<model>@<revision>#chunk_policy=v2.0#norm=v1#spec_control=v1
```

If ANY component changes:

→ New embedding_version_id

→ Full rebuild required

---

## 4.3 vector_id (unique per vector)

```
family_id#chunk_type#embedding_version_id
```

Never reuse across versions.

---

# 5) Spec Length Control (NEW in v2.0)

This integrates:

Spec Length Control Policy v1

Spec MUST declare:

- spec_length_control_mode
- spec_truncation_applied
- spec_max_chars (if truncation)
- spec_original_char_length

Track A rule:

Spec control parameters must be identical across models.

Silent transformer truncation is strictly forbidden.

---

# 6) Collection Design (Chroma)

Default: **Option A (3 collections)**

```
semantic_claim_1_v2
semantic_claim_set_v2
semantic_spec_v2
```

v2.0 adds:

## 6.1 Atomic Collection Build (NEW)

Embedding must:

1. Write to temp directory:

```
.../<model>_v2__tmp_<RUN_ID>
```

1. Validate gates (Section 8)
2. Rename to production only if ALL pass
3. Create SUCCESS.flag

If failure:

Temp directory remains marked as partial.

Partial collections must NEVER be used in evaluation.

---

# 7) Metadata Contract (expanded)

Each vector must include:

Identity:

- vector_id
- family_id
- selected_publication
- source = "GOOGLE"
- chunk_type
- chunk_policy_version
- run_id

Embedding:

- embedding_model
- embedding_version_id
- embedding_dim
- embedded_at

Spec control (if spec):

- spec_length_control_mode
- spec_truncation_applied
- spec_max_chars
- spec_original_char_length

Language evidence:

- claims_lang_hint
- html_lang (informational only)

---

# 8) Hard Gates (expanded in v2.0)

## G1 — Count equality

claim_1 == claim_set == spec

(Track A: must equal 95)

---

## G2 — Family identity equality

Sorted family_id hash must match across all 3 files.

Manifest must include:

```
family_set_hash_claim1
family_set_hash_claimset
family_set_hash_spec
```

Mismatch → FAIL.

---

## G3 — Metadata completeness

No missing mandatory fields.

---

## G4 — embedding_version_id integrity

Directory name must match manifest embedding_version_id.

---

## G5 — Spec control declared

If spec embedded:

spec_length_control_policy_version must exist.

---

## G6 — Atomic build validation

SUCCESS.flag must exist.

Without it → collection invalid.

---

# 9) Track A Fairness Enforcement

When Track A active:

- identical family set
- identical language filter
- identical spec control
- identical chunk policy
- identical normalization settings

No adaptive behavior per model allowed.

---

# 10) Resource Profile Logging (NEW)

Each embedding run must record:

- batch_size
- max_length
- device
- normalization_applied

Stored in:

```
embedding_manifest_v2.json
```

Ad-hoc runtime changes without logging → violation.

---

# 11) Explicitly Forbidden

- Embedding outside chunks_v2
- Mixing OPS + Google
- Using embedding to choose representation
- Silent spec truncation
- Partial layer persistence
- Reusing vector_id across versions

---

# 12) End-of-Scope Boundary

Policy ends at:

- Vectors persisted
- Manifest written
- SUCCESS.flag created
- Gates passed

Retrieval & evaluation are separate governance layers.

---

# Summary of v2.0 Improvements

| Area | v1.0 | v2.0 |
| --- | --- | --- |
| Spec truncation | implicit | explicit + logged |
| Partial builds | possible | forbidden |
| Track A gate | count check | + hash verification |
| Metadata | strong | expanded (spec control + profile) |
| Reproducibility | assumed | enforced |

---
