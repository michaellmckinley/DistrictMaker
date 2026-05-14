"""Tests for the METIS-based partitioning algorithm."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Polygon

from districtmaker.algorithms.metis import Metis, _to_csr
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


# --- CSR conversion -------------------------------------------------------------


def test_to_csr_empty_graph():
    xadj, adjncy, weights = _to_csr(5, np.zeros((0, 2), dtype=np.int64), np.zeros(0))
    assert len(xadj) == 6
    assert (xadj == 0).all()
    assert adjncy.size == 0
    assert weights.size == 0


def test_to_csr_2x2_square():
    # 2x2 grid produces 4 edges: (0,1), (0,2), (1,3), (2,3).
    edges = np.array([[0, 1], [0, 2], [1, 3], [2, 3]])
    lengths = np.array([1.0, 1.0, 1.0, 1.0])
    xadj, adjncy, weights = _to_csr(4, edges, lengths)
    # Each vertex has 2 neighbors.
    assert xadj.tolist() == [0, 2, 4, 6, 8]
    # Each edge in undirected form contributes 2 directed entries.
    assert len(adjncy) == 8
    assert (weights == 1000).all()  # mm scaling


def test_to_csr_scales_weights_to_millimeters_floor_at_one():
    edges = np.array([[0, 1]])
    lengths = np.array([0.0001])  # tiny edge length
    _, _, weights = _to_csr(2, edges, lengths)
    # Rounded to 0 mm, but floored to 1 so METIS doesn't choke.
    assert (weights >= 1).all()


# --- Metis end-to-end -----------------------------------------------------------


def test_metis_returns_requested_district_count():
    blocks = _grid_blocks(4, 4)
    state = _envelope(blocks)
    edges, lengths = compute_adjacency(blocks)

    out = Metis().run(state, blocks, n_districts=4, edges=edges, edge_lengths=lengths)
    assert len(out) == 4


def test_metis_preserves_total_population():
    blocks = _grid_blocks(4, 4, pop_per_block=100)
    state = _envelope(blocks)
    edges, lengths = compute_adjacency(blocks)

    out = Metis().run(state, blocks, n_districts=2, edges=edges, edge_lengths=lengths)
    assert int(out["pop"].sum()) == int(blocks["pop"].sum())


def test_metis_long_thin_rectangle_splits_along_short_axis():
    # 10x2 grid, pop=1 each. Optimal balanced 2-way split is vertical at x=5.
    blocks = _grid_blocks(10, 2, pop_per_block=1)
    state = _envelope(blocks)
    edges, lengths = compute_adjacency(blocks)

    out = Metis().run(state, blocks, n_districts=2, edges=edges, edge_lengths=lengths)
    assert len(out) == 2
    assert sorted(out["pop"].tolist()) == [10, 10]
    # Shared internal boundary along the vertical midline = length 2.
    from districtmaker.metrics.boundaries import total_internal_boundary_length
    assert total_internal_boundary_length(out) == pytest.approx(2.0, abs=1e-6)


def test_metis_single_district_is_whole_state():
    blocks = _grid_blocks(3, 3)
    state = _envelope(blocks)
    edges, lengths = compute_adjacency(blocks)

    out = Metis().run(state, blocks, n_districts=1, edges=edges, edge_lengths=lengths)
    assert len(out) == 1
    assert int(out["pop"].iloc[0]) == int(blocks["pop"].sum())


def test_metis_requires_edges():
    blocks = _grid_blocks(2, 2)
    state = _envelope(blocks)
    with pytest.raises(ValueError, match="edges"):
        Metis().run(state, blocks, n_districts=2)


def test_metis_rejects_mismatched_crs():
    blocks = _grid_blocks(2, 2)
    state = _envelope(blocks).to_crs("EPSG:4326")
    edges, lengths = compute_adjacency(blocks)
    with pytest.raises(ValueError, match="CRS"):
        Metis().run(state, blocks, n_districts=2, edges=edges, edge_lengths=lengths)


def test_metis_rejects_bad_tolerance():
    with pytest.raises(ValueError):
        Metis(tolerance=0)
    with pytest.raises(ValueError):
        Metis(tolerance=-0.01)


def test_metis_rejects_contiguous_with_recursive():
    # METIS_OPTION_CONTIG is only honored by k-way, not recursive bisection.
    # We refuse the combination rather than silently producing non-contiguous output.
    with pytest.raises(ValueError, match="contig"):
        Metis(contiguous=True, recursive=True)


def test_metis_enforces_tolerance():
    blocks = _grid_blocks(8, 8, pop_per_block=10)
    state = _envelope(blocks)
    edges, lengths = compute_adjacency(blocks)

    out = Metis(tolerance=0.005).run(
        state, blocks, n_districts=4, edges=edges, edge_lengths=lengths
    )
    total = int(out["pop"].sum())
    ideal = total / 4
    achieved = float(np.abs(out["pop"] - ideal).max() / ideal)
    assert achieved <= 0.005 + 1e-9


def test_metis_produces_contiguous_districts_on_grid():
    # Each district must be a single connected component in the block graph.
    blocks = _grid_blocks(6, 6, pop_per_block=10)
    state = _envelope(blocks)
    edges, lengths = compute_adjacency(blocks)

    out = Metis(contiguous=True).run(
        state, blocks, n_districts=3, edges=edges, edge_lengths=lengths
    )
    # The dissolved district geometries should each be a single Polygon (no MultiPolygon).
    for geom in out.geometry:
        assert geom.geom_type == "Polygon", (
            f"Expected Polygon (single contiguous district), got {geom.geom_type}"
        )
