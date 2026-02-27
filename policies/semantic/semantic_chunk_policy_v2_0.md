Status: Approved for Rebuild Phase

Scope: Semantic Layer Only

---

## 1. Purpose

This policy defines the official chunking strategy for the semantic retrieval layer.

It replaces all previous uncontrolled chunk generation logic.

This document must be referenced by any script under:

```
scripts/canonical/
```

---

## 2. Layer Separation Principle

Landscape Layer (OPS/EPO)

→ Used for IPC, jurisdiction, coverage analysis.

Semantic Layer (Google canonical full text)

→ Used for FTO-oriented semantic retrieval.

These layers are intentionally independent.

---

## 3. Canonical Text Source

All semantic embeddings must be generated from:

Google full-text canonical publication

No mixing with OPS claim XML.

No multi-source merging.

If Google text unavailable → family excluded from semantic layer.

---

## 4. Family-Level Vector Policy

For each family_id, exactly three semantic vectors are allowed:

1. claim_1 vector
2. claim_set vector
3. spec vector

No additional automatic splits allowed.

---

## 5. Chunk Definitions

### 5.1 claim_1

Definition:

- Extract only claim number 1
- Remove numbering prefix
- Preserve entire textual body
- No truncation unless model max token exceeded

Purpose:

Primary boundary definition for FTO.

---

### 5.2 claim_set

Definition:

- Concatenate all claims in numeric order
- Separate each claim by two newline characters
- Preserve full text
- No dependency-based splitting

Purpose:

Contextual claim relationship modeling.

---

### 5.3 spec

Definition:

- Use full description text (excluding claims)
    
    OR
    
- spec_focus policy (if defined separately)

Must be deterministic and versioned.

Purpose:

Claim interpretation and embodiment context.

---

## 6. Explicitly Forbidden

- Automatic splitting by paragraph
- Automatic splitting by dependency graph
- Mixed lane claim sources
- OPS XML collapse
- Per-claim embedding except claim_1

---

## 7. Equal Weight Rule

Each family contributes exactly:

- 1 claim_1 vector
- 1 claim_set vector
- 1 spec vector

No weighting by:

- Number of jurisdictions
- Number of filings
- Version A/B
- Age of filing

Semantic layer must remain neutral.

---

## 8. Metadata Requirements

Each vector must include:

- family_id
- selected_publication
- source = "GOOGLE"
- chunk_type (claim_1 / claim_set / spec)
- chunk_policy_version = "v2.0"
- embedding_model
- created_at

Missing metadata invalidates ingestion.

---

## 9. Reproducibility Rule

A semantic rebuild must be reproducible using only:

- scripts/canonical/
- Semantic Chunk Policy v2.0
- Google canonical text

Any deviation requires version increment (v2.1+).

---

## 10. Policy Versioning

If chunk structure changes:

- Update version number
- Document delta
- Regenerate embeddings
- Compare against baseline
