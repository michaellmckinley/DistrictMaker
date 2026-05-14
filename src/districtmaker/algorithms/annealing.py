"""Simulated annealing for balanced realized-cut minimization.

Different search structure from both splitline and METIS:
  - Starts from a valid balanced partition (typically splitline-realized).
  - Each step: pick a random boundary block, propose moving it to a
    random adjacent district. Accept if balance holds and Metropolis
    criterion passes (always accept improvements; accept worsening
    moves with probability exp(-Δ/T)).
  - Temperature T decays geometrically; tracks best partition seen.

This is a stochastic third independent method. If splitline+KL, METIS,
and SA all converge to similar boundary lengths, that's strong evidence
that they're collectively near the global optimum within the realized-
boundary objective.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import geopandas as gpd
import numpy as np

from districtmaker.algorithms.kl_refine import _cut_weight, refine as kl_refine
from districtmaker.algorithms.splitline import Splitline


@dataclass(frozen=True)
class AnnealStats:
    iterations: int
    moves_accepted: int
    moves_rejected_balance: int
    moves_rejected_metropolis: int
    initial_cut: float
    final_cut: float
    best_cut: float
    initial_temperature: float
    final_temperature: float


class SimulatedAnnealing:
    """Simulated annealing on the block adjacency graph."""

    name = "annealing"

    def __init__(
        self,
        tolerance: float = 0.005,
        iterations: int = 200_000,
        cooling_rate: float = 0.99995,
        seed_initial_partition: str = "splitline",
        initial_temperature: float | None = None,
    ):
        if tolerance <= 0:
            raise ValueError("tolerance must be positive")
        if iterations < 1:
            raise ValueError("iterations must be positive")
        if not (0 < cooling_rate < 1):
            raise ValueError("cooling_rate must be in (0, 1)")
        self.tolerance = tolerance
        self.iterations = iterations
        self.cooling_rate = cooling_rate
        self.seed_initial_partition = seed_initial_partition
        self.initial_temperature = initial_temperature

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
        if edges is None or edge_lengths is None:
            raise ValueError("annealing requires edges and edge_lengths")

        if n_districts == 1:
            assignments = np.zeros(len(blocks), dtype=np.int64)
            return _dissolve_districts(blocks, assignments, state_geometry.crs)

        # Seed partition.
        if self.seed_initial_partition in {"splitline", "splitline+kl"}:
            initial_districts = Splitline(objective="realized").run(
                state_geometry,
                blocks,
                n_districts=n_districts,
                seed=seed,
                edges=edges,
                edge_lengths=edge_lengths,
            )
            assignments = _assignments_from_districts(blocks, initial_districts)
            if self.seed_initial_partition == "splitline+kl":
                pops_arr = blocks["pop"].to_numpy().astype(np.int64)
                assignments, _ = kl_refine(
                    assignments=assignments,
                    pops=pops_arr,
                    edges=edges,
                    edge_lengths=edge_lengths,
                    tolerance=self.tolerance,
                )
        else:
            raise ValueError(f"Unknown seed_initial_partition: {self.seed_initial_partition!r}")

        pops = blocks["pop"].to_numpy().astype(np.int64)
        refined_assignments, _ = anneal(
            assignments=assignments,
            pops=pops,
            edges=edges,
            edge_lengths=edge_lengths,
            tolerance=self.tolerance,
            iterations=self.iterations,
            cooling_rate=self.cooling_rate,
            initial_temperature=self.initial_temperature,
            seed=seed,
        )
        return _dissolve_districts(blocks, refined_assignments, state_geometry.crs)


def anneal(
    assignments: np.ndarray,
    pops: np.ndarray,
    edges: np.ndarray,
    edge_lengths: np.ndarray,
    tolerance: float = 0.005,
    iterations: int = 200_000,
    cooling_rate: float = 0.99995,
    initial_temperature: float | None = None,
    seed: int = 42,
) -> tuple[np.ndarray, AnnealStats]:
    """Run simulated annealing from `assignments`. Returns (best_assignments, stats)."""
    rng = np.random.default_rng(seed)
    assignments = assignments.copy().astype(np.int64)
    pops = pops.astype(np.int64)
    n = len(assignments)
    k = int(assignments.max()) + 1

    pops_per_d = np.zeros(k, dtype=np.int64)
    np.add.at(pops_per_d, assignments, pops)

    total = int(pops_per_d.sum())
    ideal = total / k
    min_pop = ideal * (1 - tolerance)
    max_pop = ideal * (1 + tolerance)

    nbrs: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    for idx in range(len(edges)):
        u, v = int(edges[idx, 0]), int(edges[idx, 1])
        w = float(edge_lengths[idx])
        nbrs[u].append((v, w))
        nbrs[v].append((u, w))

    initial_cut = _cut_weight(assignments, edges, edge_lengths)
    current_cut = initial_cut
    best_cut = initial_cut
    best_assignments = assignments.copy()

    T = initial_temperature if initial_temperature is not None else _auto_initial_temperature(
        assignments, pops, nbrs, rng, target_accept=0.8
    )
    T_initial = T

    accepted = 0
    rejected_balance = 0
    rejected_metropolis = 0

    # Maintain a swap-and-pop list+position map of boundary blocks for O(1)
    # uniform sampling and O(1) add/remove.
    boundary_list: list[int] = []
    boundary_pos: dict[int, int] = {}

    def boundary_add(v: int) -> None:
        if v not in boundary_pos:
            boundary_pos[v] = len(boundary_list)
            boundary_list.append(v)

    def boundary_remove(v: int) -> None:
        pos = boundary_pos.pop(v, None)
        if pos is None:
            return
        last = boundary_list.pop()
        if pos < len(boundary_list):
            boundary_list[pos] = last
            boundary_pos[last] = pos

    def is_boundary(v: int) -> bool:
        av = int(assignments[v])
        return any(int(assignments[nbr]) != av for nbr, _w in nbrs[v])

    for v in range(n):
        if is_boundary(v):
            boundary_add(v)

    for _ in range(iterations):
        T *= cooling_rate
        if not boundary_list:
            continue
        i = boundary_list[int(rng.integers(0, len(boundary_list)))]
        a = int(assignments[i])

        nbr_districts: list[int] = []
        for nbr, _w in nbrs[i]:
            nd = int(assignments[nbr])
            if nd != a and nd not in nbr_districts:
                nbr_districts.append(nd)
        if not nbr_districts:
            boundary_remove(i)
            continue
        d = int(rng.choice(nbr_districts))

        new_a = pops_per_d[a] - pops[i]
        new_d = pops_per_d[d] + pops[i]
        if new_a < min_pop or new_d > max_pop:
            rejected_balance += 1
            continue

        sum_a = 0.0
        sum_d = 0.0
        for nbr, w in nbrs[i]:
            nd = int(assignments[nbr])
            if nd == a:
                sum_a += w
            elif nd == d:
                sum_d += w
        delta = sum_a - sum_d

        if delta < 0 or rng.random() < math.exp(-delta / T):
            assignments[i] = d
            pops_per_d[a] = new_a
            pops_per_d[d] = new_d
            current_cut += delta
            accepted += 1
            # i's boundary status may have flipped, and so may any neighbor's.
            affected = [i] + [int(nb) for nb, _w in nbrs[i]]
            for v in affected:
                if is_boundary(v):
                    boundary_add(v)
                else:
                    boundary_remove(v)
            if current_cut < best_cut:
                best_cut = current_cut
                best_assignments = assignments.copy()
        else:
            rejected_metropolis += 1

    stats = AnnealStats(
        iterations=iterations,
        moves_accepted=accepted,
        moves_rejected_balance=rejected_balance,
        moves_rejected_metropolis=rejected_metropolis,
        initial_cut=initial_cut,
        final_cut=current_cut,
        best_cut=best_cut,
        initial_temperature=T_initial,
        final_temperature=T,
    )
    return best_assignments, stats


def _auto_initial_temperature(
    assignments: np.ndarray,
    pops: np.ndarray,
    nbrs: list,
    rng: np.random.Generator,
    target_accept: float = 0.8,
    sample_size: int = 200,
) -> float:
    """Sample a few uphill moves; pick T so target_accept of them would be accepted."""
    n = len(assignments)
    uphill_deltas: list[float] = []
    for _ in range(sample_size * 5):  # try harder than sample_size, since most picks are interior
        i = int(rng.integers(0, n))
        a = int(assignments[i])
        nbr_d_set: set[int] = set()
        for nbr, _w in nbrs[i]:
            d = int(assignments[nbr])
            if d != a:
                nbr_d_set.add(d)
        if not nbr_d_set:
            continue
        d = int(rng.choice(list(nbr_d_set)))
        sum_a = 0.0
        sum_d = 0.0
        for nbr, w in nbrs[i]:
            nd = int(assignments[nbr])
            if nd == a:
                sum_a += w
            elif nd == d:
                sum_d += w
        delta = sum_a - sum_d
        if delta > 0:
            uphill_deltas.append(delta)
        if len(uphill_deltas) >= sample_size:
            break

    if not uphill_deltas:
        return 1.0  # no uphill moves found; doesn't matter much
    avg_uphill = sum(uphill_deltas) / len(uphill_deltas)
    return avg_uphill / math.log(1 / target_accept)


def _dissolve_districts(
    blocks: gpd.GeoDataFrame, assignments: np.ndarray, crs
) -> gpd.GeoDataFrame:
    blocks = blocks.copy()
    blocks["district_id"] = assignments
    dissolved = blocks.dissolve(by="district_id", aggfunc={"pop": "sum"}).reset_index()
    dissolved = gpd.GeoDataFrame(dissolved, geometry="geometry", crs=crs)
    return dissolved[["district_id", "pop", "geometry"]]


def _assignments_from_districts(
    blocks: gpd.GeoDataFrame, districts: gpd.GeoDataFrame
) -> np.ndarray:
    """Recover per-block district assignments by spatial point-in-polygon lookup."""
    block_points = blocks.geometry.representative_point()
    points_gdf = gpd.GeoDataFrame(
        {"_block_idx": np.arange(len(blocks))}, geometry=list(block_points), crs=blocks.crs
    )
    joined = gpd.sjoin(
        points_gdf, districts[["district_id", "geometry"]], predicate="within", how="left"
    )
    joined = joined.sort_values("_block_idx").drop_duplicates(subset="_block_idx", keep="first")
    assignments = joined.set_index("_block_idx")["district_id"].astype("Int64")
    if assignments.isna().any():
        missing = blocks.iloc[assignments.isna().values]
        nearest = gpd.sjoin_nearest(
            missing[["geometry"]], districts[["district_id", "geometry"]], how="left"
        )
        for idx, did in zip(nearest.index, nearest["district_id"]):
            assignments.loc[idx] = int(did)
    return assignments.astype(np.int64).to_numpy()
