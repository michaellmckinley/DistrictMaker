"""Tests for the block adjacency graph."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Polygon

from districtmaker.data.adjacency import compute_adjacency, get_adjacency


def _grid_blocks(width: int, height: int) -> gpd.GeoDataFrame:
    geom = []
    for ix in range(width):
        for iy in range(height):
            geom.append(
                Polygon([(ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)])
            )
    return gpd.GeoDataFrame(geometry=geom, crs="EPSG:5070")


def test_compute_adjacency_2x2_grid_has_four_unit_edges():
    blocks = _grid_blocks(2, 2)
    edges, lengths = compute_adjacency(blocks)

    # Four internal edges: (0,1), (0,2), (1,3), (2,3) each of length 1.
    # Block layout (column-major from _grid_blocks):
    #   ix=0,iy=0 -> 0   ix=0,iy=1 -> 1
    #   ix=1,iy=0 -> 2   ix=1,iy=1 -> 3
    assert len(edges) == 4
    assert np.all(edges[:, 0] < edges[:, 1])
    assert np.allclose(lengths, 1.0)


def test_compute_adjacency_excludes_point_only_touches():
    # Two unit squares touching only at the corner (1, 1).
    blocks = gpd.GeoDataFrame(
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(1, 1), (2, 1), (2, 2), (1, 2)]),
        ],
        crs="EPSG:5070",
    )
    edges, lengths = compute_adjacency(blocks)
    assert len(edges) == 0
    assert len(lengths) == 0


def test_compute_adjacency_disjoint_blocks_have_no_edges():
    blocks = gpd.GeoDataFrame(
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(5, 5), (6, 5), (6, 6), (5, 6)]),
        ],
        crs="EPSG:5070",
    )
    edges, lengths = compute_adjacency(blocks)
    assert len(edges) == 0


def test_compute_adjacency_empty_input():
    blocks = gpd.GeoDataFrame(geometry=[], crs="EPSG:5070")
    edges, lengths = compute_adjacency(blocks)
    assert edges.shape == (0, 2)
    assert lengths.shape == (0,)


def test_compute_adjacency_3x3_grid_has_twelve_edges():
    blocks = _grid_blocks(3, 3)
    edges, lengths = compute_adjacency(blocks)
    # 3x3 grid: 12 internal edges (2 per row * 3 rows + 2 per column * 3 columns = 12).
    assert len(edges) == 12
    assert np.allclose(lengths, 1.0)


def test_compute_adjacency_connected_graph_adds_no_synthetic_edges():
    # A 3x3 grid is one connected component — no synthetic edges expected.
    blocks = _grid_blocks(3, 3)
    edges, lengths = compute_adjacency(blocks)
    # Verify every edge has positive weight (no synthetic weight-0 edges).
    assert (lengths > 0).all()


def test_compute_adjacency_disconnected_input_adds_synthetic_edges():
    # Two unit squares far apart in space, no shared boundary.
    # Without synthetic edges this graph would be empty; with N-per-island
    # synthetic edges every island block gets a 0-weight link to mainland.
    from shapely.geometry import Polygon
    blocks = gpd.GeoDataFrame(
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
            Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]),  # mainland: 3 blocks in a row
            Polygon([(100, 100), (101, 100), (101, 101), (100, 101)]),  # 1 island block far away
        ],
        crs="EPSG:5070",
    )
    edges, lengths = compute_adjacency(blocks)
    # Real edges within mainland strip: (0,1), (1,2). Synthetic: (?, 3).
    real_edges = edges[lengths > 0]
    synth_edges = edges[lengths == 0]
    assert len(real_edges) == 2
    assert len(synth_edges) == 1
    # Synthetic edge must touch the island block (index 3).
    assert 3 in synth_edges[0]
    # Mainland endpoint should be the nearest by centroid distance — block 2
    # (closer to island block 3) rather than block 0 or 1.
    assert 2 in synth_edges[0]


def test_compute_adjacency_n_per_island_one_edge_per_island_block():
    # Mainland (5 blocks in a row, indices 0-4) + 3-block island far away
    # (indices 5,6,7 connected to each other). Expect 3 synthetic edges
    # (one per island block) and the 2 mainland-internal real edges within
    # the island.
    from shapely.geometry import Polygon
    blocks = gpd.GeoDataFrame(
        geometry=[
            *[
                Polygon([(x, 0), (x + 1, 0), (x + 1, 1), (x, 1)])
                for x in range(5)
            ],
            # Island blocks at x=50, 51, 52 (row of 3)
            *[
                Polygon([(50 + x, 50), (51 + x, 50), (51 + x, 51), (50 + x, 51)])
                for x in range(3)
            ],
        ],
        crs="EPSG:5070",
    )
    edges, lengths = compute_adjacency(blocks)
    synth_edges = edges[lengths == 0]
    real_edges = edges[lengths > 0]
    # Mainland has 4 real edges, island has 2 real edges, total 6 real.
    assert len(real_edges) == 6
    # Three island blocks → three synthetic edges, one each.
    assert len(synth_edges) == 3
    # Each synthetic edge has one endpoint in the island {5,6,7} and one
    # endpoint on the mainland.
    for e in synth_edges:
        assert (e[0] in {5, 6, 7}) != (e[1] in {5, 6, 7})


def test_get_adjacency_caches_to_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("DISTRICTMAKER_CACHE_DIR", str(tmp_path))
    blocks = _grid_blocks(3, 3)

    edges1, lengths1 = get_adjacency("TT", blocks)
    cache_file = tmp_path / "tt-edges-2020-v2.npz"
    assert cache_file.exists()

    # Second call returns cached data; corrupt the input to prove cache is used.
    edges2, lengths2 = get_adjacency("TT", blocks.iloc[:1])
    np.testing.assert_array_equal(edges1, edges2)
    np.testing.assert_array_equal(lengths1, lengths2)
