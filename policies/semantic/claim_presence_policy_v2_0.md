# Claim Presence Policy v2.0

**Version:** v2.0

**Scope:** Google Patents / OPS / other text sources that provide a `claims_raw` string

**Goal:** Determine whether **Claim 1 is present** (or detect a reliable proxy) in a governance-safe way, across multilingual claims.

## 0. Non-goals / Hard Rules

1. **It is forbidden to use** `title` / `abstract` as any basis for:
   - language determination
   - claim structure determination
   - any decision-making for claim presence / claim-1 presence

   > Reason: title/abstract are often provided in English by patent offices, which introduces bias.

2. This policy **only determines presence** (presence). It does NOT do:
   - semantic understanding of claims
   - inference of claim type (independent/dependent)
   - correctness/validity/legality of claims (that belongs to a separate structural gate)

3. **Machine Translation**:
   - This policy does not require translation and does not depend on translation results.
   - If downstream components perform MT, it may be used for display purposes, but it must not be written back in a way that affects presence decisions.

---

## 1. Inputs / Outputs

### Inputs

- `claims_raw: str`

  Extracted plain-text claims after fetch (must not store raw HTML)

- `source: str`

  e.g., `GOOGLE`, `OPS`

- `publication: str`
- `html_lang: str | ""`

  Metadata only; does not affect decision correctness (but may be used for debugging/reporting)

### Outputs (required fields)

- `has_claims: bool`

  `True` if `claims_raw` is non-empty and is not clearly residual content from interstitial/consent/robot pages

- `has_claim_1: bool`
- `claim1_method: str`

  one of:

  - `REGEX_NUMBERED` (explicit "1." / "1)" / "claim 1" patterns)
  - `CJK_NUMBERED` (請求項/权利要求/청구항 + 1 patterns)
  - `HEURISTIC_UNNUMBERED` (no explicit numbering, but strong first-claim signature)
  - `NONE`

- `claim1_reason: str | null`

  reason code when method is not `REGEX_NUMBERED` (or when NONE)

- `governance_flags: [str]` (optional but recommended)

  e.g. `["CLAIM1_HEURISTIC", "ENCODING_SUSPECT"]`

---

## 2. Presence Decision Logic (deterministic)

### 2.1 has_claims

`has_claims = True` iff:

- `claims_raw.strip()` is not empty
- and it does **not** match known “not content” patterns, e.g.:
  - consent/robot pages
  - “enable cookies” / “unusual traffic”
  - placeholders without any claim-like tokens

> Note: this performs only minimal exclusion to avoid treating robot pages as claims.

### 2.2 has_claim_1 (priority order)

**Step A — Explicit numbered claim 1 (highest confidence)**

Detect any of the following in `claims_raw`:

- Line-start numbering (common):
  - `(^|\n)\s*1\s*[.)：:]\s+\S`
- English “claim 1” mention as a label:
  - `\bclaim\s*1\b`
- Formats like:
  - `CLAIM(S) ... 1.`
  - `1-` (rare but exists in OCR-ish outputs)

If matched →

- `has_claim_1 = True`
- `claim1_method = "REGEX_NUMBERED"`
- `claim1_reason = null`

**Step B — CJK numbered claim 1 (JP/CN/KR high confidence)**

Detect “claim 1” in CJK labels:

- Japanese:
  - `請求項\s*[（(]?\s*[1１]\s*[）)]?`
- Chinese:
  - `权利要求\s*[（(]?\s*[1１]\s*[）)]?`
  - `權利要求\s*[（(]?\s*[1１]\s*[）)]?`
- Korean:
  - `청구항\s*[（(]?\s*[1１]\s*[）)]?`

If matched →

- `has_claim_1 = True`
- `claim1_method = "CJK_NUMBERED"`
- `claim1_reason = "CLAIM1_CJK_NUMBERED"`

**Step C — Heuristic unnumbered first claim (medium confidence)**

Applicable scenario: Google sometimes presents claims starting directly from the first sentence, without `1.`.

The heuristic must satisfy **both**:

1. The first non-boilerplate line begins with an English article:
   - `^(A|An|The)\b`
2. Within the first ~220 chars, contains a strong claim signal:
   - `\bcomprising\b` (case-insensitive)
   - optionally allow `comprises` or `comprise`

If satisfied →

- `has_claim_1 = True`
- `claim1_method = "HEURISTIC_UNNUMBERED"`
- `claim1_reason = "CLAIM1_HEURISTIC_UNNUMBERED"`
- add governance flag: `CLAIM1_HEURISTIC`

**Else**

- `has_claim_1 = False`
- `claim1_method = "NONE"`
- `claim1_reason = "CLAIM1_NOT_DETECTED"`

---

## 3. Encoding / Mojibake Handling (governance-safe)

### 3.1 Detection (no guesswork)

Flag suspicious encoding if any of these conditions occur:

- contains replacement char `�` frequently
- contains repeated mojibake signatures e.g. `ã`, `Â`, `ï¼`, `â€”` at high density
- `claims_raw` has very low ratio of letters/digits/punctuation to total length

If suspicious:

- add governance flag: `ENCODING_SUSPECT`
- **do not** auto-translate
- **do not** auto-repair using lossy transformations unless explicitly allowed by pipeline policy

### 3.2 Repair policy (allowed deterministic fix)

Allowed fix only if we can deterministically improve without external services:

- When HTML bytes are available in-memory at fetch time:
  - prefer `response.apparent_encoding` / declared charset
  - fallback to UTF-8
- **Never store raw HTML**, but it is OK to decode it transiently for correct text extraction.

---

## 4. Reporting Requirements

Every pipeline run must emit a JSON report containing:

- totals:
  - `total_seeds`, `ok`, `fail`
  - `missing_claims`
  - `missing_claim_1`
- breakdown:
  - by `office` (WO/EP/US/JP/KR/…)
  - by `claim1_method`
  - by `html_lang` (metadata only)
- sampling:
  - `missing_claim_1_samples`: list of publication ids (max N=50)

---

## 5. Governance / Lineage

- `has_claim_1` is a **quality gate metric**, not a legal truth claim.
- When `claim1_method != REGEX_NUMBERED`, downstream components must treat claim1 detection as:
  - “present but with reduced confidence”
  - do not use it to trigger irreversible actions (e.g., dropping documents permanently)
- Store explicit evidence fields:
  - `source`, `url`, `google_resolved_slug` (if relevant), `http_status`, `retrieved_at`
- Do not store raw HTML in artifacts; store only extracted text and minimal evidence.

---

## 6. Recommended Default Thresholds (for this project)

- Target run quality:
  - `missing_claim_1 <= 5` out of 150 (preferred)
- If `missing_claim_1 > 10`:
  - block Phase-2 deterministic chunking
  - require either encoding fixes or extraction changes first
