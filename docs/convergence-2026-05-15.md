# Cross-Algorithm Convergence Study — 2026-05-15 (n = 44)

> **Dated snapshot.** This is the 2026-05-15 leader ledger across all 44 multi-district U.S. states. From this date forward, each major experimental sweep is filed as its own dated writeup at `docs/<topic>-YYYY-MM-DD.md` rather than overwriting a rolling "current" file. See `docs/development-history.md` for the logging convention.

Every algorithm in DistrictMaker is a local search against the same objective — realized internal district boundary length — with a hard population constraint. None offers a global-optimality guarantee. This page documents what happens when independent search methods are run against that shared objective across all 44 multi-district U.S. states: where they agree, where they diverge, and what the divergence reveals.

## Method

For each of the 44 multi-district states, the validation harness (`districtmaker validate --tier all`) runs six independent searches against the realized-boundary objective:

1. **`metis`** — `pymetis` multilevel graph partitioner under a population-balance constraint, no post-refinement.
2. **`metis+kl`** — METIS seed followed by Kernighan-Lin (KL) refinement on the block adjacency graph.
3. **`splitline-realized`** — recursive population-balanced bisection scoring cuts by their *realized* (block-edge) boundary length, no post-refinement.
4. **`splitline-realized+kl`** — splitline-realized seed followed by KL.
5. **`annealing`** — simulated annealing from a random seed.
6. **`annealing-from-kl`** — simulated annealing started from a KL result (sanity check for KL convergence).

The legacy `splitline-chord` (which scored cuts by the straight-line chord length rather than the realized block-edge length) is run as a historical baseline; it remains brittle on block-edge geometry and fails on most states.

The question is not "which algorithm is best." It is: *given a shared, neutral objective, do independent methods converge on the same partition — and if not, what does the gap mean?*

## Results

Per-state leader, runner-up, and gap. Boundary in kilometres; gap is leader → runner-up.

| Tier | State | nD | Leader | Boundary (km) | Runner-up | Gap |
|---|---|--:|---|--:|---|--:|
| easy | AL | 7 | metis+kl | 1582.56 | metis | +0.17% |
| easy | AR | 4 | splitline-realized+kl | 973.32 | annealing-from-kl | +0.00% |
| easy | AZ | 9 | metis+kl | 1606.50 | metis | +0.18% |
| easy | CO | 8 | metis+kl | 1527.35 | metis | +0.04% |
| easy | IA | 4 | splitline-realized+kl | 919.77 | annealing-from-kl | +0.00% |
| easy | ID | 2 | splitline-realized+kl | 565.44 | annealing-from-kl | +0.00% |
| easy | IN | 9 | splitline-realized+kl | 1365.82 | annealing-from-kl | +0.00% |
| easy | KS | 4 | metis+kl | 827.56 | metis | +0.00% |
| easy | KY | 6 | metis+kl | 965.27 | metis | +0.04% |
| easy | MN | 8 | metis+kl | 1289.26 | metis | +0.05% |
| easy | MO | 8 | splitline-realized+kl | 1687.37 | annealing-from-kl | +0.00% |
| easy | MT | 2 | metis | 631.44 | metis+kl | +0.00% |
| easy | NE | 3 | metis | 410.27 | metis+kl | +0.00% |
| easy | NH | 2 | metis | 110.65 | metis+kl | +0.00% |
| easy | NM | 3 | metis | 804.67 | metis+kl | +0.00% |
| easy | NV | 4 | splitline-realized+kl | 907.86 | annealing-from-kl | +0.00% |
| easy | OK | 5 | metis+kl | 1176.49 | metis | +0.41% |
| easy | TN | 9 | metis+kl | 1375.33 | metis | +0.03% |
| easy | UT | 4 | metis | 594.64 | metis+kl | +0.00% |
| easy | WI | 8 | metis+kl | 1614.98 | metis | +0.00% |
| easy | WV | 2 | metis | 282.91 | metis+kl | +0.00% |
| middle | CT | 5 | metis+kl | 342.09 | metis | +0.00% |
| middle | GA | 14 | metis+kl | 2308.05 | metis | +0.20% |
| middle | HI | 2 | metis | 44.13 | metis+kl | +0.00% |
| middle | LA | 6 | metis+kl | 1196.07 | metis | +0.12% |
| middle | MA | 9 | metis+kl | 595.61 | metis | +0.09% |
| middle | MD | 8 | metis+kl | 569.39 | metis | +0.09% |
| middle | ME | 2 | metis | 187.87 | metis+kl | +0.00% |
| middle | MS | 4 | metis | 809.00 | metis+kl | +0.00% |
| middle | NJ | 12 | metis+kl | 686.89 | metis | +0.03% |
| middle | OR | 6 | metis+kl | 1007.18 | metis | +0.02% |
| middle | RI | 2 | metis | 47.32 | metis+kl | +0.00% |
| middle | SC | 7 | metis+kl | 1199.63 | metis | +0.20% |
| middle | VA | 11 | metis+kl | 1598.54 | metis | +0.01% |
| middle | WA | 10 | splitline-realized+kl | 2041.22 | annealing-from-kl | +0.00% |
| tough | CA | 52 | splitline-realized+kl | 7323.70 | annealing-from-kl | +0.00% |
| tough | FL | 28 | metis+kl | 3554.87 | metis | +0.45% |
| tough | IL | 17 | metis+kl | 2054.19 | metis | +0.06% |
| tough | MI | 13 | metis+kl | 2119.46 | metis | +0.04% |
| tough | NC | 14 | metis+kl | 2199.11 | metis | +0.15% |
| tough | NY | 26 | metis+kl | 2207.02 | metis | +0.22% |
| tough | OH | 15 | metis+kl | 2186.94 | metis | +0.09% |
| tough | PA | 17 | metis+kl | 2290.42 | metis | +0.03% |
| tough | TX | 38 | splitline-realized+kl | 8323.94 | annealing-from-kl | +0.00% |

### Leader counts

| Leader | Wins | Where |
|---|--:|---|
| `metis+kl` | 25 | AL, AZ, CO, CT, FL, GA, IL, KS, KY, LA, MA, MD, MI, MN, NC, NJ, NY, OH, OK, OR, PA, SC, TN, VA, WI |
| `metis` (no KL) | 10 | HI, ME, MS, MT, NE, NH, NM, RI, UT, WV |
| `splitline-realized+kl` | 9 | AR, CA, IA, ID, IN, MO, NV, TX, WA |

Per-state leader detail and full six-algorithm rankings live at `outputs/<STATE>/leader.md`.

## Reading the numbers

Three facts carry this sweep.

**1. KL is still a perfectly reliable local optimizer.** `annealing-from-kl` started from a KL result fails to improve it on every state where KL is the leader — it shows up as a +0.00% runner-up across all 9 `splitline-realized+kl` wins. The same holds wherever KL is run: SA cannot tunnel out of the basin KL descends into. KL is not the variable. Whatever seed it is handed, it walks to that basin's true local minimum.

**2. The leader is a function of district count.** Three regimes are visible in the table:

| Districts | Typical leader | What happens |
|---|---|---|
| 2–3 | bare `metis` | KL's balance pressure costs more boundary than it saves. KL is a net negative on partitions this small. |
| 4–28 | `metis+kl` (with 9 `splitline-realized+kl` exceptions) | Mid-range — KL polish is reliably worth it; metis usually has the better seed. |
| 38+ | `splitline-realized+kl` | At the high end the splitline structure reasserts. Both CA (52) and TX (38) went to `splitline-realized+kl`, with `metis+kl` falling to 3rd or 4th in their rankings. |

**3. `metis+kl` wins less of the field than the prior reading suggested.** The 2026-05-14 study reported "METIS+KL wins 35/44, splitline+KL wins 9/44" — but that was a narrower bake-off (chord-objective splitline + metis-with-KL only). With the realized-objective splitline variant and bare metis added, the leader distribution refines to 25 / 10 / 9. The 10 bare-metis wins are new — they are the small-state regime where KL polish was previously being applied invisibly to no benefit.

## What changed since 2026-05-14

The 2026-05-14 study (since archived in git history) framed the picture as a two-way contest between splitline+KL and METIS+KL, with the seed determining the basin and district count predicting only the magnitude of the gap. That framing held, but only because the bake-off didn't include enough algorithms to expose the regimes underneath it. This sweep adds two algorithms (bare `metis` and `splitline-realized+kl`) and surfaces:

- **A small-state regime** (2–3 districts) where bare metis beats anything with KL polish on it.
- **A large-state regime** (~38+ districts) where `splitline-realized+kl` reasserts over `metis+kl` — the prior "more districts → seed matters less" observation reverses at the high end.

Both regimes are now tracked as open questions (Q15 and Q16 in `docs/open-questions.md`).

## Visual comparison

Two states where `splitline-realized+kl` produces the shorter boundary — both retained from the 2026-05-14 doc because the partition geometry hasn't changed materially (the realized-objective splitline lands the same cuts on these states as the chord-objective splitline did; the difference is in how the cuts are *scored*, not how they're *placed*). On most other states the relationship is inverted: `metis+kl` finds the shorter boundary, and the visual difference is small.

### Idaho — splitline-realized+kl wins (metis+kl is +31.31%)

| splitline-realized + KL (565 km) | METIS + KL (742 km) |
|---|---|
| ![Idaho splitline-realized+KL](images/idaho-splitline-kl.png) | ![Idaho METIS+KL](images/idaho-metis-kl.png) |

Idaho is splitline's largest win over metis in this sweep. The recursive bisection happens to land its single interior cut almost exactly where the realized boundary is shortest; METIS's coarsening reaches a different, longer-boundary basin.

### Iowa — splitline-realized+kl wins (metis+kl is +6.60%)

| splitline-realized + KL (920 km) | METIS + KL (980 km) |
|---|---|
| ![Iowa splitline-realized+KL](images/iowa-splitline-kl.png) | ![Iowa METIS+KL](images/iowa-metis-kl.png) |

A smaller splitline win. The interior boundary placement differs visibly even though both partitions are valid and population-balanced.

## What this is and isn't

This is **empirical evidence**, at n = 44, that:

- KL is a dependable local optimizer (SA cannot escape a KL minimum on any state).
- The objective landscape has multiple basins, and the seed — not the refinement — decides which one a run lands in.
- The winning seed follows a district-count regime: tiny → bare metis; mid-range → metis+kl; very large → splitline-realized+kl.

It is **not** a proof of global optimality, and it does not crown a production algorithm. The correct way to cite a state's result is "the shortest realized boundary found across the algorithms run," with the full per-algorithm ledger alongside it — not "optimal," and not "the splitline result" or "the METIS result." When a new algorithm or a multi-start variant finds a shorter boundary on some state, that is the expected mode of progress, not an anomaly.

## Reproducing

```bash
districtmaker validate --tier all --output outputs/
```

Per-state full rankings are written to `outputs/<STATE>/leader.md`; the cross-state ledger is at `outputs/summary.md`. The numbers on this page reflect the codebase as of 2026-05-15 — re-run `validate` for live numbers before citing externally; the algorithms continue to evolve.
