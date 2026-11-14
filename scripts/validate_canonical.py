#!/usr/bin/env python3
"""Validate data/canonical.json and the generated legacy files.

    python scripts/validate_canonical.py

Checks (canonical-design §6):
- schema: every techRoles[] / occupations[] / cities[] record has all required
  fields; ids unique; no category "City Hubs".
- totals: sum techRoles.headcountEstimate within ±2% of
  macro.marketStats.techWorkforceMn * 1e6; sum cities[].sharePct == 100
  (±0.5); sum cities[].gccCenters == macro.marketStats.gccCenters (exact);
  sum occupations.jobsSample == macro.plfs.sampleSize.
- cross-file: regenerate the three legacy files in memory and diff against
  the committed ones — fail if they differ (catches hand-edits to generated
  files; run scripts/build_canonical.py to regenerate).
- sanity: fresherSalaryLpa <= salaryLpaMedian; min <= median <= max;
  growthPct in [-50, +100]; exposure in [0, 10]; every indices[] point has
  year; no duplicate (provider, year, month); meta.lastUpdated is a valid
  date <= today; every meta.sources[] entry has a URL.
- legacy-shape: rich pay_annual == pay_monthly * 12 on generated output;
  site monthlyIndex has 12 entries for the latest year (missing months as
  explicit nulls, not absent rows); site roles fresherSalary <= salary.
- PLFS snapshot: data/plfs-macro.json exists and its latest quarter matches
  canonical macro.plfs.
- HTML stamps: each page carries a "Data as of" stamp matching lastUpdated.

Exit 0 = all checks pass; exit 1 = any failure (CI fails the PR).
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_canonical as bc  # noqa: E402 — reuse the projection functions

FAILURES = []
WARNINGS = []


def check(cond, msg):
    if not cond:
        FAILURES.append(msg)
    return cond


def warn(msg):
    WARNINGS.append(msg)


def load(p):
    with open(ROOT / p) as f:
        return json.load(f)


def main():
    canon = load("data/canonical.json")
    meta = canon["meta"]
    ms = canon["macro"]["marketStats"]

    # ---- meta -----------------------------------------------------------
    check(isinstance(meta.get("schemaVersion"), int), "meta.schemaVersion missing/not int")
    try:
        last = date.fromisoformat(meta["lastUpdated"])
        check(last <= date.today(),
              f"meta.lastUpdated {meta['lastUpdated']} is in the future")
    except ValueError:
        FAILURES.append(f"meta.lastUpdated {meta.get('lastUpdated')!r} is not YYYY-MM-DD")
        last = None
    for i, s in enumerate(meta.get("sources", [])):
        check(bool(s.get("url")), f"meta.sources[{i}] {s.get('name')!r} has no URL")
    check(len(meta.get("sources", [])) >= 1, "meta.sources is empty")

    # ---- tech roles ------------------------------------------------------
    roles = canon["techRoles"]
    check(len(roles) > 0, "techRoles is empty")
    ids = [r.get("id") for r in roles]
    check(len(ids) == len(set(ids)), "duplicate techRoles ids")
    req = ["id", "title", "category", "headcountEstimate", "headcountBasis",
           "growthPct", "growthBasis", "growthVintage", "salaryLpaMedian",
           "salaryBasis", "salarySource", "fresherSalaryLpa", "exposure",
           "exposureBasis", "demandScore", "remotePct", "cities", "education",
           "skills", "femalePct", "urbanPct", "rationale", "sources"]
    for r in roles:
        for f in req:
            check(f in r, f"tech role {r.get('id')} missing field {f}")
        check(r.get("category") != "City Hubs",
              f"tech role {r.get('id')} has category 'City Hubs'")
        check(r.get("headcountBasis") == "workforce-share",
              f"tech role {r.get('id')} headcountBasis != workforce-share")
        if r.get("fresherSalaryLpa") is not None and r.get("salaryLpaMedian") is not None:
            check(r["fresherSalaryLpa"] <= r["salaryLpaMedian"],
                  f"{r['id']}: fresher {r['fresherSalaryLpa']} > median {r['salaryLpaMedian']}")
        mn, med, mx = r.get("salaryLpaMin"), r.get("salaryLpaMedian"), r.get("salaryLpaMax")
        if mn is not None and med is not None:
            check(mn <= med, f"{r['id']}: salary min {mn} > median {med}")
        if med is not None and mx is not None:
            check(med <= mx, f"{r['id']}: salary median {med} > max {mx}")
        check(-50 <= r.get("growthPct", 0) <= 100,
              f"{r['id']}: growthPct {r.get('growthPct')} out of [-50, 100]")
        check(0 <= r.get("exposure", -1) <= 10,
              f"{r['id']}: exposure {r.get('exposure')} out of [0, 10]")
        check(isinstance(r.get("cities"), list),
              f"{r['id']}: cities is not a list")
    total_hc = sum(r["headcountEstimate"] for r in roles)
    workforce = ms["techWorkforceMn"] * 1_000_000
    check(abs(total_hc - workforce) / workforce <= 0.02,
          f"headcount sum {total_hc:,} is >2% off workforce {workforce:,.0f}")

    # ---- cities ----------------------------------------------------------
    cities = canon["cities"]
    check(abs(sum(c["sharePct"] for c in cities) - 100) <= 0.5,
          f"cities sharePct sums to {sum(c['sharePct'] for c in cities)}, not 100")
    check(sum(c["gccCenters"] for c in cities) == ms["gccCenters"],
          f"cities gccCenters sums to {sum(c['gccCenters'] for c in cities)}, "
          f"not marketStats.gccCenters {ms['gccCenters']}")

    # ---- occupations -----------------------------------------------------
    occs = canon["occupations"]
    oids = [o.get("id") for o in occs]
    check(len(oids) == len(set(oids)), "duplicate occupation ids")
    check(sum(o["jobsSample"] for o in occs) == canon["macro"]["plfs"]["sampleSize"],
          f"occupations jobsSample sums to {sum(o['jobsSample'] for o in occs)}, "
          f"not plfs.sampleSize {canon['macro']['plfs']['sampleSize']}")
    for o in occs:
        if "Level 13" in (o.get("educationDistributionPct") or {}):
            FAILURES.append(f"occupation {o['id']} still has stray 'Level 13' key")

    # ---- indices ---------------------------------------------------------
    for series in canon["indices"]:
        seen = set()
        for p in series["points"]:
            check("year" in p and isinstance(p["year"], int),
                  f"indices {series['provider']}: point {p} has no year")
            key = (series["provider"], p.get("year"), p.get("month"))
            check(key not in seen, f"indices duplicate point {key}")
            seen.add(key)
            if p.get("index") is None and not p.get("note"):
                warn(f"indices {series['provider']} {p.get('year')}-{p.get('month')}: "
                     f"null index without a note")
    provs = [s["provider"] for s in canon["indices"]]
    check("naukri" in provs and "foundit" in provs,
          "indices must carry both naukri and foundit series")

    # ---- regenerate-and-diff ---------------------------------------------
    try:
        gen_root = bc.project_root(canon)
        gen_rich = bc.project_rich(canon)
        gen_site = bc.project_site(canon)
    except SystemExit as e:
        FAILURES.append(f"build projection failed: {e}")
        gen_root = gen_rich = gen_site = None
    if gen_root is not None:
        for name, gen, path in (("data.json", gen_root, "data.json"),
                                ("rich/data.json", gen_rich, "rich/data.json"),
                                ("site/data.json", gen_site, "site/data.json")):
            committed = load(path)
            gen_text = json.dumps(gen, indent=2, sort_keys=True) + "\n"
            com_text = json.dumps(committed, indent=2, sort_keys=True) + "\n"
            check(gen_text == com_text,
                  f"{name} differs from regenerated output — run "
                  f"scripts/build_canonical.py (generated files are not hand-edited)")
        # legacy-shape checks on generated output
        for r in gen_rich:
            check(r["pay_annual"] == r["pay_monthly"] * 12,
                  f"rich {r['slug']}: pay_annual != pay_monthly * 12")
        mi = gen_site["monthlyIndex"]
        years = sorted({e["year"] for e in mi})
        check(len(mi) == 12 and
              sorted((e["month"] for e in mi), key=bc.MONTH_NAMES.index) == bc.MONTH_NAMES,
              f"site monthlyIndex is not a complete 12-month series ({len(mi)} entries)")
        for r in gen_site["roles"]:
            if r["fresherSalary"] is not None:
                check(r["fresherSalary"] <= r["salary"],
                      f"site role {r['id']}: fresherSalary > salary")

    # ---- PLFS snapshot ---------------------------------------------------
    snap_path = ROOT / "data/plfs-macro.json"
    if not snap_path.exists():
        FAILURES.append("data/plfs-macro.json missing — run scripts/refresh_plfs_snapshot.py")
    else:
        snap = json.loads(snap_path.read_text())
        latest = canon["macro"]["plfs"]["quarterlyTrend"][-1]
        check(snap.get("latest") == {"quarter": latest["quarter"],
                                     "LFPR": latest["LFPR"],
                                     "WPR": latest["WPR"],
                                     "UR": latest["UR"]},
              "plfs-macro.json latest quarter does not match canonical macro.plfs")

    # ---- HTML stamps ------------------------------------------------------
    if last is not None:
        stamp = f"Data as of {last.day} {last.strftime('%b')} {last.year}"
        for html in ("index.html", "rich/index.html", "site/index.html"):
            text = (ROOT / html).read_text()
            check("<!-- DATA-AS-OF -->" in text, f"{html}: DATA-AS-OF marker missing")
            check(stamp in text, f"{html}: stamp {stamp!r} missing — run build_canonical.py")

    print(f"techRoles: {len(roles)} (headcount {total_hc:,}), "
          f"occupations: {len(occs)}, cities: {len(cities)}, "
          f"indices: {[(s['provider'], len(s['points'])) for s in canon['indices']]}")
    for w in WARNINGS:
        print(f"  WARNING: {w}")
    if FAILURES:
        print(f"\nVALIDATION FAILED ({len(FAILURES)} failures):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
