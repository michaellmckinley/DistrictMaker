# California — current leader: splitline-realized+kl

- State: CA (California)
- Districts: 52
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | splitline-realized+kl | ok | 7323.70 | +0.00% | 0.4984 | 2921.8 |
| 2 | annealing-from-kl | ok | 7323.70 | +0.00% | 0.4984 | 2966.8 |
| 3 | metis+kl | ok | 7467.96 | +1.97% | 0.4997 | 122.5 |
| 4 | metis | ok | 7472.85 | +2.04% | 0.4048 | 62.3 |
| 5 | annealing | ok | 8520.55 | +16.34% | 0.1674 | 711.4 |
| 6 | splitline-realized | ok | 8520.76 | +16.34% | 0.1674 | 646.1 |
| — | splitline-chord | FAILED | — | — | — | 16.1 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

