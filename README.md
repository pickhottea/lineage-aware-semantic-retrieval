# Lineage-Aware Semantic Retrieval

A lineage-aware semantic retrieval system with controlled data lanes, chunk symmetry enforcement, and embedding model evaluation.

---

## Motivation

This project originated from a structural failure: embedding bias caused by asymmetrical data lanes (EPO XML vs Google text).

The incident revealed that semantic retrieval performance cannot be meaningfully evaluated without:

- Controlled ingestion lanes
- Enforced chunk symmetry
- Schema-level validation
- Policy-bound station contracts
- Family-level normalization

This repository documents the redesigned, governance-controlled semantic retrieval experiment.

---

## Architecture Overview

The system enforces:

- Single canonical semantic source (Google lane)
- Fixed chunk policy (Claim 1 / Claim set / Specification)
- English isolation gate (en95)
- Equal per-family vector rule
- Station-level input/output schema validation
- Embedding layer contract enforcement

### Fig 1 — Governance-Controlled Semantic Pipeline

![Governance Pipeline](docs/assets/fig_1_governance_pipeline_v2.png)

### Fig 2 — Controlled Embedding Evaluation Flow

![Embedding Flow](docs/assets/fig_2_controlled_embedding_flow.png)

Two experimental tracks are implemented:

- **Track A** — Embedding model fairness evaluation  
- **Track B** — GPT vs Human semantic judgment stability testing  

---

## Core Contributions

- Detection and isolation of lane bias in semantic pipelines
- Chunk symmetry enforcement to eliminate structural embedding bias
- Lineage-aware validation across ingestion and embedding stages
- Governance-controlled experimental design
- Embedding model comparison under controlled constraints
- GPT reasoning drift analysis under structured evaluation

---

## Repository Structure

- `docs/` — Experimental design and evaluation reports  
- `policies/` — Governance and contract enforcement rules  
- `scripts/canonical/` — Controlled semantic pipeline  
- `experiments/` — Track A / Track B evaluation artifacts (summary only)  

---

## Status

Ongoing experimental research.  
Future extensions include cross-language embedding evaluation and LLM-enhanced semantic patent database integration.

## Quick links
- Architecture: [semantic_station_contract](docs/architecture/semantic_station_contract.md)
- Policies: [semantic policies](policies/semantic/)
- Track A execution: [track_a_execution](docs/experiments/track_a_execution.md)
- Consolidated evaluation: [embedding_comparison_consolidated](docs/experiments/embedding_comparison_consolidated.md)
