# Connecticut — current leader: metis+kl

- State: CT (Connecticut)
- Districts: 5
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 342.09 | +0.00% | 0.4544 | 5.4 |
| 2 | metis | ok | 342.10 | +0.00% | 0.4002 | 5.2 |
| 3 | splitline-realized+kl | ok | 405.35 | +18.49% | 0.1404 | 31.8 |
| 4 | annealing-from-kl | ok | 405.35 | +18.49% | 0.1404 | 38.4 |
| 5 | splitline-realized | ok | 462.20 | +35.11% | 0.0130 | 23.8 |
| 6 | annealing | ok | 462.20 | +35.11% | 0.0130 | 30.4 |
| — | splitline-chord | FAILED | — | — | — | 1.4 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

