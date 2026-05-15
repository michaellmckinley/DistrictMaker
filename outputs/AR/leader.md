# Arkansas — current leader: splitline-realized+kl

- State: AR (Arkansas)
- Districts: 4
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | splitline-realized+kl | ok | 973.32 | +0.00% | 0.1667 | 119.3 |
| 2 | annealing-from-kl | ok | 973.32 | +0.00% | 0.1667 | 137.6 |
| 3 | metis+kl | ok | 986.60 | +1.36% | 0.3985 | 20.1 |
| 4 | metis | ok | 987.68 | +1.48% | 0.3985 | 19.5 |
| 5 | annealing | ok | 1159.34 | +19.11% | 0.0220 | 90.6 |
| 6 | splitline-realized | ok | 1159.43 | +19.12% | 0.0220 | 73.7 |
| — | splitline-chord | FAILED | — | — | — | 4.9 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

