"""Tests for the shortest-splitline algorithm."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Polygon

from districtmaker.algorithms.splitline import (
    Splitline,
    _components_within_side,
    _enforce_contiguous_sides,
)
from districtmaker.data.adjacency import compute_adjacency
from districtmaker.metrics.boundaries import total_internal_boundary_length
from districtmaker.metrics.population import ideal_population, population_deviation


def _grid_blocks(
    width: int, height: int, pop_per_block: int = 100, crs: str = "EPSG:5070"
) -> gpd.GeoDataFrame:
    geom = []
    for ix in range(width):
        for iy in range(height):
            geom.append(
                Polygon([(ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)])
            )
    n = len(geom)
    return gpd.GeoDataFrame(
        {"pop": [pop_per_block] * n},
        geometry=geom,
        crs=crs,
    )


def _envelope(blocks: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = blocks.total_bounds
    return gpd.GeoDataFrame(
        geometry=[Polygon([(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)])],
        crs=blocks.crs,
    )


def _run_realized(blocks, state, n_districts, *, angle_steps=180, seed=42):
    edges, lengths = compute_adjacency(blocks)
    return Splitline(angle_steps=angle_steps, objective="realized").run(
        state, blocks, n_districts=n_districts, seed=seed,
        edges=edges, edge_lengths=lengths,
    )


# --- structural invariants -------------------------------------------------------


def test_single_district_returns_whole_state():
    blocks = _grid_blocks(4, 4)
    state = _envelope(blocks)
    out = _run_realized(blocks, state, n_districts=1)

    assert len(out) == 1
    assert out["pop"].iloc[0] == blocks["pop"].sum()


def test_returns_requested_district_count():
    blocks = _grid_blocks(4, 4)
    state = _envelope(blocks)
    out = _run_realized(blocks, state, n_districts=4)
    assert len(out) == 4


def test_total_population_preserved():
    blocks = _grid_blocks(4, 4, pop_per_block=100)
    state = _envelope(blocks)
    out = _run_realized(blocks, state, n_districts=3)
    assert int(out["pop"].sum()) == int(blocks["pop"].sum())


def test_rejects_zero_districts():
    blocks = _grid_blocks(4, 4)
    state = _envelope(blocks)
    with pytest.raises(ValueError):
        _run_realized(blocks, state, n_districts=0)


def test_rejects_mismatched_crs():
    blocks = _grid_blocks(4, 4, crs="EPSG:5070")
    state = _envelope(blocks).to_crs("EPSG:4326")
    with pytest.raises(ValueError, match="CRS"):
        _run_realized(blocks, state, n_districts=2)


def test_rejects_invalid_objective():
    with pytest.raises(ValueError, match="objective"):
        Splitline(objective="bogus")


def test_realized_objective_requires_edges():
    blocks = _grid_blocks(2, 2)
    state = _envelope(blocks)
    algo = Splitline(objective="realized")
    with pytest.raises(ValueError, match="edges"):
        algo.run(state, blocks, n_districts=2)


# --- shortest-cut behavior -------------------------------------------------------


def test_long_thin_rectangle_splits_along_short_axis():
    # 10-wide, 2-tall: vertical cut (length 2) beats horizontal (length 10).
    blocks = _grid_blocks(10, 2, pop_per_block=1)
    state = _envelope(blocks)
    out = _run_realized(blocks, state, n_districts=2)

    assert len(out) == 2
    assert sorted(out["pop"].tolist()) == [10, 10]

    boundary = total_internal_boundary_length(out)
    assert boundary == pytest.approx(2.0, abs=1e-6)


def test_population_balance_within_block_granularity():
    blocks = _grid_blocks(8, 8, pop_per_block=10)
    state = _envelope(blocks)
    out = _run_realized(blocks, state, n_districts=4)

    ideal = ideal_population(int(blocks["pop"].sum()), 4)
    report = population_deviation(out, ideal_population=ideal)
    assert report.max_abs_deviation_pct < 0.5


def test_deterministic_same_seed_same_output():
    blocks = _grid_blocks(6, 6, pop_per_block=10)
    state = _envelope(blocks)
    first = _run_realized(blocks, state, n_districts=3, seed=42)
    second = _run_realized(blocks, state, n_districts=3, seed=42)

    assert first["pop"].tolist() == second["pop"].tolist()


def test_three_districts_split_two_then_one():
    blocks = _grid_blocks(6, 6, pop_per_block=1)
    state = _envelope(blocks)
    out = _run_realized(blocks, state, n_districts=3)

    pops = sorted(out["pop"].tolist())
    assert pops == [12, 12, 12]


# --- chord vs realized -----------------------------------------------------------


def test_chord_and_realized_agree_on_simple_grid():
    # On a uniform-population 4x4 grid split into 2, both objectives should
    # produce the same partition (axis-aligned midline cut).
    blocks = _grid_blocks(4, 4, pop_per_block=10)
    state = _envelope(blocks)

    edges, lengths = compute_adjacency(blocks)
    realized = Splitline(objective="realized").run(
        state, blocks, n_districts=2, edges=edges, edge_lengths=lengths,
    )
    chord = Splitline(objective="chord").run(state, blocks, n_districts=2)

    assert sorted(realized["pop"].tolist()) == sorted(chord["pop"].tolist())
    assert total_internal_boundary_length(realized) == pytest.approx(
        total_internal_boundary_length(chord), abs=1e-6
    )


def test_chord_objective_runs_without_edges():
    blocks = _grid_blocks(4, 4, pop_per_block=10)
    state = _envelope(blocks)
    out = Splitline(objective="chord").run(state, blocks, n_districts=2)
    assert len(out) == 2


# --- contiguity correction helper ------------------------------------------------


def test_enforce_contiguity_noop_on_already_contiguous_sides():
    # 4-block line, split 2:2. Both halves are single components.
    idx = np.array([0, 1, 2, 3])
    left_mask = np.array([True, True, False, False])
    sub_edges = np.array([[0, 1], [1, 2], [2, 3]])
    pops = np.array([100, 100, 100, 100])

    new_left, new_right = _enforce_contiguous_sides(idx, left_mask, sub_edges, pops)
    np.testing.assert_array_equal(new_left, left_mask)
    np.testing.assert_array_equal(new_right, ~left_mask)


def test_enforce_contiguity_moves_stranded_component_to_connected_side():
    # 5-block line 0-1-2-3-4. Side-of-line marks {0,1,3,4} as left and {2}
    # as right. Left then has two disconnected components: {0,1} and {3,4}.
    # The smaller-by-id (tie on pop) gets flipped; result: each side a
    # single component.
    idx = np.array([0, 1, 2, 3, 4])
    left_mask = np.array([True, True, False, True, True])
    sub_edges = np.array([[0, 1], [1, 2], [2, 3], [3, 4]])
    pops = np.array([100, 100, 100, 100, 100])

    new_left, new_right = _enforce_contiguous_sides(idx, left_mask, sub_edges, pops)

    nbrs: list[list[int]] = [[] for _ in range(5)]
    for u, v in sub_edges:
        nbrs[u].append(v)
        nbrs[v].append(u)
    left_components = _components_within_side(new_left, True, nbrs)
    right_components = _components_within_side(new_left, False, nbrs)
    assert len(left_components) == 1
    assert len(right_components) == 1


def test_enforce_contiguity_picks_largest_component_as_main():
    # 5-block line; side-of-line marks {0,1,3,4} as left, {2} as right.
    # Left's components: {0,1} (pop 100) and {3,4} (pop 500). The
    # heavier component should be retained; the lighter one flips.
    idx = np.array([0, 1, 2, 3, 4])
    left_mask = np.array([True, True, False, True, True])
    sub_edges = np.array([[0, 1], [1, 2], [2, 3], [3, 4]])
    pops = np.array([50, 50, 100, 250, 250])

    new_left, _ = _enforce_contiguous_sides(idx, left_mask, sub_edges, pops)
    # Heavy {3,4} should remain on left; light {0,1} should flip to right.
    assert new_left[3] and new_left[4]
    assert not new_left[0] and not new_left[1]


def test_enforce_contiguity_leaves_isolate_alone():
    # 4 blocks; block 3 is a true isolate (no edges in sub-region).
    # Side-of-line marks {0,1} left, {2,3} right. Right has 2 components:
    # {2} (connected to nothing via sub_edges? — actually it's an isolate
    # too here) and {3}. Both isolated. Neither has an opposite-side
    # neighbor, so neither flips.
    idx = np.array([0, 1, 2, 3])
    left_mask = np.array([True, True, False, False])
    sub_edges = np.array([[0, 1]])
    pops = np.array([100, 100, 100, 100])

    new_left, new_right = _enforce_contiguous_sides(idx, left_mask, sub_edges, pops)
    # Isolates stay put.
    np.testing.assert_array_equal(new_left, left_mask)
    np.testing.assert_array_equal(new_right, ~left_mask)


def test_enforce_contiguity_both_sides_fragmented():
    # 6 blocks in a line, side-of-line: T,F,T,F,T,F. Each side has 3
    # singleton components. After correction, the heavier-pop component
    # on each side stays; others flip. Ties go to whichever id wins.
    idx = np.array([0, 1, 2, 3, 4, 5])
    left_mask = np.array([True, False, True, False, True, False])
    sub_edges = np.array([[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]])
    pops = np.array([10, 10, 10, 10, 1000, 10])

    new_left, _ = _enforce_contiguous_sides(idx, left_mask, sub_edges, pops)

    nbrs: list[list[int]] = [[] for _ in range(6)]
    for u, v in sub_edges:
        nbrs[u].append(v)
        nbrs[v].append(u)
    left_components = _components_within_side(new_left, True, nbrs)
    right_components = _components_within_side(new_left, False, nbrs)
    assert len(left_components) == 1
    assert len(right_components) == 1
    # The heavy-pop block (4) anchors the left side.
    assert new_left[4]
