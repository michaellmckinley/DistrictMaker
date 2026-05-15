# Kansas — current leader: metis+kl

- State: KS (Kansas)
- Districts: 4
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 827.56 | +0.00% | 0.4241 | 16.0 |
| 2 | metis | ok | 827.57 | +0.00% | 0.4044 | 13.8 |
| 3 | splitline-realized+kl | ok | 906.68 | +9.56% | 0.1495 | 120.3 |
| 4 | annealing-from-kl | ok | 906.68 | +9.56% | 0.1495 | 142.9 |
| 5 | splitline-realized | ok | 1026.88 | +24.09% | 0.0425 | 76.4 |
| 6 | annealing | ok | 1026.88 | +24.09% | 0.0425 | 92.3 |
| — | splitline-chord | FAILED | — | — | — | 3.7 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

