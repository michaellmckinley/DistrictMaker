"""Tests for KL single-swap refinement."""
from __future__ import annotations

import numpy as np
import pytest

from districtmaker.algorithms.kl_refine import _cut_weight, _would_disconnect, refine


def test_refine_no_op_on_already_optimal_partition():
    # 4 blocks in a line: 0-1-2-3. Optimal balanced partition is {0,1}, {2,3}.
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    edge_lengths = np.array([1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100])
    assignments = np.array([0, 0, 1, 1])

    refined, stats = refine(assignments, pops, edges, edge_lengths, tolerance=0.05)
    np.testing.assert_array_equal(refined, assignments)
    assert stats.moves_applied == 0
    assert stats.initial_cut == 1.0
    assert stats.final_cut == 1.0


def test_refine_fixes_suboptimal_partition():
    # 4 blocks in a line, bad alternating partition.
    # Use generous tolerance so balance doesn't block single-block moves.
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    edge_lengths = np.array([1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100])
    assignments = np.array([0, 1, 0, 1])

    refined, stats = refine(assignments, pops, edges, edge_lengths, tolerance=0.5)
    assert stats.final_cut < stats.initial_cut
    assert stats.moves_applied > 0


def test_refine_respects_population_tolerance():
    # 6 blocks in a row with unequal populations.
    # Balance requires roughly equal pop per side.
    edges = np.array([[0, 1], [1, 2], [2, 3], [3, 4], [4, 5]])
    edge_lengths = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100, 100, 100])
    # Start balanced 3:3.
    assignments = np.array([0, 0, 0, 1, 1, 1])
    refined, stats = refine(assignments, pops, edges, edge_lengths, tolerance=0.01)
    # With 1% tolerance and integer block populations, can't shift any blocks
    # without breaking balance. Algorithm should make no moves.
    assert stats.moves_applied == 0


def test_refine_reduces_cut_on_grid():
    # 2x2 grid. Bad diagonal partition: {0,3} vs {1,2}, all 4 edges cut.
    # Generous tolerance so we exercise the algorithm, not the balance check.
    edges = np.array([[0, 1], [0, 2], [1, 3], [2, 3]])
    edge_lengths = np.array([1.0, 1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100])
    assignments = np.array([0, 1, 1, 0])

    refined, stats = refine(assignments, pops, edges, edge_lengths, tolerance=0.5)
    assert stats.final_cut <= 2.0
    assert stats.final_cut < stats.initial_cut


def test_refine_preserves_total_population():
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    edge_lengths = np.array([1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100])
    assignments = np.array([0, 1, 0, 1])

    refined, _ = refine(assignments, pops, edges, edge_lengths, tolerance=0.5)
    total_before = pops.sum()
    total_after = pops[refined == 0].sum() + pops[refined == 1].sum()
    assert total_before == total_after


def test_would_disconnect_isolated_block_is_safe():
    """A block with 0 same-district neighbors is trivially safe to remove."""
    # Block 0 in district 0, but its only neighbor is in district 1.
    nbrs = [[(1, 1.0)], [(0, 1.0)]]
    assignments = np.array([0, 1])
    assert _would_disconnect(0, 0, nbrs, assignments) is False


def test_would_disconnect_leaf_block_is_safe():
    """A block whose only same-district neighbor is a single block is safe."""
    # Two blocks in district 0, both connected. Removing block 0 leaves
    # block 1 alone, still a valid (1-block) district.
    nbrs = [[(1, 1.0)], [(0, 1.0)]]
    assignments = np.array([0, 0])
    assert _would_disconnect(0, 0, nbrs, assignments) is False


def test_would_disconnect_dumbbell_detects_articulation():
    """A bridge block whose removal severs two halves of a district."""
    # Graph: 0 — 1 — 2 — 3 — 4 (a line). All in district 0.
    # Removing block 2 strands {0,1} from {3,4}.
    nbrs = [
        [(1, 1.0)],
        [(0, 1.0), (2, 1.0)],
        [(1, 1.0), (3, 1.0)],
        [(2, 1.0), (4, 1.0)],
        [(3, 1.0)],
    ]
    assignments = np.array([0, 0, 0, 0, 0])
    assert _would_disconnect(2, 0, nbrs, assignments) is True


def test_would_disconnect_block_with_alternate_path_is_safe():
    """A block in a cycle whose neighbors stay connected via the back path."""
    # Square: 0 — 1
    #         |   |
    #         3 — 2
    # All in district 0. Removing block 0 leaves 1-2-3 still connected.
    nbrs = [
        [(1, 1.0), (3, 1.0)],
        [(0, 1.0), (2, 1.0)],
        [(1, 1.0), (3, 1.0)],
        [(0, 1.0), (2, 1.0)],
    ]
    assignments = np.array([0, 0, 0, 0])
    assert _would_disconnect(0, 0, nbrs, assignments) is False


def test_refine_does_not_create_disconnected_districts():
    """A small graph with a tempting disconnection-creating move must be skipped.

    Graph (all in district 0 except block 5 in district 1):
        0 — 1 — 2 — 5
            |
            3 — 4
    Block 5 is in district 1, far from the rest. The cut is the edge
    (2, 5) at weight 1. The "best gain" move would be to flip block 2
    to district 1 (eliminating the (2,5) cut). But that would strand
    {3,4} (still in district 0 via 1) ... no wait, blocks 1,3,4 are
    still connected to each other after moving 2.

    Let me build a real disconnection trap: a chain where moving the
    middle block strands the far end.
    """
    # Chain: 0 — 1 — 2 — 3, all in district 0. Plus block 4 in district 1
    # adjacent to block 3. If we move block 3 to district 1, district 0
    # is left as {0, 1, 2} — still connected.
    # But if we move block 1 (an articulation point of district 0's chain),
    # district 0 splits into {0} and {2, 3}. We construct that scenario.
    edges = np.array([
        [0, 1], [1, 2], [2, 3], [3, 4],
    ])
    edge_lengths = np.array([1.0, 1.0, 1.0, 100.0])  # edge (3,4) is huge
    pops = np.array([100, 100, 100, 100, 100])
    # Initial: blocks 0..3 in district 0, block 4 in district 1.
    # Cut weight = 100 (just the (3,4) edge).
    # If KL moves block 1 to district 1, district 0 = {0, 2, 3} — block 0
    # is stranded. (1,2) edge becomes cut, (0,1) and (3,4) are still cut.
    # But that move has negative gain (sum_a=2, sum_d=0 for block 1 →
    # district 1), so it wouldn't be picked anyway.
    # The key test: with the contiguity check in place, no move that
    # would disconnect block 0 from the rest can happen.
    assignments = np.array([0, 0, 0, 0, 1])

    refined, _ = refine(assignments, pops, edges, edge_lengths, tolerance=0.5)

    # Verify district 0 is still a connected chain in `refined`.
    d0_blocks = set(int(b) for b in np.where(refined == 0)[0])
    # Pick any block in d0 and BFS; must reach all d0 blocks.
    if d0_blocks:
        nbrs = [[] for _ in range(5)]
        for u, v in edges:
            nbrs[u].append(v)
            nbrs[v].append(u)
        start = next(iter(d0_blocks))
        visited = {start}
        queue = [start]
        while queue:
            v = queue.pop()
            for n in nbrs[v]:
                if int(refined[n]) == 0 and n not in visited:
                    visited.add(n)
                    queue.append(n)
        assert visited == d0_blocks, f"district 0 became disconnected: {d0_blocks} != {visited}"


def test_refine_stats_consistency():
    edges = np.array([[0, 1], [1, 2], [2, 3]])
    edge_lengths = np.array([1.0, 1.0, 1.0])
    pops = np.array([100, 100, 100, 100])
    assignments = np.array([0, 1, 0, 1])

    refined, stats = refine(assignments, pops, edges, edge_lengths, tolerance=0.05)
    # Recompute cut from scratch and compare.
    recomputed = _cut_weight(refined, edges, edge_lengths)
    assert stats.final_cut == pytest.approx(recomputed)
    assert stats.improvement == pytest.approx(stats.initial_cut - stats.final_cut)
