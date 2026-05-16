# California — current leader: metis+kl

- State: CA (California)
- Districts: 52
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: varies (multi-start landed for `metis+kl` and `splitline-realized+kl` on 2026-05-15)
- Multi-start record: [`multi-start/2026-05-15/`](multi-start/2026-05-15/)
- Multi-start writeup: [`docs/multi-start-ca-2026-05-15.md`](../../docs/multi-start-ca-2026-05-15.md)

## Ranking

| Rank | Experiment | Status | Trials | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) | Notes |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 1 | metis+kl | ok | 20 | 6893.38 | +0.00% | 0.4996 | 172.3 | best of 20 (19 OK, 1 failed tolerance): seed 43, trial 01 |
| 2 | splitline-realized+kl | ok | 20 | 7323.70 | +6.24% | 0.4984 | 4145.6 | all 20 trials identical (std 0.000%) |
| 3 | annealing-from-kl | ok | 1 | 7323.70 | +6.24% | 0.4984 | 2966.8 | single-trial |
| 4 | metis | ok | 1 | 7472.85 | +8.41% | 0.4048 | 62.3 | single-trial |
| 5 | annealing | ok | 1 | 8520.55 | +23.60% | 0.1674 | 711.4 | single-trial |
| 6 | splitline-realized | ok | 1 | 8520.76 | +23.61% | 0.1674 | 646.1 | single-trial |
| — | splitline-chord | FAILED | 1 | — | — | — | 16.1 | RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse |

## Note on the leader change

The 2026-05-15 single-trial sweep had `splitline-realized+kl` at the top (7323.70 km) with `metis+kl` in 3rd at +1.97%. The 20-trial multi-start experiment on 2026-05-16 reversed this: 6 of 19 successful `metis+kl` trials strictly beat the `splitline-realized+kl` value, and the best `metis+kl` trial (seed 43) lands 5.88% better than the deterministic `splitline-realized+kl` result. The state-root bundle (`districts.*`) is from that best trial.

This is the same flip seen on TX, only with a smaller magnitude (5.88% on CA vs 12.74% on TX). Both very-large states where the single-trial leader ledger put `splitline-realized+kl` ahead have now reversed under multi-start METIS.

Trial-04-seed-46 came back `status=failed` with `RuntimeError: METIS could not produce a partition within tolerance 0.0050; best achieved deviation was 0.0112`. 19 of 20 `metis+kl` trials are population-feasible; the failure does not change the leader.

The cross-state ledger at `outputs/summary.md` has been updated to carry this multi-start leader; the `leader_source` field in `summary.json` flags this row (and TX's) as multi-start rather than single-trial. The mix of single-trial and multi-start rows within one ledger and the broader format question (single value vs. distribution per row) is unresolved; see `docs/open-questions.md` Q14.
