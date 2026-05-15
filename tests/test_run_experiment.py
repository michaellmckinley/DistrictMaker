"""Tests for the controller loop in validate.run_experiment.

Most of the controller is I/O (subprocesses, queues, file polling). The
scheduling *decision* layer — given current graph state, scheduler state,
and CPU readings, return the tasks to dispatch this tick — is a pure
function and is tested here.
"""
from __future__ import annotations

from districtmaker.scheduler import SchedulerState
from districtmaker.task_graph import ExperimentPlan, Task, build_graph
from districtmaker.validate import decide_dispatch


def _graph(states=("ID",), algorithms=("metis", "metis+kl")):
    return build_graph(ExperimentPlan(states=states, algorithms=algorithms))


def test_no_dispatch_when_paused():
    graph = _graph()
    sched = SchedulerState(target_cpu_pct=100.0, paused=True)
    picks = decide_dispatch(graph, live=set(), sched=sched, observed_cpu=0.0)
    assert picks == []


def test_no_dispatch_when_frozen():
    graph = _graph()
    sched = SchedulerState(target_cpu_pct=100.0, freeze=True)
    picks = decide_dispatch(graph, live=set(), sched=sched, observed_cpu=0.0)
    assert picks == []


def test_no_dispatch_when_above_cpu_cap():
    graph = _graph()
    sched = SchedulerState(target_cpu_pct=50.0)
    picks = decide_dispatch(graph, live=set(), sched=sched, observed_cpu=80.0)
    assert picks == []


def test_dispatch_one_ready_task_per_tick_when_under_cap():
    graph = _graph()
    sched = SchedulerState(target_cpu_pct=80.0)
    picks = decide_dispatch(graph, live=set(), sched=sched, observed_cpu=10.0)
    assert len(picks) == 1
    assert picks[0] in graph.ready_tasks()


def test_no_dispatch_when_max_workers_reached():
    graph = _graph()
    sched = SchedulerState(target_cpu_pct=80.0, max_workers=2)
    one = Task("ID", "metis")
    two = Task("ID", "metis+kl")
    picks = decide_dispatch(graph, live={one, two}, sched=sched, observed_cpu=10.0)
    assert picks == []


def test_no_dispatch_when_no_ready_tasks():
    """All algorithm tasks running; finalization still gated on their completion."""
    graph = _graph()
    sched = SchedulerState(target_cpu_pct=80.0, max_workers=None)
    metis = Task("ID", "metis")
    metis_kl = Task("ID", "metis+kl")
    graph.mark_running(metis)
    graph.mark_running(metis_kl)
    picks = decide_dispatch(graph, live={metis, metis_kl}, sched=sched, observed_cpu=10.0)
    assert picks == []


# --- multi-start worker path/seed derivation ---------------------------------


def test_worker_main_derives_trial_seed_and_path(tmp_path, monkeypatch) -> None:
    """When task.trial_index is set, _worker_main derives effective_seed
    and writes to <state>/<algo>/trial-NN-seed-X/."""
    import multiprocessing as mp
    from pathlib import Path

    from districtmaker.task_graph import Task
    from districtmaker.validate import _worker_main

    captured = {}

    def fake_run_single(**kwargs):
        captured["seed"] = kwargs["seed"]
        captured["experiment_dir_override"] = kwargs.get("experiment_dir_override")
        return None

    monkeypatch.setattr(
        "districtmaker.validate.run_single_algorithm_task", fake_run_single
    )

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
    assert captured["experiment_dir_override"] == Path(state_dir) / "metis+kl" / "trial-07-seed-49"


def test_worker_main_single_trial_preserves_behavior(tmp_path, monkeypatch) -> None:
    """When task.trial_index is None, no override is passed (existing behavior)."""
    import multiprocessing as mp

    from districtmaker.task_graph import Task
    from districtmaker.validate import _worker_main

    captured = {}

    def fake_run_single(**kwargs):
        captured["seed"] = kwargs["seed"]
        captured["experiment_dir_override"] = kwargs.get("experiment_dir_override")
        return None

    monkeypatch.setattr(
        "districtmaker.validate.run_single_algorithm_task", fake_run_single
    )

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


# --- record_tier_run flag ----------------------------------------------------


def test_run_experiment_skips_tier_row_when_record_tier_run_false(tmp_path) -> None:
    """With record_tier_run=False, no row is appended to summary.json's runs list."""
    import json
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
        data = json.loads(summary_path.read_text())
        assert data.get("runs", []) == [], "no tier run row should be appended"
    # If summary.json doesn't exist, that's also acceptable — nothing was written.
