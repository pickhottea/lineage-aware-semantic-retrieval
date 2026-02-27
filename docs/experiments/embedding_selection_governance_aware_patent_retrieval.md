---

## 1. What this experiment solves

Under controlled English-only conditions,

which embedding model performs better for family-level semantic patent retrieval?

We evaluate:

- Structural understanding
- Functional intent
- Causal reasoning
- Noise resistance
- Reversal sensitivity

---

## 2. Dataset & Governance Design

- 150 canonical patent families (OPS-based)
- Evaluation type: Top-3 family-level stress test (not full recall benchmark)
- Google lane for semantic text
- Fixed chunk policy (v2.0)
- Per family:
    - claim1
    - claimset
    - spec
- English-only fairness filter → en95

      See: docs/experiments/track_a_lineage.md

---

## 3. Experimental Architecture

![experiment_demo.png](attachment:f0e715d8-fd3a-410b-883a-77ace0ea2c9d:experiment_demo.png)

---

## 4. Track A — Model Fairness (English-only)

Models compared:

- PatentSBERTa
- BGE-M3

Evaluation unit:

- Family-level (not chunk-level)

Metric:

- Claim-first precision@K
- Type sensitivity matrix

Result summary:

| Dimension | Better Model |
| --- | --- |
| Causal | BGE-M3 |
| Structural | BGE-M3 |
| Functional | Tie |
| Noise | PatentSBERTa |
| Reversal | BGE-M3 |

Decision: **BGE-M3 selected**

---

## 5. Track B — GPT vs Human Interpretation

Goal:

Compare relevance reasoning process, not embedding.

Findings:

- Cross-document contamination risk
- Noise pollution in multi-query prompts
- Hard vs inferable condition instability

Operational guideline derived.

---

## 6. Governance Principles

- No title/abstract language detection
- No raw HTML storage
- All vectors traceable
- Family-first rerank enforced

---

## 7. Reproducibility

All artifacts derived from:

```
20260221T200902Z__semantic_exp_v2
```

Release gate:

See: docs/experiments/track_a_release_gate.md
