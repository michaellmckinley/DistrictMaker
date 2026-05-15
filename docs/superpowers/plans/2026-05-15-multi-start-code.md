# Multi-start (Code Changes) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the parallel scheduler to support multi-trial experiments — one `(state, algorithm)` combination fanned out into N seed-varied trials — exposed as a new `districtmaker multi-start` CLI subcommand. No experiment execution; that is Plan B.

**Architecture:** Add an optional `trial_index: int | None` to the existing `Task` dataclass. When set, `_worker_main` derives `seed = base_seed + trial_index` and writes results to `<state>/<algo>/trial-NN-seed-X/` instead of the existing `<state>/experiments/<algo>/`. A new `multi_start.py` module owns the trial-graph builder and the post-run aggregator (`distributions.json`, `best.json`, `_summary.md`). The `multi-start` CLI subcommand wires it together: validate inputs, build graph, call existing `run_experiment` with `record_tier_run=False`, run aggregator. Roughly 95% of the parallel scheduler is reused untouched.

**Tech Stack:** Python 3.11+, Click, multiprocessing, psutil, fcntl. pytest for tests. The `pymetis` and existing splitline/KL algorithms run inside trials unchanged.

---

## Context (from brainstorming, inlined because the spec is not committed)

This plan supports a follow-on experiment that resolves Q15 in `docs/open-questions.md`: does multi-start `metis+kl` close the +7.74% realized-boundary-km gap behind `splitline-realized+kl` on Texas, or is the gap structural? The experiment will run 20 trials each of `metis+kl` and `splitline-realized+kl` on TX with seeds 42–61, using this plan's code. **This plan delivers only the code surface.** No experiment runs as part of this plan.

The first trial (`trial_index=0`, seed = `base_seed + 0`) must reproduce single-trial behavior bit-exactly — that property is the determinism regression check both this plan's tests and Plan B's pre-flight rely on.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `src/districtmaker/task_graph.py` | Modify | Add optional `trial_index: int \| None = None` to `Task`. Frozen dataclass stays frozen. |
| `src/districtmaker/experiments.py` | Modify | Add optional `experiment_dir_override: Path \| None = None` to `run_single_algorithm_task`. When set, write to that dir instead of computing `state_output_dir/experiments/<algo>`. |
| `src/districtmaker/validate.py` | Modify | `_worker_main` derives `effective_seed = seed + task.trial_index` and `experiment_dir_override = state_dir / task.algorithm / f"trial-{trial_index:02d}-seed-{effective_seed}"` when `trial_index` is set. Add `record_tier_run: bool = True` to `run_experiment`; skip `append_tier_run` when False. |
| `src/districtmaker/multi_start.py` | Create | (1) `build_trial_graph(state, algorithms, trials) → TaskGraph` — fans out trials, no finalize tasks. (2) `aggregate_results(output_dir, state, algorithms, trials, base_seed) → dict` — reads each trial's metrics, writes `distributions.json`, per-algorithm `best.json`, and `_summary.md`. |
| `src/districtmaker/cli.py` | Modify | New `multi-start` subcommand with options: `--state`, `--algorithms`, `--trials`, `--base-seed`, `--cpu`, `--max-workers`, `--poll-seconds`, `--tolerance`, `--output`, `--full-artifacts/--light-artifacts` (default full), `--force/--skip-existing`. |
| `tests/test_task_graph.py` | Modify | Add tests for `Task` with `trial_index` (equality, hashability, default). |
| `tests/test_experiments.py` | Modify | Add test for `experiment_dir_override`. |
| `tests/test_multi_start.py` | Create | Tests for `build_trial_graph`, `aggregate_results`, and seed derivation. |
| `tests/test_cli.py` | Modify | Add CLI smoke test for `multi-start` invocation (with mocked experiment runner). |
| `tests/test_validate.py` | Modify | Add test for `record_tier_run=False` path in `run_experiment` (no `_finalize` tasks → no ledger row appended). |

---

## Task 1: Extend `Task` with `trial_index`

**Files:**
- Modify: `src/districtmaker/task_graph.py:27-34`
- Modify: `tests/test_task_graph.py` (append new tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_task_graph.py`:

```python
# --- trial_index field --------------------------------------------------------


def test_task_default_trial_index_is_none() -> None:
    """Single-trial tasks (the existing case) have trial_index=None."""
    t = Task("TX", "metis+kl")
    assert t.trial_index is None
    assert t.is_finalization is False


def test_task_with_trial_index_is_distinct() -> None:
    """Two tasks with same state+algorithm but different trial_index are distinct."""
    a = Task("TX", "metis+kl", trial_index=0)
    b = Task("TX", "metis+kl", trial_index=1)
    assert a != b
    assert hash(a) != hash(b)


def test_task_with_trial_index_hashable_in_set() -> None:
    """20 trial tasks for one (state, algo) all coexist in a set."""
    tasks = {Task("TX", "metis+kl", trial_index=i) for i in range(20)}
    assert len(tasks) == 20


def test_task_trial_index_is_not_finalization() -> None:
    """trial_index does not interact with finalization detection."""
    t = Task("TX", "metis+kl", trial_index=3)
    assert t.is_finalization is False
    finalize = Task("TX", "_finalize", trial_index=None)
    assert finalize.is_finalization is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_graph.py::test_task_default_trial_index_is_none -v`

Expected: `FAILED` with `TypeError: __init__() got an unexpected keyword argument 'trial_index'` or similar.

- [ ] **Step 3: Implement — add `trial_index` field**

Modify `src/districtmaker/task_graph.py`:

Change the `Task` definition (currently lines 27–34) to:

```python
@dataclass(frozen=True)
class Task:
    state_code: str
    algorithm: str
    trial_index: int | None = None

    @property
    def is_finalization(self) -> bool:
        return self.algorithm == FINALIZATION_ALGORITHM
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_task_graph.py -v`

Expected: all tests pass, including the four new ones and the existing tests (which construct `Task("ID", "metis")` and continue to work because `trial_index` defaults to `None`).

- [ ] **Step 5: Commit**

```bash
git add src/districtmaker/task_graph.py tests/test_task_graph.py
git commit -m "Add optional trial_index field to Task dataclass

Multi-start experiments need to distinguish N trial tasks per
(state, algorithm) combination. Default of None preserves single-trial
behavior for all existing callers.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: Add `experiment_dir_override` to `run_single_algorithm_task`

**Files:**
- Modify: `src/districtmaker/experiments.py:269-344`
- Modify: `tests/test_experiments.py` (append new test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_experiments.py`:

```python
# --- experiment_dir_override -------------------------------------------------


def test_run_single_algorithm_task_honors_experiment_dir_override(tmp_path) -> None:
    """When experiment_dir_override is set, results land there, not in <state>/experiments/<algo>."""
    import numpy as np
    from unittest.mock import patch
    from districtmaker.experiments import run_single_algorithm_task
    from tests.test_experiments import _fake_state_data  # module-level helper

    state_dir = tmp_path / "TX"
    override = tmp_path / "custom" / "trial-00-seed-42"

    # _fake_state_data() returns a StateData; load_state and get_adjacency
    # are the two surfaces run_single_algorithm_task touches. Patch both
    # the same way the existing tests in test_experiments.py do.
    fake_state = _fake_state_data()
    fake_edges = np.array([[0, 1]], dtype=np.int64)
    fake_lengths = np.array([1.0], dtype=np.float64)

    with patch("districtmaker.experiments.load_state", return_value=fake_state), \
         patch("districtmaker.experiments.get_adjacency",
               return_value=(fake_edges, fake_lengths)):
        result = run_single_algorithm_task(
            state_code="AA",
            algorithm="metis",
            state_output_dir=state_dir,
            seed=42,
            experiment_dir_override=override,
        )

    assert override.exists(), "override dir should be created"
    assert (override / "metrics.json").exists(), "metrics.json should be in override dir"
    assert not (state_dir / "experiments" / "metis").exists(), "default path must be skipped"
    assert result.succeeded
```

Note: `_fake_state_data` is a module-level function in `tests/test_experiments.py` returning a `StateData` instance. The patching pattern above mirrors how the existing tests in that file invoke `run_single_algorithm_task` (see lines 242, 266 of `tests/test_experiments.py`). If `_fake_state_data` is *not* module-level there (verify before relying on the import), lift it to module level in a small refactor first, or duplicate its body at the top of this test file. Do not invent new fakes.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_experiments.py::test_run_single_algorithm_task_honors_experiment_dir_override -v`

Expected: `FAILED` with `TypeError: run_single_algorithm_task() got an unexpected keyword argument 'experiment_dir_override'`.

- [ ] **Step 3: Implement**

In `src/districtmaker/experiments.py`, update the `run_single_algorithm_task` signature and the `exp_dir` computation.

Add the parameter (around line 281, after `log`):

```python
def run_single_algorithm_task(
    state_code: str,
    algorithm: str,
    state_output_dir: Path,
    *,
    seed: int = 42,
    angle_steps: int = 180,
    tolerance: float = 0.005,
    full_artifacts: bool = False,
    n_districts: int | None = None,
    state_loader=load_state,
    adjacency_loader=get_adjacency,
    log: logging.Logger | None = None,
    experiment_dir_override: Path | None = None,
) -> AlgoResult:
```

Replace line 316:

```python
    exp_dir = state_output_dir / "experiments" / algorithm
```

with:

```python
    exp_dir = (
        Path(experiment_dir_override)
        if experiment_dir_override is not None
        else state_output_dir / "experiments" / algorithm
    )
```

Update the docstring (around lines 283–292) to mention the override:

```python
    """Run exactly one (state, algorithm) task and write its experiment dir.

    Used by the parallel runner as the worker entry point. Each task is
    self-contained: it loads the state, builds adjacency, runs the named
    algorithm, and writes `state_output_dir/experiments/<algorithm>/` by
    default. Pass `experiment_dir_override` to write to a different path
    (used by multi-start trials, which write to
    `state_output_dir/<algo>/trial-NN-seed-X/`). The finalization step
    (separate task) reads each experiment's metrics and computes the
    per-state leader.

    `state_loader` and `adjacency_loader` are injected for testability;
    production callers use the defaults (real Census loaders).
    """
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_experiments.py -v`

Expected: all tests pass, including the new override test and all existing tests (which don't pass `experiment_dir_override` and get the default path behavior).

- [ ] **Step 5: Commit**

```bash
git add src/districtmaker/experiments.py tests/test_experiments.py
git commit -m "Allow run_single_algorithm_task to write to a custom experiment dir

Optional experiment_dir_override parameter lets callers (specifically
multi-start trials) write results to a path other than
state_output_dir/experiments/<algorithm>. Default behavior unchanged.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: `_worker_main` derives per-trial seed and path

**Files:**
- Modify: `src/districtmaker/validate.py:421-492` (the `_worker_main` function)
- Modify: `tests/test_run_experiment.py` (append new test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_run_experiment.py`:

```python
# --- multi-start worker path/seed derivation ---------------------------------


def test_worker_main_derives_trial_seed_and_path(tmp_path, monkeypatch) -> None:
    """When task.trial_index is set, _worker_main derives effective_seed
    and writes to <state>/<algo>/trial-NN-seed-X/."""
    import multiprocessing as mp
    from districtmaker.task_graph import Task
    from districtmaker.validate import _worker_main

    captured = {}

    def fake_run_single(**kwargs):
        captured["seed"] = kwargs["seed"]
        captured["experiment_dir_override"] = kwargs.get("experiment_dir_override")
        # The worker doesn't inspect the return value; None is safe here.
        return None

    monkeypatch.setattr("districtmaker.validate.run_single_algorithm_task", fake_run_single)

    state_dir = tmp_path / "TX"
    state_dir.mkdir()
    result_q: mp.Queue = mp.Queue()
    task = Task("TX", "metis+kl", trial_index=7)

    _worker_main(
        task=task,
        state_output_dir=str(state_dir),
        n_districts=38,
        seed=42,
        angle_steps=180,
        tolerance=0.005,
        full_artifacts=True,
        result_q=result_q,
    )

    assert captured["seed"] == 49, "effective_seed should be base_seed(42) + trial_index(7)"
    assert captured["experiment_dir_override"] == state_dir / "metis+kl" / "trial-07-seed-49"


def test_worker_main_single_trial_preserves_behavior(tmp_path, monkeypatch) -> None:
    """When task.trial_index is None, no override is passed (existing behavior)."""
    import multiprocessing as mp
    from districtmaker.task_graph import Task
    from districtmaker.validate import _worker_main

    captured = {}

    def fake_run_single(**kwargs):
        captured["seed"] = kwargs["seed"]
        captured["experiment_dir_override"] = kwargs.get("experiment_dir_override")
        from districtmaker.compare import AlgoResult
        return AlgoResult(
            name=kwargs["algorithm"],
            succeeded=True,
            districts=None,
            metrics={},
            runtime_seconds=0.1,
            error=None,
        )

    monkeypatch.setattr("districtmaker.validate.run_single_algorithm_task", fake_run_single)

    state_dir = tmp_path / "TX"
    state_dir.mkdir()
    result_q: mp.Queue = mp.Queue()
    task = Task("TX", "metis+kl")  # trial_index defaults to None

    _worker_main(
        task=task,
        state_output_dir=str(state_dir),
        n_districts=38,
        seed=42,
        angle_steps=180,
        tolerance=0.005,
        full_artifacts=False,
        result_q=result_q,
    )

    assert captured["seed"] == 42
    assert captured["experiment_dir_override"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_run_experiment.py::test_worker_main_derives_trial_seed_and_path tests/test_run_experiment.py::test_worker_main_single_trial_preserves_behavior -v`

Expected: `FAILED` — the worker currently passes `seed` through unchanged and never sets `experiment_dir_override`.

- [ ] **Step 3: Implement**

In `src/districtmaker/validate.py`, modify the algorithm-task branch of `_worker_main` (currently lines 472–484). Replace the `else:` branch with:

```python
        else:
            if task.trial_index is not None:
                effective_seed = seed + task.trial_index
                trial_dir_name = f"trial-{task.trial_index:02d}-seed-{effective_seed}"
                experiment_dir_override: Path | None = (
                    Path(state_output_dir) / task.algorithm / trial_dir_name
                )
            else:
                effective_seed = seed
                experiment_dir_override = None

            run_single_algorithm_task(
                state_code=task.state_code,
                algorithm=task.algorithm,
                state_output_dir=Path(state_output_dir),
                n_districts=n_districts,
                seed=effective_seed,
                angle_steps=angle_steps,
                tolerance=tolerance,
                full_artifacts=full_artifacts,
                experiment_dir_override=experiment_dir_override,
            )
            elapsed = time.perf_counter() - started
            result_q.put(_TaskMessage(task=task, status="ok", elapsed_seconds=elapsed))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_run_experiment.py -v`

Expected: all tests pass, including the two new tests and all existing run_experiment tests (single-trial behavior preserved because `trial_index` is None and the `effective_seed = seed` / `experiment_dir_override = None` branch fires).

- [ ] **Step 5: Commit**

```bash
git add src/districtmaker/validate.py tests/test_run_experiment.py
git commit -m "Derive per-trial seed and output path in _worker_main

When task.trial_index is set, effective_seed = base_seed + trial_index
and results land in <state>/<algorithm>/trial-NN-seed-X/. Single-trial
behavior (trial_index=None) is unchanged.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: `record_tier_run` flag on `run_experiment`

**Files:**
- Modify: `src/districtmaker/validate.py:519-663` (the `run_experiment` function)
- Modify: `tests/test_run_experiment.py` (append new test)

Background: `run_experiment` always calls `append_tier_run` at the end, writing a row into the cross-state summary ledger. Multi-start experiments have no states-as-units-of-leadership, so this row would be misleading. Add a flag to skip it.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_run_experiment.py`:

```python
# --- record_tier_run flag ----------------------------------------------------


def test_run_experiment_skips_tier_row_when_record_tier_run_false(tmp_path, monkeypatch) -> None:
    """With record_tier_run=False, no row is appended to summary.json's runs list."""
    from districtmaker.task_graph import ExperimentPlan
    from districtmaker.validate import run_experiment

    # Empty plan to keep the test fast — verifies the flag is respected
    # regardless of how many states were planned.
    plan = ExperimentPlan(states=(), algorithms=())

    run_experiment(
        plan=plan,
        output_dir=tmp_path,
        record_tier_run=False,
    )

    summary_path = tmp_path / "summary.json"
    if summary_path.exists():
        import json
        data = json.loads(summary_path.read_text())
        assert data.get("runs", []) == [], "no tier run row should be appended"
    # If summary.json doesn't exist, that's also acceptable — nothing was written.
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_experiment.py::test_run_experiment_skips_tier_row_when_record_tier_run_false -v`

Expected: `FAILED` with `TypeError: run_experiment() got an unexpected keyword argument 'record_tier_run'`.

- [ ] **Step 3: Implement**

In `src/districtmaker/validate.py`, modify `run_experiment`:

Add the parameter (just before `_cpu_observer`):

```python
def run_experiment(
    plan: ExperimentPlan,
    output_dir: Path,
    *,
    initial_cpu_pct: float = 50.0,
    max_workers: int | None = None,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    force: bool = False,
    seed: int = 42,
    angle_steps: int = 180,
    tolerance: float = 0.005,
    full_artifacts: bool = False,
    tier_name: str | None = None,
    record_tier_run: bool = True,
    log: logging.Logger | None = None,
    _cpu_observer: CpuObserver | None = None,
) -> list[StateResult]:
```

Change the last two lines (currently 661–663) from:

```python
    results = list(state_results.values())
    append_tier_run(output_dir, tier_name, results)
    return results
```

to:

```python
    results = list(state_results.values())
    if record_tier_run:
        append_tier_run(output_dir, tier_name, results)
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_run_experiment.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/districtmaker/validate.py tests/test_run_experiment.py
git commit -m "Add record_tier_run flag to run_experiment

Multi-start invocations don't represent a cross-state tier run, so they
need to suppress the summary.json runs[] row. Default True preserves
existing behavior for all current call sites.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: `build_trial_graph` in `multi_start.py`

**Files:**
- Create: `src/districtmaker/multi_start.py`
- Create: `tests/test_multi_start.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_multi_start.py`:

```python
"""Tests for multi-start trial fan-out and aggregation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from districtmaker.multi_start import build_trial_graph
from districtmaker.task_graph import Task


# --- build_trial_graph -------------------------------------------------------


def test_build_trial_graph_fans_out_state_x_algos_x_trials() -> None:
    """One state × 2 algorithms × 3 trials = 6 tasks, all trial-indexed."""
    graph = build_trial_graph(
        state="TX",
        algorithms=("metis+kl", "splitline-realized+kl"),
        trials=3,
    )

    assert len(graph.tasks) == 6
    indices_per_algo = {"metis+kl": [], "splitline-realized+kl": []}
    for t in graph.tasks:
        assert t.state_code == "TX"
        assert t.trial_index is not None
        assert not t.is_finalization
        indices_per_algo[t.algorithm].append(t.trial_index)

    assert sorted(indices_per_algo["metis+kl"]) == [0, 1, 2]
    assert sorted(indices_per_algo["splitline-realized+kl"]) == [0, 1, 2]


def test_build_trial_graph_has_no_finalization_tasks() -> None:
    """Multi-start graphs do not produce _finalize tasks (no per-state leader)."""
    graph = build_trial_graph(state="TX", algorithms=("metis+kl",), trials=20)
    assert len(graph.tasks) == 20
    assert all(not t.is_finalization for t in graph.tasks)


def test_build_trial_graph_tasks_have_no_dependencies() -> None:
    """Trial tasks are independent."""
    graph = build_trial_graph(state="TX", algorithms=("metis+kl",), trials=5)
    for t in graph.tasks:
        assert graph.dependencies[t] == frozenset()


def test_build_trial_graph_rejects_zero_trials() -> None:
    with pytest.raises(ValueError, match="trials must be >= 1"):
        build_trial_graph(state="TX", algorithms=("metis+kl",), trials=0)


def test_build_trial_graph_rejects_empty_algorithms() -> None:
    with pytest.raises(ValueError, match="at least one algorithm"):
        build_trial_graph(state="TX", algorithms=(), trials=10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_multi_start.py -v`

Expected: all tests `FAILED` with `ModuleNotFoundError: No module named 'districtmaker.multi_start'`.

- [ ] **Step 3: Implement — create `multi_start.py` with `build_trial_graph`**

Create `src/districtmaker/multi_start.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_multi_start.py -v`

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/districtmaker/multi_start.py tests/test_multi_start.py
git commit -m "Add multi_start.build_trial_graph for seed-varied fan-out

One (state, algorithm) → N trial tasks with trial_index set. No
finalization step; aggregation is a separate post-run pass. Reuses the
existing TaskGraph and parallel scheduler.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: `aggregate_results` in `multi_start.py`

**Files:**
- Modify: `src/districtmaker/multi_start.py` (append `aggregate_results`)
- Modify: `tests/test_multi_start.py` (append aggregator tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_multi_start.py`:

```python
# --- aggregate_results -------------------------------------------------------


def _write_fake_trial_metrics(
    output_dir: Path,
    state: str,
    algorithm: str,
    trial_index: int,
    seed: int,
    boundary_km: float,
    max_dev_pct: float = 0.4990,
    runtime_s: float = 200.0,
    status: str = "ok",
) -> None:
    """Helper: write a minimal metrics.json mirroring what
    run_single_algorithm_task emits for one trial."""
    trial_dir = (
        output_dir / state / algorithm /
        f"trial-{trial_index:02d}-seed-{seed}"
    )
    trial_dir.mkdir(parents=True, exist_ok=True)
    metrics = {
        "algorithm": algorithm,
        "seed": seed,
        "trial_index": trial_index,
        "status": status,
        "total_internal_boundary_km": boundary_km,
        "max_abs_deviation_pct": max_dev_pct,
        "runtime_seconds": runtime_s,
    }
    (trial_dir / "metrics.json").write_text(json.dumps(metrics))


def test_aggregate_results_picks_best_per_algorithm(tmp_path) -> None:
    """Best trial = lowest total_internal_boundary_km."""
    from districtmaker.multi_start import aggregate_results

    # Write 3 trials for metis+kl with boundaries 100, 95, 102 → best is trial 1.
    for i, boundary in enumerate([100.0, 95.0, 102.0]):
        _write_fake_trial_metrics(
            tmp_path, "TX", "metis+kl", trial_index=i,
            seed=42 + i, boundary_km=boundary,
        )

    aggregate_results(
        output_dir=tmp_path,
        state="TX",
        algorithms=("metis+kl",),
        trials=3,
        base_seed=42,
    )

    best_path = tmp_path / "TX" / "metis+kl" / "best.json"
    assert best_path.exists()
    best = json.loads(best_path.read_text())
    assert best["best"]["trial_index"] == 1
    assert best["best"]["seed"] == 43
    assert best["best"]["boundary_km"] == 95.0
    assert best["trials"] == 3
    assert best["trials_ok"] == 3
    assert best["trials_failed"] == 0
    assert best["distribution"]["min"] == 95.0
    assert best["distribution"]["max"] == 102.0
    assert best["distribution"]["mean"] == pytest.approx(99.0)


def test_aggregate_results_writes_distributions_json(tmp_path) -> None:
    """distributions.json contains per-trial entries for all algorithms."""
    from districtmaker.multi_start import aggregate_results

    _write_fake_trial_metrics(tmp_path, "TX", "metis+kl", 0, 42, 100.0)
    _write_fake_trial_metrics(tmp_path, "TX", "metis+kl", 1, 43, 95.0)
    _write_fake_trial_metrics(tmp_path, "TX", "splitline-realized+kl", 0, 42, 90.0)
    _write_fake_trial_metrics(tmp_path, "TX", "splitline-realized+kl", 1, 43, 90.0)

    aggregate_results(
        output_dir=tmp_path,
        state="TX",
        algorithms=("metis+kl", "splitline-realized+kl"),
        trials=2,
        base_seed=42,
    )

    dist = json.loads((tmp_path / "distributions.json").read_text())
    assert dist["state"] == "TX"
    assert dist["trials_per_algorithm"] == 2
    assert len(dist["results"]["metis+kl"]) == 2
    assert len(dist["results"]["splitline-realized+kl"]) == 2
    # Sorted by trial_index within each algorithm.
    assert [r["trial_index"] for r in dist["results"]["metis+kl"]] == [0, 1]


def test_aggregate_results_counts_failed_trials(tmp_path) -> None:
    """A failed trial (status != 'ok') contributes to trials_failed and is excluded from distribution."""
    from districtmaker.multi_start import aggregate_results

    _write_fake_trial_metrics(tmp_path, "TX", "metis+kl", 0, 42, 100.0, status="ok")
    _write_fake_trial_metrics(tmp_path, "TX", "metis+kl", 1, 43, 0.0, status="failed")

    aggregate_results(
        output_dir=tmp_path,
        state="TX",
        algorithms=("metis+kl",),
        trials=2,
        base_seed=42,
    )

    best = json.loads((tmp_path / "TX" / "metis+kl" / "best.json").read_text())
    assert best["trials"] == 2
    assert best["trials_ok"] == 1
    assert best["trials_failed"] == 1
    assert best["best"]["boundary_km"] == 100.0
    assert best["distribution"]["min"] == 100.0  # failed trial excluded


def test_aggregate_results_writes_summary_md(tmp_path) -> None:
    """_summary.md contains per-algorithm distribution and best-of-N rows."""
    from districtmaker.multi_start import aggregate_results

    for i, boundary in enumerate([100.0, 95.0, 102.0, 98.0, 99.0]):
        _write_fake_trial_metrics(
            tmp_path, "TX", "metis+kl", trial_index=i,
            seed=42 + i, boundary_km=boundary,
        )

    aggregate_results(
        output_dir=tmp_path,
        state="TX",
        algorithms=("metis+kl",),
        trials=5,
        base_seed=42,
    )

    summary = (tmp_path / "_summary.md").read_text()
    assert "metis+kl" in summary
    assert "95.0" in summary or "95.00" in summary  # best trial
    assert "Best-of-N" in summary  # saturation header
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_multi_start.py -v -k aggregate`

Expected: all 4 aggregator tests `FAILED` with `ImportError: cannot import name 'aggregate_results' from 'districtmaker.multi_start'`.

- [ ] **Step 3: Implement — append `aggregate_results` to `multi_start.py`**

Append to `src/districtmaker/multi_start.py`:

```python
import json
import statistics
from pathlib import Path
from typing import Iterable


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
            dist_stats = {"min": None, "max": None, "mean": None,
                          "median": None, "std": None, "std_pct": None}

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

        # Per-algorithm best.json
        algo_dir = output_dir / state / algo
        algo_dir.mkdir(parents=True, exist_ok=True)
        (algo_dir / "best.json").write_text(json.dumps(best_payload, indent=2))

        distributions[algo] = algo_trials

    # distributions.json (cross-algorithm)
    distributions_payload = {
        "state": state,
        "trials_per_algorithm": trials,
        "base_seed": base_seed,
        "results": distributions,
    }
    (output_dir / "distributions.json").write_text(
        json.dumps(distributions_payload, indent=2)
    )

    # _summary.md (human-readable)
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

    # Distribution table per algorithm.
    lines.append("## Distribution per algorithm")
    lines.append("")
    lines.append("| Algorithm | Trials OK / N | Min (km) | Max (km) | Mean (km) | Median (km) | Std (km) | Std (%) |")
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

    # Best-of-N saturation curve.
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
        lines.append(f"| {algo} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {cells[4]} |")
    lines.append("")

    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_multi_start.py -v`

Expected: all tests pass (5 graph tests + 4 aggregator tests = 9 total).

- [ ] **Step 5: Commit**

```bash
git add src/districtmaker/multi_start.py tests/test_multi_start.py
git commit -m "Add aggregate_results for multi-start post-run summarization

Scans completed trial dirs, writes per-algorithm best.json with
distribution stats, distributions.json (machine-readable cross-algorithm),
and _summary.md (human-readable: distribution table + best-of-N
saturation curve).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: `multi-start` CLI subcommand

**Files:**
- Modify: `src/districtmaker/cli.py`
- Modify: `tests/test_cli.py` (append CLI test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`:

```python
# --- multi-start subcommand --------------------------------------------------


def test_multi_start_subcommand_invokes_runner_and_aggregator(tmp_path, monkeypatch) -> None:
    """`districtmaker multi-start --state TX --algorithms metis+kl --trials 3 ...`
    builds the right graph, calls run_experiment with record_tier_run=False,
    and then calls aggregate_results."""
    from districtmaker.cli import cli

    captured = {}

    def fake_run_experiment(
        *, plan, output_dir, record_tier_run, seed, full_artifacts,
        state, algorithms, trials, **kwargs,
    ):
        captured["plan_states"] = plan.states
        captured["plan_algorithms"] = plan.algorithms
        captured["record_tier_run"] = record_tier_run
        captured["seed"] = seed
        captured["full_artifacts"] = full_artifacts
        captured["state"] = state
        captured["algorithms"] = algorithms
        captured["trials"] = trials

    # The multi-start command should call run_experiment with a pre-built
    # graph, not with an ExperimentPlan. We patch the call surface the
    # command uses — see the implementation step for the exact path.
    monkeypatch.setattr(
        "districtmaker.cli._run_multi_start_experiment", fake_run_experiment,
    )

    def fake_aggregate(**kwargs):
        captured["aggregated"] = True
        captured["aggregate_state"] = kwargs["state"]
        captured["aggregate_algorithms"] = kwargs["algorithms"]
        captured["aggregate_trials"] = kwargs["trials"]
        captured["aggregate_base_seed"] = kwargs["base_seed"]
        return {"distributions": {}, "bests": {}}

    monkeypatch.setattr("districtmaker.cli.aggregate_results", fake_aggregate)

    runner = CliRunner()
    result = runner.invoke(cli, [
        "multi-start",
        "--state", "TX",
        "--algorithms", "metis+kl",
        "--trials", "3",
        "--base-seed", "42",
        "--cpu", "75",
        "--output", str(tmp_path / "out"),
    ])

    assert result.exit_code == 0, result.output
    assert captured["aggregated"] is True
    assert captured["aggregate_state"] == "TX"
    assert captured["aggregate_algorithms"] == ("metis+kl",)
    assert captured["aggregate_trials"] == 3
    assert captured["aggregate_base_seed"] == 42


def test_multi_start_rejects_unknown_state() -> None:
    """Invalid state codes fail validation before any work runs."""
    from districtmaker.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, [
        "multi-start",
        "--state", "ZZ",  # not a real state
        "--algorithms", "metis+kl",
        "--trials", "1",
        "--output", "/tmp/should-not-be-created",
    ])

    assert result.exit_code != 0
    assert "ZZ" in result.output or "unknown" in result.output.lower()


def test_multi_start_rejects_unknown_algorithm() -> None:
    from districtmaker.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, [
        "multi-start",
        "--state", "TX",
        "--algorithms", "fake-algorithm",
        "--trials", "1",
        "--output", "/tmp/should-not-be-created",
    ])

    assert result.exit_code != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v -k multi_start`

Expected: all `FAILED` — the `multi-start` subcommand does not exist.

- [ ] **Step 3: Implement — add `multi-start` to `cli.py`**

In `src/districtmaker/cli.py`, add the following imports near the top (where other district maker imports live):

```python
from districtmaker.multi_start import aggregate_results, build_trial_graph
from districtmaker.task_graph import TaskGraph
```

Then add a small helper just above the new subcommand (so tests can monkeypatch a single seam):

```python
def _run_multi_start_experiment(
    *, plan, output_dir, record_tier_run, seed, full_artifacts,
    state: str, algorithms: tuple[str, ...], trials: int, **kwargs,
):
    """Indirection seam for the multi-start command.

    The CLI builds its task graph directly (no ExperimentPlan fan-out),
    so it can't reuse the same call shape as `validate`. This helper
    is the single surface tests monkeypatch; in production it builds the
    trial graph and forwards to `run_experiment` with `graph_override`.
    """
    from districtmaker.validate import run_experiment
    graph = build_trial_graph(state=state, algorithms=algorithms, trials=trials)
    return run_experiment(
        plan=plan,
        output_dir=output_dir,
        record_tier_run=record_tier_run,
        seed=seed,
        full_artifacts=full_artifacts,
        graph_override=graph,
        **kwargs,
    )
```

Then add the `multi-start` subcommand. Locate the existing `cli` group and add this command alongside `validate`:

```python
@cli.command("multi-start")
@click.option("--state", required=True, type=str,
              help="Single state code (e.g. TX).")
@click.option("--algorithms", required=True, type=str,
              help="Comma-separated algorithms (e.g. metis+kl,splitline-realized+kl).")
@click.option("--trials", required=True, type=int,
              help="Number of trials per algorithm.")
@click.option("--base-seed", type=int, default=42, show_default=True,
              help="seed_i = base_seed + i for i in 0..trials-1.")
@click.option("--output", required=True,
              type=click.Path(file_okay=False, path_type=Path),
              help="Output directory for this experiment.")
@click.option("--cpu", type=click.FloatRange(1.0, 100.0), default=None,
              help="Target CPU percentage cap (parallel mode). Required for multi-start.")
@click.option("--max-workers", type=int, default=None,
              help="Hard ceiling on concurrent trials.")
@click.option("--poll-seconds", type=float, default=3.0, show_default=True,
              help="Scheduler poll interval.")
@click.option("--tolerance", type=float, default=0.005, show_default=True)
@click.option("--full-artifacts/--light-artifacts", default=True, show_default=True,
              help="Default --full-artifacts: emit geojson + shapefile for every trial.")
@click.option("--force/--skip-existing", default=False, show_default=True,
              help="Re-run trials whose metrics.json already exists.")
def multi_start_cmd(
    state: str,
    algorithms: str,
    trials: int,
    base_seed: int,
    output: Path,
    cpu: float | None,
    max_workers: int | None,
    poll_seconds: float,
    tolerance: float,
    full_artifacts: bool,
    force: bool,
) -> None:
    """Run a multi-start (seed-varied) experiment for one state.

    Each algorithm runs `trials` times with seeds `base_seed`, `base_seed+1`,
    ..., `base_seed + trials - 1`. Aggregated outputs land in `output/`.
    """
    from districtmaker.compare import ALGORITHM_NAMES
    from districtmaker.data.census import districts_for_state
    from districtmaker.task_graph import ExperimentPlan

    state = state.upper()
    try:
        districts_for_state(state)
    except KeyError as exc:
        raise click.BadParameter(f"unknown state: {state}") from exc

    algos = tuple(a.strip() for a in algorithms.split(",") if a.strip())
    unknown = [a for a in algos if a not in ALGORITHM_NAMES]
    if unknown:
        raise click.BadParameter(f"unknown algorithm(s): {', '.join(unknown)}")

    if cpu is None:
        raise click.BadParameter("--cpu is required for multi-start (parallel mode)")

    if trials < 1:
        raise click.BadParameter("--trials must be >= 1")

    output.mkdir(parents=True, exist_ok=True)

    # Multi-start uses an ad-hoc graph, not an ExperimentPlan with finalize
    # tasks. We still pass an (effectively empty) plan to run_experiment for
    # compatibility — the real fan-out comes from the graph we attach via
    # the runner seam.
    plan = ExperimentPlan(states=(state,), algorithms=algos)

    _run_multi_start_experiment(
        plan=plan,
        output_dir=output,
        record_tier_run=False,
        seed=base_seed,
        full_artifacts=full_artifacts,
        state=state,
        algorithms=algos,
        trials=trials,
        initial_cpu_pct=cpu,
        max_workers=max_workers,
        poll_seconds=poll_seconds,
        tolerance=tolerance,
        force=force,
    )

    aggregate_results(
        output_dir=output,
        state=state,
        algorithms=algos,
        trials=trials,
        base_seed=base_seed,
    )

    click.echo(f"multi-start complete. results in {output}/")
```

**IMPORTANT — graph wiring note for implementer:** `run_experiment` currently builds its own graph from the `ExperimentPlan` via `build_graph(effective_plan)` (validate.py around line 552). For multi-start we need the trial graph instead. The minimum-invasive way is to add a `graph_override: TaskGraph | None = None` parameter to `run_experiment` that, when set, replaces the internally-built graph. Make that change in this task (it's small):

In `src/districtmaker/validate.py`, change the `run_experiment` signature once more:

```python
def run_experiment(
    plan: ExperimentPlan,
    output_dir: Path,
    *,
    initial_cpu_pct: float = 50.0,
    max_workers: int | None = None,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    force: bool = False,
    seed: int = 42,
    angle_steps: int = 180,
    tolerance: float = 0.005,
    full_artifacts: bool = False,
    tier_name: str | None = None,
    record_tier_run: bool = True,
    graph_override: TaskGraph | None = None,
    log: logging.Logger | None = None,
    _cpu_observer: CpuObserver | None = None,
) -> list[StateResult]:
```

Change the graph-building block (currently around lines 548–552) from:

```python
    targets = list(plan.states)
    if not force:
        targets = [s for s in targets if not (output_dir / s / "leader.json").exists()]
    effective_plan = ExperimentPlan(states=tuple(targets), algorithms=plan.algorithms)
    graph = build_graph(effective_plan)
```

to:

```python
    if graph_override is not None:
        graph = graph_override
    else:
        targets = list(plan.states)
        if not force:
            targets = [s for s in targets if not (output_dir / s / "leader.json").exists()]
        effective_plan = ExperimentPlan(states=tuple(targets), algorithms=plan.algorithms)
        graph = build_graph(effective_plan)
```

The `_run_multi_start_experiment` helper and the `multi_start_cmd` call site defined above already pass `state`, `algorithms`, and `trials` through to the trial-graph builder. No further edits to those bodies are needed in this step.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v -k multi_start && pytest -v`

Expected: the three new CLI tests pass, and the full test suite still passes (no regressions).

- [ ] **Step 5: Commit**

```bash
git add src/districtmaker/cli.py src/districtmaker/validate.py tests/test_cli.py
git commit -m "Add districtmaker multi-start CLI subcommand

Wires the trial graph builder, parallel scheduler, and aggregator into
a single command:

  districtmaker multi-start --state TX --algorithms metis+kl,splitline-realized+kl \\
    --trials 20 --base-seed 42 --cpu 75 --output outputs/_multi-start/...

Requires --cpu (multi-start is parallel-only). Adds graph_override to
run_experiment so callers can supply a pre-built TaskGraph; default
behavior unchanged.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: End-to-end integration smoke test

**Files:**
- Modify: `tests/test_multi_start.py` (append integration test)

This test exercises the full pipeline against a tiny fake state — proves that all the pieces fit together: trial graph → worker → per-trial metrics.json → aggregator → distributions.json.

- [ ] **Step 1: Write the integration test**

Append to `tests/test_multi_start.py`:

```python
# --- end-to-end integration --------------------------------------------------


def test_end_to_end_multi_start_writes_aggregated_outputs(tmp_path, monkeypatch) -> None:
    """Full pipeline: graph → run_experiment (with fakes) → aggregate_results.

    Uses fake state/adjacency loaders so the test runs in milliseconds.
    Verifies that:
    - 3 trials per algorithm produce 3 trial dirs each
    - effective_seed varies per trial
    - distributions.json and best.json both materialize
    """
    import numpy as np
    from districtmaker.multi_start import build_trial_graph, aggregate_results
    from districtmaker.task_graph import ExperimentPlan
    from districtmaker.validate import run_experiment
    from tests.test_experiments import _fake_state_data

    fake_state = _fake_state_data()
    fake_edges = np.array([[0, 1]], dtype=np.int64)
    fake_lengths = np.array([1.0], dtype=np.float64)

    monkeypatch.setattr("districtmaker.experiments.load_state",
                        lambda code: fake_state)
    monkeypatch.setattr("districtmaker.experiments.get_adjacency",
                        lambda code, blocks: (fake_edges, fake_lengths))
    monkeypatch.setattr("districtmaker.experiments.districts_for_state",
                        lambda s: 2)

    state = "AA"  # fake state code from _fake_state_loader
    graph = build_trial_graph(state=state, algorithms=("metis",), trials=3)
    plan = ExperimentPlan(states=(state,), algorithms=("metis",))

    run_experiment(
        plan=plan,
        output_dir=tmp_path,
        graph_override=graph,
        record_tier_run=False,
        seed=42,
        full_artifacts=False,
        initial_cpu_pct=95.0,  # high cap so trials dispatch fast in test
        poll_seconds=0.05,
    )

    # Three trial dirs should exist.
    for i in range(3):
        trial_dir = tmp_path / state / "metis" / f"trial-{i:02d}-seed-{42 + i}"
        assert trial_dir.exists(), f"missing trial dir: {trial_dir}"
        assert (trial_dir / "metrics.json").exists(), f"missing metrics.json: {trial_dir}"

    aggregate_results(
        output_dir=tmp_path,
        state=state,
        algorithms=("metis",),
        trials=3,
        base_seed=42,
    )

    assert (tmp_path / "distributions.json").exists()
    assert (tmp_path / state / "metis" / "best.json").exists()
    assert (tmp_path / "_summary.md").exists()
```

- [ ] **Step 2: Run test to verify it passes (it should, given the previous tasks)**

Run: `pytest tests/test_multi_start.py::test_end_to_end_multi_start_writes_aggregated_outputs -v`

Expected: PASS. If it fails, the failure points to whichever previous task's seam didn't quite fit. Triage from there — do not paper over by mocking.

If `tests/test_experiments.py` doesn't expose `_fake_state_loader` / `_fake_adjacency_loader` as module-level names, look at how `tests/test_experiments.py` constructs its fakes inside test functions, and lift them to module-level conftest-style fixtures or duplicate them at the top of `tests/test_multi_start.py`. Reuse first; duplicate as a fallback. Do not invent new fakes — they may not match the production interfaces.

- [ ] **Step 3: Run the full test suite**

Run: `pytest -v`

Expected: all tests pass. No regressions in any existing test file.

- [ ] **Step 4: Commit**

```bash
git add tests/test_multi_start.py
git commit -m "Add end-to-end smoke test for multi-start pipeline

Exercises build_trial_graph → run_experiment → aggregate_results on a
fake state. Confirms trial dirs, metrics.json, and aggregated outputs
all materialize in the expected layout.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Final Verification

- [ ] **Step 1: Run the full test suite one more time**

Run: `pytest -v`

Expected: all tests pass. Note the count.

- [ ] **Step 2: Confirm CLI surface**

Run: `districtmaker multi-start --help`

Expected: help text appears, lists all options (`--state`, `--algorithms`, `--trials`, `--base-seed`, `--cpu`, `--max-workers`, `--poll-seconds`, `--tolerance`, `--output`, `--full-artifacts/--light-artifacts`, `--force/--skip-existing`).

- [ ] **Step 3: Confirm validate is unchanged**

Run: `districtmaker validate --help`

Expected: identical to pre-plan output (same options, same defaults). No regressions to the existing surface.

- [ ] **Step 4: Confirm validate-ctl is unchanged**

Run: `districtmaker validate-ctl --help`

Expected: identical to pre-plan output.

---

## What This Plan Deliberately Does NOT Do

- No experiment run, no TX trials, no real data. Plan B covers all of that.
- No changes to the leader ledger format (`outputs/summary.md`) or `finalize_state` semantics. Multi-start is a separate output universe.
- No tests against the real `metis` or `splitline-realized+kl` algorithms inside trials — those are exercised by their own existing test suites. The integration smoke test uses fake state/adjacency loaders and exercises `metis` only.
- No updates to `docs/open-questions.md`. That edit happens in Plan B's writeup step, after the experiment lands findings.
