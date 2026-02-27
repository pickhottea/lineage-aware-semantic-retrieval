---

# Track B — GPT Reasoning Stability Report

Track B evaluates GPT semantic reasoning stability under controlled retrieval conditions.

This is an engineering validation layer built on top of Track A results.

---

# 🎯 Objective

To measure GPT reasoning consistency when:

- Retrieval candidates are fixed (Top-3)
- Query dimension is isolated
- Evidence citation is enforced
- Cross-document inference is prohibited

This track evaluates protocol stability, not model intelligence.

---

# 📦 Dataset Scope

- 5 semantic dimensions (Structural, Functional, Causal, Noise, Reversal)
- Top-3 retrieval per query
- 30 total evaluation cases
- English-only corpus (from Track A)

Each test case includes:

- 1 query_id
- 1 dimension
- 3 candidate patents

---

# 🧪 Experimental Protocol

Strict Isolation Rules:

1. One query_id at a time
2. One dimension at a time
3. GPT must:
    - Extract core requirement
    - Identify patent main problem
    - Compare alignment
    - Cite evidence snippet
4. Only evidence from the current patent allowed
5. No cross-document memory usage

---

# 📊 Observed Results

- < 5 inconsistencies across 30 cases
- Stability improves significantly under strict isolation

Conclusion:

Reasoning stability is protocol-dependent.

Drift primarily originates from:

- Multi-question mixing
- Noise overweighting
- Weak hard-vs-inferred condition separation
