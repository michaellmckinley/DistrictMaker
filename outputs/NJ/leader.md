# New Jersey — current leader: metis+kl

- State: NJ (New Jersey)
- Districts: 12
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 686.89 | +0.00% | 0.5000 | 13.3 |
| 2 | metis | ok | 687.08 | +0.03% | 0.4042 | 11.1 |
| 3 | splitline-realized+kl | ok | 732.15 | +6.59% | 0.4979 | 190.2 |
| 4 | annealing-from-kl | ok | 732.15 | +6.59% | 0.4979 | 202.8 |
| 5 | annealing | ok | 806.11 | +17.36% | 0.4993 | 107.5 |
| 6 | splitline-realized | ok | 828.50 | +20.62% | 0.1354 | 94.6 |
| — | splitline-chord | FAILED | — | — | — | 2.8 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

