# Nevada — current leader: splitline-realized+kl

- State: NV (Nevada)
- Districts: 4
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | splitline-realized+kl | ok | 907.86 | +0.00% | 0.1536 | 36.4 |
| 2 | annealing-from-kl | ok | 907.86 | +0.00% | 0.1536 | 49.1 |
| 3 | metis | ok | 927.76 | +2.19% | 0.4037 | 10.4 |
| 4 | metis+kl | ok | 927.76 | +2.19% | 0.4037 | 10.5 |
| 5 | splitline-realized | ok | 1075.13 | +18.43% | 0.0720 | 27.8 |
| 6 | annealing | ok | 1075.13 | +18.43% | 0.0720 | 39.5 |
| — | splitline-chord | FAILED | — | — | — | 1.7 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

