# Alabama — current leader: metis+kl

- State: AL (Alabama)
- Districts: 7
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 1582.56 | +0.00% | 0.4990 | 27.5 |
| 2 | metis | ok | 1585.33 | +0.17% | 0.4047 | 24.0 |
| 3 | splitline-realized+kl | ok | 1680.94 | +6.22% | 0.2881 | 260.7 |
| 4 | annealing-from-kl | ok | 1680.94 | +6.22% | 0.2881 | 284.6 |
| 5 | splitline-realized | ok | 1930.23 | +21.97% | 0.0324 | 118.3 |
| 6 | annealing | ok | 1930.23 | +21.97% | 0.0324 | 143.3 |
| — | splitline-chord | FAILED | — | — | — | 5.4 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

