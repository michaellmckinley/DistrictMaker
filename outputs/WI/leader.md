# Wisconsin — current leader: metis+kl

- State: WI (Wisconsin)
- Districts: 8
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 1614.98 | +0.00% | 0.4146 | 28.2 |
| 2 | metis | ok | 1614.98 | +0.00% | 0.4041 | 26.9 |
| 3 | splitline-realized+kl | ok | 1629.01 | +0.87% | 0.1335 | 267.2 |
| 4 | annealing-from-kl | ok | 1629.01 | +0.87% | 0.1335 | 302.6 |
| 5 | splitline-realized | ok | 1921.25 | +18.96% | 0.0154 | 142.3 |
| 6 | annealing | ok | 1921.25 | +18.96% | 0.0154 | 169.8 |
| — | splitline-chord | FAILED | — | — | — | 4.5 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

