---

# Embedding Comparison — Consolidated Evaluation (Track A + Track B)

---

# 1. Scope

This document summarizes controlled semantic evaluation across two layers:

- Track A — Embedding retrieval robustness
- Track B — Protocol-constrained reasoning stability

Dataset:

- 95 English LED patent families
- Google canonical text source
- Deterministic chunk policy (v2.0)
- Family-level evaluation
- Top-3 retrieval comparison

This study measures semantic behavior under controlled stress conditions,
not full production recall performance.

---

# 2. Track A — Embedding Retrieval Robustness

Models evaluated:

- PatentSBERTa
- bge-m3 (multilingual)

Evaluation method:

- Top-3 retrieval
- Family-level collapse
- Manual relevance labeling

Five semantic stress categories:

- Structural
- Functional
- Causal
- Noise
- Reversal

---

## Observations

Structural:
Moderate sensitivity. Multilingual slightly stronger.

Functional:
Both models perform well.

Causal:
Clear differentiator.
Multilingual better captures multi-step cause chains.

Noise:
Both models degrade significantly.

Reversal:
Both models struggle with negation directionality.

---

## Track A Decision

Multilingual embedding is selected as baseline
specifically due to stronger causal abstraction robustness.

However:

- Embedding-only retrieval remains unstable under noise and negation.
- Top-3 evaluation does not imply full recall superiority.

Future systems require reranking or constraint-aware filtering.

---

# 3. Track B — Reasoning Stability

Track B tests protocol-constrained reasoning stability
on fixed Top-3 retrieval candidates.

Under strict dimension isolation:

- <5 inconsistencies across 30 cases
- Drift largely eliminated

Conclusion:

Semantic reasoning stability is protocol-sensitive.
Isolation and evidence enforcement significantly reduce drift.

---

# 4. Engineering Takeaways

1. Canonical Google-only lane eliminates source bias.
2. Causal stress testing is a strong embedding discriminator.
3. Embedding-only retrieval fails under:
    - negation-heavy queries
    - high-noise contextual perturbation
4. Reasoning stability improves with strict isolation protocol.
