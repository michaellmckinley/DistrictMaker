# Metrics

Two distinct things to measure:

1. **The objective** — what the algorithm optimizes (internal boundary length + population balance).
2. **The validation metrics** — how we judge the output and compare to other maps (compactness scores, deviation, visual diff).

These are not the same and conflating them is the most common framing error in this space.

---

## The Objective We Are Actually Optimizing

### Internal boundary length

For a partition of the state into districts $D_1, \ldots, D_k$, the **internal boundary length** is:

$$L_{\text{internal}} = \sum_{i < j} \text{length}(\partial D_i \cap \partial D_j)$$

The sum of the lengths of the edges shared between *adjacent districts*. The state's external boundary (coastline, state borders) is **not counted**.

This is the natural objective for the brief because it is exactly what gets "drawn" by humans. The state's perimeter is fixed; only the internal cuts are choices.

### Population balance

Ideal population per district: $P_{\text{ideal}} = P_{\text{state}} / k$.

Population deviation per district: $\delta_i = (P_i - P_{\text{ideal}}) / P_{\text{ideal}}$.

Two summary statistics worth reporting:

- **Max absolute deviation:** $\max_i |\delta_i|$ — what courts care about.
- **Range:** $\max_i \delta_i - \min_i \delta_i$ — sometimes used in case law (Karcher v. Daggett).

See `open-questions.md` for the tolerance threshold decision.

### Combined objective (for SA, etc.)

$$\text{cost} = L_{\text{internal}} + \lambda \cdot \max_i |\delta_i|$$

with $\lambda$ large enough to make population imbalance dominate. For splitline, balance is enforced exactly per cut and there is no $\lambda$.

---

## Why "Internal Boundary" Is Not the Same as "Compactness"

Standard compactness metrics penalize a district's *full* perimeter, including the part along the state boundary. Our objective only penalizes shared internal edges. The two reward different shapes.

**Concrete example.** Imagine a coastal state with a long, jagged shoreline. A district hugging that coast has:

- A very long total perimeter → **bad Polsby-Popper**.
- Zero contribution to internal boundary length along the coast portion → **fine under our objective**.

If you optimize Polsby-Popper, you will push districts away from the coast to round them off, lengthening internal cuts. That's the wrong direction for our objective.

**Implication.** We should not use Polsby-Popper as the optimization target — only as a validation/comparison metric. The optimization target should be the cut length itself.

**Equivalent framing.** This is graph-cut partitioning. Build the dual graph (one node per population unit, edges between adjacent units weighted by shared edge length). Find a partition into *k* connected subgraphs of roughly equal weight that minimizes the cut. This is NP-hard in general but admits good heuristics — splitline being one of them.

---

## Validation Metrics

We report all of these per district and as state-level aggregates. None of them is the optimization objective, but each captures something useful for comparison to enacted maps and to other algorithms' output.

### Polsby-Popper

$$PP(D) = \frac{4\pi \cdot \text{Area}(D)}{\text{Perimeter}(D)^2}$$

Range: 0 to 1. A circle scores 1. Penalizes long, thin, or irregular shapes. Most widely used compactness metric in academic and legal contexts.

### Reock

$$R(D) = \frac{\text{Area}(D)}{\text{Area}(\text{minimum bounding circle of } D)}$$

Range: 0 to 1. A circle scores 1. Penalizes elongated districts. Less sensitive to small perimeter wiggles than Polsby-Popper; more sensitive to overall shape.

### Schwartzberg

$$S(D) = \frac{\text{Perimeter}(D)}{\text{Perimeter of circle with same area as } D}$$

Range: 1 to ∞ (lower is better). Mathematically related to Polsby-Popper ($S = 1/\sqrt{PP}$). Reported for parity with academic literature; redundant if Polsby-Popper is shown.

### Convex Hull Ratio

$$CH(D) = \frac{\text{Area}(D)}{\text{Area}(\text{convex hull of } D)}$$

Range: 0 to 1. A convex district scores 1. Sensitive to indentations and concavities; insensitive to overall elongation. Useful complement to Reock.

### Population deviation

Reported per district as a percentage; reported state-wide as max absolute deviation.

### Total internal boundary length

The objective itself. Reported in kilometers (or whatever the projection's units are). The headline number for cross-algorithm comparison.

---

## Comparing Algorithms and Maps

For each run, emit `metrics.json`:

```json
{
  "state": "ID",
  "districts": 2,
  "algorithm": "splitline",
  "total_internal_boundary_km": 412.3,
  "population": {
    "ideal": 920000,
    "max_abs_deviation_pct": 0.31,
    "per_district": [918500, 921500]
  },
  "compactness": {
    "polsby_popper": [0.43, 0.51],
    "reock": [0.55, 0.62],
    "convex_hull_ratio": [0.79, 0.84]
  },
  "runtime_seconds": 12.4,
  "seed": 42
}
```

Cross-algorithm comparison plots itself: same state, same district count, different `algorithm` field, line up the rows.

Cross-map comparison (algorithm output vs. enacted map): same JSON shape, different `algorithm` value (`"enacted_2022"`, `"iowa_commission_2021"`, etc.).

---

## Projection and Units

CRS choice matters for area and perimeter calculations. The Census ships TIGER/Line in EPSG:4269 (NAD83 lat/lon), which is **not suitable** for measuring length or area. Reproject to:

- **EPSG:5070** (CONUS Albers Equal Area) for any state in the lower 48.
- **EPSG:3338** (Alaska Albers) for Alaska.
- **EPSG:3759** (Hawaii UTM) for Hawaii.

All metrics computed in the projected CRS, in meters / square meters, then reported in km / km².

---

## Validation Workflow for MVP

For each MVP state run:

1. Run the algorithm. Emit `districts.geojson` + `metrics.json`.
2. Render `districts.png` (matplotlib, basemap optional).
3. Compare side-by-side with the **enacted map** (downloadable from Census or Redistricting Data Hub) in the same projection. Eyeball + metrics diff.
4. For Iowa specifically: compare against the 2021 Iowa Legislative Services Agency map, which is the closest thing to a "fair human" baseline.
5. If `gerrychain` is integrated later: report the percentile rank of the algorithm's cut length within an ensemble of N=10,000 ReCom samples.
