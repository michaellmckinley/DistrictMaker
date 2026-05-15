# Colorado — current leader: metis+kl

- State: CO (Colorado)
- Districts: 8
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 1527.35 | +0.00% | 0.4657 | 22.3 |
| 2 | metis | ok | 1527.97 | +0.04% | 0.4050 | 20.2 |
| 3 | splitline-realized+kl | ok | 1751.69 | +14.69% | 0.4779 | 186.0 |
| 4 | annealing-from-kl | ok | 1751.69 | +14.69% | 0.4779 | 206.2 |
| 5 | splitline-realized | ok | 2007.80 | +31.46% | 0.0943 | 93.7 |
| 6 | annealing | ok | 2007.80 | +31.46% | 0.0943 | 114.6 |
| — | splitline-chord | FAILED | — | — | — | 3.0 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

