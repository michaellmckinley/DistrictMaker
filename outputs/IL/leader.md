# Illinois — current leader: metis+kl

- State: IL (Illinois)
- Districts: 17
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 2054.19 | +0.00% | 0.4977 | 33.4 |
| 2 | metis | ok | 2055.34 | +0.06% | 0.4035 | 25.7 |
| 3 | splitline-realized+kl | ok | 2112.96 | +2.86% | 0.2209 | 856.8 |
| 4 | annealing-from-kl | ok | 2112.96 | +2.86% | 0.2209 | 869.5 |
| 5 | annealing | ok | 2385.88 | +16.15% | 0.0402 | 350.4 |
| 6 | splitline-realized | ok | 2385.90 | +16.15% | 0.0402 | 329.4 |
| — | splitline-chord | FAILED | — | — | — | 7.9 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

