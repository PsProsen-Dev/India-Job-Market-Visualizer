"""
Build the ROOT data.json (whole-economy PLFS occupations) by merging India
occupation stats with AI exposure scores.

Reads data/india_occupations_stats.json (for stats) and data/india_scores.json
(for AI exposure). Writes data.json at the REPO ROOT (the 121-record PLFS list).

This script used to be named build_site_data.py and wrote to site/data.json —
that was a live overwrite trap: site/data.json is the /site/ page's object-shaped
dataset, and writing the PLFS list over it would destroy it. Do NOT point this
script at site/data.json. The canonical build (scripts/build_canonical.py) now
generates all three data.json files from data/canonical.json; this script is
kept only as the documented PLFS-pipeline step it originally was.

Usage:
    python scripts/build_root_data.py
"""

import json
import os


def main():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(base_dir, "data")

    # Load AI exposure scores
    scores_file = os.path.join(data_dir, "india_scores.json")
    if os.path.exists(scores_file):
        with open(scores_file) as f:
            scores_list = json.load(f)
        scores = {s["nco_code"]: s for s in scores_list}
    else:
        print("Warning: india_scores.json not found. AI exposure will be empty.")
        scores = {}

    # Load occupation stats
    stats_file = os.path.join(data_dir, "india_occupations_stats.json")
    with open(stats_file) as f:
        occupations = json.load(f)

    # Merge data for the visualizer
    data = []
    for occ in occupations:
        nco_code = occ["nco_code"]
        score = scores.get(nco_code, {})

        # Create slug from title
        slug = (
            occ["title"]
            .lower()
            .replace(" ", "-")
            .replace("(", "")
            .replace(")", "")
            .replace("/", "-")
        )

        item = {
            "title": occ["title"],
            "slug": slug,
            "category": occ["category"],
            "nco_code": nco_code,
            "jobs": occ.get("total_employment"),
            "pay_monthly": occ.get("median_monthly_wage"),
            "pay_annual": occ.get("median_monthly_wage", 0) * 12
            if occ.get("median_monthly_wage")
            else None,
            "outlook": occ.get("outlook_pct"),
            "outlook_desc": occ.get("outlook_desc"),
            "female_pct": occ.get("female_percentage"),
            "urban_pct": round(
                100
                * occ.get("urban_count", 0)
                / max(occ.get("total_employment", 1), 1),
                1,
            ),
            "education": occ.get("education_distribution", {}),
            "exposure": score.get("exposure"),
            "exposure_rationale": score.get("rationale"),
            "url": "https://www.ncs.gov.in/",  # Placeholder
        }
        data.append(item)

    # Sort by employment count (largest first)
    data.sort(key=lambda x: x.get("jobs", 0), reverse=True)

    # GUARD (H-1): never write the PLFS list over the /site/ object dataset.
    # The root target must be a JSON list (or absent); the site file is a JSON
    # object with marketStats/roles keys. Refuse if the target parses as the
    # site object shape, and refuse if the payload is not a list.
    output_file = os.path.join(base_dir, "data.json")
    if os.path.exists(output_file):
        with open(output_file) as f:
            existing = json.load(f)
        if isinstance(existing, dict) and ("marketStats" in existing or "roles" in existing):
            raise SystemExit(
                "REFUSING TO WRITE: target data.json parses as the /site/ object "
                "dataset (has marketStats/roles). This script writes the root PLFS "
                "list only. Aborting so site/data.json is not destroyed."
            )
    if not isinstance(data, list):
        raise SystemExit("REFUSING TO WRITE: payload is not a list of occupations.")
    with open(output_file, "w") as f:
        json.dump(data, f)

    print(f"Wrote {len(data)} occupations to {output_file}")
    total_jobs = sum(d.get("jobs", 0) for d in data if d.get("jobs"))
    print(f"Total jobs represented: {total_jobs:,}")

    # Category summary
    print("\nBy Category:")
    categories = {}
    for d in data:
        cat = d.get("category", "Unknown")
        if cat not in categories:
            categories[cat] = {"count": 0, "jobs": 0}
        categories[cat]["count"] += 1
        categories[cat]["jobs"] += d.get("jobs", 0)

    for cat in sorted(
        categories.keys(), key=lambda x: categories[x]["jobs"], reverse=True
    ):
        print(
            f"  {cat}: {categories[cat]['count']} occupations, {categories[cat]['jobs']:,} jobs"
        )

    # Exposure distribution
    if scores:
        exposures = [d.get("exposure") for d in data if d.get("exposure") is not None]
        if exposures:
            avg_exp = sum(exposures) / len(exposures)
            print(f"\nAverage AI Exposure: {avg_exp:.1f}")
            high_exp = len([e for e in exposures if e >= 7])
            print(f"High exposure (7+): {high_exp} occupations")


if __name__ == "__main__":
    main()
