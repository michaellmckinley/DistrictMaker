# Texas — current leader: metis+kl

- State: TX (Texas)
- Districts: 38
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: varies (multi-start landed for `metis+kl` and `splitline-realized+kl` on 2026-05-15)
- Multi-start record: [`multi-start/2026-05-15/`](multi-start/2026-05-15/)
- Multi-start writeup: [`docs/multi-start-tx-2026-05-15.md`](../../docs/multi-start-tx-2026-05-15.md)

## Ranking

| Rank | Experiment | Status | Trials | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) | Notes |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 1 | metis+kl | ok | 20 | 7263.79 | +0.00% | 0.4994 | 213.7 | best of 20: seed 45, trial 03 |
| 2 | splitline-realized+kl | ok | 20 | 8323.94 | +14.60% | 0.4969 | 4164.1 | all 20 trials identical (std 0.000%) |
| 3 | annealing-from-kl | ok | 1 | 8323.94 | +14.60% | 0.4969 | 4274.7 | single-trial |
| 4 | metis | ok | 1 | 8982.36 | +23.66% | 0.4050 | 73.4 | single-trial |
| 5 | splitline-realized | ok | 1 | 9760.26 | +34.37% | 0.2220 | 821.2 | single-trial |
| 6 | annealing | ok | 1 | 9760.26 | +34.37% | 0.2220 | 907.9 | single-trial |
| — | splitline-chord | FAILED | 1 | — | — | — | 26.5 | RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse |

## Note on the leader change

The 2026-05-15 single-trial sweep had `splitline-realized+kl` at the top (8323.94 km) with `metis+kl` in 3rd at +7.74%. The 20-trial multi-start experiment on the same day reversed this: 11 of 20 `metis+kl` trials strictly beat the `splitline-realized+kl` value, and the best `metis+kl` trial (seed 45) lands 12.74% better than the single-trial `splitline-realized+kl` result. The state-root bundle (`districts.*`) is from that best trial.

The cross-state ledger at `outputs/summary.md` has been updated to carry this multi-start leader; the `leader_source` field in `summary.json` flags this row (and CA's) as multi-start rather than single-trial. The mix of single-trial and multi-start rows within one ledger and the broader format question (single value vs. distribution per row) is unresolved; see `docs/open-questions.md` Q14.
