# Run Summary  
## 20260221T200902Z__semantic_exp_v2

This run represents the **final governance-corrected Track A fairness experiment**.

---

## 1. Experiment Scope

Track: A — Model Fairness (English-only isolation)  
Chunk Policy: v2.0  
Text Source: Google Patents (original page only)  
Language Mode: ORIGINAL_ONLY  

---

## 2. Seeds

Total seeds: 150  

Office distribution:
- EP: 29  
- US: 57  
- WO: 64  

All seeds were fetched via Google Patents without forced `/en`.

---

## 3. Claims Language Distribution

Script hint distribution:

- ascii_en_like: 95  
- ja_like: 21  
- nonascii_other: 29  
- ko_like: 3  
- cjk_like: 2  

English isolation gate (en95) applied.

Only ascii_en_like (95 families) were embedded.

---

## 4. Chunk Policy

Per-family, per-asset cap:

- claim_1 → 1 vector
- claim_set → 1 vector
- spec → 1 vector

Total embedded families: 95  
Total collections per model: 3  
Total vectors per model: 285  

---

## 5. Models Compared

### Model A
PatentSBERTa  
Embedding dim: 768  

### Model B
bge-m3  
Embedding dim: 1024  

Both models:
- Same corpus
- Same chunks
- Same query set
- Same evaluation metric

---

## 6. Evaluation Protocol

- Top-K retrieval
- Collapse to family-level
- Recall@10
- Claim-first precision
- Type sensitivity comparison

---

## 7. Governance Guarantees

- Single canonical semantic source (Google only)
- No OPS/EPO semantic mixing
- English isolation enforced
- Equal per-family vector rule
- Atomic embedding build
- Family-level evaluation only

---

## 8. Status

This run is considered:

Governance-clean  
Fairness-isolated  
Reproducible  
Production-quality baseline for Track A
