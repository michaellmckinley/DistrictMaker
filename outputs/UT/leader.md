# Utah — current leader: metis

- State: UT (Utah)
- Districts: 4
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis | ok | 594.64 | +0.00% | 0.2120 | 14.8 |
| 2 | metis+kl | ok | 594.64 | +0.00% | 0.2120 | 15.0 |
| 3 | splitline-realized+kl | ok | 985.83 | +65.79% | 0.1668 | 56.1 |
| 4 | annealing-from-kl | ok | 985.83 | +65.79% | 0.1668 | 71.2 |
| 5 | annealing | ok | 1170.00 | +96.76% | 0.0190 | 53.1 |
| 6 | splitline-realized | ok | 1171.25 | +96.97% | 0.0131 | 38.0 |
| — | splitline-chord | FAILED | — | — | — | 2.1 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

