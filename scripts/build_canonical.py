#!/usr/bin/env python3
"""Generate the three legacy-shaped data.json files from data/canonical.json.

    python scripts/build_canonical.py

Canonical is the ONLY hand-edited dataset. These files are build output —
never hand-edit them (scripts/validate_canonical.py fails the build if they
drift from what this script generates). Output is deterministic: sorted
keys, 2-space indent, trailing newline.

Projections (canonical-design §5d):
- data.json (root): occupations[] -> 15-field PLFS list, sorted by jobs desc.
- rich/data.json: techRoles[] -> 15-field list, sorted by jobs desc.
  pay_monthly = round(salaryLpaMedian * 100000 / 12);
  pay_annual  = pay_monthly * 12  (so pay_annual == pay_monthly * 12 exactly).
  nco_code is derived ("TECH-" + zero-padded position), not stored.
- site/data.json: object with meta / marketStats / monthlyIndex (Naukri 2026,
  12 months, explicit nulls) / indices (Naukri + foundit, native) / cities /
  roles / epfo (closed series). Legacy monthlyIndex is the Naukri series
  only; foundit must never be squeezed into it.

Also injects the visible "Data as of" stamp into each HTML file by rewriting
the content of <span id="dataAsOf">...</span> ahead of the <!-- DATA-AS-OF -->
marker (idempotent — re-running the build rewrites the same span).

Fails loudly (non-zero exit) on any mapping miss.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/PsProsen-Dev/India-Job-Market-Visualizer"
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def outlook_desc(pct):
    # Thresholds VERIFIED from the shipped root data (see populate script):
    # Very Fast >= 15, Fast >= 8, Moderate >= 0, Slow Decline < 0.
    if pct >= 15:
        return "Very Fast Growth"
    if pct >= 8:
        return "Fast Growth"
    if pct >= 0:
        return "Moderate Growth"
    return "Slow Decline"


def fail(msg):
    raise SystemExit(f"build_canonical: ERROR: {msg}")


def load_canonical():
    with open(ROOT / "data/canonical.json") as f:
        return json.load(f)


def project_root(canon):
    out = []
    for o in canon["occupations"]:
        for field in ("title", "category", "ncoCode", "jobsSample", "outlookPct",
                      "outlookDesc", "femalePct", "urbanPct",
                      "educationDistributionPct", "exposure", "exposureRationale"):
            if field not in o:
                fail(f"occupation {o.get('id')} missing {field}")
        if o["jobsSample"] is None:
            fail(f"occupation {o['id']} has null jobsSample")
        out.append({
            "title": o["title"],
            "slug": o["id"],
            "category": o["category"],
            "nco_code": o["ncoCode"],
            "jobs": o["jobsSample"],
            "pay_monthly": o["payMonthlyMedian"],
            "pay_annual": o["payAnnualMedian"],
            "outlook": o["outlookPct"],
            "outlook_desc": outlook_desc(o["outlookPct"]),
            "female_pct": o["femalePct"],
            "urban_pct": o["urbanPct"],
            "education": o["educationDistributionPct"],
            "exposure": o["exposure"],
            "exposure_rationale": o["exposureRationale"],
            "url": o["url"],
        })
    out.sort(key=lambda x: x["jobs"], reverse=True)
    return out


def project_rich(canon):
    roles = []
    for r in canon["techRoles"]:
        for field in ("id", "title", "category", "headcountEstimate",
                      "salaryLpaMedian", "growthPct", "exposure", "rationale"):
            if field not in r or r[field] is None:
                fail(f"tech role {r.get('id')} missing {field}")
        if r.get("headcountBasis") != "workforce-share":
            fail(f"tech role {r['id']} has unexpected headcountBasis "
                 f"{r.get('headcountBasis')!r}")
        if r["category"] == "City Hubs":
            fail("tech role with category 'City Hubs' — hubs live in cities[] only")
        pay_monthly = round(r["salaryLpaMedian"] * 100000 / 12)
        roles.append({
            "title": r["title"],
            "slug": r["id"],
            "category": r["category"],
            "nco_code": None,  # filled below, after sorting
            "jobs": r["headcountEstimate"],
            "pay_monthly": pay_monthly,
            "pay_annual": pay_monthly * 12,
            "outlook": r["growthPct"],
            "outlook_desc": outlook_desc(r["growthPct"]),
            "female_pct": int(round(r["femalePct"])),
            "urban_pct": int(round(r["urbanPct"])),
            "education": r["education"]["distributionPct"],
            "exposure": r["exposure"],
            "exposure_rationale": r["rationale"],
            "url": REPO_URL,
        })
    roles.sort(key=lambda x: x["jobs"], reverse=True)
    for i, rec in enumerate(roles, start=1):
        rec["nco_code"] = f"TECH-{i:03d}"
    return roles


def project_site(canon):
    macro = canon["macro"]
    ms = macro["marketStats"]
    if sum(c["sharePct"] for c in canon["cities"]) != 100:
        fail("cities sharePct does not sum to 100")
    if sum(c["gccCenters"] for c in canon["cities"]) != ms["gccCenters"]:
        fail("cities gccCenters does not sum to marketStats.gccCenters")

    naukri = next(s for s in canon["indices"] if s["provider"] == "naukri")
    pts2026 = [p for p in naukri["points"] if p["year"] == 2026]
    if len(pts2026) != 12 or sorted(p["month"] for p in pts2026) != list(range(1, 13)):
        fail("naukri 2026 series is not a complete 12-month series")
    monthly_index = [{
        "year": p["year"],
        "month": MONTH_NAMES[p["month"] - 1],
        "index": p["index"],
        "yoy": p["yoyPct"],
        "aiMlYoy": p["aiMlYoyPct"],
        **({"note": p["note"]} if p.get("note") else {}),
    } for p in sorted(pts2026, key=lambda p: p["month"])]

    roles = []
    for r in canon["techRoles"]:
        roles.append({
            "id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "headcount": r["headcountEstimate"],
            "growth": r["growthPct"],
            "salary": r["salaryLpaMedian"],
            "fresherSalary": r["fresherSalaryLpa"],
            "exposure": r["exposure"],
            "demand": r["demandScore"],
            "remote": r["remotePct"],
            "city": " / ".join(r["cities"]),
            "education": r["education"]["label"],
            "skills": r["skills"],
            "rationale": r["rationale"],
        })

    plfs = macro["plfs"]
    meta = {
        "title": "India Jobs Market Visualizer",
        "subtitle": "Karpathy-style treemap for India's FY2026 tech labour market",
        "year": "FY2026 / 2026",
        "currency": "INR LPA",
        "methodology": ("Static, auditable dataset assembled from NASSCOM, Naukri "
                        "JobSpeak, foundit, PLFS (MoSPI) and salary surveys. Areas are "
                        "workforce-share allocations of the 6.0M tech workforce; colors "
                        "are driven by selectable metrics. AI exposure is heuristic and "
                        "indicates how much AI may reshape work, not whether a job "
                        "disappears. Naukri and foundit indices are shown side by side "
                        "and never blended — they measure different platforms."),
        "lastUpdated": canon["meta"]["lastUpdated"],
        "generatedFrom": "data/canonical.json (generated file — do not hand-edit; "
                         "run python scripts/build_canonical.py)",
        "sources": [f"{s['name']} ({', '.join(s['usedFor'])})"
                    for s in canon["meta"]["sources"]],
        "plfsSnapshot": {
            "vintage": plfs["vintage"],
            "latest": {"quarter": plfs["quarterlyTrend"][-1]["quarter"],
                       "LFPR": plfs["quarterlyTrend"][-1]["LFPR"],
                       "WPR": plfs["quarterlyTrend"][-1]["WPR"],
                       "UR": plfs["quarterlyTrend"][-1]["UR"]},
            "source": plfs["source"],
            "note": ("Live browser fetch is blocked by the API (403 CORS blocked "
                     "for non-MoSPI origins); this baked snapshot is the macro "
                     "source. Refresh with scripts/refresh_plfs_snapshot.py."),
        },
    }
    return {
        "meta": meta,
        "marketStats": ms,
        "monthlyIndex": monthly_index,
        "indices": canon["indices"],
        "cities": [{
            "city": c["city"], "share": c["sharePct"], "gcc": c["gccCenters"],
            "salary": c["avgSalaryLpa"], "growth": c["growthPct"],
            "specialization": c["specialization"],
        } for c in canon["cities"]],
        "roles": roles,
        "epfo": macro["epfo"],
    }


def stamp_html(path, last_updated):
    """Rewrite the visible 'Data as of' stamp in one HTML file (idempotent)."""
    text = Path(path).read_text()
    d = date.fromisoformat(last_updated)
    stamp = f"Data as of {d.day} {d.strftime('%b')} {d.year}"
    pattern = re.compile(r'(<span id="dataAsOf">).*?(<!-- DATA-AS-OF -->)',
                         re.DOTALL)
    new, n = pattern.subn(r'\g<1>' + stamp + r' \g<2>', text)
    if n != 1:
        fail(f"{path}: expected exactly 1 dataAsOf stamp span, found {n}")
    Path(path).write_text(new)
    return stamp


def dump(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def main():
    canon = load_canonical()
    root_data = project_root(canon)
    rich_data = project_rich(canon)
    site_data = project_site(canon)

    dump(ROOT / "data.json", root_data)
    dump(ROOT / "rich/data.json", rich_data)
    dump(ROOT / "site/data.json", site_data)

    stamps = []
    for html in ("index.html", "rich/index.html", "site/index.html"):
        stamps.append((html, stamp_html(ROOT / html, canon["meta"]["lastUpdated"])))

    print(f"Built from data/canonical.json (lastUpdated {canon['meta']['lastUpdated']})")
    print(f"  data.json:       {len(root_data)} occupations, "
          f"sample total {sum(r['jobs'] for r in root_data):,}")
    print(f"  rich/data.json:  {len(rich_data)} roles, "
          f"jobs total {sum(r['jobs'] for r in rich_data):,}")
    print(f"  site/data.json:  {len(site_data['roles'])} roles, "
          f"headcount total {sum(r['headcount'] for r in site_data['roles']):,}; "
          f"monthlyIndex {len(site_data['monthlyIndex'])} entries; "
          f"indices {[len(s['points']) for s in site_data['indices']]} points")
    print(f"  warnings: root pay nulls: "
          f"{sum(1 for r in root_data if r['pay_monthly'] is None)} occupations "
          f"without wage data (as shipped); site roles with null demand: "
          f"{sum(1 for r in site_data['roles'] if r['demand'] is None)} "
          f"(rich-only roles — no demand composite exists for them); "
          f"site roles with null fresherSalary: "
          f"{sum(1 for r in site_data['roles'] if r['fresherSalary'] is None)}")
    for html, stamp in stamps:
        print(f"  stamp {html}: {stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
