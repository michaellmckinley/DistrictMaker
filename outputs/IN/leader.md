# Indiana — current leader: splitline-realized+kl

- State: IN (Indiana)
- Districts: 9
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | splitline-realized+kl | ok | 1365.82 | +0.00% | 0.4774 | 297.8 |
| 2 | annealing-from-kl | ok | 1365.82 | +0.00% | 0.4774 | 319.5 |
| 3 | metis+kl | ok | 1413.28 | +3.47% | 0.4989 | 23.6 |
| 4 | metis | ok | 1416.58 | +3.72% | 0.4049 | 16.3 |
| 5 | annealing | ok | 1558.81 | +14.13% | 0.0976 | 153.5 |
| 6 | splitline-realized | ok | 1561.03 | +14.29% | 0.0976 | 130.6 |
| — | splitline-chord | FAILED | — | — | — | 4.8 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

