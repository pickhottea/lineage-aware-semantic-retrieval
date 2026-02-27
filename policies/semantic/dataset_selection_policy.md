### Governance Positioning

The dataset is intentionally designed as:

> *Large enough to show structure, small enough to remain explainable.*
> 

The goal is not volume.

The goal is **structural clarity under governance control**.

---

### Domain Anchoring Policy

The dataset is anchored in the luminaire system domain.

> *The dataset is intentionally anchored in the luminaire system domain (F21V), with controlled representation of upstream chips and downstream drivers, ensuring architectural completeness without diluting governance interpretability.*
> 

The dataset is intentionally designed as a **governance-friendly, explainable portfolio** rather than a maximum-coverage crawl.

### IPC Layering Structure

| IPC Class | Role | Governance Intent |
| --- | --- | --- |
| **F21V** | Luminaire / optics (system layer) | Anchor domain |
| **F21K** | LED module | Controlled mid-layer |
| **H01L33** | LED chip (upstream) | Present but constrained |
| **H05B33** | Driver layer | Thin boundary control |
- **Anchor domain (system layer): F21V** — primary narrative for luminaire system architecture.
- **Bridge layer: F21K** — proportionally sampled to preserve module-layer realism without dominating the system view.
- **Upstream layer: H01L33** — included but intentionally constrained to avoid drifting into a semiconductor-only tool.
- **Downstream boundary: H05B33** — included as a thin boundary to prevent scope creep into power electronics.

**Governance rationale (scale):**

*Large enough to show structure, small enough to remain explainable.*

### 1. Executive Overview

Project 1 establishes a **governance-aware patent data warehouse** built on authoritative EPO OPS data, designed to transform raw multi-jurisdiction patent publications into a structured, auditable, exploration-ready asset.

The warehouse:

- Anchors at **patent family level**
- Preserves original legal identifiers
- Applies deterministic sampling and deduplication rules
- Enables structured IPC landscape analysis
- Serves as the foundation for later semantic and RAG layers

This stage is focused on:

> Data ingestion, normalization, deduplication, and structured aggregation
> 
> 
> — not legal interpretation and not semantic inference.
> 

### new add Patent Family Deduplication & Corporate Structure Transition Summary

### 1️⃣ Sample Definition

- Source: Espacenet
- IPC: F21V
- Priority ≥ 2019
- Family language: EN
- Selection logic: Top 5 applicants (raw count)

Deduplication key: **Patent Family (priority-based family number)**

For IPC subclasses such as F21K and H01L33:

> *Families were proportionally sampled from top applicants based on their overall representation, preserving upstream technology leadership signals while keeping the dataset audit-friendly.*
> 

This prevents:

- Over-amplification of dominant corporate groups
- Artificial distortion of technical landscape
- Governance imbalance across IPC layers

---

### 2️⃣ Deduplication Results (Before → After)

| Applicant | Before | After | Change |
| --- | --- | --- | --- |
| Signify Holding BV | 33 | 33 | — |
| Philips | 16 | 7 | ↓ Significant reduction |
| Opple Lighting | 14 | 14 | — |
| Suzhou Opple Lighting | 14 | 1 | ↓ Structural consolidation |
| KOITO | 11 | 11 | — |

Total duplicate publications identified at family level: **28**

---

### 3️⃣ Key Governance Observation #1 — EU Corporate Transition

### Philips → Signify Holding BV

- Multiple Philips publications align to Signify at the family level.
- Indicates:
    - IP ownership migration
    - Post spin-off filing consolidation

### Governance Implication

Raw applicant counts overstate Philips’ position.

Signify is the structurally consolidated IP holder in this domain.

📌 Not a data error — a corporate restructuring effect.

---

### 4️⃣ Key Governance Observation #2 — CN Corporate Fragmentation

Entities observed:

- SUZHOU OPPLE LIGHTING CO LTD
- OPPLE LIGHTING CO LTD

After family deduplication:

- Suzhou Opple: 14 → 1
- Opple Lighting: 14 → 14

### Interpretation

- Multiple legal entities
- Highly
