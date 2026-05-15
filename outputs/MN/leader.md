# Minnesota — current leader: metis+kl

- State: MN (Minnesota)
- Districts: 8
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 1289.26 | +0.00% | 0.4869 | 27.8 |
| 2 | metis | ok | 1289.89 | +0.05% | 0.4048 | 22.9 |
| 3 | splitline-realized+kl | ok | 1332.88 | +3.38% | 0.1101 | 236.9 |
| 4 | annealing-from-kl | ok | 1332.88 | +3.38% | 0.1101 | 249.4 |
| 5 | annealing | ok | 1533.08 | +18.91% | 0.0606 | 158.1 |
| 6 | splitline-realized | ok | 1533.09 | +18.91% | 0.0606 | 139.8 |
| — | splitline-chord | FAILED | — | — | — | 5.5 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

