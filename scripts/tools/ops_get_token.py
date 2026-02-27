#!/usr/bin/env python3
import os
import sys
import requests

TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"

def main() -> int:
    key = os.environ.get("OPS_KEY", "").strip()
    secret = os.environ.get("OPS_SECRET", "").strip()

    if not key or not secret:
        print("ERROR: missing OPS_KEY / OPS_SECRET in env", file=sys.stderr)
        return 2

    data = {"grant_type": "client_credentials"}
    r = requests.post(
        TOKEN_URL,
        data=data,
        auth=(key, secret),
        headers={"Accept": "application/json"},
        timeout=20,
    )

    if r.status_code != 200:
        print(f"ERROR: token http {r.status_code}", file=sys.stderr)
        print(r.text[:500], file=sys.stderr)
        return 3

    j = r.json()
    token = (j.get("access_token") or "").strip()
    if not token:
        print("ERROR: access_token missing in response", file=sys.stderr)
        print(str(j)[:500], file=sys.stderr)
        return 4

    # print token only (for export)
    sys.stdout.write(token)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

