# EPO vs Google — Two-Lane Architecture Policy

Status: Approved  
Supersedes: EPO_vs_Google_fallback  
Scope: Source acquisition governance

---

# 1. Architectural Principle

The system operates as two independent governance lanes:

Landscape Lane and Semantic Lane.

They are not fallback mechanisms for each other.

They serve different purposes and must never mix content silently.

---

# 2. Lane Definitions

## 2.1 Landscape Lane

Source: EPO OPS  
Purpose:
- Family equivalence
- Publication identity
- IPC classification
- Coverage reporting
- BI aggregation

Characteristics:
- Identity authority
- No semantic embedding
- No Google claims mixing

Landscape is authoritative for identity and lineage.

---

## 2.2 Semantic Lane

Source: Google canonical full text  
Purpose:
- Claim text extraction
- Specification text extraction
- Semantic chunking
- Embedding
- Retrieval experiments

Characteristics:
- Google is the canonical semantic source
- OPS XML claims must not be embedded
- No OPS fallback for semantic layer
- If Google full text unavailable → family excluded from semantic layer

Semantic lane is optimized for deterministic text structure,
not legal authority.

---

# 3. Identity Boundary

Even though lanes are independent:

- family_id must originate from OPS
- asset_id/doc_id/chunk_id must follow Internal Reference Number Policy
- Google publication keys must not overwrite OPS identity anchors

Google is a semantic text provider, not identity authority.

---

# 4. Explicitly Forbidden

- Treating Google as fallback inside semantic lane
- Embedding OPS XML claims
- Silent source switching
- Mixing OPS + Google text inside a single semantic asset
- Using semantic text to redefine family equivalence

---

# 5. Governance Summary

Landscape and Semantic are parallel governance lanes.

OPS governs identity.
Google governs semantic text structure.

They must remain isolated to prevent cross-layer drift.
