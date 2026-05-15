# Tennessee — current leader: metis+kl

- State: TN (Tennessee)
- Districts: 9
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 1375.33 | +0.00% | 0.4173 | 27.5 |
| 2 | metis | ok | 1375.71 | +0.03% | 0.4014 | 26.4 |
| 3 | splitline-realized+kl | ok | 1548.24 | +12.57% | 0.3123 | 310.1 |
| 4 | annealing-from-kl | ok | 1548.24 | +12.57% | 0.3123 | 343.2 |
| 5 | splitline-realized | ok | 1827.55 | +32.88% | 0.0982 | 137.5 |
| 6 | annealing | ok | 1827.55 | +32.88% | 0.0982 | 162.4 |
| — | splitline-chord | FAILED | — | — | — | 5.8 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

