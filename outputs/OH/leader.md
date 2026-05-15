# Ohio — current leader: metis+kl

- State: OH (Ohio)
- Districts: 15
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 2186.94 | +0.00% | 0.4982 | 39.5 |
| 2 | metis | ok | 2188.93 | +0.09% | 0.4049 | 24.3 |
| 3 | splitline-realized+kl | ok | 2268.96 | +3.75% | 0.3893 | 630.0 |
| 4 | annealing-from-kl | ok | 2268.96 | +3.75% | 0.3893 | 615.7 |
| 5 | splitline-realized | ok | 2632.14 | +20.36% | 0.0642 | 245.3 |
| 6 | annealing | ok | 2632.14 | +20.36% | 0.0642 | 268.2 |
| — | splitline-chord | FAILED | — | — | — | 9.0 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

