#!/usr/bin/env python3
"""
Step B — Fetch OPS Family Members (robust)

Input:
  seed/seed_publications.txt   (e.g. WO2025201951A1 / US20210372574A1 / EP3919806A1)

Output:
  artifacts/ops_family_members.jsonl   (one row per seed)
  artifacts/run_log.jsonl              (one row per request)

Cache:
  artifacts/cache/ops/family/<sha1(docdb)>.json   (ONLY cache success 200 responses)

Key behaviors:
- Accept seed pub in "raw" format and auto-convert to docdb "CC.NUMBER.KIND"
- Token is short-lived: auto-refresh by calling scripts/ops_get_token.py when needed
- Never cache failures (prevents being stuck with cached 400/401)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Tuple

import requests

# =====================
# Paths
# =====================
ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "seed" / "seed_publications.txt"
OUT = ROOT / "artifacts" / "ops_family_members.jsonl"
LOG = ROOT / "artifacts" / "run_log.jsonl"
CACHE_DIR = ROOT / "artifacts" / "cache" / "ops" / "family"

# =====================
# OPS config
# =====================
OPS_BASE = "https://ops.epo.org/3.2/rest-services"
OPS_ENDPOINT = "/family/publication/docdb/{}"  # expects docdb, like WO.2025201951.A1
RATE_SLEEP = 0.8
MAX_RETRY = 3
TIMEOUT_S = 25


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log_event(event: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def to_docdb(pub: str) -> str | None:
    """
    Convert 'WO2025201951A1' -> 'WO.2025201951.A1'
            'EP3919806A1'  -> 'EP.3919806.A1'
            'US20210372574A1' -> 'US.20210372574.A1'
    If already in docdb form, returns normalized.
    """
    p = (pub or "").strip().upper()

    # already docdb-like: CC.NUMBER.KIND
    if re.match(r"^[A-Z]{2}\.\d+\.[A-Z0-9]{1,2}$", p):
        return p

    if len(p) < 6:
        return None
    if not p[:2].isalpha():
        return None
    if p.endswith("P"):  # provisional-like
        return None

    cc = p[:2]
    kind = p[-2:]  # A1, B2, U1...
    number = p[2:-2]
    if not number.isdigit():
        return None
    return f"{cc}.{number}.{kind}"


def get_token_from_script() -> str:
    """
    Calls scripts/ops_get_token.py which should print token to stdout.
    """
    token_script = ROOT / "scripts" / "ops_get_token.py"
    if not token_script.exists():
        raise RuntimeError(f"missing token helper: {token_script}")

    out = subprocess.check_output(
        [sys.executable, str(token_script)],
        cwd=str(ROOT),
        env=os.environ.copy(),
        stderr=subprocess.STDOUT,
        text=True,
    ).strip()

    if not out or len(out) < 20:
        raise RuntimeError(f"ops_get_token.py returned unexpected output: {out[:80]}")
    return out


def ensure_token() -> str:
    """
    Prefer OPS_TOKEN from env; otherwise fetch a new one.
    """
    t = (os.environ.get("OPS_TOKEN") or "").strip()
    if t and len(t) >= 20:
        return t
    t = get_token_from_script()
    os.environ["OPS_TOKEN"] = t
    return t


def cache_path_for_docdb(docdb: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{sha1(docdb)}.json"


def fetch_family_docdb(docdb: str) -> Tuple[dict | None, bool, int, int, int, str]:
    """
    Returns: (raw_json_or_none, cache_hit, http_status, retry_count, elapsed_ms, token_state)
    token_state: "env" or "refreshed"
    """
    docdb = docdb.strip().upper()
    p = cache_path_for_docdb(docdb)

    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")), True, 200, 0, 0, "cache"
        except Exception:
            # corrupted cache -> ignore
            try:
                p.unlink()
            except Exception:
                pass

    token = ensure_token()
    token_state = "env"

    headers = {
        "Authorization": f"Bearer {token}",
        # OPS sometimes returns XML on errors; request JSON for success parsing
        "Accept": "application/json",
    }
    url = OPS_BASE + OPS_ENDPOINT.format(docdb)

    for attempt in range(1, MAX_RETRY + 1):
        start = time.time()
        try:
            r = requests.get(url, headers=headers, timeout=TIMEOUT_S)
            elapsed = int((time.time() - start) * 1000)

            # token invalid/expired: refresh once and retry immediately
            if r.status_code in (400, 401):
                body = (r.text or "")[:2000]
                if "invalid_access_token" in body or "Invalid Access Token" in body or "oauth.v2.InvalidAccessToken" in body:
                    token = get_token_from_script()
                    os.environ["OPS_TOKEN"] = token
                    headers["Authorization"] = f"Bearer {token}"
                    token_state = "refreshed"
                    # retry without counting as a backoff attempt
                    continue

            if r.status_code == 200:
                data = r.json()
                # ONLY cache success
                p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                return data, False, 200, attempt - 1, elapsed, token_state

            if r.status_code in (429, 500, 502, 503):
                time.sleep(RATE_SLEEP * attempt)
                continue

            return None, False, r.status_code, attempt - 1, elapsed, token_state

        except Exception:
            time.sleep(RATE_SLEEP * attempt)

    return None, False, -1, MAX_RETRY, 0, token_state


def normalize_family(seed_pub_raw: str, seed_docdb: str, raw: dict) -> dict:
    """
    Very conservative parsing:
    - Extract @family-id if present
    - Extract docdb publication members -> publication_number like CC+NUMBER+KIND and jurisdiction=CC
    """
    fam_id = None
    members = []

    try:
        fam = raw["ops:world-patent-data"]["ops:patent-family"]["ops:family-member"]
        if isinstance(fam, dict):
            fam = [fam]

        for m in fam:
            fam_id = fam_id or m.get("@family-id")
            pubs = m.get("publication-reference", {}).get("document-id", [])
            if isinstance(pubs, dict):
                pubs = [pubs]

            for p in pubs:
                if p.get("@document-id-type") == "docdb":
                    cc = p.get("country")
                    num = p.get("doc-number")
                    kind = p.get("kind")
                    if cc and num and kind:
                        pubno = f"{cc}{num}{kind}"
                        members.append(
                            {
                                "publication_number": pubno,
                                "publication_docdb": f"{cc}.{num}.{kind}",
                                "jurisdiction": cc,
                                "kind": kind,
                                "is_seed": (f"{cc}.{num}.{kind}" == seed_docdb),
                            }
                        )
    except Exception:
        pass

    return {
        "seed_publication_number": seed_pub_raw.strip(),
        "seed_publication_docdb": seed_docdb,
        "ops_family_id": fam_id,
        "family_members": members,
        "family_members_count": len(members),
        "fetched_at": now(),
    }


def main() -> int:
    if not SEED.exists():
        print(f"ERROR: missing seed file: {SEED}")
        return 2

    pubs = [p.strip() for p in SEED.read_text(encoding="utf-8").splitlines() if p.strip()]
    OUT.parent.mkdir(parents=True, exist_ok=True)

    for pub_raw in pubs:
        docdb = to_docdb(pub_raw)
        if not docdb:
            log_event(
                {
                    "step": "step_b_fetch_ops_family",
                    "publication_number": pub_raw,
                    "publication_docdb": None,
                    "endpoint": "ops/family",
                    "cache_hit": False,
                    "http_status": -2,
                    "retry_count": 0,
                    "elapsed_ms": 0,
                    "token_state": "n/a",
                    "error": "DOCDB_NORMALIZE_FAIL",
                    "timestamp": now(),
                }
            )
            continue

        raw, cache_hit, status, retry, elapsed, token_state = fetch_family_docdb(docdb)

        log_event(
            {
                "step": "step_b_fetch_ops_family",
                "publication_number": pub_raw,
                "publication_docdb": docdb,
                "endpoint": "ops/family",
                "cache_hit": cache_hit,
                "http_status": status,
                "retry_count": retry,
                "elapsed_ms": elapsed,
                "token_state": token_state,
                "timestamp": now(),
            }
        )

        if raw is None:
            continue

        rec = normalize_family(pub_raw, docdb, raw)
        with OUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        time.sleep(RATE_SLEEP)

    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main())
