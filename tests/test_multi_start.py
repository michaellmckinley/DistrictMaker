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
    indices_per_algo: dict[str, list[int]] = {
        "metis+kl": [],
        "splitline-realized+kl": [],
    }
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
