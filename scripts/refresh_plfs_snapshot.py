#!/usr/bin/env python3
"""Refresh the baked PLFS snapshot (data/plfs-macro.json) from the MoSPI
eSankhyiki API — build-time fetch ONLY.

Why build-time: the API returns HTTP 403 {"message":"CORS blocked"} for any
browser Origin other than MoSPI's own hosts (verified 14 Nov 2026, see
research_notes/.../phase2/spike-esankhyiki.md §3). No page may fetch() this
API at runtime; the snapshot shipped with the site is the only macro source.

Procedure (spike §6.2): three quarterly calls (LFPR/WPR/UR, indicator_code
1/2/3, frequency_code=2, year=2025,2026) + two monthly calls (UR/LFPR,
frequency_code=3). Plain requests carry NO Origin header — urllib sends
none by default; do not add one.

Safety: every response must be HTTP 200 with msg "Data fetched successfully",
statusCode true, and non-empty data. On ANY failure the snapshot is NOT
overwritten — a stale good snapshot is always better than an empty one.
Never use year=all (returns "No Data Found").

Usage:
    python scripts/refresh_plfs_snapshot.py [--years 2025,2026] [--out data/plfs-macro.json]
"""

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.mospi.gov.in/api/plfs/getData"
COMMON = "state_code=99&gender_code=3&age_code=1&sector_code=3&limit=100&Format=JSON"
QUARTERS = {"Apr-Jun": 1, "Jul-Sep": 2, "Oct-Dec": 3, "Jan-Mar": 4}
MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
    "December": 12,
}


def fetch(indicator_code, frequency_code, years):
    url = (f"{BASE}?indicator_code={indicator_code}&frequency_code={frequency_code}"
           f"&year={years}&{COMMON}")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        payload = json.load(resp)
    if payload.get("msg") != "Data fetched successfully":
        raise RuntimeError(f"API refused data for {url}: msg={payload.get('msg')!r}")
    if payload.get("statusCode") is not True:
        raise RuntimeError(f"API statusCode != true for {url}: {payload.get('statusCode')!r}")
    if not payload.get("data"):
        raise RuntimeError(f"API returned empty data for {url}")
    return payload["data"]


def quarterly(rows):
    """rows -> sorted [{quarter: 'YYYY Q', LFPR/WPR/UR}] merged by caller."""
    out = []
    for r in rows:
        q = r["quarter"]
        out.append((int(r["year"]), QUARTERS[q], f"{r['year']} {q}", float(r["value"])))
    out.sort()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--years", default="2025,2026")
    ap.add_argument("--out", default="data/plfs-macro.json")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    out_path = root / args.out

    # Quarterly: one call per indicator (LFPR=1, WPR=2, UR=3).
    q = {}
    for ind, name in ((1, "LFPR"), (2, "WPR"), (3, "UR")):
        q[name] = {label: v for _, _, label, v in quarterly(fetch(ind, 2, args.years))}
    labels = sorted(q["LFPR"])
    quarterly_series = [
        {"quarter": lab, "LFPR": q["LFPR"][lab], "WPR": q["WPR"][lab], "UR": q["UR"][lab]}
        for lab in labels
    ]
    latest = quarterly_series[-1]

    # Monthly UR + LFPR (Mar 2026 is genuinely absent from the API — keep the gap).
    def monthly(ind):
        rows = fetch(ind, 3, args.years)
        series = []
        for r in rows:
            series.append((int(r["year"]), MONTHS[r["month"]], float(r["value"])))
        series.sort()
        return [{"month": f"{y:04d}-{m:02d}", "value": v} for y, m, v in series]

    monthly_ur = monthly(3)
    monthly_lfpr = monthly(1)

    fetched_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    snapshot = {
        "source": "PLFS (NSO/MoSPI) via eSankhyiki API https://api.mospi.gov.in/api/plfs/getData",
        "source_url": "https://esankhyiki.mospi.gov.in/",
        "vintage": "Quarterly bulletin Jul–Sep 2026, released 10 Nov 2026",
        "fetched_at": fetched_at,
        "coverage": "All India, person, age 15+, rural+urban, Current Weekly Status (CWS), revamped series from Apr 2025",
        "note": ("Live browser fetch is blocked by the API (403 CORS blocked for "
                 "non-MoSPI origins); this is a baked snapshot refreshed manually. "
                 "Revamped series is not comparable with pre-2025 rounds."),
        "latest": {"quarter": latest["quarter"], "LFPR": latest["LFPR"],
                   "WPR": latest["WPR"], "UR": latest["UR"]},
        "quarterly": quarterly_series,
        "monthly_ur": [{"month": p["month"], "UR": p["value"]} for p in monthly_ur],
        "monthly_lfpr": [{"month": p["month"], "LFPR": p["value"]} for p in monthly_lfpr],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, indent=2, sort_keys=False) + "\n")
    tmp.replace(out_path)
    print(f"Wrote {out_path} ({len(quarterly_series)} quarters, "
          f"{len(monthly_ur)} monthly UR, {len(monthly_lfpr)} monthly LFPR)")
    print(f"Latest: {latest['quarter']} LFPR {latest['LFPR']} WPR {latest['WPR']} UR {latest['UR']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
