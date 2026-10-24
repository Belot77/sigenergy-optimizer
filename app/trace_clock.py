"""Bounded, passive UTC corroboration for trace storage only.

Executed in a disposable subprocess so even a stuck OS DNS resolver cannot
occupy an archive worker indefinitely. No control code imports this module.
"""
from __future__ import annotations

import json
import secrets
import sys
import time
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime

import httpx

SOURCES = (("google", "https://www.google.com/generate_204"),
           ("cloudflare", "https://www.cloudflare.com/"))
PROBE_SECONDS = 3.0
PAIR_SECONDS = 10.0
DATE_TOLERANCE = 5.0
DRIFT_TOLERANCE = 1.0


def _corroborate(expected: datetime) -> dict | None:
    started = time.monotonic()
    wall_started = datetime.now(timezone.utc)
    if abs((wall_started - expected).total_seconds()) > DATE_TOLERANCE:
        return None
    evidence = []
    with httpx.Client(verify=True, trust_env=False, follow_redirects=False,
                      timeout=PROBE_SECONDS) as client:
        for source, endpoint in SOURCES:
            before = time.monotonic()
            wall_before = datetime.now(timezone.utc)
            response = client.head(endpoint, params={"trace_clock_nonce": secrets.token_hex(16)},
                                   headers={"Cache-Control": "no-cache, no-store", "Pragma": "no-cache"})
            after = time.monotonic()
            wall_after = datetime.now(timezone.utc)
            elapsed = after - before
            if not 0 <= elapsed <= PROBE_SECONDS or not 200 <= response.status_code < 300:
                return None
            dates, ages = response.headers.get_list("date"), response.headers.get_list("age")
            if len(dates) != 1 or (ages and ages != ["0"]):
                return None
            date = parsedate_to_datetime(dates[0])
            if (date.tzinfo is None or date.utcoffset().total_seconds() != 0
                    or format_datetime(date, usegmt=True) != dates[0]):
                return None
            if (abs((wall_after - wall_before).total_seconds() - elapsed) > DRIFT_TOLERANCE
                    or not wall_before.timestamp() - DATE_TOLERANCE <= date.timestamp()
                    <= wall_after.timestamp() + DATE_TOLERANCE):
                return None
            evidence.append({"source": source, "date": date.isoformat(), "rtt_seconds": elapsed})
    elapsed = time.monotonic() - started
    if (not 0 <= elapsed <= PAIR_SECONDS
            or abs((datetime.now(timezone.utc) - wall_started).total_seconds() - elapsed) > DRIFT_TOLERANCE
            or abs((datetime.fromisoformat(evidence[0]["date"])
                    - datetime.fromisoformat(evidence[1]["date"])).total_seconds())
            > DATE_TOLERANCE + elapsed):
        return None
    return {"method": "dual_https_date", "sources": evidence}


def corroborate(expected: datetime) -> dict | None:
    try:
        return _corroborate(expected)
    except Exception:
        return None


def main() -> None:
    # Input/output contain UTC and public source labels only; never response bodies.
    try:
        expected = datetime.fromisoformat(sys.stdin.read(128))
        result = corroborate(expected)
    except Exception:
        result = None
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
