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


# --- ctype knob ----------------------------------------------------------------


def _ctype_fixture():
    """Small graph with VARIED edge weights AND varied populations so ctype
    differentiates outputs.

    Two things had to vary for SHEM vs RM to land on different partitions:
      1. Edge weights — a uniform-weight graph causes SHEM (sorted
         heavy-edge matching) to degenerate to RM (random matching).
      2. Block populations — a uniform-population grid is so symmetric
         that even with weight variation METIS converges to the same
         best partition across both coarsening choices.

    Callers should also use ncuts=1 (see test_metis_ctype_rm_differs_from_shem):
    with multiple independent trials METIS averages out the coarsening
    choice and SHEM/RM produce the same final answer on graphs this small.
    """
    rng = np.random.default_rng(1)
    w, h = 10, 10
    geom = []
    for ix in range(w):
        for iy in range(h):
            geom.append(
                Polygon([(ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)])
            )
    pops = rng.integers(10, 200, size=w * h)
    blocks = gpd.GeoDataFrame({"pop": pops}, geometry=geom, crs="EPSG:5070")
    state = _envelope(blocks)
    edges, lengths = compute_adjacency(blocks)
    rng2 = np.random.default_rng(2)
    lengths = lengths * (1.0 + rng2.uniform(0.0, 10.0, size=len(lengths)))
    return state, blocks, edges, lengths


def test_metis_ctype_default_matches_current_behavior():
    """Default ctype must preserve bit-exact output of pre-ctype code path.

    Guards against accidental regression: existing leader ledger values
    (e.g. CA seed 42 metis+kl 7467.96 km) depend on this.
    """
    state, blocks, edges, lengths = _ctype_fixture()
    m_default = Metis(tolerance=0.05, ncuts=1)
    m_explicit = Metis(tolerance=0.05, ncuts=1, ctype="SHEM")
    d_default = m_default.run(
        state, blocks, n_districts=4, seed=42, edges=edges, edge_lengths=lengths
    )
    d_explicit = m_explicit.run(
        state, blocks, n_districts=4, seed=42, edges=edges, edge_lengths=lengths
    )
    # Compare district assignments (not geometries — dissolve is deterministic)
    assert list(d_default["district_id"]) == list(d_explicit["district_id"])
    assert list(d_default["pop"]) == list(d_explicit["pop"])
    # And the geometries themselves should be identical.
    default_shapes = sorted(g.wkb_hex for g in d_default.geometry)
    explicit_shapes = sorted(g.wkb_hex for g in d_explicit.geometry)
    assert default_shapes == explicit_shapes


def test_metis_ctype_rm_differs_from_shem():
    """ctype='RM' must produce a different partition than ctype='SHEM'.

    The fixture deliberately uses VARIED edge weights (see _ctype_fixture).
    A uniform-weight graph causes SHEM and RM to degenerate to the same
    matching, which would falsely pass this test or, depending on tie
    breaks, falsely fail it. With varied weights, SHEM's heavy-edge
    preference produces a measurably different partition than RM.
    """
    state, blocks, edges, lengths = _ctype_fixture()
    # ncuts=1 is intentional: with multiple trials METIS averages out the
    # coarsening choice and SHEM/RM produce the same final partition on
    # graphs this small. ctype's effect is observable on a single trial.
    m_shem = Metis(tolerance=0.05, ncuts=1, ctype="SHEM")
    m_rm = Metis(tolerance=0.05, ncuts=1, ctype="RM")
    d_shem = m_shem.run(
        state, blocks, n_districts=4, seed=42, edges=edges, edge_lengths=lengths
    )
    d_rm = m_rm.run(
        state, blocks, n_districts=4, seed=42, edges=edges, edge_lengths=lengths
    )
    # Compare the dissolved geometries — uniform pops make the pop split
    # identical regardless of which blocks landed in which district, so
    # geometry equality (set-of-WKBs, order-independent) is the right signal.
    shem_shapes = sorted(g.wkb_hex for g in d_shem.geometry)
    rm_shapes = sorted(g.wkb_hex for g in d_rm.geometry)
    assert shem_shapes != rm_shapes, (
        "ctype=RM and ctype=SHEM produced identical partitions on the "
        "test fixture; fixture may be too small/symmetric for ctype to "
        "differentiate. Vary the edge weights further."
    )


def test_metis_ctype_invalid_raises():
    with pytest.raises(ValueError, match="ctype must be 'SHEM' or 'RM'"):
        Metis(tolerance=0.005, ctype="BOGUS")
