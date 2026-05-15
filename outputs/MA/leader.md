# Massachusetts — current leader: metis+kl

- State: MA (Massachusetts)
- Districts: 9
- Criterion: shortest realized internal boundary; ties broken by lower max population deviation
- Trials per experiment: 1 (single-run; will change as multi-start lands)

## Ranking

| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |
|---:|---|---|---:|---:|---:|---:|
| 1 | metis+kl | ok | 595.61 | +0.00% | 0.4987 | 11.1 |
| 2 | metis | ok | 596.13 | +0.09% | 0.4029 | 9.7 |
| 3 | splitline-realized+kl | ok | 628.85 | +5.58% | 0.2883 | 110.6 |
| 4 | annealing-from-kl | ok | 628.85 | +5.58% | 0.2883 | 128.0 |
| 5 | splitline-realized | ok | 722.29 | +21.27% | 0.1461 | 65.9 |
| 6 | annealing | ok | 722.29 | +21.27% | 0.1461 | 79.2 |
| — | splitline-chord | FAILED | — | — | — | 2.2 (RuntimeError: No valid cut found — region may be degenerate or angle resolution too coarse) |

