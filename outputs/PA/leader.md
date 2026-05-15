# Pennsylvania — current leader: metis+kl

- State: PA (Pennsylvania)
- Districts: 17
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 2290.42 | +0.00% | 0.4905 | 55.8 |
| 2 | metis | ok | 2291.08 | +0.03% | 0.4048 | 35.2 |
| 3 | splitline-realized+kl | ok | 2408.69 | +5.16% | 0.2549 | 850.3 |
| 4 | annealing-from-kl | ok | 2408.69 | +5.16% | 0.2549 | 895.8 |
| 5 | annealing | ok | 2823.47 | +23.27% | 0.0993 | 361.7 |
| 6 | splitline-realized | ok | 2823.55 | +23.28% | 0.0993 | 308.5 |
| — | splitline-chord | FAILED | — | — | — | 7.6 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

