# Georgia — current leader: metis+kl

- State: GA (Georgia)
- Districts: 14
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 2308.05 | +0.00% | 0.4985 | 38.1 |
| 2 | metis | ok | 2312.58 | +0.20% | 0.4047 | 25.8 |
| 3 | splitline-realized+kl | ok | 2427.02 | +5.15% | 0.2307 | 521.0 |
| 4 | annealing-from-kl | ok | 2427.02 | +5.15% | 0.2307 | 558.4 |
| 5 | splitline-realized | ok | 2810.52 | +21.77% | 0.0979 | 206.1 |
| 6 | annealing | ok | 2810.52 | +21.77% | 0.0979 | 230.7 |
| — | splitline-chord | FAILED | — | — | — | 9.8 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

