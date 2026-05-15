# Iowa — current leader: splitline-realized+kl

- State: IA (Iowa)
- Districts: 4
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | splitline-realized+kl | ok | 919.77 | +0.00% | 0.1951 | 133.1 |
| 2 | annealing-from-kl | ok | 919.77 | +0.00% | 0.1951 | 149.7 |
| 3 | metis | ok | 980.45 | +6.60% | 0.2318 | 13.3 |
| 4 | metis+kl | ok | 980.45 | +6.60% | 0.2318 | 13.8 |
| 5 | splitline-realized | ok | 1056.16 | +14.83% | 0.0197 | 74.6 |
| 6 | annealing | ok | 1056.16 | +14.83% | 0.0197 | 93.3 |
| — | splitline-chord | FAILED | — | — | — | 3.9 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

