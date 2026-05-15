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
