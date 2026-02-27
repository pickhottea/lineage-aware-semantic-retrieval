#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import re
import time
import html as ihtml
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import xml.etree.ElementTree as ET

# ----------------------------
# Paths / constants
# ----------------------------
ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"

CACHE_DIR = ROOT / "cache" / "claims"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_GOOGLE_DIR = ROOT / "cache" / "claims_google"
CACHE_GOOGLE_DIR.mkdir(parents=True, exist_ok=True)

INPUT = ARTIFACTS / "rep_selection_v3.jsonl"
OUTPUT = ARTIFACTS / "claims_representation_v3.jsonl"

OPS_BASE = "https://ops.epo.org/3.2"
OPS_REST = f"{OPS_BASE}/rest-services"
OPS_TOKEN_URL = f"{OPS_BASE}/auth/accesstoken"

ARTIFACT_VERSION = "claims_representation_v3"


# ----------------------------
# Time / cache helpers
# ----------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def cache_path(docdb_dotted: str) -> Path:
    return CACHE_DIR / f"{docdb_dotted}.xml"


def cache_google_path(docdb_dotted: str) -> Path:
    return CACHE_GOOGLE_DIR / f"{docdb_dotted}.txt"


# ----------------------------
# Candidate normalization
# ----------------------------
_KIND_RE = re.compile(r"([A-Z]\d?)$")


def parse_concat_pub(pub: str) -> Optional[Tuple[str, str, str]]:
    """
    US2021372574A1 -> (US, 2021372574, A1)
    EP3825599A1 -> (EP, 3825599, A1)
    """
    p = (pub or "").strip().upper().replace(" ", "")
    if len(p) < 4 or not p[:2].isalpha():
        return None
    cc = p[:2]
    m = _KIND_RE.search(p)
    if not m:
        return None
    kind = m.group(1).upper()
    number = p[2:-len(kind)]
    if not number.isdigit():
        return None
    return cc, number, kind


def to_dotted_from_concat(pub: str) -> Optional[str]:
    t = parse_concat_pub(pub)
    if not t:
        return None
    cc, number, kind = t
    return f"{cc}.{number}.{kind}"


def split_dotted(docdb: str) -> Optional[Tuple[str, str, str]]:
    parts = (docdb or "").strip().upper().split(".")
    if len(parts) != 3:
        return None
    cc, number, kind = parts
    if not cc or not number or not kind:
        return None
    return cc, number, kind


def is_kind_letter_only(kind: str) -> bool:
    k = (kind or "").strip().upper()
    return len(k) == 1 and k.isalpha()


def kind_letter(kind: str) -> str:
    return (kind or "").strip().upper()[:1]


# ----------------------------
# OPS token (client_credentials)
# ----------------------------
@dataclass
class TokenState:
    access_token: Optional[str] = None
    expires_at_epoch: float = 0.0


def get_access_token(session: requests.Session, key: str, secret: str, state: TokenState) -> str:
    now = time.time()
    if state.access_token and now < state.expires_at_epoch - 30:
        return state.access_token

    r = session.post(
        OPS_TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(key, secret),
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    state.access_token = token
    state.expires_at_epoch = now + expires_in
    return token


# ----------------------------
# Fetch claims via OPS REST (docdb dotted)
# ----------------------------
def fetch_claims_xml(
    session: requests.Session,
    token: str,
    docdb_dotted: str,
    timeout: int = 30,
) -> Tuple[Optional[str], str]:
    """
    Returns (xml_text, status)
    status:
      OK, OK(CACHE), OPS_404, OPS_401, OPS_403, OPS_NON_XML, OPS_OTHER_*
    """
    p = cache_path(docdb_dotted)
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore"), "OK(CACHE)"

    url = f"{OPS_REST}/published-data/publication/docdb/{docdb_dotted}/claims"
    r = session.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=timeout)

    if r.status_code == 404:
        return None, "OPS_404"
    if r.status_code == 401:
        return None, "OPS_401"
    if r.status_code == 403:
        return None, "OPS_403"
    if r.status_code >= 400:
        return None, f"OPS_OTHER_{r.status_code}"

    ctype = (r.headers.get("content-type") or "").lower()
    if "xml" not in ctype:
        return None, "OPS_NON_XML"

    text = r.text or ""
    p.write_text(text, encoding="utf-8")
    return text, "OK"


# ----------------------------
# Minimal structure gate (OPS XML)
# ----------------------------
def has_claim_structure(xml_text: str) -> Tuple[bool, int, str]:
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return False, 0, "XML_PARSE_FAIL"

    claims = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""
        if tag.lower() == "claim":
            claims.append(el)

    if not claims:
        return False, 0, "NO_CLAIM_TAG"

    nums = []
    for c in claims:
        n = c.attrib.get("num")
        if n and str(n).isdigit():
            nums.append(int(n))

    if nums and (1 not in nums):
        return True, len(claims), "OK_NO_NUM"
    return True, len(claims), "OK"


# ----------------------------
# Candidate resolver (app-like -> pub-like)
# ----------------------------
def build_try_list(row: Dict[str, Any], candidate: str) -> List[str]:
    tries: List[str] = []

    dotted = candidate if "." in candidate else (to_dotted_from_concat(candidate) or "")
    dotted = dotted.strip().upper()
    if dotted:
        tries.append(dotted)

    proc = row.get("processing_publications") or []
    proc_dotted: List[str] = []
    for p in proc:
        d = to_dotted_from_concat(p)
        if d:
            proc_dotted.append(d)

    info = split_dotted(dotted) if dotted else None
    if not info:
        seen = set()
        out = []
        for t in tries:
            if t and t not in seen:
                out.append(t)
                seen.add(t)
        return out

    cc, _number, kind = info

    if is_kind_letter_only(kind):
        want_letter = kind_letter(kind)
        preferred_suffix = ["1", "2"] if want_letter == "A" else ["1", "2", "3"]

        candidates2: List[str] = []
        for d in proc_dotted:
            i = split_dotted(d)
            if not i:
                continue
            cc2, _num2, kind2 = i
            if cc2 != cc:
                continue
            if kind_letter(kind2) != want_letter:
                continue
            if not is_kind_letter_only(kind2):
                candidates2.append(d)

        def score(d: str) -> Tuple[int, str]:
            i = split_dotted(d)
            if not i:
                return (999, d)
            _ccx, _nx, k = i
            if len(k) >= 2 and k[0] == want_letter:
                suf = k[1:]
                if suf in preferred_suffix:
                    return (0 if suf == "1" else 1, d)
            return (5, d)

        candidates2 = sorted(set(candidates2), key=score)
        tries.extend(candidates2)

    seen = set()
    out = []
    for t in tries:
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    return out


# ----------------------------
# Google Patents: claims text fetch (best-effort)
# ----------------------------
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_NL_RE = re.compile(r"\n{3,}")

_US_PUB_RE = re.compile(r"^US(20\d{2})(\d+)([A-Z]\d?)$", re.I)


def _strip_tags(s: str) -> str:
    s = _TAG_RE.sub("", s)
    s = ihtml.unescape(s)
    s = s.replace("\r", "\n")
    s = "\n".join(_WS_RE.sub(" ", line).strip() for line in s.split("\n"))
    s = _NL_RE.sub("\n\n", s).strip()
    return s


def _us_insert_zero_variant(pub: str) -> Optional[str]:
    """
    你要的洞：US2021372574A1 -> US20210372574A1（年後補 0，因為中段 6 digits）
    """
    p = (pub or "").strip().upper().replace(" ", "")
    m = _US_PUB_RE.match(p)
    if not m:
        return None
    year, mid, kind = m.group(1), m.group(2), m.group(3).upper()

    # 這個 case：mid 長度 6 -> 插 0
    if len(mid) == 6:
        return f"US{year}0{mid}{kind}"
    return None


def _google_url(pub: str, with_en: bool) -> str:
    p = (pub or "").strip().upper().replace(" ", "")
    if with_en:
        return f"https://patents.google.com/patent/{p}/en"
    return f"https://patents.google.com/patent/{p}"


def _http_get_google(session: requests.Session, url: str, timeout: int) -> requests.Response:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en,en-US;q=0.9",
    }
    return session.get(url, headers=headers, timeout=timeout)


def fetch_claims_google_text(
    session: requests.Session,
    publication: str,
    sleep_s: float = 1.0,
    timeout: int = 30,
) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Returns (claims_text, status, resolved_publication)

    status:
      GOOGLE_OK, GOOGLE_OK_ALT0, GOOGLE_OK(CACHE), GOOGLE_404, GOOGLE_BLOCKED,
      GOOGLE_NO_CLAIMS, GOOGLE_NON_HTML, GOOGLE_ERROR_*
    """
    pub = (publication or "").strip().upper().replace(" ", "")
    if not pub:
        return None, "GOOGLE_ERROR_EMPTY_PUBLICATION", None

    cache_file = CACHE_GOOGLE_DIR / f"{pub}.txt"
    if cache_file.exists():
        txt = cache_file.read_text(encoding="utf-8", errors="ignore").strip()
        if txt:
            return txt, "GOOGLE_OK(CACHE)", pub

    # 這裡就是你要的：一定會試「原本」+「補0」兩條
    pubs_to_try = [pub]
    alt0 = _us_insert_zero_variant(pub)
    if alt0 and alt0 != pub:
        pubs_to_try.append(alt0)

    time.sleep(max(0.0, sleep_s))

    last_status = "GOOGLE_404"

    for idx, pub_try in enumerate(pubs_to_try):
        # A) /en
        try:
            r = _http_get_google(session, _google_url(pub_try, with_en=True), timeout=timeout)
        except Exception as e:
            return None, f"GOOGLE_ERROR_REQUEST:{e}", None

        # B) if 404 -> no /en
        if r.status_code == 404:
            try:
                r = _http_get_google(session, _google_url(pub_try, with_en=False), timeout=timeout)
            except Exception as e:
                return None, f"GOOGLE_ERROR_REQUEST2:{e}", None

        if r.status_code == 404:
            last_status = "GOOGLE_404"
            continue
        if r.status_code in (429, 403):
            return None, "GOOGLE_BLOCKED", pub_try
        if r.status_code >= 400:
            return None, f"GOOGLE_ERROR_HTTP_{r.status_code}", pub_try

        ctype = (r.headers.get("content-type") or "").lower()
        if "html" not in ctype:
            last_status = "GOOGLE_NON_HTML"
            continue

        html_text = r.text or ""
        if not html_text.strip():
            last_status = "GOOGLE_ERROR_EMPTY_BODY"
            continue

        claims_block = None

        # Pattern A: itemprop="claims"
        m = re.search(r'itemprop\s*=\s*["\']claims["\']', html_text, flags=re.I)
        if m:
            start = max(0, m.start() - 2000)
            end = min(len(html_text), m.start() + 200000)
            window = html_text[start:end]
            m2 = re.search(r"(<section[^>]*itemprop\s*=\s*['\"]claims['\"][\s\S]*?</section>)", window, flags=re.I)
            if m2:
                claims_block = m2.group(1)
            else:
                m3 = re.search(r"(<div[^>]*itemprop\s*=\s*['\"]claims['\"][\s\S]*?</div>)", window, flags=re.I)
                if m3:
                    claims_block = m3.group(1)

        # Pattern B: class contains "claims"
        if not claims_block:
            m4 = re.search(r"(<section[^>]*class=['\"][^'\"]*claims[^'\"]*['\"][\s\S]*?</section>)", html_text, flags=re.I)
            if m4:
                claims_block = m4.group(1)

        if not claims_block:
            last_status = "GOOGLE_NO_CLAIMS"
            continue

        claims_text = _strip_tags(claims_block)
        if not claims_text or len(claims_text) < 80:
            last_status = "GOOGLE_NO_CLAIMS"
            continue

        # cache under ORIGINAL pub key (so你下次不用再跑)
        cache_file.write_text(claims_text, encoding="utf-8")

        if idx == 1 and alt0 and pub_try == alt0:
            return claims_text, "GOOGLE_OK_ALT0", pub_try
        return claims_text, "GOOGLE_OK", pub_try

    return None, last_status, None


# ----------------------------
# Main
# ----------------------------
def main() -> int:
    key = os.getenv("OPS_KEY") or os.getenv("EPO_OPS_KEY")
    secret = os.getenv("OPS_SECRET") or os.getenv("EPO_OPS_SECRET")
    if not key or not secret:
        raise SystemExit("Missing OPS_KEY/OPS_SECRET (or EPO_OPS_KEY/EPO_OPS_SECRET)")

    enable_google = os.getenv("ENABLE_GOOGLE_FALLBACK", "0").strip() == "1"
    google_sleep_s = float(os.getenv("GOOGLE_SLEEP_S", "1.5"))

    session = requests.Session()
    token_state = TokenState()

    total = ok = hitl = 0

    with INPUT.open("r", encoding="utf-8") as f_in, OUTPUT.open("w", encoding="utf-8") as f_out:
        for line in f_in:
            total += 1
            row = json.loads(line)

            family_id = row.get("family_id")
            asset_id = row.get("asset_id")
            candidates = row.get("claims_candidates") or []

            selected: Optional[str] = None
            selected_source: Optional[str] = None
            structure_status: Optional[str] = None
            claims_count = 0
            claim_gate_reason: Optional[str] = None
            last_fetch_status: Optional[str] = None

            claims_source: Optional[str] = None  # OPS / GOOGLE / None
            governance_flags: List[str] = []
            hitl_cause: Optional[str] = None

            google_status: Optional[str] = None
            google_seed_publication: Optional[str] = None
            google_resolved_publication: Optional[str] = None

            attempted_docdb_count = 0
            attempted_docdb_head: List[str] = []
            last_attempted_docdb: Optional[str] = None
            attempt_log_head: List[Dict[str, Any]] = []

            token = get_access_token(session, key, secret, token_state)

            # ----------------------------
            # Phase 1: OPS claims retrieval
            # ----------------------------
            for cand in candidates:
                try_list = build_try_list(row, cand)

                for docdb_dotted in try_list:
                    attempted_docdb_count += 1
                    last_attempted_docdb = docdb_dotted
                    if len(attempted_docdb_head) < 5:
                        attempted_docdb_head.append(docdb_dotted)

                    xml_text, fetch_status = fetch_claims_xml(session, token, docdb_dotted)
                    last_fetch_status = fetch_status

                    if len(attempt_log_head) < 10:
                        attempt_log_head.append({"docdb": docdb_dotted, "fetch_status": fetch_status})

                    if xml_text is None:
                        continue

                    ok_struct, cnt, reason = has_claim_structure(xml_text)
                    if not ok_struct:
                        structure_status = "STRUCTURE_UNCERTAIN"
                        claim_gate_reason = reason
                        continue

                    selected = docdb_dotted
                    claims_count = cnt
                    claim_gate_reason = reason
                    structure_status = "OK"
                    claims_source = "OPS"

                    cand_norm = cand if "." in cand else (to_dotted_from_concat(cand) or "")
                    cand_norm = (cand_norm or "").upper()
                    selected_source = "DIRECT" if docdb_dotted == cand_norm else "FAMILY_FALLBACK"
                    break

                if selected:
                    break

            # If OPS succeeded
            if selected:
                ok += 1
            else:
                # ----------------------------
                # Phase 2: classify HITL + optional Google fallback
                # ----------------------------
                hitl += 1

                statuses = [x.get("fetch_status") for x in attempt_log_head if isinstance(x, dict)]
                all_404 = (len(statuses) > 0) and all(s == "OPS_404" for s in statuses)

                targets = row.get("required_set_targets") or {}
                has_ep_or_wo = any([targets.get("wo_a1_pub"), targets.get("ep_a_pub"), targets.get("ep_b_pub")])
                has_us = any([targets.get("us_a_pub"), targets.get("us_b_pub")])

                if all_404 and has_us and (not has_ep_or_wo):
                    hitl_cause = "HITL_US_ONLY_OPS_CLAIMS_404"
                    structure_status = hitl_cause
                else:
                    structure_status = structure_status or "NO_VALID_PUBLICATION"

                if enable_google:
                    # Prefer seed publication first
                    google_seed_concat = row.get("seed_publication_number")
                    if not google_seed_concat:
                        google_seed_concat = targets.get("us_b_pub") or targets.get("us_a_pub")
                    if not google_seed_concat and last_attempted_docdb:
                        info = split_dotted(last_attempted_docdb)
                        if info:
                            cc, number, kind = info
                            google_seed_concat = f"{cc}{number}{kind}"

                    google_seed_publication = google_seed_concat

                    claims_text = None
                    if google_seed_concat:
                        claims_text, google_status, google_resolved_publication = fetch_claims_google_text(
                            session=session,
                            publication=google_seed_concat,
                            sleep_s=google_sleep_s,
                        )
                    else:
                        google_status = "GOOGLE_ERROR_NO_SEED"

                    if claims_text:
                        selected = to_dotted_from_concat(google_seed_concat) if google_seed_concat else last_attempted_docdb
                        selected_source = "GOOGLE_FALLBACK_SEED"
                        structure_status = "OK"
                        claim_gate_reason = "GOOGLE_CLAIMS_TEXT"
                        claims_count = 0
                        claims_source = "GOOGLE"
                        governance_flags.extend(["THIRD_PARTY_SOURCE", "COVERAGE_FALLBACK"])

                        if selected:
                            cache_google_path(selected).write_text(claims_text, encoding="utf-8")
                    else:
                        governance_flags.append("GOOGLE_ATTEMPTED")

            out = {
                "artifact_version": ARTIFACT_VERSION,
                "created_at": now_iso(),
                "family_id": family_id,
                "asset_id": asset_id,

                "selected_publication": selected,
                "selected_source": selected_source,
                "structure_status": structure_status,
                "claims_count": claims_count,
                "claim_gate_reason": claim_gate_reason,
                "last_fetch_status": last_fetch_status,

                "claims_source": claims_source,
                "hitl_cause": hitl_cause,
                "governance_flags": governance_flags,

                "google_status": google_status,
                "google_seed_publication": google_seed_publication,
                "google_resolved_publication": google_resolved_publication,

                "claims_raw_xml_path": str(cache_path(selected)) if (selected and claims_source == "OPS") else None,
                "claims_google_text_path": str(cache_google_path(selected)) if (selected and claims_source == "GOOGLE") else None,

                "attempted_docdb_count": attempted_docdb_count,
                "attempted_docdb_head": attempted_docdb_head,
                "last_attempted_docdb": last_attempted_docdb,
                "attempt_log_head": attempt_log_head,

                "seed_publication_number": row.get("seed_publication_number"),
                "required_set_targets": row.get("required_set_targets"),
            }

            f_out.write(json.dumps(out, ensure_ascii=False) + "\n")

    print(json.dumps({"total": total, "ok": ok, "hitl": hitl, "out": str(OUTPUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
