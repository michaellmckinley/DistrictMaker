# Kentucky — current leader: metis+kl

- State: KY (Kentucky)
- Districts: 6
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 965.27 | +0.00% | 0.4403 | 24.8 |
| 2 | metis | ok | 965.68 | +0.04% | 0.4045 | 23.2 |
| 3 | splitline-realized+kl | ok | 1024.41 | +6.13% | 0.0752 | 133.9 |
| 4 | annealing-from-kl | ok | 1024.41 | +6.13% | 0.0752 | 157.1 |
| 5 | splitline-realized | ok | 1224.00 | +26.80% | 0.0560 | 88.3 |
| 6 | annealing | ok | 1224.00 | +26.80% | 0.0560 | 112.2 |
| — | splitline-chord | FAILED | — | — | — | 5.5 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

