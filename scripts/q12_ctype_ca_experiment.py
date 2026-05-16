"""Run 20 trials of metis+kl on CA with ctype=RM (Q12 structural probe).

Mirrors the multi-start dir layout so outputs/CA/multi-start/2026-05-16-ctype-rm/
can be fed to the existing aggregate_results() function.

NOT part of the production CLI — this is a one-shot experimental script.
If ctype=RM proves valuable, promote 'metis-rm+kl' to ALGORITHM_NAMES in
a follow-up plan and remove this script.
"""
from __future__ import annotations

import json
import logging
import multiprocessing as mp
import time
from pathlib import Path

from districtmaker.experiments import run_single_algorithm_task
from districtmaker.multi_start import aggregate_results
from districtmaker.output.writer import get_logger


OUTPUT_DIR = Path("outputs/CA/multi-start/2026-05-16-ctype-rm")
STATE = "CA"
ALGORITHM = "metis+kl"  # base 'metis' runs internally; ctype=RM applies to it
TRIALS = 20
BASE_SEED = 42


def _run_trial(trial_index: int) -> dict:
    """Worker entry — runs one trial with ctype=RM and writes trial dir."""
    seed = BASE_SEED + trial_index
    trial_dir = OUTPUT_DIR / STATE / ALGORITHM / f"trial-{trial_index:02d}-seed-{seed}"
    # Monkey-patch the metis instantiation in run_one_algorithm to pass
    # ctype="RM". Cleanest patch point: replace Metis.__init__'s default
    # for this process via a shim.
    from districtmaker.algorithms import metis as metis_mod
    orig_init = metis_mod.Metis.__init__

    def patched_init(self, *args, **kwargs):
        kwargs.setdefault("ctype", "RM")
        orig_init(self, *args, **kwargs)

    metis_mod.Metis.__init__ = patched_init
    try:
        run_single_algorithm_task(
            state_code=STATE,
            algorithm=ALGORITHM,
            state_output_dir=OUTPUT_DIR,
            seed=seed,
            tolerance=0.005,
            full_artifacts=True,
            experiment_dir_override=trial_dir,
        )
        return {"trial_index": trial_index, "seed": seed, "status": "ok"}
    except Exception as exc:
        return {
            "trial_index": trial_index,
            "seed": seed,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        metis_mod.Metis.__init__ = orig_init


def main(workers: int = 6) -> None:
    log = get_logger()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Q12 ctype=RM experiment: state=%s trials=%d workers=%d",
             STATE, TRIALS, workers)

    started = time.perf_counter()
    with mp.Pool(processes=workers) as pool:
        results = pool.map(_run_trial, range(TRIALS))
    elapsed = time.perf_counter() - started
    log.info("All trials done in %.1fs", elapsed)

    for r in results:
        log.info("trial-%02d-seed-%d: %s", r["trial_index"], r["seed"], r["status"])

    log.info("Aggregating…")
    agg = aggregate_results(
        output_dir=OUTPUT_DIR,
        state=STATE,
        algorithms=(ALGORITHM,),
        trials=TRIALS,
        base_seed=BASE_SEED,
    )
    print(json.dumps({
        "elapsed_seconds": elapsed,
        "trials": results,
        "best": agg.get("bests", {}).get(ALGORITHM),
    }, indent=2))


if __name__ == "__main__":
    main()
