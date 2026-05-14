"""Shortest-splitline redistricting (Warren D. Smith), realized-boundary variant.

The algorithm recurses on the state. At each level it splits the current
region's blocks into two population shares (ceil(n/2) and floor(n/2)) by
sweeping candidate straight lines and picking the one that minimizes the
chosen objective.

Two objectives are available:
  - "realized" (default): minimize the realized internal boundary length
    — the sum of shared-edge lengths between adjacent blocks that end up
    in different districts. This is the actual political boundary on the
    map and matches docs/metrics.md's objective definition. Requires
    a precomputed adjacency graph (see data/adjacency.py).
  - "chord": minimize the straight-line chord length of the cut. This is
    the original Smith splitline objective and serves as a fast proxy,
    but at fine granularity it diverges materially from the realized
    boundary it's meant to approximate.

Search strategy per split:
  - Sweep angle theta over [0, pi) at `angle_steps` discrete values.
  - For each theta, sort blocks by signed distance along the line's normal
    and pick the threshold whose left-side cumpop is closest to target.
  - Evaluate the cost (realized or chord), keep the minimum.

Blocks are atomic — a block sits entirely on one side based on its
centroid's signed distance. Population balance per cut is discrete at
block granularity; for ~80k blocks in Idaho the achievable deviation
is well under 0.5%.

Strict side-of-line assignment can strand a block whose centroid lies
on side A but whose only block-graph neighbors lie on side B (a
peninsula, fjord, or off-line spur of the sub-region). Such blocks
form disconnected components inside their assigned side. The cut
search therefore evaluates each candidate `(theta, threshold)` on a
contiguity-corrected assignment — each non-largest component of a side
is flipped to the side it's actually adjacent to — and scores it by
its corrected realized cost. Candidates whose correction would shift
population balance beyond a per-cut budget (≈0.08% of the sub-region)
are filtered out so the global ≤0.5% deviation budget survives the
recursion; if no candidate passes, the budget loosens 2× until one
does. This prevents the pathological case where a large stranded
component would have to be moved across the cut to repair contiguity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import split as shp_split, unary_union


@dataclass(frozen=True)
class Cut:
    theta: float
    threshold: float
    length: float
    left_fraction_achieved: float


class Splitline:
    """Shortest-splitline algorithm with configurable cost objective."""

    name = "splitline"

    def __init__(self, angle_steps: int = 180, objective: str = "realized"):
        if angle_steps < 2:
            raise ValueError("angle_steps must be >= 2")
        if objective not in {"realized", "chord"}:
            raise ValueError(f"objective must be 'realized' or 'chord', got {objective!r}")
        self.angle_steps = angle_steps
        self.objective = objective

    def run(
        self,
        state_geometry: gpd.GeoDataFrame,
        blocks: gpd.GeoDataFrame,
        n_districts: int,
        seed: int = 42,
        edges: np.ndarray | None = None,
        edge_lengths: np.ndarray | None = None,
    ) -> gpd.GeoDataFrame:
        if n_districts < 1:
            raise ValueError("n_districts must be >= 1")

        if state_geometry.crs != blocks.crs:
            raise ValueError("state_geometry and blocks must share a CRS")
        crs = state_geometry.crs

        if self.objective == "realized":
            if edges is None or edge_lengths is None:
                raise ValueError(
                    "objective='realized' requires edges and edge_lengths "
                    "(see districtmaker.data.adjacency.get_adjacency)"
                )

        # Single state polygon as the seed region. unary_union flattens any
        # multi-row state geometry into one (Multi)Polygon.
        region = unary_union(state_geometry.geometry.values)
        block_index = np.arange(len(blocks))
        centroids = blocks.geometry.centroid
        cx = centroids.x.to_numpy()
        cy = centroids.y.to_numpy()
        pops = blocks["pop"].to_numpy().astype(np.int64)

        district_assignments = np.full(len(blocks), -1, dtype=np.int64)
        next_id = [0]

        def assign(region_poly, idx):
            district_assignments[idx] = next_id[0]
            next_id[0] += 1

        def recurse(region_poly, idx, n):
            if n == 1:
                assign(region_poly, idx)
                return
            n_left = math.ceil(n / 2)
            left_fraction = n_left / n
            sub_edges, sub_lengths = _restrict_edges(edges, edge_lengths, idx, len(blocks)) \
                if self.objective == "realized" else (None, None)
            cut, corrected_left = _find_best_cut(
                region_poly,
                cx,
                cy,
                pops,
                idx,
                left_fraction,
                self.angle_steps,
                objective=self.objective,
                sub_edges=sub_edges,
                sub_lengths=sub_lengths,
            )
            if corrected_left is not None:
                left_mask = corrected_left
                right_mask = ~corrected_left
            else:
                left_mask, right_mask = _split_blocks(
                    cx[idx], cy[idx], cut.theta, cut.threshold
                )
            left_idx = idx[left_mask]
            right_idx = idx[right_mask]
            # Polygon split is only needed when the cost function references
            # region geometry (chord). For realized, sub-regions are fully
            # described by block indices, so reuse the parent region. This
            # also avoids Shapely failures on degenerate polygons (Iowa).
            if self.objective == "realized":
                left_poly, right_poly = region_poly, region_poly
            else:
                left_poly, right_poly = _split_polygon(region_poly, cut)
            recurse(left_poly, left_idx, n_left)
            recurse(right_poly, right_idx, n - n_left)

        recurse(region, block_index, n_districts)

        assert (district_assignments >= 0).all(), "every block must be assigned"
        return _dissolve_districts(blocks, district_assignments, crs)


def _find_best_cut(
    region: Polygon,
    cx: np.ndarray,
    cy: np.ndarray,
    pops: np.ndarray,
    idx: np.ndarray,
    left_fraction: float,
    angle_steps: int,
    objective: str = "realized",
    sub_edges: np.ndarray | None = None,
    sub_lengths: np.ndarray | None = None,
) -> tuple[Cut, np.ndarray | None]:
    """Search angles; return the cut minimizing the chosen objective.

    For each angle, sort the sub-region's blocks by signed distance from
    the line's normal, pick the split position whose cumulative population
    is closest to the target left-side fraction, and place the threshold
    strictly between two distinct d-values so block-level ties on the
    boundary are unambiguous.

    Cost depends on `objective`:
      - "chord": in-region length of the cut line itself.
      - "realized": sum of `sub_lengths` whose endpoints lie on opposite
        sides of the threshold (evaluated on the contiguity-corrected
        assignment). This matches the realized internal boundary length
        of the resulting partition.

    For the realized objective, each candidate is contiguity-corrected
    (stranded components flipped to the side they're adjacent to) before
    cost is scored, and candidates whose correction would shift the
    cut's population balance beyond a per-cut budget are filtered out.
    This keeps the recursive bisection's cumulative population deviation
    inside the global ≤0.5% target. Returned as `(cut, corrected_left)`;
    `corrected_left` is the local-index boolean mask to use, or `None`
    for the chord objective (caller falls back to side-of-line).
    """
    cx_idx = cx[idx]
    cy_idx = cy[idx]
    pops_idx = pops[idx]
    total_pop = int(pops_idx.sum())
    target_left_pop = total_pop * left_fraction

    nbrs_local: list[list[int]] | None = None
    if objective == "realized" and sub_edges is not None and len(sub_edges) > 0:
        nbrs_local = _build_local_adjacency(idx, sub_edges)

    # Per-cut population balance budget. The global 0.5% deviation budget
    # must survive ~log2(k) levels of recursion; 0.08% per level leaves
    # headroom. Loosens 2× below if no candidate passes.
    initial_balance_budget = max(1.0, total_pop * 0.0008)

    candidates: list[dict] = []
    thetas = np.linspace(0.0, math.pi, angle_steps, endpoint=False)
    for theta in thetas:
        nx, ny = -math.sin(theta), math.cos(theta)
        d_idx = nx * cx_idx + ny * cy_idx
        order = np.argsort(d_idx, kind="mergesort")  # stable for determinism
        sorted_d = d_idx[order]
        sorted_pops = pops_idx[order]
        cumpop = np.cumsum(sorted_pops)

        breaks = np.where(sorted_d[:-1] < sorted_d[1:])[0]
        if breaks.size == 0:
            continue

        chosen = breaks[int(np.argmin(np.abs(cumpop[breaks] - target_left_pop)))]
        threshold = (sorted_d[chosen] + sorted_d[chosen + 1]) / 2.0
        on_left_local = (d_idx < threshold)

        if objective == "chord":
            line = _cut_line(region, theta, threshold)
            clipped = region.intersection(line)
            cost = clipped.length
            # A zero-length chord is degenerate for the chord objective.
            if cost == 0:
                continue
            candidates.append({
                "cost": cost,
                "theta": theta,
                "threshold": threshold,
                "corrected_left": None,
                "balance_error": abs(int(cumpop[chosen]) - target_left_pop),
                "left_pop": int(cumpop[chosen]),
            })
        else:  # realized
            if nbrs_local is not None:
                corrected_left = _correct_contiguity_local(
                    on_left_local, nbrs_local, pops_idx
                )
            else:
                corrected_left = on_left_local
            on_left_full = np.zeros(len(cx), dtype=bool)
            on_left_full[idx] = corrected_left
            cut_mask = on_left_full[sub_edges[:, 0]] != on_left_full[sub_edges[:, 1]]
            cost = float(sub_lengths[cut_mask].sum())
            left_pop = int(pops_idx[corrected_left].sum())
            # cost == 0 here is *valid and optimal* — the threshold separates
            # two disconnected components of the sub-region's block graph at
            # zero realized boundary cost.
            candidates.append({
                "cost": cost,
                "theta": theta,
                "threshold": threshold,
                "corrected_left": corrected_left,
                "balance_error": abs(left_pop - target_left_pop),
                "left_pop": left_pop,
            })

    if not candidates:
        raise RuntimeError(
            "No valid cut found — region may be degenerate or angle resolution too coarse"
        )

    if objective == "realized":
        budget = initial_balance_budget
        feasible = [c for c in candidates if c["balance_error"] <= budget]
        while not feasible and budget < total_pop:
            budget *= 2
            feasible = [c for c in candidates if c["balance_error"] <= budget]
        if not feasible:
            feasible = candidates
        winner = min(feasible, key=lambda c: c["cost"])
    else:
        winner = min(candidates, key=lambda c: c["cost"])

    cut = Cut(
        theta=winner["theta"],
        threshold=winner["threshold"],
        length=winner["cost"],
        left_fraction_achieved=winner["left_pop"] / total_pop,
    )
    return cut, winner["corrected_left"]


def _restrict_edges(
    edges: np.ndarray,
    lengths: np.ndarray,
    idx: np.ndarray,
    n_total: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return only edges whose both endpoints lie in `idx`."""
    in_region = np.zeros(n_total, dtype=bool)
    in_region[idx] = True
    mask = in_region[edges[:, 0]] & in_region[edges[:, 1]]
    return edges[mask], lengths[mask]


def _cut_line(region: Polygon, theta: float, threshold: float) -> LineString:
    """Build a line segment in the (theta, threshold) family long enough to span `region`."""
    minx, miny, maxx, maxy = region.bounds
    diag = math.hypot(maxx - minx, maxy - miny) * 2 + 1.0
    dx, dy = math.cos(theta), math.sin(theta)
    nx, ny = -math.sin(theta), math.cos(theta)
    cx_line = threshold * nx
    cy_line = threshold * ny
    p1 = (cx_line - dx * diag, cy_line - dy * diag)
    p2 = (cx_line + dx * diag, cy_line + dy * diag)
    return LineString([p1, p2])


def _split_blocks(
    cx: np.ndarray, cy: np.ndarray, theta: float, threshold: float
) -> tuple[np.ndarray, np.ndarray]:
    nx, ny = -math.sin(theta), math.cos(theta)
    d = nx * cx + ny * cy
    left = d < threshold
    return left, ~left


def _split_polygon(region: Polygon, cut: Cut) -> tuple[Polygon, Polygon]:
    """Split `region` by the cut line; group resulting pieces into the two sides.

    Pieces with centroid on the "low" side of the line go left; the rest go right.
    Non-convex regions can produce more than 2 pieces; this groups them correctly.
    """
    line = _cut_line(region, cut.theta, cut.threshold)
    pieces = list(shp_split(region, line).geoms)
    nx, ny = -math.sin(cut.theta), math.cos(cut.theta)
    left_pieces, right_pieces = [], []
    for piece in pieces:
        c = piece.representative_point()
        d = nx * c.x + ny * c.y
        if d < cut.threshold:
            left_pieces.append(piece)
        else:
            right_pieces.append(piece)
    left = unary_union(left_pieces) if left_pieces else Polygon()
    right = unary_union(right_pieces) if right_pieces else Polygon()
    return left, right


def _build_local_adjacency(
    idx: np.ndarray, sub_edges: np.ndarray
) -> list[list[int]]:
    """Local-index adjacency lists for the sub-region.

    `idx` enumerates the sub-region's blocks in global order; the result
    indexes them 0..len(idx)-1. `sub_edges` must already be restricted to
    the sub-region (both endpoints in `idx`).
    """
    n_sub = len(idx)
    if n_sub == 0 or len(sub_edges) == 0:
        return [[] for _ in range(n_sub)]
    max_global = int(idx.max())
    global_to_local = np.full(max_global + 1, -1, dtype=np.int64)
    global_to_local[idx] = np.arange(n_sub)
    nbrs: list[list[int]] = [[] for _ in range(n_sub)]
    for e_idx in range(len(sub_edges)):
        u_g = int(sub_edges[e_idx, 0])
        v_g = int(sub_edges[e_idx, 1])
        u_l = int(global_to_local[u_g])
        v_l = int(global_to_local[v_g])
        if u_l < 0 or v_l < 0:
            continue
        nbrs[u_l].append(v_l)
        nbrs[v_l].append(u_l)
    return nbrs


def _correct_contiguity_local(
    on_left: np.ndarray,
    nbrs_local: list[list[int]],
    sub_pops: np.ndarray,
) -> np.ndarray:
    """Flip stranded components to the side they're adjacent to.

    Operates entirely in local indices using pre-built adjacency. Each
    side's largest-by-population component is kept; non-main components
    flip to the opposite side, where by construction they connect. A
    true isolate (no neighbors in the sub-region) is left alone.

    Converges in 1–2 passes for typical fragments. Capped at 10.
    """
    side = on_left.copy()
    for _ in range(10):
        changed = False
        for is_left in (True, False):
            components = _components_within_side(side, is_left, nbrs_local)
            if len(components) <= 1:
                continue
            components.sort(key=lambda c: -int(sub_pops[c].sum()))
            for fragment in components[1:]:
                has_other_side_neighbor = False
                for i in fragment:
                    for nb in nbrs_local[i]:
                        if bool(side[nb]) != is_left:
                            has_other_side_neighbor = True
                            break
                    if has_other_side_neighbor:
                        break
                if not has_other_side_neighbor:
                    continue
                side[fragment] = not is_left
                changed = True
        if not changed:
            break
    return side


def _enforce_contiguous_sides(
    idx: np.ndarray,
    left_mask: np.ndarray,
    sub_edges: np.ndarray,
    pops: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Global-index wrapper around `_correct_contiguity_local`.

    Builds local adjacency from `sub_edges` and applies the correction.
    Returns both the corrected left mask and its complement.
    """
    n_sub = len(idx)
    if n_sub == 0:
        return left_mask.copy(), ~left_mask.copy()
    nbrs = _build_local_adjacency(idx, sub_edges)
    corrected = _correct_contiguity_local(left_mask, nbrs, pops[idx])
    return corrected, ~corrected


def _components_within_side(
    side: np.ndarray, is_left: bool, nbrs: list[list[int]]
) -> list[np.ndarray]:
    """Connected components within {i : side[i] == is_left}."""
    n = len(side)
    visited = np.zeros(n, dtype=bool)
    out: list[np.ndarray] = []
    for start in range(n):
        if visited[start] or bool(side[start]) != is_left:
            continue
        component = [start]
        stack = [start]
        visited[start] = True
        while stack:
            v = stack.pop()
            for nb in nbrs[v]:
                if visited[nb] or bool(side[nb]) != is_left:
                    continue
                visited[nb] = True
                stack.append(nb)
                component.append(nb)
        out.append(np.array(component, dtype=np.int64))
    return out


def _dissolve_districts(
    blocks: gpd.GeoDataFrame, assignments: np.ndarray, crs
) -> gpd.GeoDataFrame:
    blocks = blocks.copy()
    blocks["district_id"] = assignments
    dissolved = blocks.dissolve(by="district_id", aggfunc={"pop": "sum"}).reset_index()
    dissolved = gpd.GeoDataFrame(dissolved, geometry="geometry", crs=crs)
    return dissolved[["district_id", "pop", "geometry"]]
