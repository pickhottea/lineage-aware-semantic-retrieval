# Legacy Representation Rule — Post-hoc Clarification (Archived)

Status: Archived  
Superseded by:
- semantic_chunk_policy_v2.0
- semantic_embedding_layer_policy_v2.0
- epo_vs_google_two_lane_policy

Scope:
Historical clarification of representation drift observed in pre-v2.0 pipeline.

---

# 1. Background

During early semantic experiments, representation selection mixed:

- OPS XML claims
- Google full-text claims
- Inconsistent publication normalization

This produced asymmetric semantic coverage across families.

Observed artifact:

- 122 families represented via OPS XML
- 28 families represented via Google text

This imbalance was not domain-driven.
It was a transport-layer artifact caused by:

- OPS claims endpoint inconsistencies
- Parsing instability
- Silent fallback behaviors

---

# 2. Root Cause

The previous pipeline implicitly assumed:

“If claim text is retrievable from any source, it is semantically equivalent.”

This assumption was false.

OPS XML and Google full-text:

- Differ in structure
- Differ in formatting
- Differ in deterministic chunking stability

Mixing them introduced:

- Density bias
- Retrieval skew
- Non-reproducible semantic artifacts

---

# 3. Governance Correction (v2.0)

The architecture was redesigned to eliminate source mixing.

Current enforced rules:

- Landscape lane → OPS only
- Semantic lane → Google canonical full text only
- No fallback mixing inside semantic layer
- No OPS XML allowed for embedding
- Families without valid Google full text are excluded from semantic layer

This guarantees:

- Deterministic chunk structure
- Reproducible embeddings
- Fair model comparison
- No silent source substitution

---

# 4. Architectural Separation

The system now operates under a Two-Lane Architecture:

Landscape Lane:
- Identity authority
- Family anchoring
- IPC classification

Semantic Lane:
- Canonical Google text
- Deterministic chunk policy
- Embedding-only source

These lanes are independent.
They do not act as fallback mechanisms for each other.

---

# 5. Why This File Exists

This document remains archived to:

- Explain historical artifacts in earlier runs
- Document the reasoning behind v2.0 strict source isolation
- Provide audit transparency for past experimental discrepancies

It is not an active policy.

All new runs must follow:

- semantic_chunk_policy_v2.0
- semantic_embedding_layer_policy_v2.0
- epo_vs_google_two_lane_policy
- track_a_execution (current version)

---

# 6. Governance Statement

Representation consistency is not an optimization detail.

It is a structural requirement for:

- Fair embedding comparison
- Stable semantic retrieval
- Reproducible evaluation
- Audit-ready system design

The legacy mixing behavior is permanently deprecated.
