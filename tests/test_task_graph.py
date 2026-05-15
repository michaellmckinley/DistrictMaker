"""Tests for src/districtmaker/task_graph.py — DAG over (state, algorithm) tasks."""
from __future__ import annotations

from districtmaker.task_graph import (
    ExperimentPlan,
    Task,
    build_graph,
)


def test_plan_expands_into_algorithm_tasks_per_state() -> None:
    plan = ExperimentPlan(
        states=("ID", "MT"),
        algorithms=("metis", "metis+kl"),
    )
    graph = build_graph(plan)

    algorithm_tasks = [t for t in graph.tasks if not t.is_finalization]
    assert set(algorithm_tasks) == {
        Task("ID", "metis"),
        Task("ID", "metis+kl"),
        Task("MT", "metis"),
        Task("MT", "metis+kl"),
    }


def test_plan_adds_one_finalization_task_per_state() -> None:
    plan = ExperimentPlan(states=("ID", "MT"), algorithms=("metis",))
    graph = build_graph(plan)

    finalizations = [t for t in graph.tasks if t.is_finalization]
    assert set(finalizations) == {
        Task("ID", "_finalize"),
        Task("MT", "_finalize"),
    }


def test_initially_algorithm_tasks_are_ready_and_finalization_is_pending() -> None:
    plan = ExperimentPlan(states=("ID",), algorithms=("metis", "splitline-realized"))
    graph = build_graph(plan)

    ready = set(graph.ready_tasks())
    assert ready == {Task("ID", "metis"), Task("ID", "splitline-realized")}
    assert graph.status(Task("ID", "_finalize")) == "pending"


def test_marking_running_removes_task_from_ready() -> None:
    plan = ExperimentPlan(states=("ID",), algorithms=("metis",))
    graph = build_graph(plan)

    t = Task("ID", "metis")
    graph.mark_running(t)
    assert t not in graph.ready_tasks()
    assert graph.status(t) == "running"


def test_finalization_becomes_ready_when_all_state_algorithms_done() -> None:
    plan = ExperimentPlan(states=("ID",), algorithms=("metis", "splitline-realized"))
    graph = build_graph(plan)
    finalize = Task("ID", "_finalize")

    graph.mark_running(Task("ID", "metis"))
    graph.mark_done(Task("ID", "metis"))
    assert finalize not in graph.ready_tasks()    # one still pending

    graph.mark_running(Task("ID", "splitline-realized"))
    graph.mark_done(Task("ID", "splitline-realized"))
    assert finalize in graph.ready_tasks()


def test_finalization_runs_even_if_some_algorithms_failed() -> None:
    """A failed algorithm shouldn't block leader computation —
    leader.md handles failed entries explicitly."""
    plan = ExperimentPlan(states=("ID",), algorithms=("metis", "splitline-chord"))
    graph = build_graph(plan)
    finalize = Task("ID", "_finalize")

    graph.mark_running(Task("ID", "metis"))
    graph.mark_done(Task("ID", "metis"))
    graph.mark_running(Task("ID", "splitline-chord"))
    graph.mark_failed(Task("ID", "splitline-chord"), "RuntimeError: no valid cut")

    assert finalize in graph.ready_tasks()
    assert graph.status(Task("ID", "splitline-chord")) == "failed"


def test_all_done_only_when_every_task_in_terminal_state() -> None:
    plan = ExperimentPlan(states=("ID",), algorithms=("metis",))
    graph = build_graph(plan)
    assert not graph.all_done()

    graph.mark_running(Task("ID", "metis"))
    graph.mark_done(Task("ID", "metis"))
    assert not graph.all_done()       # finalization still pending

    graph.mark_running(Task("ID", "_finalize"))
    graph.mark_done(Task("ID", "_finalize"))
    assert graph.all_done()
