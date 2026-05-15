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
    """A failed trial (status != 'ok') contributes to trials_failed
    and is excluded from distribution."""
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
