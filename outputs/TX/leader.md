# Texas — current leader: splitline-realized+kl

- State: TX (Texas)
- Districts: 38
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | splitline-realized+kl | ok | 8323.94 | +0.00% | 0.4969 | 4164.1 |
| 2 | annealing-from-kl | ok | 8323.94 | +0.00% | 0.4969 | 4274.7 |
| 3 | metis+kl | ok | 8967.86 | +7.74% | 0.4992 | 245.2 |
| 4 | metis | ok | 8982.36 | +7.91% | 0.4050 | 73.4 |
| 5 | splitline-realized | ok | 9760.26 | +17.26% | 0.2220 | 821.2 |
| 6 | annealing | ok | 9760.26 | +17.26% | 0.2220 | 907.9 |
| — | splitline-chord | FAILED | — | — | — | 26.5 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

