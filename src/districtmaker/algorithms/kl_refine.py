"""Kernighan-Lin / FM-style single-swap local refinement.

Given a balanced partition and the block adjacency graph, repeatedly move
boundary blocks across district lines if doing so reduces the realized
internal boundary length while:
  (a) keeping every district's population within `tolerance` of the ideal, and
  (b) preserving each source district's contiguity (no move that would
      strand part of the source district from the rest).

The algorithm terminates when no single-block move satisfies both
constraints and improves the cut. That's a "1-swap, contiguity-preserving
local minimum" — strictly stronger than splitline's output.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RefineStats:
    iterations: int
    moves_applied: int
    initial_cut: float
    final_cut: float
    improvement: float
    improvement_pct: float


def refine(
    assignments: np.ndarray,
    pops: np.ndarray,
    edges: np.ndarray,
    edge_lengths: np.ndarray,
    tolerance: float = 0.005,
    max_iterations: int = 1_000_000,
) -> tuple[np.ndarray, RefineStats]:
    """Single-swap KL refinement.

    Parameters
    ----------
    assignments : (N,) int array, district id per block (0..k-1)
    pops : (N,) int array, population per block
    edges : (E, 2) int array, undirected edge endpoints (i < j by convention)
    edge_lengths : (E,) float array, edge weights
    tolerance : max absolute population deviation as a fraction (e.g. 0.005 = 0.5%)
    max_iterations : safety bound

    Returns
    -------
    refined_assignments : (N,) int array
    stats : RefineStats
    """
    assignments = assignments.copy().astype(np.int64)
    pops = pops.astype(np.int64)
    n = len(assignments)
    k = int(assignments.max()) + 1

    pops_per_d = np.zeros(k, dtype=np.int64)
    np.add.at(pops_per_d, assignments, pops)

    total = int(pops_per_d.sum())
    ideal = total / k
    max_pop = ideal * (1 + tolerance)
    min_pop = ideal * (1 - tolerance)

    # Per-block neighbor lists.
    nbrs: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for idx in range(len(edges)):
        u, v = int(edges[idx, 0]), int(edges[idx, 1])
        w = float(edge_lengths[idx])
        nbrs[u].append((v, w))
        nbrs[v].append((u, w))

    initial_cut = _cut_weight(assignments, edges, edge_lengths)
    running_cut = initial_cut
    iterations = 0
    moves_applied = 0

    while iterations < max_iterations:
        best_gain = 0.0
        best_block = -1
        best_target = -1

        for i in range(n):
            a = int(assignments[i])
            weight_to: dict[int, float] = {}
            for nbr, w in nbrs[i]:
                d = int(assignments[nbr])
                weight_to[d] = weight_to.get(d, 0.0) + w
            sum_a = weight_to.get(a, 0.0)
            for d, sum_d in weight_to.items():
                if d == a:
                    continue
                gain = sum_d - sum_a
                if gain <= best_gain:
                    continue
                new_a = pops_per_d[a] - pops[i]
                new_d = pops_per_d[d] + pops[i]
                if new_a < min_pop or new_d > max_pop:
                    continue
                # Contiguity check: removing block i from district a must
                # not strand any part of a from the rest. This is the
                # bottleneck check — only run it for candidate moves that
                # have already passed the gain and balance filters.
                if _would_disconnect(i, a, nbrs, assignments):
                    continue
                best_gain = gain
                best_block = i
                best_target = d

        if best_block < 0:
            break

        a = int(assignments[best_block])
        pops_per_d[a] -= int(pops[best_block])
        pops_per_d[best_target] += int(pops[best_block])
        assignments[best_block] = best_target
        running_cut -= best_gain
        moves_applied += 1
        iterations += 1

    final_cut = _cut_weight(assignments, edges, edge_lengths)
    improvement = initial_cut - final_cut
    stats = RefineStats(
        iterations=iterations,
        moves_applied=moves_applied,
        initial_cut=initial_cut,
        final_cut=final_cut,
        improvement=improvement,
        improvement_pct=(improvement / initial_cut * 100.0) if initial_cut > 0 else 0.0,
    )
    return assignments, stats


def _cut_weight(
    assignments: np.ndarray, edges: np.ndarray, edge_lengths: np.ndarray
) -> float:
    """Sum of edge_lengths whose endpoints lie in different districts."""
    cut = assignments[edges[:, 0]] != assignments[edges[:, 1]]
    return float(edge_lengths[cut].sum())


def _would_disconnect(
    block_i: int,
    district_a: int,
    nbrs: list,
    assignments: np.ndarray,
) -> bool:
    """Return True if removing block_i from district_a would disconnect it.

    Strategy: gather the neighbors of block_i that are also in district_a.
    If 0 or 1, removal is trivially safe (no neighbors to potentially
    strand). Otherwise BFS from one of them through the rest of district_a
    (treating block_i as absent) and check that all the others are
    reachable. Early-terminates as soon as all targets are found, so the
    typical cost is O(neighborhood size), not O(district size).
    """
    a_neighbors = [int(n) for n, _ in nbrs[block_i] if int(assignments[n]) == district_a]
    if len(a_neighbors) <= 1:
        return False

    start = a_neighbors[0]
    targets = set(a_neighbors[1:])
    visited = {start}
    queue = [start]
    while queue and targets:
        v = queue.pop()
        for nbr, _w in nbrs[v]:
            nbr = int(nbr)
            if nbr == block_i:
                continue
            if int(assignments[nbr]) != district_a:
                continue
            if nbr in visited:
                continue
            visited.add(nbr)
            targets.discard(nbr)
            queue.append(nbr)
    return bool(targets)
