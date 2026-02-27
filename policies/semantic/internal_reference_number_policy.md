# Internal Reference Number Policy (ID Governance & Traceability)

## B1. Why Internal Reference Numbers Exist

Patent datasets combine:

- Multi-jurisdiction publications
- Multiple publication formats (raw / docdb / Google format)
- Family-level aggregation
- Claim-level and chunk-level semantic assets

External identifiers (publication_number, family_id) are:

- Not stable across transformations
- Sometimes missing or malformed
- Not always unique across serving layers

Therefore, the system defines internal reference numbers to ensure:

- Cross-layer consistency
- Audit traceability
- Deterministic re-indexing
- Semantic asset alignment

---

## B2. ID Hierarchy Design

The system uses a layered identifier model.

### 1️⃣ asset_id (Family-level)

Represents the invention unit.

Definition example:

```
asset_id = sha1("family|" + family_id)
```

Used in:

- families_v1 (Elasticsearch)
- Chroma metadata
- Coverage reports
- Dedup logic
- BI aggregation key

Purpose:

> Anchor semantic and warehouse layers to a single invention identity.
> 

---

### 2️⃣ doc_id (Publication-level)

Represents one specific publication.

Definition example:

```
doc_id = sha1("pub|" + publication_number_docdb)
```

Used in:

- patents_v1 index
- Claims extraction artifacts
- Spec-level embedding
- RAG evidence display

Purpose:

> Preserve publication-specific context while allowing family collapse upstream.
> 

---

### 3️⃣ chunk_id (Semantic-level)

Represents a semantic chunk.

Definition example:

```
chunk_id = sha1(doc_id +"|" + span_start +"|" + layer)
```

Layer ∈ {claim1, claims_set, spec}

Used in:

- Chroma collection
- Rerank pipeline
- Evidence highlighting in RAG

Purpose:

> Enable explainable semantic retrieval with positional traceability.
> 

---

## B3. When IDs Are Generated

ID creation timing is intentional.

### Step B (Family selection)

- asset_id generated
- Linked to OPS family members

### Step C (Claim representation)

- doc_id generated for selected publication
- claims_source recorded

### Step E (Spec fetch)

- doc_id reused
- spec_source recorded

### Semantic embedding stage

- chunk_id generated
- layer metadata attached

This ensures IDs are:

- Deterministic
- Reproducible
- Stable across re-runs

---

## B4. Where IDs Are Used

| Layer | ID Used | Why |
| --- | --- | --- |
| Coverage gate | asset_id | Count unique invention units |
| Elasticsearch (families_v1) | asset_id | BI aggregation |
| Elasticsearch (publication mode) | doc_id | Result-level trace |
| Chroma | chunk_id + metadata | Semantic retrieval |
| RAG output | doc_id + chunk_id | Evidence citation |

---

## B5. Traceability Model

Every UI-visible item must be traceable backward.

Example trace path:

RAG answer

→ chunk_id

→ doc_id

→ publication_number

→ asset_id

→ family_id

→ representation_selection_report.jsonl

→ original OPS seed

This creates full lineage from:

LLM output → raw API source

---

## B6. Why This Matters (Governance Framing)

Without internal reference numbers:

- Family-level BI and publication-level semantic layers drift apart
- Google-derived semantic artifacts cannot be audited
- RAG evidence cannot be deterministically traced
- Incremental reprocessing may produce orphan semantic vectors

With this ID policy:

- Re-indexing is safe
- Semantic re-embedding is stable
- Multi-source merging remains explainable
- Audit trail is continuous

---

## B7. Governance Summary

Internal reference numbers are not replacements for external patent identifiers.

They are structural anchors that guarantee cross-layer traceability across:

- Source APIs
- ETL normalization
- Warehouse indexing
- Semantic embedding
- RAG generation

They enable the system to be explainable, reproducible, and governance-ready.
