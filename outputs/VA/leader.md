# Virginia — current leader: metis+kl

- State: VA (Virginia)
- Districts: 11
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 1598.54 | +0.00% | 0.4729 | 29.5 |
| 2 | metis | ok | 1598.67 | +0.01% | 0.4047 | 27.2 |
| 3 | splitline-realized+kl | ok | 1677.95 | +4.97% | 0.4273 | 280.2 |
| 4 | annealing-from-kl | ok | 1677.95 | +4.97% | 0.4273 | 313.6 |
| 5 | splitline-realized | ok | 2020.51 | +26.40% | 0.0740 | 133.5 |
| 6 | annealing | ok | 2020.51 | +26.40% | 0.0740 | 165.4 |
| — | splitline-chord | FAILED | — | — | — | 5.8 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

