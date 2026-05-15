# Algorithm Survey

How each candidate algorithm performs against DistrictMaker's two stated objectives:

1. **Minimize total internal boundary length within the state.**
2. **Equal population across districts.**

Read `metrics.md` first if you haven't — the boundary-length objective is *not* the same as per-district compactness, and that distinction shapes which algorithms are a good fit.

---

## 1. Shortest Splitline (Warren D. Smith) — realized-boundary variant

**How it works.** Recursively split the state. At each step, sweep candidate straight lines that divide the region's population into the correct ratio (⌈k/2⌉ : ⌊k/2⌋), and pick the one that minimizes the **realized internal boundary length** — the sum of shared-edge lengths between adjacent blocks that end up in different districts. Recurse on each side.

Smith's original formulation minimizes the cut chord (the length of the straight line through the region). We diverge from that and optimize the realized boundary directly, because at Census-block granularity the realized boundary follows block edges and is a much longer, more meaningful quantity than the chord. The chord is the line you'd draw with a ruler; the realized boundary is the actual political district boundary on the map.

The original chord objective remains available via `--objective chord` for comparison or speed.

**Implementation note.** Per-cut cost is computed via the precomputed **block adjacency graph** (see `src/districtmaker/data/adjacency.py`): for each candidate threshold, the cost is `sum(edge_length where on_left[edge_a] != on_left[edge_b])`. This is O(E) per candidate and fully vectorized in numpy, so the realized objective runs at essentially the same speed as the chord proxy. The adjacency graph itself takes ~30s to build for a small state like Idaho and is cached.

**Against objective 1 (minimize internal boundary length).** Excellent local fit — every cut directly minimizes the realized boundary it contributes. Still globally greedy: an early split can't be undone, so the global minimum is not guaranteed.

**Against objective 2 (equal population).** Direct enforcement. Each cut produces an exact population ratio (subject to the granularity of the underlying units — see `data-sources.md`). For ~80k blocks in Idaho the achievable per-cut deviation is well under 0.0005%.

**Empirical (Idaho, 2 districts):**
- Realized objective: 664 km boundary, Polsby-Popper 0.38/0.21
- Chord objective: 1,650 km boundary, Polsby-Popper 0.17/0.06

The realized objective produces a substantially better map by every compactness metric *and* by the user's stated objective.

**Verdict.** Deterministic, transparent, and both objectives are first-class — which made it the natural first experiment. But it is one experiment among several, not a privileged "production" algorithm: the n=44 cross-algorithm study ([`convergence-2026-05-15.md`](convergence-2026-05-15.md)) finds the leader split three ways — `metis+kl` on 25 states, bare `metis` on 10 (the smallest states), and `splitline-realized+kl` on 9 (which includes both of the largest, CA and TX). Splitline's recursive bisection commits to early cuts it cannot undo, and on many mid-range states those cuts land KL in a worse basin than METIS reaches — but at the high end the structure reasserts. Known weakness, by design under the project's hypothesis: cuts ignore everything except geometry and population, so they routinely chop through cities, counties, and natural communities.

**Reference.** Smith, "Gerrymandering and a cure for it: shortest splitline algorithm" (rangevoting.org). Smith uses the chord objective; the realized-boundary variant is our adaptation, motivated by docs/metrics.md's argument that the chord is only a proxy for the user's stated "internal boundary length" objective.

---

## 2. Weighted K-Means / Centroidal Voronoi

**How it works.** Place *k* seed points. Assign each population unit (block, block group) to the nearest seed, weighted by population. Move each seed to the weighted centroid of its assignment. Iterate until stable (Lloyd's algorithm).

**Against objective 1.** Indirect. Voronoi cells minimize the within-cell variance of distance to the centroid, which produces *compact* regions but does not directly minimize the shared-edge perimeter between cells. In practice the cuts are reasonably short because cells are roughly convex, but it is not optimizing the right objective.

**Against objective 2.** Hard to enforce strictly. Standard k-means produces unequal populations. "Capacitated" or "balanced" k-means variants force equal populations but are slower and lose the clean Voronoi geometry. You typically end up post-processing with swap heuristics.

**Verdict.** Kept as a comparison algorithm — a representative of "what compactness-optimizing approaches produce." Implement using **off-the-shelf best practice** (e.g., `scipy.cluster.vq` weighted k-means + a standard balanced/capacitated post-process). Do **not** invest in custom tuning or inventing better balanced-k-means variants — practitioners have done that work and our research question isn't "how good can k-means be?" Will lose to splitline on objective 1 if implemented honestly; that result is part of the point.

---

## 3. ReCom — Recombination Markov Chain (DeFord, Duchin, Solomon)

**How it works.** Start with any valid contiguous, equal-population partition. At each step: pick two adjacent districts, merge them, build a spanning tree of the merged region, cut one edge to produce a new partition with balanced population. Repeat for many steps to sample the space of valid maps.

**Against objective 1.** Not an optimizer — it's a sampler. You can run a long chain and report the lowest-cut map seen, but that is a weak optimization strategy. Better used to characterize the *distribution* of cut lengths achievable.

**Against objective 2.** Equal population is enforced by construction at every step.

**Verdict.** Industry-standard tool (`gerrychain`) for redistricting *analysis*, not for producing a single "best" map. Worth integrating in a later phase as a baseline ensemble — "the algorithm beats N% of valid contiguous maps on internal boundary length." Not the primary algorithm.

**Reference.** GerryChain library (mggg.org/gerrychain). DeFord, Duchin, Solomon (2019), "Recombination: A family of Markov chains for redistricting."

---

## 4. Simulated Annealing (on the dual graph)

**How it works.** Build the adjacency graph of population units. Start with any valid partition. Propose a swap (move a unit from one district to an adjacent district). Accept if it improves the objective; accept worsening moves with probability that decays over time. Iterate.

**Against objective 1.** Direct fit. The objective function is `sum_of_internal_edge_lengths + λ · population_imbalance_penalty`. You can plug in exactly what the brief asks for.

**Against objective 2.** Enforced via penalty term in the objective, or as a hard constraint on which swaps are legal.

**Verdict.** The most flexible option and the most honest fit to the stated objectives — but requires tuning (cooling schedule, penalty weights, swap proposal distribution). Good Phase 5 stretch goal once you have splitline as a baseline to measure against.

---

## 5. Constraint Optimization (ILP / MIP)

**How it works.** Formulate the partition as an integer program: binary variables for "unit *i* assigned to district *j*", linear constraints for population balance and contiguity, objective is the cut length.

**Against objective 1 / 2.** Provably optimal solutions when the solver finishes.

**Verdict.** Beautiful in theory, intractable in practice for census-block-level data. Even at block-group level, big states will not solve. Useful only on heavily aggregated units (counties, in small states). Skip for MVP. If revisited, use as a sanity check on small instances.

**Reference.** Validi, Buchanan, Lykhovyd (2022), "Imposing contiguity constraints in political districting models." Uses commercial solvers (Gurobi).

---

## 6. Voronoi-Based / Power Diagrams

**How it works.** Like k-means but assignment is by *weighted* distance (power diagram). Adjusting weights lets you match target populations exactly (Aurenhammer's algorithm).

**Against objective 1.** Same indirect relationship as k-means.

**Against objective 2.** Can be made exact via weight adjustment.

**Verdict.** A more principled k-means. Slightly more complex to implement. Skip unless k-means turns out to be unsatisfying.

---

## Summary Matrix

| Algorithm | Obj. 1: Internal boundary | Obj. 2: Equal pop | Determinism | Implementation cost | MVP fit |
|---|---|---|---|---|---|
| Shortest splitline | Direct (greedy) | Direct (exact) | Deterministic | Low–Medium | First built |
| Weighted k-means | Indirect | Approximate | Deterministic given seeds | Low | Comparison |
| ReCom | Not optimized | Direct | Stochastic | Library available | Phase 5 |
| Simulated annealing | Direct | Penalty / constraint | Stochastic | Medium | Phase 5 |
| ILP / MIP | Direct | Exact | Deterministic | High; needs solver | Skip |
| Power Voronoi | Indirect | Exact | Deterministic | Medium | Skip |

**Note.** The "MVP fit" column reflects the original (2026-05) planning sequence, when splitline was the first algorithm built and the others were staged behind it. It is preserved as historical context. The implemented algorithms — splitline, METIS, simulated annealing, KL refinement — are now treated as co-equal experiments against the objective; [`convergence-2026-05-15.md`](convergence-2026-05-15.md) reports how they compare across all 44 states. No algorithm is "the production algorithm" — the result for a state is the shortest realized boundary any of them finds.

---

## Things This Survey Deliberately Does Not Address

- **Voting Rights Act compliance.** Pure-geometry algorithms can produce maps that fail VRA Section 2 by fragmenting protected-class voting power. This is a known critique. Out of scope per the brief.
- **Communities of interest, county/municipal boundaries.** Same — algorithmically ignored. The point of the project is to see what geometry alone produces.
- **Partisan fairness metrics** (efficiency gap, mean-median, partisan symmetry). Not part of the objective. ReCom is the right tool if you ever want to evaluate this.

Decision (2026-05-12): pure geometry is **non-negotiable**. The above are not deferred for later relaxation — they are permanent exclusions under the project's thesis. See `open-questions.md` Q9.
