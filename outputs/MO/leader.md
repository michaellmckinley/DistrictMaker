# Missouri — current leader: splitline-realized+kl

- State: MO (Missouri)
- Districts: 8
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | splitline-realized+kl | ok | 1687.37 | +0.00% | 0.2774 | 359.5 |
| 2 | annealing-from-kl | ok | 1687.37 | +0.00% | 0.2774 | 404.0 |
| 3 | metis+kl | ok | 1892.56 | +12.16% | 0.4999 | 36.2 |
| 4 | metis | ok | 1894.10 | +12.25% | 0.4050 | 30.2 |
| 5 | splitline-realized | ok | 1986.04 | +17.70% | 0.0686 | 177.6 |
| 6 | annealing | ok | 1986.04 | +17.70% | 0.0686 | 213.8 |
| — | splitline-chord | FAILED | — | — | — | 5.8 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

