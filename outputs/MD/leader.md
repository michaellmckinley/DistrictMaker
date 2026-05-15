# Maryland — current leader: metis+kl

- State: MD (Maryland)
- Districts: 8
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 569.39 | +0.00% | 0.4986 | 10.6 |
| 2 | metis | ok | 569.91 | +0.09% | 0.4050 | 9.8 |
| 3 | splitline-realized+kl | ok | 632.19 | +11.03% | 0.1495 | 71.0 |
| 4 | annealing-from-kl | ok | 632.19 | +11.03% | 0.1495 | 82.8 |
| 5 | splitline-realized | ok | 718.88 | +26.26% | 0.1065 | 49.4 |
| 6 | annealing | ok | 718.88 | +26.26% | 0.1065 | 61.6 |
| — | splitline-chord | FAILED | — | — | — | 3.0 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

