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
