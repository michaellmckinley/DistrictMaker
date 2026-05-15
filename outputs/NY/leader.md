# New York — current leader: metis+kl

- State: NY (New York)
- Districts: 26
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 2207.02 | +0.00% | 0.4990 | 52.9 |
| 2 | metis | ok | 2211.80 | +0.22% | 0.4048 | 30.3 |
| 3 | splitline-realized+kl | ok | 2247.23 | +1.82% | 0.4764 | 811.2 |
| 4 | annealing-from-kl | ok | 2247.23 | +1.82% | 0.4764 | 871.2 |
| 5 | annealing | ok | 2584.52 | +17.10% | 0.1386 | 339.5 |
| 6 | splitline-realized | ok | 2584.64 | +17.11% | 0.1386 | 294.4 |
| — | splitline-chord | FAILED | — | — | — | 9.9 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

