# Florida — current leader: metis+kl

- State: FL (Florida)
- Districts: 28
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 3554.87 | +0.00% | 0.5000 | 77.0 |
| 2 | metis | ok | 3570.85 | +0.45% | 0.4048 | 36.6 |
| 3 | splitline-realized+kl | ok | 3855.91 | +8.47% | 0.4980 | 1377.5 |
| 4 | annealing-from-kl | ok | 3855.91 | +8.47% | 0.4980 | 1316.9 |
| 5 | annealing | ok | 4216.92 | +18.62% | 0.4995 | 461.0 |
| 6 | splitline-realized | ok | 4431.90 | +24.67% | 0.2279 | 416.0 |
| — | splitline-chord | FAILED | — | — | — | 10.5 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

