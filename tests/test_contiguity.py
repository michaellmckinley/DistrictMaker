"""Tests for the contiguity repair post-process."""
from __future__ import annotations

import numpy as np

from districtmaker.algorithms.contiguity import (
    _connected_components_of,
    repair_contiguity,
)


def test_connected_components_single_district():
    # 4 blocks in a line, all district 0: one component.
    nbrs = [
        [(1, 1.0)],
        [(0, 1.0), (2, 1.0)],
        [(1, 1.0), (3, 1.0)],
        [(2, 1.0)],
    ]
    assignments = np.array([0, 0, 0, 0])
    components = _connected_components_of(0, assignments, nbrs)
    assert len(components) == 1
    assert sorted(components[0]) == [0, 1, 2, 3]


def test_connected_components_split_district():
    # Blocks: 0-1 are district 0; 2 is district 1; 3-4 are district 0 again.
    # Edges: 0-1, 1-2, 2-3, 3-4. So in district 0's subgraph: {0,1} and {3,4}.
    nbrs = [
        [(1, 1.0)],
        [(0, 1.0), (2, 1.0)],
        [(1, 1.0), (3, 1.0)],
        [(2, 1.0), (4, 1.0)],
        [(3, 1.0)],
    ]
    assignments = np.array([0, 0, 1, 0, 0])
    components = _connected_components_of(0, assignments, nbrs)
    assert len(components) == 2
    assert sorted(sorted(c) for c in components) == [[0, 1], [3, 4]]


def test_repair_absorbs_small_fragment():
    # 5 blocks in a line. Districts: 0,0,1,0,0 — district 0 is split into
    # {0,1} (pop 200) and {3,4} (pop 200). Fragment {3,4} should be
    # absorbed into district 1 because reassignment is balance-feasible.
    edges = np.array([[0, 1], [1, 2], [2, 3], [3, 4]])
    edge_lengths = np.array([1.0, 1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100, 100])
    assignments = np.array([0, 0, 1, 0, 0])
    repaired, reports = repair_contiguity(
        assignments, pops, edges, edge_lengths, tolerance=1.0
    )
    # With generous tolerance, the smaller component should get absorbed
    # (both fragments have equal pop here; algorithm picks one).
    assert len(reports) == 1
    assert reports[0].action.startswith("absorbed_into_")
    # All district 0 blocks now form a single connected component.
    nbrs = [[] for _ in range(5)]
    for u, v in edges:
        nbrs[u].append((v, 1.0))
        nbrs[v].append((u, 1.0))
    components = _connected_components_of(0, repaired, nbrs)
    assert len(components) <= 1


def test_repair_leaves_balance_breaking_fragments_alone():
    # Tight tolerance: even a small fragment can't be reassigned without
    # blowing the population budget.
    edges = np.array([[0, 1], [1, 2], [2, 3], [3, 4]])
    edge_lengths = np.array([1.0, 1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100, 100])
    assignments = np.array([0, 0, 1, 0, 0])  # d0 split: {0,1} and {3,4}
    repaired, reports = repair_contiguity(
        assignments, pops, edges, edge_lengths, tolerance=0.01
    )
    # 100/250 = 40% of district 0; way outside 1% tolerance.
    assert len(reports) == 1
    assert reports[0].action == "unfixed_balance"
    # Assignments unchanged.
    np.testing.assert_array_equal(repaired, assignments)


def test_repair_noop_on_contiguous_input():
    # All districts already contiguous: no fragment reports, no changes.
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    edge_lengths = np.array([1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100])
    assignments = np.array([0, 0, 1, 1])
    repaired, reports = repair_contiguity(
        assignments, pops, edges, edge_lengths, tolerance=0.5
    )
    assert reports == []
    np.testing.assert_array_equal(repaired, assignments)


def test_repair_picks_neighbor_with_largest_shared_boundary():
    # A fragment that touches two neighboring districts; one shares more
    # edge weight. The fragment should go to the heavier-weighted neighbor.
    # Blocks 0,1,2 form a triangle, all in district 0. Block 3 connects to
    # only block 2 of district 0, and is in district 0 — but disconnected
    # from {0,1,2} by being on the "other side" of district 1.
    #
    # Simpler setup:
    #   0(d0) - 1(d0)
    #   |
    #   2(d1)
    #   |
    #   3(d0)  <- fragment, connects to 2(d1) and to 4(d2)
    #   |
    #   4(d2)
    # Edge (2,3) has weight 5, edge (3,4) has weight 1.
    # Fragment {3} should go to district 1 (heavier edge).
    edges = np.array([[0, 1], [0, 2], [2, 3], [3, 4]])
    edge_lengths = np.array([1.0, 1.0, 5.0, 1.0])
    pops = np.array([100, 100, 100, 100, 100])
    assignments = np.array([0, 0, 1, 0, 2])
    repaired, reports = repair_contiguity(
        assignments, pops, edges, edge_lengths, tolerance=1.0
    )
    assert len(reports) == 1
    assert reports[0].action == "absorbed_into_1"
    assert repaired[3] == 1
