# Michigan — current leader: metis+kl

- State: MI (Michigan)
- Districts: 13
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 2119.46 | +0.00% | 0.5000 | 24.3 |
| 2 | metis | ok | 2120.37 | +0.04% | 0.4049 | 21.4 |
| 3 | splitline-realized+kl | ok | 2208.60 | +4.21% | 0.3761 | 472.3 |
| 4 | annealing-from-kl | ok | 2208.60 | +4.21% | 0.3761 | 520.2 |
| 5 | splitline-realized | ok | 2465.24 | +16.31% | 0.0607 | 205.7 |
| 6 | annealing | ok | 2465.24 | +16.31% | 0.0607 | 247.0 |
| — | splitline-chord | FAILED | — | — | — | 5.6 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

