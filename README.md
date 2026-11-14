# India Jobs Market Visualizer 🇮🇳

A production-grade, Karpathy-style interactive treemap for India's tech job market — plus a whole-economy view built on PLFS occupations.

Inspired by Andrej Karpathy's [`karpathy/jobs`](https://github.com/karpathy/jobs) and the live US visualizer at <https://karpathy.ai/jobs/>. This version retargets the concept to India using a curated, auditable static dataset covering AI/ML demand, GCC growth, salaries, city concentration, remote readiness, and AI exposure.

## Live Demo

- Whole-economy (PLFS) view: <https://psprosen-dev.github.io/India-Job-Market-Visualizer/>
- Rich Hinglish UI (flagship tech view): <https://psprosen-dev.github.io/India-Job-Market-Visualizer/rich/>
- Tech market dashboard: <https://psprosen-dev.github.io/India-Job-Market-Visualizer/site/>

## What it visualizes

- **Area** = workforce-share allocation of the tech workforce (tech pages) or PLFS sample count (whole-economy page)
- **Color layer** = selectable metric:
  - AI Risk / AI Exposure
  - Growth Outlook
  - Salary
  - Education concentration
  - Female workforce share
  - Urban concentration
- **Hover tooltip** = role, category, salary, fresher salary, growth, AI risk, urban share, female share, and rationale
- **Side ranking** = top roles for the selected metric
- **Guide section** = simple Hinglish explanation for normal users
- **Indices panel** (dashboard page) = Naukri JobSpeak and foundit Insights Tracker side by side — never blended or averaged; the two measure different platforms and routinely diverge

## Production features

- Static GitHub Pages-ready site
- No framework or runtime dependency
- CDN-free and tracking-free
- Responsive layout for desktop and mobile
- Clickable metric buttons with live explanations
- Data isolated in `data.json` files; every page shows a visible "Data as of" stamp
- Single-file frontends: `index.html`, `rich/index.html`, `site/index.html`

## Run locally

```bash
python -m http.server 8000
# open http://localhost:8000/ (whole-economy), /rich/, /site/
```

## Deploy on GitHub Pages

1. Open repository **Settings** → **Pages**
2. Source: **GitHub Actions** or **Deploy from branch**
3. Branch: `main`
4. Folder: `/root` if using branch deploy
5. Save

Your visualizer will be served from the GitHub Pages URL for this repository.

## Repository structure

```text
index.html                  # Whole-economy (PLFS) treemap
data.json                   # PLFS occupations (121) — GENERATED, do not hand-edit
data/
├── canonical.json          # SINGLE SOURCE OF TRUTH — edit this, then build
├── plfs-macro.json          # Baked PLFS snapshot (quarterly LFPR/WPR/UR)
├── india_occupations_stats.json   # PLFS pipeline intermediate
├── india_scores.json              # AI exposure pipeline intermediate
└── occupations.json / occupations.csv
rich/
├── index.html              # Flagship Hinglish tech treemap
└── data.json               # Tech roles (60) — GENERATED, do not hand-edit
site/
├── index.html              # Tech dashboard (KPIs, cities, indices)
└── data.json               # Tech dashboard dataset — GENERATED, do not hand-edit
scripts/
├── build_canonical.py      # Generates the three data.json files from canonical.json
├── validate_canonical.py   # Consistency checks (also runs in CI)
├── refresh_plfs_snapshot.py # Re-fetches the PLFS snapshot (build-time only)
└── build_root_data.py      # Legacy PLFS pipeline step (writes ROOT data.json)
.github/workflows/
├── pages.yml               # GitHub Pages deploy
├── validate-data.yml       # Runs validate_canonical.py on push/PR
└── fix-india-tricolour-flag.yml   # One-off flag styling patch (manual trigger)
README.md
```

## Dataset: one canonical file, three generated files

`data/canonical.json` is the single source of truth. It holds every concept once: macro indicators (PLFS, NASSCOM, Naukri/foundit indices, hiring intent, EPFO closed series), cities, 60 tech roles, and 121 PLFS occupations. Every figure carries a source and an as-of date in `meta.sources` / `meta.notes`.

The three `data.json` files are **generated build output** — never hand-edit them. A GitHub Action (`.github/workflows/validate-data.yml`) fails the PR if they drift from what the build script generates.

### One-command refresh

```bash
# 1. Edit data/canonical.json (numbers + meta.lastUpdated + sources)
# 2. Rebuild the three generated files + refresh the HTML "Data as of" stamps
python scripts/build_canonical.py
# 3. Validate (schema, totals, city sums, regenerate-and-diff, sanity bounds)
python scripts/validate_canonical.py
# 4. Review the diff, then commit
git diff --stat
```

### PLFS snapshot refresh (quarterly)

The PLFS macro layer is a **baked snapshot**, not a live browser fetch: the MoSPI eSankhyiki API returns HTTP 403 `{"message":"CORS blocked"}` for any browser Origin other than MoSPI's own hosts (verified 14 Nov 2026). No page fetches `api.mospi.gov.in` at runtime, and no proxy is used. To refresh the snapshot when a new PLFS bulletin lands:

```bash
python scripts/refresh_plfs_snapshot.py   # verifies every API response before writing
python scripts/build_canonical.py         # pick the new snapshot into site/data.json
python scripts/validate_canonical.py
```

If the API ever returns 200 with the Pages Origin (re-test the one-liner in `research_notes/.../phase2/spike-esankhyiki.md` §3a at each refresh), a live layer can be revisited.

## Dataset methodology

This visualizer uses a curated FY2026 India tech-market dataset assembled from NASSCOM Strategic Review 2026, NASSCOM–Zinnov GCC Landscape FY2026, Naukri JobSpeak monthly releases, foundit Insights Tracker, PLFS (MoSPI), ManpowerGroup / TeamLease hiring-intent surveys, Randstad salary trends, and TeamLease GCC salary findings. Role headcounts are **modelled workforce-share allocations** scaled to the NASSCOM FY26 workforce of 6.0M — no source publishes per-role headcounts, so do not cite a per-role headcount as a published fact (see `meta.notes` in `canonical.json` for the full method).

The AI exposure score follows the spirit of the Karpathy rubric: digital, computer-mediated work scores higher because current AI systems act most directly on text, code, analysis, design and communication. A high exposure score means **AI will reshape the work**, not that the role will disappear.

### The two indices (dashboard page)

Naukri JobSpeak and foundit Insights Tracker are shown side by side with their own source labels, **never blended or averaged**. Naukri counts new job listings + recruiter searches on Naukri.com; foundit counts online job postings on its platform. Different platform mix, different definitions — they routinely diverge (Jul 2026: Naukri +5% vs foundit −12%; Sep 2026: +2% vs −11%). The Oct-2026 Naukri YoY (+14%) is flattered by the Oct-2025 Diwali base — the index actually fell month-on-month from 3,053 in Sep to 2,836 in Oct.

### EPFO (closed series)

EPFO payroll data is included only as an **annotated closed historical series (Apr 2018–Sep 2025)**, labelled "Series discontinued after Sep 2025 — no EPFO payroll data published since." It is never presented as current data.

## India context represented

- FY2026 tech industry revenue: about **$315B** (NASSCOM Strategic Review 2026, estimate)
- FY2026 tech workforce: about **6.0M**
- FY2026 net new hires: about **135K**
- GCC centers: **2,117** (NASSCOM–Zinnov FY2026), workforce about **2.36M**
- AI/ML hiring: **+20–37% YoY** across 2026 months (Naukri); **+45%** for FY26 as a whole
- PLFS Jul–Sep 2026: LFPR **55.5%**, WPR **52.7%**, UR **5.1%**
- Major hiring hubs: Bengaluru, Hyderabad, Pune, Chennai, Delhi NCR, Mumbai, and Tier-2 expansion cities

## Caveats

This is not an official economic forecast. It is a visual exploration tool, similar in spirit to the original Karpathy project. The numbers are approximate and intended for comparative visualization, not payroll planning, investment decisions, or policy conclusions. Per-role headcounts are modelled allocations (see above); PLFS occupation counts are sample counts (123,888), not population employment.

## Contributors

- **Jarvis (RTX⚡)** — project contributor, India-market adaptation, UI/UX enhancement, Hinglish explanation layer, and production-grade visualizer support

> GitHub's automatic contributor graph is generated from commit authors. This section is the project's visible contributor credit.

## Credits

- Original concept: [Andrej Karpathy / jobs](https://github.com/karpathy/jobs)
- India market research: NASSCOM, Naukri JobSpeak, foundit, PLFS (MoSPI), GCC reports, salary guides, and AI workforce disruption context
- Project contributor: **Jarvis (RTX⚡)**

## License

MIT (claimed in this README; no LICENSE file is shipped yet — adding one needs the copyright holder/year confirmed by the repo owner).
