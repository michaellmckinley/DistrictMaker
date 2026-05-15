"""Multi-start (seed-varied) trial fan-out and post-run aggregation.

A multi-start experiment runs one (state, algorithm) combination N times
with deterministic seeds derived from a base seed. Each trial writes to
`<output>/<state>/<algorithm>/trial-NN-seed-X/`. After all trials finish,
`aggregate_results` produces:

- `<output>/<state>/<algorithm>/best.json` — per-algorithm best trial +
  distribution stats.
- `<output>/distributions.json` — per-trial machine-readable view.
- `<output>/_summary.md` — human-readable writeup.

The trial graph reuses `Task` with `trial_index` populated; the existing
parallel scheduler (`run_experiment`) dispatches and CPU-governs the
trials. Pause/freeze/resume/set-cpu controls work identically.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Iterable

from districtmaker.task_graph import Task, TaskGraph


def build_trial_graph(
    state: str,
    algorithms: Iterable[str],
    trials: int,
) -> TaskGraph:
    """Fan out (state, algorithm) into N trial tasks per algorithm.

    Tasks have no inter-task dependencies and no finalization step:
    aggregation runs separately after all trials complete.
    """
    algorithms = tuple(algorithms)
    if trials < 1:
        raise ValueError("trials must be >= 1")
    if not algorithms:
        raise ValueError("at least one algorithm required")

    tasks: list[Task] = []
    deps: dict[Task, frozenset[Task]] = {}
    for algo in algorithms:
        for trial_index in range(trials):
            t = Task(state_code=state, algorithm=algo, trial_index=trial_index)
            tasks.append(t)
            deps[t] = frozenset()

    return TaskGraph(tasks=tasks, dependencies=deps)


def aggregate_results(
    output_dir: Path,
    state: str,
    algorithms: Iterable[str],
    trials: int,
    base_seed: int,
) -> dict:
    """Scan completed trial dirs, write best.json / distributions.json / _summary.md.

    Returns the in-memory aggregate dict (also written to disk) so the
    CLI can render a short post-run console message without re-reading
    the files.
    """
    output_dir = Path(output_dir)
    algorithms = tuple(algorithms)
    distributions: dict[str, list[dict]] = {}
    bests: dict[str, dict] = {}

    for algo in algorithms:
        algo_trials: list[dict] = []
        for trial_index in range(trials):
            seed = base_seed + trial_index
            trial_dir = (
                output_dir / state / algo /
                f"trial-{trial_index:02d}-seed-{seed}"
            )
            metrics_path = trial_dir / "metrics.json"
            if not metrics_path.exists():
                algo_trials.append({
                    "trial_index": trial_index,
                    "seed": seed,
                    "status": "missing",
                    "boundary_km": None,
                    "max_dev_pct": None,
                    "runtime_s": None,
                })
                continue
            metrics = json.loads(metrics_path.read_text())
            algo_trials.append({
                "trial_index": trial_index,
                "seed": seed,
                "status": metrics.get("status", "ok"),
                "boundary_km": metrics.get("total_internal_boundary_km"),
                "max_dev_pct": metrics.get("max_abs_deviation_pct"),
                "runtime_s": metrics.get("runtime_seconds"),
            })

        ok_trials = [t for t in algo_trials if t["status"] == "ok"]
        failed_trials = [t for t in algo_trials if t["status"] != "ok"]

        if ok_trials:
            best = min(ok_trials, key=lambda t: t["boundary_km"])
            boundaries = [t["boundary_km"] for t in ok_trials]
            dist_stats = {
                "min": min(boundaries),
                "max": max(boundaries),
                "mean": statistics.mean(boundaries),
                "median": statistics.median(boundaries),
                "std": statistics.stdev(boundaries) if len(boundaries) > 1 else 0.0,
                "std_pct": (
                    100.0 * statistics.stdev(boundaries) / statistics.mean(boundaries)
                    if len(boundaries) > 1 else 0.0
                ),
            }
        else:
            best = None
            dist_stats = {
                "min": None, "max": None, "mean": None,
                "median": None, "std": None, "std_pct": None,
            }

        best_payload = {
            "algorithm": algo,
            "trials": len(algo_trials),
            "trials_ok": len(ok_trials),
            "trials_failed": len(failed_trials),
            "best": (
                {
                    "trial_index": best["trial_index"],
                    "seed": best["seed"],
                    "boundary_km": best["boundary_km"],
                    "max_dev_pct": best["max_dev_pct"],
                    "trial_dir": f"trial-{best['trial_index']:02d}-seed-{best['seed']}",
                }
                if best is not None else None
            ),
            "distribution": dist_stats,
        }
        bests[algo] = best_payload

        algo_dir = output_dir / state / algo
        algo_dir.mkdir(parents=True, exist_ok=True)
        (algo_dir / "best.json").write_text(json.dumps(best_payload, indent=2))

        distributions[algo] = algo_trials

    distributions_payload = {
        "state": state,
        "trials_per_algorithm": trials,
        "base_seed": base_seed,
        "results": distributions,
    }
    (output_dir / "distributions.json").write_text(
        json.dumps(distributions_payload, indent=2)
    )

    (output_dir / "_summary.md").write_text(
        _render_summary_md(state, algorithms, bests, distributions)
    )

    return {"distributions": distributions_payload, "bests": bests}


def _render_summary_md(
    state: str,
    algorithms: tuple[str, ...],
    bests: dict[str, dict],
    distributions: dict[str, list[dict]],
) -> str:
    """Render the per-experiment writeup."""
    lines: list[str] = []
    lines.append(f"# Multi-start results — {state}")
    lines.append("")

    lines.append("## Distribution per algorithm")
    lines.append("")
    lines.append(
        "| Algorithm | Trials OK / N | Min (km) | Max (km) | Mean (km) | "
        "Median (km) | Std (km) | Std (%) |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for algo in algorithms:
        b = bests[algo]
        d = b["distribution"]
        if d["min"] is None:
            lines.append(f"| {algo} | 0 / {b['trials']} | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| {algo} | {b['trials_ok']} / {b['trials']} | "
            f"{d['min']:.2f} | {d['max']:.2f} | "
            f"{d['mean']:.2f} | {d['median']:.2f} | "
            f"{d['std']:.2f} | {d['std_pct']:.3f} |"
        )
    lines.append("")

    lines.append("## Best-of-N saturation")
    lines.append("")
    lines.append("| Algorithm | N=1 | N=2 | N=5 | N=10 | N=20 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for algo in algorithms:
        ok_trials = [
            t for t in distributions[algo]
            if t["status"] == "ok" and t["boundary_km"] is not None
        ]
        ok_trials.sort(key=lambda t: t["trial_index"])
        cells: list[str] = []
        for n in (1, 2, 5, 10, 20):
            window = ok_trials[:n]
            if not window:
                cells.append("—")
            else:
                cells.append(f"{min(t['boundary_km'] for t in window):.2f}")
        lines.append(
            f"| {algo} | {cells[0]} | {cells[1]} | {cells[2]} | "
            f"{cells[3]} | {cells[4]} |"
        )
    lines.append("")

    return "\n".join(lines) + "\n"
