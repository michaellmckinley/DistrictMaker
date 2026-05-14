# Data Sources

Everything we need is free, public, and downloadable. The question is which preprocessing layer to sit on top of.

---

## The Source of Truth: U.S. Census Bureau

### TIGER/Line Shapefiles

Geographic boundary files for every Census geography (states, counties, tracts, block groups, blocks, voting districts, etc.). Updated annually.

- Direct download: <https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html>
- Format: ESRI shapefile (`.shp` + companions) or GeoJSON via API.
- Default CRS: EPSG:4269 (NAD83). Reproject before measuring — see `metrics.md`.

### 2020 Decennial Census — P.L. 94-171 Redistricting Data

The official population counts used for apportionment and redistricting. Released in 2021 for the 2020 cycle.

- Direct download: <https://www.census.gov/programs-surveys/decennial-census/about/rdo/summary-files.html>
- Format: pipe-delimited tables, joinable to TIGER on GEOID.
- Population at every level down to Census block.

### 2020 Apportionment

How many House seats each state gets, in effect through 2030.

- Reference table: <https://www.census.gov/library/visualizations/2021/dec/2020-apportionment-map.html>
- Hardcode the integers in a small lookup table; this only changes once per decade.

---

## Preprocessed Layers (Recommended)

Working directly with raw TIGER + raw P.L. 94-171 is doable but tedious — joining population tables to geometry, handling water-only blocks, building adjacency graphs. Several projects have done this preprocessing and publish ready-to-use data.

### `pygris` (Python wrapper for TIGER)

- PyPI: `pip install pygris`
- Functions like `pygris.blocks(state="ID", year=2020)` return a GeoDataFrame directly.
- Caches downloads locally. This is the cleanest ingestion path for our project.

### Redistricting Data Hub (RDH)

- <https://redistrictingdatahub.org/>
- Free registration required.
- Provides cleaned, joined TIGER + population + (optionally) election results, per state.
- Useful when we want enacted-map shapefiles for comparison.

### MGGG States

- <https://github.com/mggg-states>
- Per-state repositories with cleaned dual graphs already built (JSON adjacency + GeoJSON geometry).
- Designed for `gerrychain` but the GeoJSON works standalone.
- Coverage varies by state — check before assuming a state is available.

---

## What We Actually Need for MVP

For each target state:

| File | Source | Purpose |
|---|---|---|
| State boundary (polygon) | `pygris.states()` | Outer envelope; defines what is "internal" |
| Population units (block groups) | `pygris.block_groups(state=...)` | Geometry for partitioning |
| Population per unit | P.L. 94-171, joined on GEOID | Weights for balance constraint |
| District count | Apportionment lookup table | How many pieces to cut into |
| Enacted map (for comparison) | RDH or Census | Validation baseline |

Block groups are the recommended starting unit — see the unit-of-aggregation discussion below.

---

## Unit of Aggregation: Block vs. Block Group vs. Precinct

This is one of the major open questions (`open-questions.md`). Quick comparison:

| Unit | Count (US-wide, 2020) | Count (typical state) | Pros | Cons |
|---|---|---|---|---|
| Census block | ~8.1M | ~50K–500K per state | Finest possible balance | Slow; many tiny/empty blocks; awkward in dense areas |
| Block group | ~242K | ~2K–15K per state | Good speed/precision tradeoff; standard analytic unit | Coarser balance — may not hit ≤0.5% deviation in small states |
| Precinct (VTD) | ~180K | varies; some states don't publish them cleanly | Aligns with election-administration boundaries | Inconsistent across states; not strictly geographic |
| Census tract | ~85K | ~1K–8K per state | Fast; demographically meaningful | Too coarse for tight population balance |

**Recommendation for MVP.** Block groups. Fast enough for splitline iteration, fine enough to hit ~1% deviation for 2-district states, and avoids the empty-block headaches you hit at the block level.

If we miss the tolerance target for a given state, drop to blocks for that state. Don't pre-optimize.

---

## Caching and Storage

- `data/raw/` — gitignored. Original TIGER downloads. ~50–500 MB per state at block-group level.
- `data/processed/` — gitignored. GeoPandas-friendly cached files (Parquet via `geopandas.to_parquet`). One per state per geographic level.
- The CLI's data loader checks `processed/` first, falls back to `raw/`, falls back to `pygris` download. This makes iteration fast after the first run.

---

## States Worth Knowing About

For MVP target selection, see `open-questions.md`. A few that stand out:

- **Wyoming, Vermont, Alaska, North Dakota, South Dakota, Delaware** — single-district states. Trivial; not useful for testing.
- **Idaho, West Virginia, Hawaii, Maine, Montana, Rhode Island, New Hampshire, Nebraska** — 2 districts each. Smallest meaningful tests. (Hawaii and Maine introduce island geography.)
- **Iowa** — 4 districts. Has a non-partisan-commission-drawn map (Iowa LSA), making it the gold standard for "what would a fair human draw?" comparison.
- **Colorado, Oregon, Connecticut, Oklahoma, Kentucky** — 6–8 districts. Good "medium" test cases without the runtime hit of California or Texas.
- **California, Texas, Florida, New York** — large, complex, save for after MVP works.

---

## Licensing

- Census data: public domain.
- TIGER/Line: public domain.
- RDH: their own data is freely licensed; check per-dataset before redistribution.
- MGGG States: MIT or similar permissive license per repo.

No licensing concerns for personal research use.
