"""Tests for the experiment-record framework."""
from __future__ import annotations

import json
import math

import geopandas as gpd
from shapely.geometry import Polygon

from unittest.mock import patch

from districtmaker.compare import AlgoResult
from districtmaker.data.loader import StateData
from districtmaker.experiments import CRITERION, compute_leader, run_state_experiments, write_state_record


def _ok(name: str, km: float, dev: float = 0.01, runtime: float = 1.0) -> AlgoResult:
    return AlgoResult(
        name=name,
        districts=None,
        runtime_seconds=runtime,
        total_internal_boundary_km=km,
        max_abs_deviation_pct=dev,
        polsby_popper=[],
        reock=[],
        convex_hull_ratio=[],
    )


def _failed(name: str, error: str = "RuntimeError: boom") -> AlgoResult:
    return AlgoResult(
        name=name,
        districts=None,
        runtime_seconds=0.5,
        total_internal_boundary_km=float("inf"),
        max_abs_deviation_pct=float("nan"),
        polsby_popper=[],
        reock=[],
        convex_hull_ratio=[],
        error=error,
    )


def test_compute_leader_picks_shortest_boundary():
    report = compute_leader([
        _ok("splitline-realized+kl", 1548.24),
        _ok("metis+kl", 1375.33),
        _ok("annealing-from-kl", 1548.24),
    ])
    assert report.leader == "metis+kl"
    assert report.criterion == CRITERION
    assert report.ranking[0].experiment == "metis+kl"
    assert report.ranking[0].rank == 1
    assert report.ranking[0].gap_to_leader_pct == 0.0
    # runner-up gap pinned to the exact computed value
    assert math.isclose(report.ranking[1].gap_to_leader_pct, 12.572, rel_tol=1e-3)


def test_compute_leader_breaks_ties_by_population_deviation():
    report = compute_leader([
        _ok("a", 1000.0, dev=0.40),
        _ok("b", 1000.0, dev=0.10),
    ])
    assert report.leader == "b"


def test_compute_leader_lists_failures_with_null_rank():
    report = compute_leader([
        _ok("metis+kl", 900.0),
        _failed("splitline-chord", "RuntimeError: No valid cut found"),
    ])
    assert report.leader == "metis+kl"
    failed = [e for e in report.ranking if e.status == "failed"]
    assert len(failed) == 1
    assert failed[0].experiment == "splitline-chord"
    assert failed[0].rank is None
    assert failed[0].gap_to_leader_pct is None
    assert "No valid cut" in failed[0].error


def test_compute_leader_handles_all_failed():
    report = compute_leader([
        _failed("splitline-chord"),
        _failed("metis"),
    ])
    assert report.leader is None
    assert all(e.rank is None for e in report.ranking)


def _districts_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"district_id": [0, 1], "pop": [1000, 1000]},
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
        ],
        crs="EPSG:5070",
    )


def _ok_with_districts(name: str, km: float, dev: float = 0.01) -> AlgoResult:
    return AlgoResult(
        name=name,
        districts=_districts_gdf(),
        runtime_seconds=2.0,
        total_internal_boundary_km=km,
        max_abs_deviation_pct=dev,
        polsby_popper=[0.4, 0.5],
        reock=[0.3, 0.4],
        convex_hull_ratio=[0.9, 0.95],
    )


_STATE_INFO = {
    "code": "TT",
    "name": "Testlandia",
    "fips": "99",
    "n_districts": 2,
    "block_count": 100,
    "total_population": 2000,
}


def test_write_state_record_creates_experiment_folders(tmp_path):
    results = [
        _ok_with_districts("splitline-realized+kl", 1200.0),
        _ok_with_districts("metis+kl", 1000.0),
        _failed("splitline-chord", "RuntimeError: No valid cut found"),
    ]
    report = write_state_record(tmp_path, results, _STATE_INFO, seed=42)

    # Every experiment has a folder.
    assert (tmp_path / "experiments" / "splitline-realized+kl" / "districts.png").exists()
    assert (tmp_path / "experiments" / "splitline-realized+kl" / "metrics.json").exists()
    assert (tmp_path / "experiments" / "splitline-realized+kl" / "run.log").exists()
    assert (tmp_path / "experiments" / "metis+kl" / "metrics.json").exists()
    # Light bundle by default: no per-experiment geojson/shapefile.
    assert not (tmp_path / "experiments" / "metis+kl" / "districts.geojson").exists()
    # Failed experiment: folder with only run.log.
    chord_dir = tmp_path / "experiments" / "splitline-chord"
    assert (chord_dir / "run.log").exists()
    assert not (chord_dir / "metrics.json").exists()
    assert "No valid cut" in (chord_dir / "run.log").read_text()

    assert report.leader == "metis+kl"


def test_write_state_record_promotes_leader_bundle_to_root(tmp_path):
    results = [
        _ok_with_districts("splitline-realized+kl", 1200.0),
        _ok_with_districts("metis+kl", 1000.0),
    ]
    write_state_record(tmp_path, results, _STATE_INFO, seed=42)

    # Leader's FULL bundle at the state root.
    assert (tmp_path / "districts.geojson").exists()
    assert (tmp_path / "districts.shp").exists()
    assert (tmp_path / "districts.png").exists()
    assert (tmp_path / "metrics.json").exists()
    assert (tmp_path / "run.log").exists()
    root_metrics = json.loads((tmp_path / "metrics.json").read_text())
    assert root_metrics["algorithm"] == "metis+kl"


def test_write_state_record_writes_leader_files(tmp_path):
    results = [
        _ok_with_districts("splitline-realized+kl", 1200.0),
        _ok_with_districts("metis+kl", 1000.0),
        _failed("splitline-chord"),
    ]
    write_state_record(tmp_path, results, _STATE_INFO, seed=42)

    leader_json = json.loads((tmp_path / "leader.json").read_text())
    assert leader_json["leader"] == "metis+kl"
    assert leader_json["state"]["code"] == "TT"
    assert leader_json["trials_per_experiment"] == 1
    assert "generated_at" in leader_json
    assert len(leader_json["ranking"]) == 3

    leader_md = (tmp_path / "leader.md").read_text()
    assert "Testlandia" in leader_md
    assert "metis+kl" in leader_md
    assert "current leader" in leader_md.lower()
    assert "splitline-chord" in leader_md
    assert "FAILED" in leader_md


def test_write_state_record_full_artifacts_emits_per_experiment_geojson(tmp_path):
    results = [_ok_with_districts("metis+kl", 1000.0)]
    write_state_record(tmp_path, results, _STATE_INFO, seed=42, full_artifacts=True)
    assert (tmp_path / "experiments" / "metis+kl" / "districts.geojson").exists()
    assert (tmp_path / "experiments" / "metis+kl" / "districts.shp").exists()


def test_write_state_record_all_failed_writes_no_root_bundle(tmp_path):
    results = [_failed("splitline-chord"), _failed("metis")]
    report = write_state_record(tmp_path, results, _STATE_INFO, seed=42)
    assert report.leader is None
    assert not (tmp_path / "districts.geojson").exists()
    assert (tmp_path / "leader.json").exists()
    leader_json = json.loads((tmp_path / "leader.json").read_text())
    assert leader_json["leader"] is None


def test_write_state_record_empty_results(tmp_path):
    report = write_state_record(tmp_path, [], _STATE_INFO, seed=42)
    assert report.leader is None
    assert not (tmp_path / "districts.geojson").exists()
    leader_json = json.loads((tmp_path / "leader.json").read_text())
    assert leader_json["leader"] is None
    assert leader_json["ranking"] == []


def _fake_state_data() -> StateData:
    state_geom = gpd.GeoDataFrame(
        {"NAME": ["Testlandia"], "STATEFP": ["99"], "STUSPS": ["TT"]},
        geometry=[Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])],
        crs="EPSG:5070",
    )
    blocks_geom = [
        Polygon([(ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)])
        for ix in range(10)
        for iy in range(10)
    ]
    blocks = gpd.GeoDataFrame(
        {"pop": [100] * 100, "GEOID20": [f"99{i:08d}" for i in range(100)]},
        geometry=blocks_geom,
        crs="EPSG:5070",
    )
    return StateData(
        code="TT", name="Testlandia", fips="99", geometry=state_geom, blocks=blocks
    )


def test_run_state_experiments_writes_record_and_returns_report(tmp_path):
    import numpy as np

    fake_results = [
        _ok_with_districts("splitline-realized+kl", 1200.0),
        _ok_with_districts("metis+kl", 1000.0),
    ]
    with patch("districtmaker.experiments.load_state", return_value=_fake_state_data()), \
         patch(
             "districtmaker.experiments.get_adjacency",
             return_value=(np.zeros((0, 2), dtype=np.int64), np.zeros(0)),
         ), \
         patch("districtmaker.experiments.run_all", return_value=fake_results) as mock_run_all, \
         patch("districtmaker.experiments.districts_for_state", return_value=2):
        report = run_state_experiments("tt", tmp_path / "TT", seed=42)

    assert mock_run_all.call_count == 1
    _, run_all_kwargs = mock_run_all.call_args
    assert run_all_kwargs["seed"] == 42
    assert run_all_kwargs["angle_steps"] == 180
    assert run_all_kwargs["tolerance"] == 0.005
    assert report.leader == "metis+kl"
    assert (tmp_path / "TT" / "leader.json").exists()
    assert (tmp_path / "TT" / "experiments" / "splitline-realized+kl" / "metrics.json").exists()
    assert (tmp_path / "TT" / "districts.geojson").exists()


def test_run_state_experiments_all_failed_returns_no_leader(tmp_path):
    import numpy as np

    fake_results = [_failed("splitline-chord"), _failed("metis")]
    with patch("districtmaker.experiments.load_state", return_value=_fake_state_data()), \
         patch(
             "districtmaker.experiments.get_adjacency",
             return_value=(np.zeros((0, 2), dtype=np.int64), np.zeros(0)),
         ), \
         patch("districtmaker.experiments.run_all", return_value=fake_results), \
         patch("districtmaker.experiments.districts_for_state", return_value=2):
        report = run_state_experiments("tt", tmp_path / "TT", seed=42)

    assert report.leader is None
    assert (tmp_path / "TT" / "leader.json").exists()
    assert not (tmp_path / "TT" / "districts.geojson").exists()


# --- experiment_dir_override -------------------------------------------------


def test_run_single_algorithm_task_honors_experiment_dir_override(tmp_path):
    """When experiment_dir_override is set, results land there, not in
    <state>/experiments/<algo>."""
    import numpy as np
    from districtmaker.experiments import run_single_algorithm_task

    state_dir = tmp_path / "TX"
    override = tmp_path / "custom" / "trial-00-seed-42"
    fake_state = _fake_state_data()
    fake_adj = (np.zeros((0, 2), dtype=np.int64), np.zeros(0))
    fake_result = _ok_with_districts("metis", 100.0)

    with patch("districtmaker.experiments.run_one_algorithm", return_value=fake_result):
        result = run_single_algorithm_task(
            state_code="tt",
            algorithm="metis",
            state_output_dir=state_dir,
            seed=42,
            n_districts=2,
            state_loader=lambda code: fake_state,
            adjacency_loader=lambda code, blocks: fake_adj,
            experiment_dir_override=override,
        )

    assert override.exists(), "override dir should be created"
    assert (override / "metrics.json").exists(), "metrics.json should be in override dir"
    assert not (state_dir / "experiments" / "metis").exists(), "default path must be skipped"
    assert result.succeeded
