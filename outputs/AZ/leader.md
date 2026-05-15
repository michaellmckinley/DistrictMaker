# Arizona — current leader: metis+kl

- State: AZ (Arizona)
- Districts: 9
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 1606.50 | +0.00% | 0.5000 | 26.0 |
| 2 | metis | ok | 1609.46 | +0.18% | 0.4046 | 18.4 |
| 3 | splitline-realized+kl | ok | 2403.00 | +49.58% | 0.4943 | 287.0 |
| 4 | annealing-from-kl | ok | 2403.00 | +49.58% | 0.4943 | 324.7 |
| 5 | splitline-realized | ok | 2807.78 | +74.78% | 0.1070 | 108.9 |
| 6 | annealing | ok | 2807.78 | +74.78% | 0.1070 | 132.0 |
| — | splitline-chord | FAILED | — | — | — | 6.1 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

