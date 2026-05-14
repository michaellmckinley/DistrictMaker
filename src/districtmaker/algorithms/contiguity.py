"""Post-process repair for non-contiguous district assignments.

Splitline assigns blocks by which side of a straight line their centroid
sits on, so a peninsula whose centroid is on one side but whose only
land neighbors are on the other side ends up stranded. KL's contiguity
check prevents KL from *creating* new fragments but won't repair ones
inherited from splitline.

`repair_contiguity` runs after KL: it finds each district's connected
components, treats the largest-population component as canonical, and
tries to reassign each smaller component to an adjacent district that
can absorb it without breaking the population tolerance. Fragments too
large to absorb are left in place and reported.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FragmentReport:
    district: int
    fragment_size_blocks: int
    fragment_population: int
    action: str  # "absorbed_into_<d>" or "unfixed_balance" or "unfixed_no_neighbor"
    target_district: int | None = None


def repair_contiguity(
    assignments: np.ndarray,
    pops: np.ndarray,
    edges: np.ndarray,
    edge_lengths: np.ndarray,
    tolerance: float = 0.005,
) -> tuple[np.ndarray, list[FragmentReport]]:
    """Detect non-contiguous districts and absorb small fragments into neighbors.

    For each district with multiple components, the largest by population
    is canonical. Each smaller component is offered to its adjacent
    districts (weighted by shared boundary length); the highest-weight
    neighbor that can absorb the fragment without breaking tolerance wins.
    Returns refined assignments plus a per-fragment audit log.
    """
    assignments = assignments.copy().astype(np.int64)
    n = len(assignments)
    k = int(assignments.max()) + 1

    pops_per_d = np.zeros(k, dtype=np.int64)
    np.add.at(pops_per_d, assignments, pops)

    total = int(pops_per_d.sum())
    ideal = total / k
    min_pop = ideal * (1 - tolerance)
    max_pop = ideal * (1 + tolerance)

    # Adjacency lists with edge weights.
    nbrs: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for idx in range(len(edges)):
        u, v = int(edges[idx, 0]), int(edges[idx, 1])
        w = float(edge_lengths[idx])
        nbrs[u].append((v, w))
        nbrs[v].append((u, w))

    reports: list[FragmentReport] = []

    for d in range(k):
        components = _connected_components_of(d, assignments, nbrs)
        if len(components) <= 1:
            continue
        components.sort(key=lambda c: -sum(int(pops[i]) for i in c))
        # components[0] is the canonical main piece; the rest are fragments
        for fragment in components[1:]:
            fragment_pop = sum(int(pops[i]) for i in fragment)
            # Tally edge weight from fragment to each adjacent district.
            target_weights: dict[int, float] = {}
            for i in fragment:
                for nbr, w in nbrs[i]:
                    if nbr in fragment:
                        continue
                    nd = int(assignments[nbr])
                    if nd == d:
                        # Same district but not in this component? Shouldn't
                        # happen if components were computed correctly.
                        continue
                    target_weights[nd] = target_weights.get(nd, 0.0) + w

            if not target_weights:
                reports.append(FragmentReport(
                    district=d,
                    fragment_size_blocks=len(fragment),
                    fragment_population=fragment_pop,
                    action="unfixed_no_neighbor",
                ))
                continue

            # Find best target: highest shared-boundary weight, subject to
            # balance still holding in both source and target after move.
            new_d_pop = pops_per_d[d] - fragment_pop
            best_target = None
            best_weight = -1.0
            for t, w in target_weights.items():
                new_t_pop = pops_per_d[t] + fragment_pop
                if new_d_pop < min_pop or new_t_pop > max_pop:
                    continue
                if w > best_weight:
                    best_weight = w
                    best_target = t

            if best_target is None:
                reports.append(FragmentReport(
                    district=d,
                    fragment_size_blocks=len(fragment),
                    fragment_population=fragment_pop,
                    action="unfixed_balance",
                ))
                continue

            for i in fragment:
                assignments[i] = best_target
            pops_per_d[d] -= fragment_pop
            pops_per_d[best_target] += fragment_pop
            reports.append(FragmentReport(
                district=d,
                fragment_size_blocks=len(fragment),
                fragment_population=fragment_pop,
                action=f"absorbed_into_{best_target}",
                target_district=best_target,
            ))

    return assignments, reports


def _connected_components_of(
    district: int, assignments: np.ndarray, nbrs: list
) -> list[list[int]]:
    """Return the connected components of `district` as lists of block indices."""
    in_district = (assignments == district)
    visited = np.zeros(len(assignments), dtype=bool)
    components: list[list[int]] = []
    for start in range(len(assignments)):
        if not in_district[start] or visited[start]:
            continue
        # BFS
        component: list[int] = []
        stack = [start]
        visited[start] = True
        while stack:
            v = stack.pop()
            component.append(v)
            for nbr, _w in nbrs[v]:
                if not in_district[nbr] or visited[nbr]:
                    continue
                visited[nbr] = True
                stack.append(nbr)
        components.append(component)
    return components
