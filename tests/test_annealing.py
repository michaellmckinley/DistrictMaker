"""Tests for simulated annealing."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Polygon

from districtmaker.algorithms.annealing import SimulatedAnnealing, anneal
from districtmaker.data.adjacency import compute_adjacency


def _grid_blocks(width: int, height: int, pop_per_block: int = 100) -> gpd.GeoDataFrame:
    geom = []
    for ix in range(width):
        for iy in range(height):
            geom.append(
                Polygon([(ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)])
            )
    return gpd.GeoDataFrame(
        {"pop": [pop_per_block] * len(geom)},
        geometry=geom,
        crs="EPSG:5070",
    )


def _envelope(blocks: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = blocks.total_bounds
    return gpd.GeoDataFrame(
        geometry=[Polygon([(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)])],
        crs=blocks.crs,
    )


# --- low-level anneal -----------------------------------------------------------


def test_anneal_no_op_on_already_optimal():
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    edge_lengths = np.array([1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100])
    assignments = np.array([0, 0, 1, 1])
    refined, stats = anneal(
        assignments, pops, edges, edge_lengths,
        tolerance=0.5, iterations=1000, seed=42,
    )
    # Best cut should stay at 1 (no better partition exists).
    assert stats.best_cut == 1.0


def test_anneal_reduces_cut_from_bad_start():
    # 4 blocks in a line. Bad partition: [0,1,0,1] cuts all 3 edges.
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    edge_lengths = np.array([1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100])
    assignments = np.array([0, 1, 0, 1])
    refined, stats = anneal(
        assignments, pops, edges, edge_lengths,
        tolerance=0.5, iterations=2000, seed=42,
    )
    assert stats.best_cut < stats.initial_cut


def test_anneal_preserves_population_total():
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    edge_lengths = np.array([1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100])
    assignments = np.array([0, 0, 1, 1])
    refined, _ = anneal(
        assignments, pops, edges, edge_lengths,
        tolerance=0.5, iterations=500, seed=42,
    )
    total_before = int(pops.sum())
    total_after = int(pops[refined == 0].sum() + pops[refined == 1].sum())
    assert total_before == total_after


def test_anneal_respects_tolerance():
    # Tight tolerance + balanced start: no moves should be accepted.
    edges = np.array([[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]])
    edge_lengths = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100, 100, 100])
    assignments = np.array([0, 0, 0, 1, 1, 1])
    refined, stats = anneal(
        assignments, pops, edges, edge_lengths,
        tolerance=0.01, iterations=500, seed=42,
    )
    # Each block is 1/6 of population. Single move shifts balance by 1/3.
    # Tolerance is 1%, so all moves should fail the balance check.
    assert stats.moves_accepted == 0


# --- SimulatedAnnealing class ---------------------------------------------------


def test_simulated_annealing_returns_requested_district_count():
    blocks = _grid_blocks(4, 4)
    state = _envelope(blocks)
    edges, lengths = compute_adjacency(blocks)

    out = SimulatedAnnealing(iterations=500).run(
        state, blocks, n_districts=2, edges=edges, edge_lengths=lengths
    )
    assert len(out) == 2


def test_simulated_annealing_single_district():
    blocks = _grid_blocks(3, 3)
    state = _envelope(blocks)
    edges, lengths = compute_adjacency(blocks)
    out = SimulatedAnnealing().run(
        state, blocks, n_districts=1, edges=edges, edge_lengths=lengths
    )
    assert len(out) == 1


def test_simulated_annealing_rejects_bad_params():
    with pytest.raises(ValueError):
        SimulatedAnnealing(tolerance=0)
    with pytest.raises(ValueError):
        SimulatedAnnealing(iterations=0)
    with pytest.raises(ValueError):
        SimulatedAnnealing(cooling_rate=0)
    with pytest.raises(ValueError):
        SimulatedAnnealing(cooling_rate=1)


def test_simulated_annealing_requires_edges():
    blocks = _grid_blocks(2, 2)
    state = _envelope(blocks)
    with pytest.raises(ValueError, match="edges"):
        SimulatedAnnealing().run(state, blocks, n_districts=2)


def test_simulated_annealing_deterministic_with_seed():
    blocks = _grid_blocks(4, 4)
    state = _envelope(blocks)
    edges, lengths = compute_adjacency(blocks)

    first = SimulatedAnnealing(iterations=200).run(
        state, blocks, n_districts=2, seed=42, edges=edges, edge_lengths=lengths
    )
    second = SimulatedAnnealing(iterations=200).run(
        state, blocks, n_districts=2, seed=42, edges=edges, edge_lengths=lengths
    )
    assert first["pop"].tolist() == second["pop"].tolist()
