# Architecture Contract — Governance-Aware Patent Intelligence Platform

Status: Active  
Scope: System-level governance boundary  
Applies to: All layers (Landscape, Semantic, ID, Retrieval, RAG)

---

# 1. Design Philosophy

This system is designed under a governance-first principle.

The objective is not maximum crawl volume,
but deterministic, explainable, and reproducible behavior.

Every layer must satisfy:

- Deterministic input boundary
- Explicit source authority
- Stable internal identifiers
- Reproducible transformation rules
- Audit-traceable outputs

No layer may silently override another layer’s authority.

---

# 2. Two-Lane Architecture

The platform operates under strict lane separation.

## 2.1 Landscape Lane (Identity Authority)

Source: EPO OPS

Responsibilities:
- Patent family equivalence
- Publication identity normalization
- IPC classification
- Deduplication
- Coverage reporting
- BI aggregation

Constraints:
- No semantic embedding
- No Google text injection
- No claim rewriting

OPS is the authority for identity and lineage.

---

## 2.2 Semantic Lane (Text Authority)

Source: Google canonical full text

Responsibilities:
- Claim text extraction
- Specification text extraction
- Deterministic chunking (v2.0)
- Embedding generation
- Retrieval experiments

Constraints:
- No OPS XML claims for embedding
- No multi-source merging
- No fallback mixing
- If Google text unavailable → exclude from semantic layer

Google is the authority for semantic text structure,
not for family identity.

---

# 3. Cross-Lane Contract

The only bridge between lanes is identity.

Shared anchor:
- family_id (from OPS)
- asset_id (internal deterministic hash)

Rules:
- Semantic lane must never redefine family equivalence
- Landscape lane must never consume semantic embeddings
- No bidirectional override

Identity flows downward.
Text does not flow upward.

---

# 4. Internal ID Governance

All layers must comply with:

- asset_id (family-level)
- doc_id (publication-level)
- chunk_id (semantic-level)
- embedding_version_id (model-level)

ID generation must be:

- Deterministic
- Reproducible
- Version-aware
- Never reused across incompatible builds

Every UI-visible artifact must be traceable:

LLM output  
→ chunk_id  
→ doc_id  
→ publication_number  
→ asset_id  
→ family_id  
→ original OPS seed  

---

# 5. Deterministic Chunk Boundary

Chunking is governed by:

semantic_chunk_policy_v2.0

Rules:

- Exactly three vectors per family:
  - claim_1
  - claim_set
  - spec
- No automatic paragraph splitting
- No dependency-based chunking
- No per-claim expansion beyond claim_1
- Equal per-family vector contribution

Chunk structure must be stable across models.

---

# 6. Embedding Layer Contract

Embedding is governed by:

semantic_embedding_layer_policy_v2.0

Hard requirements:

- Google-only source
- Atomic build
- SUCCESS.flag required
- Family-set equality enforced
- Spec length control logged
- embedding_version_id integrity validated

Partial collections are invalid.

Silent truncation is forbidden.

---

# 7. Evaluation Boundary

Track A:
- Top-3 family-level stress evaluation
- English-only isolation
- Identical corpus and chunk policy

Track B:
- Protocol-constrained reasoning stability
- Strict dimension isolation
- Evidence-only citation

Evaluation must never:

- Mix source lanes
- Override chunk policy
- Redefine identity anchors

---

# 8. Forbidden Behaviors

The following actions violate the architecture contract:

- Mixing OPS XML and Google text inside a semantic asset
- Using semantic layer to redefine family equivalence
- Silent fallback substitution
- Title/abstract-based language gating
- Reusing embeddings across incompatible policy versions
- Partial collection promotion without SUCCESS.flag

---

# 9. Reproducibility Requirement

A full rebuild must be reproducible using:

- OPS family selection
- Google canonical full text
- semantic_chunk_policy_v2.0
- semantic_embedding_layer_policy_v2.0
- scripts/canonical/
- versioned query set

Any structural deviation requires version increment.

---

# 10. Governance Statement

This platform is not a heuristic prototype.

It is a governance-aware architecture.

Authority is explicit.
Boundaries are enforced.
Identity is deterministic.
Semantic behavior is auditable.

System correctness is defined by:
- structural clarity
- reproducibility
- traceability
- isolation discipline

Not by retrieval score alone.
