"""Cross-algorithm comparison harness.

Runs every available algorithm/refinement combination on the same state
and reports realized boundary length, compactness, population deviation,
and runtime side by side. The convergence (or divergence) of independent
methods is the empirical grounding for "we are near-optimal" claims.

Writing the per-state experiment record (artifact folders, leader.json,
leader.md) is handled by `experiments.py`, not here.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import geopandas as gpd
import numpy as np

from districtmaker.algorithms.annealing import SimulatedAnnealing
from districtmaker.algorithms.kl_refine import refine
from districtmaker.algorithms.metis import Metis
from districtmaker.algorithms.splitline import Splitline
from districtmaker.metrics.boundaries import total_internal_boundary_length
from districtmaker.metrics.compactness import (
    convex_hull_ratio,
    polsby_popper,
    reock,
)
from districtmaker.metrics.population import ideal_population, population_deviation


@dataclass(frozen=True)
class AlgoResult:
    name: str
    districts: gpd.GeoDataFrame | None
    runtime_seconds: float
    total_internal_boundary_km: float
    max_abs_deviation_pct: float
    polsby_popper: list[float]
    reock: list[float]
    convex_hull_ratio: list[float]
    refine_iterations: int = 0
    refine_improvement_pct: float = 0.0
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


def run_all(
    state_geometry: gpd.GeoDataFrame,
    blocks: gpd.GeoDataFrame,
    n_districts: int,
    edges: np.ndarray,
    edge_lengths: np.ndarray,
    seed: int = 42,
    angle_steps: int = 180,
    tolerance: float = 0.005,
) -> list[AlgoResult]:
    """Run every configured algorithm and return per-algorithm results.

    The configurations covered:
      - splitline (chord proxy)
      - splitline (realized objective)
      - splitline (realized) + KL refinement
      - metis
      - metis + KL refinement
    """
    pops = blocks["pop"].to_numpy().astype(np.int64)

    results: list[AlgoResult] = []

    # 1. Splitline (chord — kept for historical comparison)
    results.append(_run_and_measure(
        name="splitline-chord",
        algo=Splitline(angle_steps=angle_steps, objective="chord"),
        state=state_geometry,
        blocks=blocks,
        n_districts=n_districts,
        seed=seed,
    ))

    # 2. Splitline (realized)
    sl_realized = _run_and_measure(
        name="splitline-realized",
        algo=Splitline(angle_steps=angle_steps, objective="realized"),
        state=state_geometry,
        blocks=blocks,
        n_districts=n_districts,
        seed=seed,
        edges=edges,
        edge_lengths=edge_lengths,
    )
    results.append(sl_realized)

    # 3. Splitline + KL refinement
    results.append(_refine_and_measure(
        name="splitline-realized+kl",
        base=sl_realized,
        blocks=blocks,
        pops=pops,
        edges=edges,
        edge_lengths=edge_lengths,
        tolerance=tolerance,
        crs=state_geometry.crs,
    ))

    # 4. METIS
    metis_result = _run_and_measure(
        name="metis",
        algo=Metis(tolerance=tolerance),
        state=state_geometry,
        blocks=blocks,
        n_districts=n_districts,
        seed=seed,
        edges=edges,
        edge_lengths=edge_lengths,
    )
    results.append(metis_result)

    # 5. METIS + KL refinement
    results.append(_refine_and_measure(
        name="metis+kl",
        base=metis_result,
        blocks=blocks,
        pops=pops,
        edges=edges,
        edge_lengths=edge_lengths,
        tolerance=tolerance,
        crs=state_geometry.crs,
    ))

    # 6. Simulated annealing (seeded from splitline-realized internally).
    results.append(_run_and_measure(
        name="annealing",
        algo=SimulatedAnnealing(tolerance=tolerance),
        state=state_geometry,
        blocks=blocks,
        n_districts=n_districts,
        seed=seed,
        edges=edges,
        edge_lengths=edge_lengths,
    ))

    # 7. Simulated annealing seeded from splitline+kl (the current best).
    # If SA cannot improve from KL's local minimum, that's evidence the
    # minimum is robust against stochastic exploration.
    results.append(_run_and_measure(
        name="annealing-from-kl",
        algo=SimulatedAnnealing(
            tolerance=tolerance, seed_initial_partition="splitline+kl"
        ),
        state=state_geometry,
        blocks=blocks,
        n_districts=n_districts,
        seed=seed,
        edges=edges,
        edge_lengths=edge_lengths,
    ))

    return results


def _run_and_measure(
    name: str,
    algo,
    state: gpd.GeoDataFrame,
    blocks: gpd.GeoDataFrame,
    n_districts: int,
    seed: int,
    edges: np.ndarray | None = None,
    edge_lengths: np.ndarray | None = None,
) -> AlgoResult:
    started = time.perf_counter()
    kwargs = {"seed": seed}
    if edges is not None:
        kwargs["edges"] = edges
        kwargs["edge_lengths"] = edge_lengths
    try:
        districts = algo.run(state, blocks, n_districts=n_districts, **kwargs)
    except Exception as exc:
        return AlgoResult(
            name=name,
            districts=None,
            runtime_seconds=time.perf_counter() - started,
            total_internal_boundary_km=float("inf"),
            max_abs_deviation_pct=float("nan"),
            polsby_popper=[],
            reock=[],
            convex_hull_ratio=[],
            error=f"{type(exc).__name__}: {exc}",
        )
    elapsed = time.perf_counter() - started
    return _build_result(name, districts, elapsed)


def _refine_and_measure(
    name: str,
    base: AlgoResult,
    blocks: gpd.GeoDataFrame,
    pops: np.ndarray,
    edges: np.ndarray,
    edge_lengths: np.ndarray,
    tolerance: float,
    crs,
) -> AlgoResult:
    """Take a base partition, apply KL, re-dissolve, return refined result."""
    if not base.succeeded:
        return AlgoResult(
            name=name,
            districts=None,
            runtime_seconds=0.0,
            total_internal_boundary_km=float("inf"),
            max_abs_deviation_pct=float("nan"),
            polsby_popper=[],
            reock=[],
            convex_hull_ratio=[],
            error=f"base '{base.name}' failed: {base.error}",
        )
    assignments = _assignments_from_districts(blocks, base.districts)
    started = time.perf_counter()
    refined_assignments, stats = refine(
        assignments=assignments,
        pops=pops,
        edges=edges,
        edge_lengths=edge_lengths,
        tolerance=tolerance,
    )
    elapsed = time.perf_counter() - started

    refined_districts = _dissolve(blocks, refined_assignments, crs)
    result = _build_result(name, refined_districts, base.runtime_seconds + elapsed)
    return AlgoResult(
        name=result.name,
        districts=result.districts,
        runtime_seconds=result.runtime_seconds,
        total_internal_boundary_km=result.total_internal_boundary_km,
        max_abs_deviation_pct=result.max_abs_deviation_pct,
        polsby_popper=result.polsby_popper,
        reock=result.reock,
        convex_hull_ratio=result.convex_hull_ratio,
        refine_iterations=stats.iterations,
        refine_improvement_pct=stats.improvement_pct,
    )


def _build_result(name: str, districts: gpd.GeoDataFrame, runtime: float) -> AlgoResult:
    total_pop = int(districts["pop"].sum())
    ideal = ideal_population(total_pop, len(districts))
    pop_report = population_deviation(districts, ideal_population=ideal)
    return AlgoResult(
        name=name,
        districts=districts,
        runtime_seconds=runtime,
        total_internal_boundary_km=total_internal_boundary_length(districts) / 1000.0,
        max_abs_deviation_pct=pop_report.max_abs_deviation_pct,
        polsby_popper=[polsby_popper(g) for g in districts.geometry],
        reock=[reock(g) for g in districts.geometry],
        convex_hull_ratio=[convex_hull_ratio(g) for g in districts.geometry],
    )


def _assignments_from_districts(
    blocks: gpd.GeoDataFrame, districts: gpd.GeoDataFrame
) -> np.ndarray:
    """Recover per-block district assignments by spatial point-in-polygon lookup."""
    # Use representative points to avoid edge-case ambiguity at shared boundaries.
    block_points = blocks.geometry.representative_point()
    points_gdf = gpd.GeoDataFrame(
        {"_block_idx": np.arange(len(blocks))}, geometry=list(block_points), crs=blocks.crs
    )
    joined = gpd.sjoin(
        points_gdf, districts[["district_id", "geometry"]], predicate="within", how="left"
    )
    # Some points may fall on a shared boundary and land in neither / multiple polygons.
    # Drop duplicates by block index, keeping first.
    joined = joined.sort_values("_block_idx").drop_duplicates(subset="_block_idx", keep="first")
    assignments = joined.set_index("_block_idx")["district_id"].astype("Int64")
    # Fill any NaN (block fell exactly on a boundary) by nearest-polygon assignment.
    if assignments.isna().any():
        missing = blocks.iloc[assignments.isna().values]
        nearest = gpd.sjoin_nearest(
            missing[["geometry"]], districts[["district_id", "geometry"]], how="left"
        )
        for idx, did in zip(nearest.index, nearest["district_id"]):
            assignments.loc[idx] = int(did)
    return assignments.astype(np.int64).to_numpy()


def _dissolve(blocks: gpd.GeoDataFrame, assignments: np.ndarray, crs) -> gpd.GeoDataFrame:
    blocks = blocks.copy()
    blocks["district_id"] = assignments
    dissolved = blocks.dissolve(by="district_id", aggfunc={"pop": "sum"}).reset_index()
    dissolved = gpd.GeoDataFrame(dissolved, geometry="geometry", crs=crs)
    return dissolved[["district_id", "pop", "geometry"]]
