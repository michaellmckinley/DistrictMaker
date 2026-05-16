# Multi-start on California — 2026-05-15

**Question (Q15 in [`open-questions.md`](open-questions.md)):** Is the +1.97% gap between `metis+kl` and `splitline-realized+kl` on California seed-explained, or structural?

**Verdict: Gap closed — and reversed.** With 20 seeds, `metis+kl` not only reaches `splitline-realized+kl`'s basin but surpasses it; 6 of 19 successful `metis+kl` trials strictly beat `splitline-realized+kl`'s best, and the best `metis+kl` trial (6893.38 km, seed 43) is **5.88% better** than `splitline-realized+kl`'s best (7323.70 km). The single-trial leader ledger had California exactly backwards, just like Texas did — only with a narrower margin.

## Setup

- State: CA (52 districts).
- Algorithms: `metis+kl`, `splitline-realized+kl`.
- Trials: 20 each; seeds 42–61 (`seed_i = base_seed + i`).
- Compute: 24-core / 192 GB host, `--cpu 75`, no `--max-workers`.
- Run started 2026-05-16 at 04:05:26 UTC; controller exited 2026-05-16 at 06:13 UTC.
- Wall clock ~2h 8m, continuous — no freezes used.

## Distributions

| Algorithm | Trials OK / N | Best (km) | Worst (km) | Mean (km) | Median (km) | Std (km) | Std (%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `metis+kl` | 19 / 20 | 6893.38 | 7946.90 | 7441.84 | 7395.80 | 287.72 | 3.866 |
| `splitline-realized+kl` | 20 / 20 | 7323.70 | 7323.70 | 7323.70 | 7323.70 | 0.00 | 0.000 |

Trial-00-seed-42 for `metis+kl` reproduced the 2026-05-15 leader-ledger value bit-exactly (7467.96 km), confirming the seed plumbing is intact. The `splitline-realized+kl` trials are bit-identical across all 20 seeds (std 0.000%) — same finding as TX, consistent with the splitline-realized partition being deterministic and KL converging to a single local minimum.

One `metis+kl` trial failed: trial-04-seed-46 came back `status=failed` with `RuntimeError: METIS could not produce a partition within tolerance 0.0050; best achieved deviation was 0.0112`. METIS's internal `ncuts=10` did not find a population-feasible partition for that seed on the 52-district CA graph. The 19 surviving trials are population-feasible. Distributions and rankings below exclude the failed trial.

### `metis+kl` trials sorted by quality

| Rank | Seed | Trial | Boundary (km) | Δ vs splitline best |
|---:|---:|---:|---:|---:|
| 1 | 43 | 1 | 6893.38 | -5.88% |
| 2 | 57 | 15 | 7105.55 | -2.98% |
| 3 | 54 | 12 | 7113.38 | -2.87% |
| 4 | 53 | 11 | 7128.72 | -2.66% |
| 5 | 59 | 17 | 7284.90 | -0.53% |
| 6 | 55 | 13 | 7318.13 | -0.08% |
| 7 | 51 | 9 | 7349.35 | +0.35% |
| 8 | 44 | 2 | 7353.03 | +0.40% |
| 9 | 56 | 14 | 7388.42 | +0.88% |
| 10 | 45 | 3 | 7395.80 | +0.98% |
| 11 | **42** | **0** | **7467.96** | **+1.97%** |
| 12 | 50 | 8 | 7480.85 | +2.15% |
| 13 | 48 | 6 | 7500.49 | +2.41% |
| 14 | 60 | 18 | 7516.85 | +2.64% |
| 15 | 47 | 5 | 7576.08 | +3.45% |
| 16 | 58 | 16 | 7812.65 | +6.68% |
| 17 | 49 | 7 | 7860.60 | +7.33% |
| 18 | 61 | 19 | 7901.87 | +7.89% |
| 19 | 52 | 10 | 7946.90 | +8.51% |
| — | 46 | 4 | FAILED | (METIS could not satisfy population tolerance) |

The seed-42 single-trial result — the value enshrined in the 2026-05-15 leader ledger — sits at **rank 11 of 19**, near the median of the distribution. Unlike TX (where seed 42 was the 18th of 20), the CA leader-ledger draw was middle-of-the-pack rather than tail; the +1.97% headline gap was a representative seed-42 read against a deterministic splitline value, not a particularly unlucky one. The flip is real because the upper half of the metis+kl seed distribution genuinely reaches a shorter-boundary basin, not because seed 42 was an outlier.

## Saturation curve

Best boundary km after the first N trials (in seed order, 42 → 42+N-1; failed seed 46 excluded from cumulative).

| Algorithm | N=1 | N=2 | N=5 | N=10 | N=19 |
|---|---:|---:|---:|---:|---:|
| `metis+kl` | 7467.96 | 6893.38 | 6893.38 | 6893.38 | 6893.38 |
| `splitline-realized+kl` | 7323.70 | 7323.70 | 7323.70 | 7323.70 | 7323.70 |

For `metis+kl`, the global best lands at N=2 (seed 43) and stays put through the remaining 17 trials. Saturation is even sharper than TX (which peaked at N=5). On CA the second seed sampled was enough to reach the best basin the search found across 19 successful trials.

## Q15 verdict

**The numerical answer.** 6 of 19 `metis+kl` trials strictly beat `splitline-realized+kl`'s best of 7323.70 km, and 3 of those 19 landed within 0.5% of it. The best `metis+kl` trial is 5.88% better than the best `splitline-realized+kl` trial. By the plan's decision tree this is again the "Gap closed by seed variation" outcome, with the magnitude large enough that "gap reversed" is the more accurate framing.

**What this implies (with TX context).** Both very-large states (CA at 52 districts and TX at 38 districts) where `splitline-realized+kl` won the single-trial leader ledger flip to `metis+kl` once 20 seeds are searched. The earlier reading — "`splitline-realized+kl` reasserts at 38+ districts" — was an artifact of single-trial sampling at the largest geographies; METIS's multilevel coarsening reaches shorter-boundary basins than splitline-realized's deterministic recursive halving on both states, provided you sample enough seeds. Q15 is now fully resolved: the high-district-count splitline-realized reassertion was not structural.

The CA magnitude is smaller than TX (5.88% vs 12.74%) and the CA leader-ledger single-trial pick was less unlucky (rank 11 of 19 vs rank 18 of 20), but the *direction* and the *cause* are the same. The pattern looks robust across both very-large-state geographies, not a TX-specific quirk.

**The `splitline-realized+kl` distribution.** Standard deviation is **0.000%** — every one of the 20 trials produced the bit-identical 7323.70 km result, matching TX's finding. The splitline-realized partition is deterministic by construction; KL polish on top of it lands at a local minimum that seed cannot perturb away from. This is another Q16 data point: on `splitline-realized` seeds at very-large-state scale, KL converges deterministically.

## What this experiment did NOT settle

- Whether structural-option diversification (Q12) would yield basins shorter than the 6893.38 km `metis+kl` best. The saturation curve plateaus at N=2, so 20 more `metis+kl` seeds are unlikely to improve it — but a different *structural* search (varying METIS coarsening type, iterated local search) could.
- Whether the pattern holds for medium-district states where `splitline-realized+kl` already won the single-trial leader ledger (AR, IA, ID, IN, MO, NV, WA). Those leader margins are all 0.00% (tied with `annealing-from-kl`), meaning the splitline value already matched its theoretical companion — multi-start may not move them.
- Why CA's best metis+kl seed is 43 while TX's is 45. The "lucky seed" appears to be state-specific, which makes sense given the partition basins depend on the input graph. This argues against expecting any particular seed to be reliably good across states.
- The failed seed-46 trial. It's the first multi-start trial across two states (TX and CA, 40 trials each algorithm) to come back infeasible. METIS+KL's tolerance-failure mode at very-large states with tight (`--tolerance 0.005`) constraints exists; one failure out of 20 is not alarming but worth knowing.
- `outputs/summary.md` was updated to reflect both the CA and TX multi-start leaders alongside the other 42 single-trial leaders. The cross-state ledger now mixes single-trial and multi-start rows in the same table; the ledger format question (single value vs. distribution per row) is still open as Q14. The mixing is signaled via the per-state `leader_source` field in `summary.json` rather than visible structure in `summary.md`.

## Saturation observation (Q11)

The plan's hypothesis of "logarithmic improvement with plateau after a handful" continues to hold. TX plateaued at N=5; CA plateaued at N=2. Across the two experiments a default trial count of 5–10 looks defensible for routine multi-start; 20 is overkill for the saturation question but useful as a distribution sample when resolving an open question.

## Artifacts

- Raw per-trial metrics: `outputs/CA/multi-start/2026-05-15/distributions.json`
- Aggregator summary: `outputs/CA/multi-start/2026-05-15/_summary.md`
- Per-trial outputs: `outputs/CA/multi-start/2026-05-15/<algo>/trial-NN-seed-NN/`
- Controller log: `outputs/CA/multi-start/2026-05-15/_validate.log`
