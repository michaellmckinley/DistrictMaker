# South Carolina — current leader: metis+kl

- State: SC (South Carolina)
- Districts: 7
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 1199.63 | +0.00% | 0.4994 | 22.0 |
| 2 | metis | ok | 1202.02 | +0.20% | 0.4049 | 17.2 |
| 3 | splitline-realized+kl | ok | 1269.90 | +5.86% | 0.2283 | 159.6 |
| 4 | annealing-from-kl | ok | 1269.90 | +5.86% | 0.2283 | 181.7 |
| 5 | splitline-realized | ok | 1479.49 | +23.33% | 0.1500 | 91.6 |
| 6 | annealing | ok | 1479.49 | +23.33% | 0.1500 | 111.5 |
| — | splitline-chord | FAILED | — | — | — | 3.5 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

