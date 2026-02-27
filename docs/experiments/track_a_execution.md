# Track A — Execution (English-only, Model Fairness)

Run ID: <RUN_ID>  
Chunk Policy: v2.0  
Canonical Text Source: Google full text only  
Population Rule: claims_lang_hint == "ascii_en_like"  
Expected Families: 95  

---

# 0. Preconditions

0.1 Chunk artifacts exist  
- claim_1.jsonl  
- claim_set.jsonl  
- spec.jsonl  

0.2 Chunk validation passed  
validate_chunks_v2.py must succeed.

0.3 Track A population check  
- Unique family_id count == 95  
- Family set identical across 3 layers  

---

# 1. Embedding Build

For each model:

- Build 3 separate collections:
  - claim_1
  - claim_set
  - spec
- Atomic build required
- SUCCESS.flag must exist

Metadata must include:
- family_id
- selected_publication
- source = "GOOGLE"
- chunk_policy_version = "v2.0"
- embedding_version_id
- run_id
- track = "A"

---

# 2. Retrieval Experiment

Query set:
experiments/semantic_trackA_en95_v2/inputs/query_set_v2.jsonl

For each model:

- Retrieve Top-3 hits per query
- Collapse to family-level ranking
- Record rank + score
- Manual relevance labeling

Required artifacts:
- experiment_results_trackA.json
- query_runs.jsonl
- hits.jsonl

---

# 3. Evaluation Method

Primary evaluation:

- Top-3 family-level precision comparison

Secondary observations:

- Structural robustness
- Functional abstraction
- Causal chain recognition
- Noise resistance
- Negation handling

This track does not compute full Recall@10
unless ground truth family sets are explicitly defined.

---

# 4. Decision Logic

Model selection is based on:

- Observed robustness under semantic stress
- Consistency across query categories

Track A is a controlled stress evaluation,
not a full quantitative recall benchmark.

This experiment does not fork the canonical pipeline.
It reuses the canonical extraction and chunk policy.
The only experimental constraint is language-filtered family selection (ascii_en_like).
