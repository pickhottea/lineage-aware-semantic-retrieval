#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Semantic Rebuild v2 — Phase 1B
Fetch Google Patents ORIGINAL-LANGUAGE full text (claims + description) for seeds.

Policy / Governance:
- Text source: GOOGLE ONLY
- Fetch original page only: https://patents.google.com/patent/{PUB}
  (DO NOT force /en, DO NOT translate)
- Data minimization: do NOT store raw HTML; store only extracted text + minimal evidence.

Input:
- seed/seed_publications.txt (150 publication identifiers like WO2021260493A1, EP3825599A1, US11118740B1)

Output (run-scoped):
- artifacts/_pipeline_runs/<RUN_ID>/02_text/google_raw/{PUB}.json
- artifacts/_pipeline_runs/<RUN_ID>/02_text/google_text_validation_report.json
- artifacts/_pipeline_runs/<RUN_ID>/02_text/google_language_distribution.json
- artifacts/_pipeline_runs/<RUN_ID>/02_text/google_claims_language_distribution.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup  # pip install beautifulsoup4


# ---------------------------
# Claim 1 detection patterns
# ---------------------------
_RE_CLAIM1_NUMBERED_LINESTART = re.compile(r"(?m)^\s*1\s*[\.):]\s+\S")
_RE_CLAIM1_NUMBERED_ANYWHERE = re.compile(r"(?m)(?:^|\n|\b)(?:claim\s*)?1\s*[\.):]\s+\S")
_RE_CLAIM1_HEURISTIC_START = re.compile(
    r"(?is)^\s*(claims?\s*(\(\s*\d+\s*\))?\s*)?(a|an|the)\b.{0,220}\b(comprising|comprises|including|includes)\b"
)

# ---------------------------
# Claims content script hints
# (QC / observability signal)
# ---------------------------
_RE_NONASCII = re.compile(r"[^\x00-\x7F]")
_RE_CJK = re.compile(r"[\u4e00-\u9fff]")     # Han ideographs (CJK)
_RE_KANA = re.compile(r"[\u3040-\u30ff]")    # Japanese Hiragana/Katakana
_RE_HANGUL = re.compile(r"[\uac00-\ud7af]")  # Korean Hangul


def detect_claim1_presence(claims_raw: str) -> tuple[bool, str, str | None]:
    """
    Detect presence of claim 1 across English + CJK.

    Returns:
      (has_claim_1, method, reason)

    method:
      - REGEX_NUMBERED
      - CJK_NUMBERED
      - HEURISTIC_UNNUMBERED
      - NONE
    """
    txt = (claims_raw or "").strip()
    if not txt:
        return False, "NONE", "CLAIMS_EMPTY"

    # 1) Explicit numbering (covers common Google variants)
    if _RE_CLAIM1_NUMBERED_LINESTART.search(txt) or _RE_CLAIM1_NUMBERED_ANYWHERE.search(txt):
        return True, "REGEX_NUMBERED", None

    # 2) CJK numbering markers (JP/CN/KR)
    if re.search(r"(請求項\s*[0-9１]|【\s*請求項\s*[0-9１]\s*】)", txt):
        return True, "CJK_NUMBERED", None
    if re.search(r"(权利要求\s*[0-9１]|權利要求\s*[0-9１]|【\s*(权利要求|權利要求)\s*[0-9１]\s*】)", txt):
        return True, "CJK_NUMBERED", None
    if re.search(r"(청구항\s*[0-9１]|\[\s*청구항\s*[0-9１]\s*\])", txt):
        return True, "CJK_NUMBERED", None

    # 3) Heuristic: unnumbered independent-claim opening (common on Google pages)
    if _RE_CLAIM1_HEURISTIC_START.search(txt):
        return True, "HEURISTIC_UNNUMBERED", "CLAIM1_HEURISTIC_UNNUMBERED"

    return False, "NONE", "CLAIM1_NOT_DETECTED"


def claims_script_flags(claims_raw: str) -> dict:
    """
    Lightweight content-based script detection for claims text.

    Governance note:
      - NOT a legal language determination.
      - QC/observability signal derived from the actual claims text being embedded.
    """
    txt = (claims_raw or "")
    nonascii = bool(_RE_NONASCII.search(txt))
    return {
        "has_nonascii": nonascii,
        "has_cjk": bool(_RE_CJK.search(txt)),
        "has_kana": bool(_RE_KANA.search(txt)),
        "has_hangul": bool(_RE_HANGUL.search(txt)),
        "is_ascii_only": (txt != "" and not nonascii),
    }


def claims_language_hint_from_flags(flags: dict) -> str:
    """
    Coarse label for dashboarding / QC:
      - ko_like / ja_like / cjk_like / nonascii_other / ascii_en_like / empty / unknown
    """
    if not flags:
        return "unknown"
    if flags.get("has_hangul"):
        return "ko_like"
    if flags.get("has_kana"):
        return "ja_like"
    if flags.get("has_cjk"):
        return "cjk_like"
    if flags.get("has_nonascii"):
        return "nonascii_other"
    if flags.get("is_ascii_only"):
        return "ascii_en_like"
    return "empty"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha1(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8")).hexdigest()


def office_from_pub(pub: str) -> str:
    pub = (pub or "").strip().upper()
    return pub[:2] if len(pub) >= 2 else ""


def read_seeds(p: Path) -> List[str]:
    seeds: List[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            seeds.append(s.upper())
    # unique + stable
    out = []
    seen = set()
    for s in seeds:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def google_url(pub: str) -> str:
    pub = (pub or "").strip().upper()
    return f"https://patents.google.com/patent/{pub}"


def us_insert_zero_variants(pub: str) -> List[str]:
    """
    Generate deterministic US publication slug variants.

    Some US publication slugs on Google Patents require 0-padding in the serial
    segment (year + padded serial). Without this, many valid US seeds return
    404 even though the document exists.
    """
    p = (pub or "").strip().upper()
    if not p.startswith("US"):
        return []

    m = re.match(r"^(US)(\d{4})(\d+)([A-Z]\d?)$", p)
    if not m:
        return []
    cc, year, serial, kind = m.group(1), m.group(2), m.group(3), m.group(4)
    if not serial.isdigit():
        return []

    v7 = f"{cc}{year}{serial.zfill(7)}{kind}"
    v8 = f"{cc}{year}{serial.zfill(8)}{kind}"
    out: List[str] = []
    for v in (v7, v8):
        if v != p and v not in out:
            out.append(v)
    return out


def candidate_google_slugs(pub: str) -> List[str]:
    p = (pub or "").strip().upper()
    cands: List[str] = [p]
    for v in us_insert_zero_variants(p):
        if v not in cands:
            cands.append(v)
    return cands


def extract_html_lang(soup: BeautifulSoup) -> str:
    html = soup.find("html")
    if html and html.has_attr("lang"):
        return str(html.get("lang") or "").strip().lower()
    return ""


def normalize_text(t: str) -> str:
    t = (t or "").strip()
    t = re.sub(r"\r\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def extract_section_text(soup: BeautifulSoup, itemprop: str) -> str:
    sec = soup.find("section", attrs={"itemprop": itemprop})
    if not sec:
        return ""
    return normalize_text(sec.get_text("\n", strip=True))


def extract_claims(soup: BeautifulSoup) -> str:
    return extract_section_text(soup, "claims")


def extract_description(soup: BeautifulSoup) -> str:
    return extract_section_text(soup, "description")


def looks_like_consent_or_robot(soup: BeautifulSoup, html_text: str) -> bool:
    """Detect consent/robot/interstitial pages that still return HTTP 200."""
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip().lower()
    h1 = ""
    h1_el = soup.find("h1")
    if h1_el:
        h1 = (h1_el.get_text(" ", strip=True) or "").strip().lower()

    blob = h1.strip()
    indicators = [
        "before you continue",
        "consent",
        "unusual traffic",
        "automated queries",
        "verify you are a human",
        "captcha",
        "robot",
    ]
    if any(k in blob for k in indicators):
        return True

    sample = (html_text or "")[:8000].lower()
    if "captcha" in sample or "unusual traffic" in sample:
        return True
    if "consent" in sample and "google" in sample:
        return True
    return False


def request_with_retry(
    session: requests.Session,
    url: str,
    timeout_s: int,
    max_retries: int,
    sleep_s: float,
) -> requests.Response:
    """GET with limited retry/backoff for transient errors."""
    attempt = 0
    backoff = max(0.8, float(sleep_s) if sleep_s else 0.8)
    while True:
        attempt += 1
        try:
            resp = session.get(url, timeout=timeout_s)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt <= max_retries:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 8.0)
                continue
            return resp
        except requests.RequestException:
            if attempt <= max_retries:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 8.0)
                continue
            raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="seed/seed_publications.txt")
    ap.add_argument("--run_id", default="", help="optional; if empty, auto timestamp")
    ap.add_argument("--sleep_s", type=float, default=0.6)
    ap.add_argument("--timeout_s", type=int, default=30)
    ap.add_argument("--max_retries", type=int, default=2, help="retries for 429/5xx/transient network errors")
    ap.add_argument("--max_fail", type=int, default=9999, help="stop early if too many failures")
    ap.add_argument("--overwrite", action="store_true", help="overwrite existing {PUB}.json (re-fetch)")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[2]
    seeds_p = repo / args.seeds
    if not seeds_p.exists():
        raise SystemExit(f"[error] missing seeds file: {seeds_p}")

    run_id = args.run_id.strip()
    if not run_id:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "__semantic_exp_v2"

    run_dir = repo / "artifacts" / "_pipeline_runs" / run_id / "02_text"
    out_raw = run_dir / "google_raw"
    out_raw.mkdir(parents=True, exist_ok=True)

    seeds = read_seeds(seeds_p)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        }
    )

    # metrics
    counters = Counter()
    ui_lang_counts = Counter()
    claims_lang_hint_counts = Counter()
    by_office = Counter()
    failures: List[Dict] = []
    fail_reason_counts = Counter()
    fail_http_counts = Counter()

    for i, pub in enumerate(seeds, start=1):
        office = office_from_pub(pub)
        by_office[office] += 1

        out_path = out_raw / f"{pub}.json"
        if out_path.exists() and not args.overwrite:
            counters["skipped_cached"] += 1
            continue

        slug_attempts = candidate_google_slugs(pub)
        url = google_url(slug_attempts[0])

        rec: Dict = {
            "publication": pub,
            "office": office,
            "source": "GOOGLE",
            "url": url,
            "google_requested_slug": slug_attempts[0],
            "google_resolved_slug": "",
            "slug_attempts": slug_attempts,
            "retrieved_at": utc_now_iso(),
            "http_status": None,
            "html_lang": "",
            "claims_script_flags": {},
            "claims_lang_hint": "",
            "claims_raw": "",
            "description_raw": "",
            "claims_chars": 0,
            "description_chars": 0,
            "has_claims": False,
            "has_claim_1": False,
            "has_description": False,
            "claim1_method": "NONE",
            "claim1_reason": None,
            "status": "FAIL",
            "reason": "",
            "error": "",
        }

        try:
            last_err: Optional[str] = None
            chosen_resp: Optional[requests.Response] = None
            chosen_slug: str = ""

            for slug in slug_attempts:
                candidate_url = google_url(slug)
                resp = request_with_retry(
                    session,
                    candidate_url,
                    timeout_s=args.timeout_s,
                    max_retries=args.max_retries,
                    sleep_s=args.sleep_s,
                )
                # Force UTF-8 to avoid mojibake in JP/KR/CN content.
                resp.encoding = "utf-8"
                rec["http_status"] = int(resp.status_code)
                rec["url"] = candidate_url
                if resp.status_code == 200:
                    chosen_resp = resp
                    chosen_slug = slug
                    break
                last_err = f"HTTP {resp.status_code}"

            if not chosen_resp:
                rec["reason"] = "HTTP_NON_200"
                raise RuntimeError(last_err or "HTTP_NON_200")

            rec["google_resolved_slug"] = chosen_slug
            html_text = chosen_resp.text
            soup = BeautifulSoup(chosen_resp.content, "html.parser", from_encoding="utf-8")

            # Some interstitial pages still return 200; treat as FAIL.
            if looks_like_consent_or_robot(soup, html_text):
                rec["reason"] = "CONSENT_OR_ROBOT_PAGE"
                raise RuntimeError("CONSENT_OR_ROBOT_PAGE")

            rec["html_lang"] = extract_html_lang(soup)

            title = ""
            if soup.title and soup.title.string:
                title = soup.title.string.strip()

            claims = extract_claims(soup)
            desc = extract_description(soup)

            has, method, claim1_reason = detect_claim1_presence(claims)

            rec["claims_raw"] = claims
            rec["description_raw"] = desc
            rec["claims_chars"] = len(claims)
            rec["description_chars"] = len(desc)
            rec["has_claims"] = bool(claims)
            rec["has_description"] = bool(desc)
            rec["has_claim_1"] = has
            rec["claim1_method"] = method
            rec["claim1_reason"] = claim1_reason

            flags = claims_script_flags(claims)
            rec["claims_script_flags"] = flags
            rec["claims_lang_hint"] = claims_language_hint_from_flags(flags)

            if not claims and not desc:
                rec["reason"] = "NO_TEXT_FOUND"
                rec["status"] = "FAIL"
                counters["fail_no_text"] += 1
            else:
                rec["status"] = "OK"
                counters["ok"] += 1

            # language stats
            ui_lang = (rec["html_lang"] or "unknown").lower()
            ui_lang_counts[ui_lang] += 1
            claims_lang_hint_counts[rec["claims_lang_hint"] or "unknown"] += 1

            # missing stats (even if OK)
            if not rec["has_claims"]:
                counters["missing_claims"] += 1
            if rec["has_claims"] and not rec["has_claim_1"]:
                counters["missing_claim_1"] += 1
            if not rec["has_description"]:
                counters["missing_description"] += 1

        except Exception as e:
            counters["fail"] += 1
            rec["status"] = "FAIL"
            rec["reason"] = rec["reason"] or "HTTP_OR_PARSE_ERROR"
            rec["error"] = str(e)
            fail_reason_counts[rec["reason"]] += 1
            if rec.get("http_status") is not None:
                fail_http_counts[str(rec["http_status"])] += 1
            failures.append(
                {
                    "publication": pub,
                    "office": office,
                    "url": rec.get("url") or url,
                    "slug_attempts": slug_attempts,
                    "google_resolved_slug": rec.get("google_resolved_slug") or "",
                    "http_status": rec["http_status"],
                    "reason": rec["reason"],
                    "error": rec["error"],
                }
            )
            if counters["fail"] >= args.max_fail:
                print("[error] too many failures, stopping early")
                break

        out_path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        if args.sleep_s > 0:
            time.sleep(args.sleep_s)

        if i % 10 == 0:
            print(
                f"[progress] {i}/{len(seeds)} ok={counters['ok']} fail={counters['fail']} cached={counters['skipped_cached']}"
            )

    # write reports
    report = {
        "generated_at": utc_now_iso(),
        "run_id": run_id,
        "policy": {"chunk_policy_version": "v2.0", "text_source": "GOOGLE", "language_mode": "ORIGINAL_ONLY"},
        "inputs": {"seeds_file": str(seeds_p), "total_seeds": len(seeds)},
        "outputs": {"google_raw_dir": str(out_raw)},
        "totals": {
            "total_seeds": len(seeds),
            "ok": int(counters["ok"]),
            "fail": int(counters["fail"]),
            "skipped_cached": int(counters["skipped_cached"]),
            "missing_claims": int(counters["missing_claims"]),
            "missing_claim_1": int(counters["missing_claim_1"]),
            "missing_description": int(counters["missing_description"]),
        },
        "office_distribution": dict(sorted(by_office.items())),
        "page_ui_lang_distribution_html_lang": dict(sorted(ui_lang_counts.items())),
        "claims_language_distribution_hint": dict(sorted(claims_lang_hint_counts.items())),
        "failures_by_reason": dict(sorted(fail_reason_counts.items())),
        "failures_by_http_status": dict(sorted(fail_http_counts.items())),
        "failures_sample": failures[:50],
        "notes": [
            "Fetched Google Patents pages without forcing /en (policy intent: original page).",
            "Stored only extracted claims/description text; no raw HTML stored (data minimization).",
            "html_lang is derived from <html lang='...'>; it reflects UI locale and is NOT authoritative for claims language.",
            "claims_script_flags and claims_lang_hint are derived from claims_raw content (the exact text that will be embedded).",
            "US seeds may require 0-padding slug variants; slug_attempts and google_resolved_slug are recorded per publication.",
            "Retries are applied for 429/5xx transient errors; consent/robot interstitial pages are detected under HTTP 200.",
        ],
    }

    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "google_text_validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # UI / page locale distribution (NOT claims language)
    (run_dir / "google_language_distribution.json").write_text(
        json.dumps(dict(sorted(ui_lang_counts.items())), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Claims content-based distribution (QC signal)
    (run_dir / "google_claims_language_distribution.json").write_text(
        json.dumps(dict(sorted(claims_lang_hint_counts.items())), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[ok] wrote -> {run_dir/'google_text_validation_report.json'}")
    print(f"[ok] wrote -> {run_dir/'google_language_distribution.json'}")
    print(f"[ok] wrote -> {run_dir/'google_claims_language_distribution.json'}")
    print(f"[ok] raw dir -> {out_raw}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())