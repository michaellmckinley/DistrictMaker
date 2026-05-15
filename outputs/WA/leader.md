# Washington — current leader: splitline-realized+kl

- State: WA (Washington)
- Districts: 10
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | splitline-realized+kl | ok | 2041.22 | +0.00% | 0.4915 | 280.4 |
| 2 | annealing-from-kl | ok | 2041.22 | +0.00% | 0.4915 | 326.8 |
| 3 | metis+kl | ok | 2058.47 | +0.84% | 0.4797 | 20.7 |
| 4 | metis | ok | 2058.67 | +0.85% | 0.4023 | 18.6 |
| 5 | splitline-realized | ok | 2363.31 | +15.78% | 0.0951 | 113.9 |
| 6 | annealing | ok | 2363.31 | +15.78% | 0.0951 | 135.5 |
| — | splitline-chord | FAILED | — | — | — | 5.6 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

