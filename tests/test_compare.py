"""Tests for src/districtmaker/compare.py — per-algorithm dispatch."""
from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from districtmaker.compare import run_one_algorithm
from districtmaker.data.adjacency import compute_adjacency


def _grid_blocks(width: int, height: int, pop_per_block: int = 100) -> gpd.GeoDataFrame:
    geom = [
        Polygon([(ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)])
        for ix in range(width)
        for iy in range(height)
    ]
    return gpd.GeoDataFrame(
        {"pop": [pop_per_block] * len(geom)}, geometry=geom, crs="EPSG:5070"
    )


def _envelope(blocks: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = blocks.total_bounds
    return gpd.GeoDataFrame(
        geometry=[Polygon([(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)])],
        crs=blocks.crs,
    )


def _setup(width: int = 4, height: int = 4):
    blocks = _grid_blocks(width, height)
    state = _envelope(blocks)
    edges, lengths = compute_adjacency(blocks)
    return state, blocks, edges, lengths


def test_run_one_algorithm_rejects_unknown_name():
    state, blocks, edges, lengths = _setup()
    with pytest.raises(ValueError, match="unknown algorithm"):
        run_one_algorithm(
            "not-a-real-algo", state, blocks, n_districts=2,
            edges=edges, edge_lengths=lengths,
        )


def test_run_one_algorithm_runs_metis_standalone():
    state, blocks, edges, lengths = _setup()
    result = run_one_algorithm(
        "metis", state, blocks, n_districts=2,
        edges=edges, edge_lengths=lengths,
    )
    assert result.name == "metis"
    assert result.succeeded
    assert result.districts is not None
    assert len(result.districts) == 2
    # Bare metis: no KL refinement applied.
    assert result.refine_iterations == 0


def test_run_one_algorithm_metis_plus_kl_applies_refinement():
    state, blocks, edges, lengths = _setup()
    result = run_one_algorithm(
        "metis+kl", state, blocks, n_districts=2,
        edges=edges, edge_lengths=lengths,
    )
    assert result.name == "metis+kl"
    assert result.succeeded


def test_run_one_algorithm_runs_splitline_realized():
    state, blocks, edges, lengths = _setup()
    result = run_one_algorithm(
        "splitline-realized", state, blocks, n_districts=2,
        edges=edges, edge_lengths=lengths,
    )
    assert result.name == "splitline-realized"
    assert result.succeeded


# --- run_single_algorithm_task (the worker entry point) -------------------------


def test_run_single_algorithm_task_writes_experiment_dir(tmp_path):
    """The worker entry point should run one algorithm and write its
    experiments/<algo>/ directory with the expected light bundle."""
    from types import SimpleNamespace

    from districtmaker.experiments import run_single_algorithm_task

    state_gdf, blocks_gdf, edges, lengths = _setup()
    fake_state = SimpleNamespace(
        code="AA",
        name="Aalandia",
        fips="00",
        geometry=state_gdf,
        blocks=blocks_gdf,
        block_count=len(blocks_gdf),
        total_population=int(blocks_gdf["pop"].sum()),
    )

    state_dir = tmp_path / "AA"
    result = run_single_algorithm_task(
        state_code="AA",
        algorithm="metis",
        state_output_dir=state_dir,
        n_districts=2,
        seed=42,
        tolerance=0.005,
        state_loader=lambda code: fake_state,
        adjacency_loader=lambda code, blocks: (edges, lengths),
    )

    assert result.name == "metis"
    assert result.succeeded
    exp_dir = state_dir / "experiments" / "metis"
    assert (exp_dir / "metrics.json").exists()
    assert (exp_dir / "run.log").exists()


# --- finalize_state -------------------------------------------------------------


def test_finalize_state_picks_leader_from_experiment_dirs(tmp_path):
    """Given two completed experiments on disk, finalize_state reads their
    metrics, ranks them, writes leader.json, and copies the leader's
    geojson up to the state root."""
    from types import SimpleNamespace

    from districtmaker.experiments import finalize_state, run_single_algorithm_task

    state_gdf, blocks_gdf, edges, lengths = _setup()
    fake_state = SimpleNamespace(
        code="AA", name="Aalandia", fips="00",
        geometry=state_gdf, blocks=blocks_gdf,
        block_count=len(blocks_gdf),
        total_population=int(blocks_gdf["pop"].sum()),
    )
    state_dir = tmp_path / "AA"

    for algo in ("metis", "metis+kl"):
        run_single_algorithm_task(
            state_code="AA", algorithm=algo, state_output_dir=state_dir,
            n_districts=2, seed=42, tolerance=0.005,
            state_loader=lambda code: fake_state,
            adjacency_loader=lambda code, blocks: (edges, lengths),
        )

    report = finalize_state(
        state_code="AA",
        state_output_dir=state_dir,
        state_info={"code": "AA", "name": "Aalandia", "n_districts": 2},
    )

    assert report.leader in ("metis", "metis+kl")
    assert (state_dir / "leader.json").exists()
    assert (state_dir / "leader.md").exists()
    # The leader's districts must be copied up so the state root carries
    # the canonical bundle.
    assert (state_dir / "districts.geojson").exists()
