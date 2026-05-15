# Oregon — current leader: metis+kl

- State: OR (Oregon)
- Districts: 6
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 1007.18 | +0.00% | 0.4449 | 28.6 |
| 2 | metis | ok | 1007.33 | +0.02% | 0.4011 | 27.6 |
| 3 | splitline-realized+kl | ok | 1299.25 | +29.00% | 0.2241 | 184.5 |
| 4 | annealing-from-kl | ok | 1299.25 | +29.00% | 0.2241 | 214.6 |
| 5 | splitline-realized | ok | 1567.68 | +55.65% | 0.0397 | 88.8 |
| 6 | annealing | ok | 1567.68 | +55.65% | 0.0397 | 119.2 |
| — | splitline-chord | FAILED | — | — | — | 4.8 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

