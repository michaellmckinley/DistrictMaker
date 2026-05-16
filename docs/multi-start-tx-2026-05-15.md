# Multi-start on Texas — 2026-05-15

**Question (Q15 in [`open-questions.md`](open-questions.md)):** Is the +7.74% gap between `metis+kl` and `splitline-realized+kl` on Texas seed-explained, or structural?

**Verdict: Gap closed — and reversed.** With 20 seeds, `metis+kl` not only reaches `splitline-realized+kl`'s basin but surpasses it; 11 of 20 `metis+kl` trials strictly beat `splitline-realized+kl`'s best, and the best `metis+kl` trial (7263.79 km, seed 45) is **12.74% better** than `splitline-realized+kl`'s best (8323.94 km). The single-trial leader ledger had Texas exactly backwards.

## Setup

- State: TX (38 districts).
- Algorithms: `metis+kl`, `splitline-realized+kl`.
- Trials: 20 each; seeds 42–61 (`seed_i = base_seed + i`).
- Compute: 24-core / 192 GB host, `--cpu 75`, no `--max-workers`.
- Run started 2026-05-15 at 19:16:13 UTC; controller exited 2026-05-16 at 03:11:07 UTC.
- Wall clock 7h 55m, of which ~5h were a freeze for interactive CPU during the long splitline-realized+kl tail; effective compute ~3h, matching plan estimate.

## Distributions

| Algorithm | Trials OK | Best (km) | Worst (km) | Mean (km) | Median (km) | Std (km) | Std (%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `metis+kl` | 20 / 20 | 7263.79 | 9116.54 | 8305.25 | 8289.78 | 508.17 | 6.119 |
| `splitline-realized+kl` | 20 / 20 | 8323.94 | 8323.94 | 8323.94 | 8323.94 | 0.00 | 0.000 |

Trial-00-seed-42 for both algorithms reproduced the 2026-05-15 leader-ledger values bit-exactly (`metis+kl` 8967.8563 km → 8967.86; `splitline-realized+kl` 8323.9447 km → 8323.94), confirming the seed plumbing is intact.

### `metis+kl` trials sorted by quality

| Rank | Seed | Trial | Boundary (km) | Δ vs splitline best |
|---:|---:|---:|---:|---:|
| 1 | 45 | 3 | 7263.79 | -12.74% |
| 2 | 55 | 13 | 7616.82 | -8.50% |
| 3 | 44 | 2 | 7823.81 | -6.01% |
| 4 | 46 | 4 | 7882.25 | -5.31% |
| 5 | 51 | 9 | 7896.86 | -5.13% |
| 6 | 56 | 14 | 7916.58 | -4.89% |
| 7 | 54 | 12 | 7966.57 | -4.29% |
| 8 | 50 | 8 | 8144.69 | -2.15% |
| 9 | 52 | 10 | 8153.85 | -2.04% |
| 10 | 61 | 19 | 8281.61 | -0.51% |
| 11 | 43 | 1 | 8297.96 | -0.31% |
| 12 | 57 | 15 | 8350.95 | +0.32% |
| 13 | 60 | 18 | 8454.05 | +1.56% |
| 14 | 48 | 6 | 8563.23 | +2.87% |
| 15 | 59 | 17 | 8647.86 | +3.89% |
| 16 | 53 | 11 | 8846.58 | +6.28% |
| 17 | 49 | 7 | 8891.73 | +6.82% |
| 18 | **42** | **0** | **8967.86** | **+7.74%** |
| 19 | 58 | 16 | 9021.45 | +8.38% |
| 20 | 47 | 5 | 9116.54 | +9.52% |

The seed-42 single-trial result — the value enshrined in the 2026-05-15 leader ledger — is the **18th of 20** sorted by quality. The leader ledger sampled a particularly poor draw and treated it as representative.

## Saturation curve

Best boundary km after the first N trials (in seed order, 42 → 42+N-1).

| Algorithm | N=1 | N=2 | N=5 | N=10 | N=20 |
|---|---:|---:|---:|---:|---:|
| `metis+kl` | 8967.86 | 8297.96 | 7263.79 | 7263.79 | 7263.79 |
| `splitline-realized+kl` | 8323.94 | 8323.94 | 8323.94 | 8323.94 | 8323.94 |

For `metis+kl`, the global best is hit by N=5 (seed 45, trial 3) and the additional 15 trials add nothing. Saturation is sharp: the search either samples seed 45 (or another low-boundary draw) early, or it doesn't, but past N≈5 it doesn't improve.

## Q15 verdict

**The numerical answer.** 12 of 20 `metis+kl` trials landed within 0.5% of `splitline-realized+kl`'s best of 8323.94 km, and 11 strictly beat it. The best `metis+kl` trial is 12.74% better than the best `splitline-realized+kl` trial. By the plan's decision tree, this is unambiguously the "Gap closed by seed variation" outcome — but the magnitude is large enough that "gap reversed" is the more accurate framing.

**What this implies.** METIS's multilevel coarsening can reach much shorter-boundary basins than `splitline-realized`'s recursive halving on a 38-district partition, *provided you sample enough seeds*. The single-trial leader ledger's pick — `splitline-realized+kl` for TX — is an artifact of the seed-42 draw being on the wrong tail of the `metis+kl` distribution. Multi-start METIS is the right tool for the largest states, not just a redundant pass at a basin we'd already found. The Q15 framing that motivated this experiment (METIS losing to splitline-realized on TX) inverts once seed variation is accounted for.

**The `splitline-realized+kl` distribution.** Standard deviation is **0.000%** — every one of the 20 trials produced the bit-identical 8323.94 km result. The splitline-realized partition is deterministic by construction (no seed-dependent choice in the recursive halving), and KL polish on top of it lands at a local minimum that seed cannot perturb away from. This is consistent with the spec's hypothesis, and it confirms for Q16 (is KL polish always net-positive?) that on `splitline-realized` seeds at TX scale, KL is converging deterministically to a stable local minimum — the seed variation in `metis+kl` is coming from the METIS coarsening, not from KL.

## What this experiment did NOT settle

- Whether structural-option diversification (Q12) would yield basins shorter than the 7263.79 km `metis+kl` best. The saturation curve plateaus at N=5, so 20 more `metis+kl` seeds are unlikely to improve it — but a different *structural* search could.
- Whether the same pattern holds on CA (52 districts), the only other tough-tier state where `splitline-realized+kl` won the leader ledger. The CA gap (`metis+kl` +1.97%) is much smaller than TX's was (+7.74%), so CA could close more modestly or also reverse — multi-start CA is the natural next experiment.
- Whether the same pattern holds for medium-district states where `splitline-realized+kl` already won (AR, IA, ID, IN, MO, NV, WA). Those leader margins are all 0.00%, meaning `splitline-realized+kl` and `annealing-from-kl` tied — multi-start may not move them.
- The leader ledger at `outputs/summary.md` is not updated by this experiment. The single-trial ledger remains the operational source of truth until multi-start lands on more states. Once it does, the ledger format itself needs to evolve to carry distributions rather than single draws.

## Saturation observation (Q11)

The spec hypothesized "logarithmic improvement with plateau after a handful." The `metis+kl` best-of-N curve confirms it: the best result lands at N=5 and stays put through N=20. Pending replication on other states, a default trial count of 5–10 looks defensible for routine multi-start, with 20 reserved for high-stakes decisions like resolving an open question.

## Artifacts

- Raw per-trial metrics: `outputs/_multi-start/2026-05-15-TX/distributions.json`
- Per-algorithm bests: `outputs/_multi-start/2026-05-15-TX/TX/<algo>/best.json`
- Aggregator writeup: `outputs/_multi-start/2026-05-15-TX/_summary.md`
- Telemetry trace: `outputs/_multi-start/2026-05-15-TX/_telemetry.csv`
- Controller log: `outputs/_multi-start/2026-05-15-TX/_validate.log`
