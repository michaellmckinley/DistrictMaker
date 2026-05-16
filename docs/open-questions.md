# Open Questions

Decisions to make before implementation starts. Each has a recommendation, but the recommendation is not the decision — the decision is yours.

---

## Decisions Locked — 2026-05-12

All 10 questions below are resolved. The detail and reasoning behind each option remain in place as historical context; the table below is the authoritative answer.

| # | Question | Decision |
|---|---|---|
| 1 | Population tolerance | **≤0.5%** |
| 2 | Geographic unit | **Census blocks**. Accept runtime hit; only reexamine if a run goes from hours to weeks |
| 3 | Islands / water contiguity | **Allowed.** Don't disadvantage island/coastline states |
| 4 | Contiguity enforcement for non-splitline algorithms | **Author's discretion** — don't burn time fitting algorithms whose objective disagrees with the philosophy |
| 5 | Stopping criteria | **Skip for now.** Revisit when/if SA is added |
| 6 | Validation | **All four checks** (1–4); hard constraints (1) + visual inspection (3) are primary |
| 7 | First MVP states | **Idaho → Iowa** |
| 8 | Determinism | **`--seed` flag, default 42.** Always logged |
| 9 | Pure geometry scope | **NEVER RELAX.** Gerrymandering is a product of human intervention; the only neutral procedure is one with no human-encoded preferences. Real-world adoption would require a Constitutional amendment overriding the VRA |
| 10 | Output artifacts | **All of them:** GeoJSON + Shapefile + PNG + `metrics.json` + `run.log` |
| — | Comparison algorithm scope | **k-means stays, using off-the-shelf best practice only** — no custom tuning, no inventing better balanced-k-means variants |

---

## Open Questions — 2026-05-14 (post n=44 study)

The 44-state convergence study ([`convergence-2026-05-15.md`](convergence-2026-05-15.md)) settled the empirical picture: KL is a reliable local optimizer, but the *seed* determines which basin a run lands in, and the winning seed follows a district-count regime — bare `metis` for 2–3 district states, `metis+kl` for the mid-range, `splitline-realized+kl` reasserts at the high end (CA, TX). That raises a new set of questions about how to search the seed space more thoroughly. These are **not yet decided** — they are the scoped next phase. Recommendations below; the decision is the author's.

### 11. Multi-start (random-restart) METIS

**Question.** METIS's partition depends on a random seed. Should we run it N times per state and keep the shortest realized boundary?

**What's true.** Best-of-N is monotone (never gets worse as N grows) and shows diminishing returns (best-of-N improves roughly logarithmically — the first handful of restarts find the big basins, then you mostly re-discover them). But it converges to METIS's *reachable* floor, not the true global minimum: METIS's multilevel coarsening samples basins from a particular distribution, and any region of partition space its coarsening never carves into is unreachable by any number of restarts. The honest claim from N restarts is "near METIS's floor," not "near optimal."

**Implementation note (from 2026-05-14 read-only research).** Seed plumbing already works — `metis.py` sets `options.seed` and it flows cleanly from `compare.py` through `Metis.run(seed=...)`. Multi-start is a config/loop change, not plumbing work. Caveat: `Metis.__init__` already defaults `ncuts=10`, so METIS runs 10 internal partitionings per call and keeps the best — external restarts give N×10 trials, and some of the cheap diminishing-returns gains are already eaten.

**Recommendation.** Add multi-start with a modest N (10–20) and record every trial's result, so the saturation curve is observable rather than assumed.

### 12. Diversifying the reachable basin set

**Question.** Can we shorten the gap between "near METIS's floor" and "near optimal"?

**What's true.** A METIS random seed only shuffles tie-breaking *within* its coarsening heuristic — it does not change which basins are reachable. That is why best-of-N METIS plateaus. Two levers genuinely broaden the reachable set:

- **Vary METIS's *structural* options, not just the seed** — coarsening type (`RM` random matching is far more stochastic than the default `SHEM`), `ncuts`, `niter`, refinement type. Different options carve genuinely different basins. (Not all of these were confirmed exposed through the current `pymetis` binding during the 2026-05-14 research pass — needs verification before relying on them.)
- **Iterated local search** — take a good partition, perturb it (randomly reassign a chunk of boundary blocks, or swap two districts' territory), re-run KL. This reaches basins adjacent to known-good ones that no fresh seed would land in.

**Recommendation.** Treat this as the higher-value follow-on to plain multi-start. Structural-option diversification first (cheap if the bindings expose it); iterated local search second.

### 13. Parallelization

**Question.** The overnight 44-state batch ran sequentially and left the machine largely idle. Should runs be parallelized?

**What's true.** States are independent; algorithms within a state are independent. The batch is embarrassingly parallel. Running ~5 at once is a straightforward wall-clock win with no shared-state hazard, and multi-start (Q11) multiplies the workload enough to make it worth doing.

**Recommendation.** Parallelize at the state level (and/or the restart level) with a small fixed worker pool. Start with ~5 concurrent and watch resource use.

### 14. Per-state "leading contender" selection

**Question.** Should `outputs/` carry a designated best partition per state, with the full ranking and rationale?

**What's true.** The author wants this eventually: each state names its current leading algorithm, shows the ranked results of every run against that state, and states why that one is the current best. It is explicitly **not** urgent — deferred until the search infrastructure (Q11–Q13) is in place, since the ranking is only meaningful once the seed space is searched thoroughly.

**Status — partially landed 2026-05-15.** `outputs/<STATE>/leader.json` and `leader.md` now carry the leader plus the full six-algorithm ranking with gaps to the leader, max-deviation, and runtime per experiment. `outputs/summary.md` is the cross-state ledger (leader + runner-up + gap). What is still missing from the original ask: a written rationale on *why* the current leader is the current leader for that state. That rationale becomes meaningful once Q11–Q13 land — until then, the ranking is single-trial and the "why" is just "this seed dropped KL into the shortest basin we've sampled."

**Recommendation.** The ranked-ledger half is done; defer the per-state rationale narrative until multi-start (Q11) is producing trial distributions worth narrating.

### 15. Why does `splitline-realized+kl` beat `metis+kl` at the highest district counts?

**Question.** Both CA (52 districts) and TX (38 districts) went to `splitline-realized+kl` in the 2026-05-15 sweep, with `metis+kl` falling to 3rd or 4th in their rankings (CA: metis+kl +1.97%; TX: metis+kl effectively further behind). Every other tough-tier state went to `metis+kl`. What is the splitline structure doing at the high end that metis's basin can't reach?

**What's true.** The earlier read — "more districts → seed matters less, gaps shrink monotonically" — held from ~4 to ~28 districts and then reversed. At 38+ districts the partition is the aggregate of so many cuts that splitline-realized's deterministic recursive halving appears to find a basin metis's multilevel coarsening cannot. This is the opposite of the convergence study's prior framing, which assumed metis was the right ceiling and Q11 (multi-start METIS) would tighten the picture.

If splitline-realized is structurally better above ~30 districts, Q11 effort may not buy what we expected for the largest states — multi-start METIS would search harder within a basin that already lost to splitline-realized there. The right Q11 design is then "multi-start METIS *and* multi-start splitline-realized, compared," not METIS alone.

**Recommendation.** Investigate this before sinking time into multi-start METIS as the primary lever. Cheap first step: look at the CA and TX partition geometries and at the rankings in `outputs/{CA,TX}/leader.md` — does splitline-realized+kl beat metis+kl by a small margin (which would suggest seed variation alone might close it) or a large one (structural)? If it's structural, Q11 expands to cover multi-start splitline-realized too.

**Resolved (TX) — 2026-05-15 (multi-start TX experiment).** The TX gap is fully seed-explained — and reversed. 20 multi-start `metis+kl` trials on TX produced a distribution from 7263.79 km (seed 45) to 9116.54 km (seed 47); 11 of 20 strictly beat `splitline-realized+kl`'s deterministic 8323.94 km, and the best is 12.74% better. The single-trial leader-ledger pick (seed 42, +7.74%) was the 18th of 20 by quality. `splitline-realized+kl` showed zero seed variance (std 0.000%) — its recursive halving is deterministic and KL converges to the same local minimum every time. Multi-start METIS is the right tool at TX scale, not a redundant lever as the original Q15 framing suggested. Full writeup at [`multi-start-tx-2026-05-15.md`](multi-start-tx-2026-05-15.md).

**Resolved (CA) — 2026-05-16 (multi-start CA experiment).** Same direction, smaller magnitude. 19 of 20 `metis+kl` trials on CA produced population-feasible results (seed 46 failed METIS tolerance); 6 of 19 strictly beat `splitline-realized+kl`'s deterministic 7323.70 km, and the best `metis+kl` trial (6893.38 km, seed 43) is 5.88% better. The single-trial leader-ledger pick (seed 42, +1.97%) was the 11th of 19 — middle of the distribution, not tail. `splitline-realized+kl` again showed zero seed variance (std 0.000%). Saturation was sharper than TX: best lands at N=2 (seed 43) and stays put through the remaining 17 trials. Full writeup at [`multi-start-ca-2026-05-15.md`](multi-start-ca-2026-05-15.md).

**Q15 fully resolved.** Both very-large states where `splitline-realized+kl` won the single-trial leader ledger flip to `metis+kl` under multi-start. The "splitline-realized+kl reasserts at 38+ districts" district-count regime from the 2026-05-15 convergence study was an artifact of single-trial sampling at the largest geographies — not structural. METIS reaches shorter-boundary basins than splitline-realized on both 38- and 52-district graphs once seeds are searched. `outputs/summary.md` has been updated to carry both multi-start leaders alongside the other 42 single-trial rows; the resulting mix of single-trial and multi-start sources within one ledger is signaled per row via the `leader_source` field in `summary.json`. The ledger format question (single value vs. distribution per row) is still deferred to Q14.

### 16. Is KL polish always net-positive against the realized-boundary objective?

**Question.** Bare `metis` (no KL post-refinement) beat `metis+kl` on every 2–3 district state in the 2026-05-15 sweep — 10 of 10. KL's balance pressure may be costing more boundary than it saves when there are only a couple of districts to balance.

**What's true.** KL refines a partition by population-feasible boundary-block swaps that strictly reduce a weighted objective (balance + boundary). The balance term has a fixed weight; on a partition with 2 districts and ~half a million blocks each, that weight pulls the refinement toward tightening population deviation that the metis seed already had comfortably below tolerance — and the price is a slightly longer realized boundary. On a partition with 15 districts, the same balance weight is spread thinner per district and the boundary term dominates again.

The fix is probably not "drop KL on small partitions" — it's "look at the balance weight." If the weight were district-count-aware (or simply lower when nD is small and the seed is already inside tolerance), KL would stop trading boundary for unnecessary balance.

**Recommendation.** Inspect the 10 bare-metis wins. For each: how close was metis's seed to the population tolerance, and how much boundary did `metis+kl` add while tightening it further? Cheap to investigate; results should suggest whether to tune the KL balance weight, gate KL on a tolerance check, or leave it alone and accept bare metis as the legitimate leader on tiny partitions.

---

## 1. Population Tolerance Threshold

**Question.** How tight does population balance need to be?

**Legal context.** Congressional districts are held to a stricter standard than state legislative districts. *Karcher v. Daggett* (1983) struck down a New Jersey map with 0.7% deviation. Practitioners typically target ≤0.5% as a safe ceiling; some target ≤1 person per district at the block level (which is symbolic — the underlying Census counts have larger error than that).

**Options:**

| Tolerance | Implication |
|---|---|
| ≤0.1% | Requires block-level granularity; symbolic only |
| ≤0.5% | Standard "courts won't object" target |
| ≤1.0% | Achievable at block-group level for most states |
| ≤5.0% | State-legislative-district standard; way too loose for Congress |

**Recommendation.** **≤1.0% for MVP** (block-group level), tighten to ≤0.5% when we drop to blocks. Don't chase 0.1% — the gain over the Census measurement error is not real.

---

## 2. Geographic Unit of Aggregation

**Question.** Do we partition Census blocks, block groups, voting districts, or something else?

See `data-sources.md` for the comparison table. Tradeoff is runtime vs. precision.

**Recommendation.** **Block groups for MVP.** Drop to blocks only if a target state can't hit the tolerance threshold at block-group level.

---

## 3. Islands and Non-Contiguous Geography

**Question.** What happens when a state has populated islands (Maine, Hawaii, Michigan UP, Washington's San Juans, Florida Keys)?

**Sub-questions:**

- Do we require strict contiguity per district? Most courts do; some states allow "water contiguity" (district crosses water to reach an island).
- If contiguity is required, an island smaller than ideal-district population must attach to the mainland district nearest it. Which one — Euclidean distance? Geodesic? Across the water gap?
- Does the algorithm see the dual graph including water edges, or only the land?

**Recommendation.** **Allow water contiguity, with an explicit edge in the dual graph for each populated island connecting it to the nearest mainland unit by Euclidean distance.** This matches how most states actually treat it (e.g., Maine's enacted map). For MVP, pick states without major island geography (Idaho, Iowa). Defer the question.

---

## 4. Contiguity Enforcement

**Question.** How do we guarantee districts are contiguous?

**Sub-questions:**

- Splitline produces contiguous districts by construction. K-means does not — it can produce a district that's two separate blobs. Do we post-process to fix this, or reject non-contiguous output and retry?
- For SA (later phase), do we restrict the proposal distribution to swaps that preserve contiguity?

**Recommendation.** **For k-means: post-process by reassigning isolated fragments to the nearest district they share a boundary with.** Log how often this happens — if it's frequent, k-means isn't the right algorithm. For SA: restrict proposals to boundary swaps.

---

## 5. Stopping Criteria

**Question.** When does the algorithm stop?

- **Splitline:** Deterministic, runs to completion. No stopping question.
- **K-means:** Stop when assignments don't change between iterations, or after a max iteration count (default 100). Standard.
- **SA / ReCom:** This is the hard one. Options:
  - Fixed iteration count.
  - Fixed wall-clock time.
  - Convergence threshold (no improvement in N iterations).
  - Combination: "stop after 1 hour or N iterations without improvement, whichever comes first."

**Recommendation.** **Not relevant for MVP** (splitline and k-means both terminate deterministically). When SA is added: fixed wall-clock budget (e.g., 30 minutes per state for MVP-scale states) with a convergence-based early-exit.

---

## 6. Validation Approach

**Question.** How do we know the output is good?

**Multi-layered:**

1. **Hard constraints satisfied?** Population deviation under tolerance, districts contiguous, district count correct. Boolean checks.
2. **Compactness metrics.** Polsby-Popper, Reock, convex hull ratio per district. Sanity check, not optimization target.
3. **Visual inspection.** Render the map. Does it look reasonable to a human?
4. **Comparison to enacted map.** Same metrics, side by side. Are our cuts shorter? Our shapes more compact? Both? Neither?
5. **Ensemble percentile (later).** Run gerrychain ReCom for N=10K samples. What percentile is our map's cut length?

**Recommendation.** **All of 1–4 for MVP.** Defer 5 to Phase 5.

---

## 7. Choice of MVP Target States

**Question.** Which states do we run first?

**Options considered:**

- **Idaho (2 districts).** Cleanest small state. Largely rectangular shape, no major islands. Two-district splits are the easiest to verify by eye. **Recommended Phase 2 target.**
- **West Virginia (2 districts).** Similar size, more irregular outline. Reasonable second option.
- **Iowa (4 districts).** Has a gold-standard non-partisan map for comparison (Iowa LSA). 4 districts is enough to see real algorithmic differences. **Recommended Phase 4 MVP completion target.**
- **Maine (2 districts).** Tempting but has island geography. Defer until question 3 is settled.
- **Hawaii (2 districts).** Major island geography. Defer.

**Recommendation.** **Idaho first, Iowa second.** Settles the easy case before introducing the comparison-to-enacted-map workflow.

---

## 8. Determinism and Seeds

**Question.** Should runs be reproducible?

Splitline is deterministic with no seed needed. K-means depends on seed initialization. SA and ReCom are inherently stochastic.

**Recommendation.** **Always accept a `--seed` flag; default to a fixed seed (e.g., 42).** Log it in `run.log`. Same input + same seed → same output, always. This matters for the "is this map fair?" question — if rerunning produces a different map, "fair" becomes a distribution question, not a single-map question.

---

## 9. Scope of "Pure Geometry"

**Question.** The brief says "minimize internal boundaries and balance population." Should we ever relax that?

**Examples of relaxations:**

- Preserve county lines where possible (soft penalty for cuts that cross them).
- Add a VRA Section 2 constraint (don't fragment majority-minority populations below thresholds).
- Add a partisan-fairness term (target a partisan-symmetric efficiency gap).
- Preserve "communities of interest" (school districts, native lands).

These are real critiques of pure-geometry redistricting. Adding any of them transforms the project.

**Recommendation.** **Hold the line for MVP.** The hypothesis is specifically "what falls out of pure geometry?" — answering that question requires actually running pure geometry. After MVP, document the failure modes (which specific cuts a human would object to and why) before deciding whether to relax.

---

## 10. Output Formats and Reproducibility Artifacts

**Question.** What does a run produce beyond the map itself?

**Recommendation.** **Per-run output directory containing:**

- `districts.geojson` — district polygons with district IDs and populations.
- `districts.shp` — same data as shapefile (some tools prefer it).
- `districts.png` — static rendered map.
- `metrics.json` — all metrics (see `metrics.md`).
- `run.log` — input state, district count, algorithm, seed, runtime, library versions, git commit.

Last item matters: "rerun this exact analysis 6 months from now" requires knowing the library versions and the commit. Cheap to log; expensive when missing.

---

## Summary — Decisions You Need to Make Before Coding

| # | Question | My recommendation | Decision (2026-05-12) |
|---|---|---|---|
| 1 | Population tolerance | ≤1.0% MVP, ≤0.5% after | **≤0.5%** |
| 2 | Geographic unit | Block groups | **Census blocks** (precision over runtime) |
| 3 | Islands | Water contiguity; defer until needed | **Water contiguity allowed; don't disadvantage island/coastline states** |
| 4 | Contiguity enforcement | Post-process k-means; constrain SA | **Author's discretion; don't solve other practitioners' problems** |
| 5 | Stopping criteria | N/A for MVP algorithms | **Skip for now** |
| 6 | Validation | Hard constraints + compactness + visual + enacted-map diff | **All four; hard constraints + visual are primary** |
| 7 | MVP states | Idaho, then Iowa | **Confirmed** |
| 8 | Determinism | Always log `--seed`; default 42 | **Confirmed** |
| 9 | Pure geometry scope | Hold the line for MVP | **NEVER RELAX** (see #9 above) |
| 10 | Output formats | GeoJSON + Shapefile + PNG + metrics.json + run.log | **Confirmed (all)** |
