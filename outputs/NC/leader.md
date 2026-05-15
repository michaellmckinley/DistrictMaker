# North Carolina — current leader: metis+kl

- State: NC (North Carolina)
- Districts: 14
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 2199.11 | +0.00% | 0.4575 | 42.2 |
| 2 | metis | ok | 2202.47 | +0.15% | 0.4045 | 32.0 |
| 3 | splitline-realized+kl | ok | 2301.56 | +4.66% | 0.2121 | 581.3 |
| 4 | annealing-from-kl | ok | 2301.56 | +4.66% | 0.2121 | 610.0 |
| 5 | splitline-realized | ok | 2695.69 | +22.58% | 0.0447 | 218.3 |
| 6 | annealing | ok | 2695.69 | +22.58% | 0.0447 | 243.8 |
| — | splitline-chord | FAILED | — | — | — | 7.5 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

