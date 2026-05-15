# Nebraska — current leader: metis

- State: NE (Nebraska)
- Districts: 3
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis | ok | 410.27 | +0.00% | 0.2480 | 7.6 |
| 2 | metis+kl | ok | 410.27 | +0.00% | 0.2480 | 7.9 |
| 3 | splitline-realized+kl | ok | 425.63 | +3.74% | 0.1356 | 48.5 |
| 4 | annealing-from-kl | ok | 425.63 | +3.74% | 0.1356 | 59.3 |
| 5 | splitline-realized | ok | 470.19 | +14.61% | 0.0223 | 33.2 |
| 6 | annealing | ok | 470.19 | +14.61% | 0.0223 | 43.1 |
| — | splitline-chord | FAILED | — | — | — | 2.6 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

