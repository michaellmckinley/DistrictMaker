# DistrictMaker — Research Plan

> Personal research project. **Phase 2 complete** as of 2026-05-12. Production
> algorithm is **splitline against the realized-boundary objective followed by
> Kernighan-Lin refinement** (`districtmaker run --state ID --output ...`).
> Empirically validated on Idaho and Iowa via cross-algorithm convergence
> against METIS and simulated annealing.
>
> This document is the executive overview. Detail lives in `docs/`.

## Hypothesis

Congressional districts can be drawn fairly by removing humans from the process. An algorithm should:

1. **Minimize the total length of internal district boundaries within a state.**
2. **Split the state's population approximately evenly across its allotted districts.**

Everything else — partisan balance, racial composition, communities of interest, county/municipal preservation — is excluded by design. The point of the research is to see what falls out of geometry alone.

**Pure geometry is non-negotiable.** Gerrymandering exists because humans intervene with biases and political objectives. The only neutral procedure is one with no human-encoded preferences at all. Real-world adoption of this approach would require a Constitutional amendment overriding the Voting Rights Act and similar constraints. That is part of the thesis, not a bug. See `docs/open-questions.md` Q9.

## Plan at a Glance

| Question | Decision |
|---|---|
| Language | Python 3.11+ |
| Core libs | GeoPandas, Shapely, NumPy, SciPy, NetworkX, Matplotlib |
| Data source | Census TIGER/Line + 2020 P.L. 94-171 via `pygris` |
| Geographic unit | **Census blocks** (precision over runtime) |
| Population tolerance | **≤0.5%** |
| Production algorithm | **Splitline (realized objective) + KL refinement** (`districtmaker run`) |
| Convergence checks | METIS (`pymetis`) and simulated annealing as independent search methods (`districtmaker compare`) |
| MVP target states | Idaho (2 districts) ✓, Iowa (4 districts) ✓ |
| Validation | All four: hard constraints + compactness + visual + enacted-map diff. **Hard constraints + visual are primary.** |
| Entry point | CLI (`click`); notebooks for exploration |
| Output | GeoJSON + Shapefile + PNG + `metrics.json` + `run.log` per run, written to `outputs/` |

Detail and rationale: see the `docs/` files cross-referenced below.

## The One Conceptual Issue You Should Read Before Anything Else

**"Minimize internal boundary length" is not the same as "maximize per-district compactness."** This is the most important framing decision in the project and it shapes the algorithm choice. The full argument is in `docs/metrics.md` — read it first. Short version:

- Per-district compactness metrics (Polsby-Popper, Reock, Schwartzberg) penalize each district's *full* perimeter, including the part along the state boundary.
- Your stated objective only penalizes the *shared* perimeter between adjacent districts inside the state.
- These two objectives reward different shapes. A district that hugs a long coastline can be terrible by Polsby-Popper but zero-cost under your objective.
- This makes the problem a **minimum-cut graph partitioning problem with population balance**, not a "draw round districts" problem.

Algorithms that directly optimize the cut objective (shortest splitline, simulated annealing on the dual graph) are a better fit than algorithms that optimize per-district compactness (k-means, Voronoi).

## Approach

### Phase 1 — Foundations ✓
Planning artifacts produced.

### Phase 2 — Reference implementation ✓
Shortest splitline against the realized-boundary objective. End-to-end pipeline (ingest → split → score → render) verified on Idaho.

### Phase 2.5 — Convergence study ✓
Added Kernighan-Lin refinement, METIS (industry-standard graph partitioner), and simulated annealing. Cross-method comparison on Idaho and Iowa established that splitline+KL and SA-from-KL converge to identical partitions on both states, with METIS finding a different (worse) local minimum. Production algorithm: splitline+KL.

### Phase 3+ — Open
Scale to larger states (Texas, California). Add provable lower bounds via LP relaxation at coarser granularity. Compare against enacted maps. Interactive visualization. ReCom ensembles via `gerrychain` for distributional comparison.

## MVP Definition of Done

```
$ districtmaker run --state ID --algorithm splitline --output outputs/id-splitline/
```

Produces:
- `outputs/id-splitline/districts.geojson` — district polygons
- `outputs/id-splitline/districts.png` — static map
- `outputs/id-splitline/metrics.json` — population per district, deviation from ideal, Polsby-Popper per district, total internal boundary length
- `outputs/id-splitline/run.log` — parameters, runtime, seed

Same command works for `--state IA --districts 4` and produces the same artifacts. That is MVP done.

## Repo Structure (proposed)

```
DistrictMaker/
├── PLAN.md                          # this file
├── README.md                        # short pitch (already exists)
├── LICENSE                          # already exists
├── pyproject.toml                   # deps, project metadata
├── .gitignore                       # exclude data/, outputs/
│
├── docs/
│   ├── algorithms.md                # survey of approaches vs. our two objectives
│   ├── data-sources.md              # TIGER/Line, RDH, MGGG, acquisition workflow
│   ├── metrics.md                   # compactness vs. boundary-length, scoring
│   └── open-questions.md            # decisions you need to make before coding
│
├── src/districtmaker/
│   ├── __init__.py
│   ├── cli.py                       # click entry point
│   ├── data/
│   │   ├── loader.py                # state geometry + population assembly
│   │   └── census.py                # pygris / TIGER fetch + cache
│   ├── algorithms/
│   │   ├── base.py                  # Algorithm protocol
│   │   ├── splitline.py             # shortest splitline (baseline)
│   │   └── kmeans.py                # weighted k-means / Voronoi
│   ├── metrics/
│   │   ├── compactness.py           # Polsby-Popper, Reock, Schwartzberg
│   │   ├── boundaries.py            # internal boundary length (the objective)
│   │   └── population.py            # deviation, ideal-population checks
│   ├── viz/
│   │   └── maps.py                  # matplotlib + contextily renderer
│   └── output/
│       └── writer.py                # geojson, shapefile, metrics.json, run.log
│
├── notebooks/                       # exploration only — not the entry point
│
├── tests/
│   ├── test_metrics.py
│   ├── test_splitline.py
│   └── test_kmeans.py
│
├── data/                            # gitignored — local cache of TIGER files
│   ├── raw/
│   └── processed/
│
└── outputs/                         # gitignored — generated maps and shapefiles
```

Rationale: `src/` layout (vs. flat package) avoids import-path footguns and matches modern Python practice. `data/` and `outputs/` are gitignored because TIGER files are large and outputs are reproducible. Algorithms, metrics, viz, and I/O are separated so a second algorithm doesn't need to touch the metrics or rendering code.

## Cross-Reference Index

| Topic | File |
|---|---|
| Algorithm survey, scoring against the two objectives | `docs/algorithms.md` |
| Compactness metrics and the boundary-length distinction | `docs/metrics.md` |
| Data sources, acquisition, and the unit-of-aggregation question | `docs/data-sources.md` |
| Decisions still open | `docs/open-questions.md` |
| Most recent cross-algorithm convergence sweep | `docs/convergence-2026-05-15.md` |

## Logging Convention (from 2026-05-15)

Major experimental sweeps are filed as their own dated writeups at `docs/<topic>-YYYY-MM-DD.md` — not by overwriting a rolling "current" file. The previous convergence study (the rolling `docs/convergence.md` overwritten on 2026-05-14) is the last artifact under the old convention; its 2026-05-14 content lives in git history and is the predecessor of `docs/convergence-2026-05-15.md`. Each dated writeup is a snapshot: numbers and methodology reflect the codebase as of that date and are not revised in place. Findings that mature into decisions migrate to `docs/open-questions.md`; questions raised by a sweep get appended there (Q15 and Q16 came out of the 2026-05-15 sweep, for instance).

## Constraints (from the brief)

- Personal research project. Not optimizing for production scale.
- Reasonable, well-maintained dependencies.
- No web app, no API, no database. Local files and scripts only.
