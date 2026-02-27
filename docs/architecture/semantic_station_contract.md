# Semantic Layer — Station Contract Matrix

Status: Active  
Scope: Semantic retrieval pipeline (Google canonical lane only)  
Related: policies/semantic/*.md  


Architectural Lesson Learned

A previous failure revealed that lane heterogeneity (OPS XML vs Google TXT) introduced silent chunk bias.

To prevent recurrence, we introduced a station-level contract system:

Each station defines explicit input schema

Each station defines deterministic output schema

Each transformation is linked to a governing policy document

No UI layer is allowed to discover structural inconsistency


This document defines the **station-level input/output contracts**
for the semantic layer.

Each station must:

- Declare explicit input artifacts
- Produce deterministic output artifacts
- Enforce linked governance policies
- Pass defined gates before proceeding

This document does NOT redefine policies.
It maps policies to executable pipeline stages.

---

# Overview

Semantic Pipeline (Track A / Track B compatible)

Station 1 — Acquisition  
Station 2 — Canonical Text Validation  
Station 3 — Chunking  
Station 4 — Embedding  
Station 5 — Retrieval  
Station 6 — Evaluation  

All stations are reproducible and must be versioned.

---

# Station 1 — Acquisition

## Purpose

Fetch canonical Google full-text publication data
under governed OPS/Google fallback rules.

## Input

- Seed list defined by:
  - `dataset_selection_policy.md`
- OPS identity anchors
- Fallback triggers (if applicable)

## Output

Directory:
artifacts/_pipeline_runs/<RUN_ID>/02_text/google_raw/


Each record must include:

- family_id
- selected_publication
- source = "GOOGLE"
- claims_raw
- description_raw
- has_claims
- has_claim_1
- claim1_method
- governance_flags
- lineage metadata

## Enforced Policies

- epo_vs_google_two_lane_policy.md
- claim_presence_policy_v2_0.md
- internal_reference_number_policy.md

## Hard Gates

- No missing family_id
- claims_raw must exist (unless explicitly flagged)
- has_claim_1 flag present

---

# Station 2 — Canonical Text Validation

## Purpose

Validate structural integrity of canonical Google text.

## Input
artifacts/_pipeline_runs/<RUN_ID>/02_text/google_raw/*.json


## Output

- google_text_validation_report.json
- google_language_distribution.json

## Enforced Policies

- claim_presence_policy_v2_0.md

## Hard Gates

- missing_claim_1 <= defined threshold
- Encoding not flagged as corrupted
- No robot/interstitial page content

If gate fails → pipeline stops.

---

# Station 3 — Chunking (Semantic Structuring)

## Purpose

Generate deterministic semantic units per family.

## Input

- Canonical Google text
- Semantic Chunk Policy v2.0

## Output

Directory:
artifacts/_pipeline_runs/<RUN_ID>/chunks_v2/


Files:

- claim_1.jsonl
- claim_set.jsonl
- spec.jsonl

Each record must include:

- family_id
- selected_publication
- chunk_type (claim_1 | claim_set | spec)
- text
- chunk_policy_version = "v2.0"
- claims_lang_hint
- created_at

## Enforced Policies

- semantic_chunk_policy_v2_0.md

## Hard Gates

- claim_1 count == claim_set count == spec count
- Family ID sets must match exactly across files
- No additional chunk types allowed
- Exactly 3 semantic units per family

Failure → stop.

---

# Station 4 — Embedding

## Purpose

Convert semantic units into vector representations
under reproducible governance rules.

## Input
artifacts/_pipeline_runs/<RUN_ID>/chunks_v2/*.jsonl

- embedding_model
- spec control parameters

## Output

Vector collections:
outputs/chroma/<model>/<collection>


Plus:

- embedding_manifest_v2.json
- SUCCESS.flag

Each vector must include:

- vector_id
- family_id
- selected_publication
- chunk_type
- embedding_model
- embedding_version_id
- chunk_policy_version
- created_at

Spec must additionally log:

- spec_length_control_mode
- spec_truncation_applied
- spec_max_chars
- spec_original_char_length

## Enforced Policies

- semantic_embedding_layer_policy_v2_0.md
- Track A fairness constraints (if active)

## Hard Gates

- Family hash consistency
- Metadata completeness
- embedding_version_id deterministic
- SUCCESS.flag must exist

Partial collections are invalid.

---

# Station 5 — Retrieval (Track A)

## Purpose

Evaluate embedding behavior under controlled semantic queries.

## Input

- Vector collections
- query_set_v2.jsonl

## Output

- results_<model>.jsonl
- query_runs.jsonl
- top3_scoring.jsonl

All evaluation must be collapsed to family level.

## Enforced Policies

- track_a_embedding_model_fairness_evaluation.md

## Hard Rules

- No chunk-level scoring reported as final metric
- Query set must be frozen + hashed

---

# Station 6 — Evaluation (Track A + Track B)

## Purpose

Analyze semantic robustness and reasoning stability.

## Input

- Retrieval outputs
- Human relevance judgments (if Track B)

## Output

- embedding_comparison_consolidated.md
- track_b_gpt_reasoning_stability_report.md
- summary_metrics.json

## Enforced Policies

- embedding_selection_governance_aware_patent_retrieval.md

---

# Station Isolation Principle

Each station must:

- Consume only declared inputs
- Produce only declared outputs
- Not mutate upstream artifacts
- Not infer hidden metadata

Cross-station coupling is forbidden.

---

# Reproducibility Rule

A full semantic rebuild must be reproducible using:

- dataset_selection_policy.md
- semantic_chunk_policy_v2_0.md
- semantic_embedding_layer_policy_v2_0.md
- canonical Google text
- identical query_set_v2.jsonl

If outputs differ,
version increment is required.

---

# Final Note

Policies define rules.

Stations execute those rules.

This document binds policies to executable pipeline stages,
ensuring semantic governance is operational,
auditable,
and reproducible.
