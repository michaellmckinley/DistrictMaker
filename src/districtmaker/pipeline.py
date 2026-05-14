"""Reusable production pipeline for `districtmaker run` and `validate`.

Both the per-state CLI and the tier validation driver should produce
byte-identical outputs for the same inputs. They share `execute_run`,
the single function that owns the production sequence:

    load_state → build adjacency (if needed) → run algorithm
    → KL refine (if requested) → write_outputs → return RunSummary

The CLI command is a thin click wrapper around this; the validator
calls it once per state with exception handling.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import numpy as np

from districtmaker.algorithms.annealing import SimulatedAnnealing
from districtmaker.algorithms.contiguity import repair_contiguity
from districtmaker.algorithms.kl_refine import refine as kl_refine
from districtmaker.algorithms.metis import Metis
from districtmaker.algorithms.splitline import Splitline
from districtmaker.apportionment import districts_for_state
from districtmaker.compare import _assignments_from_districts
from districtmaker.data.adjacency import get_adjacency
from districtmaker.data.loader import load_state
from districtmaker.output.writer import RunInfo, current_git_commit, get_logger, write_outputs


ALGORITHMS = {
    "splitline": Splitline,
    "metis": Metis,
    "annealing": SimulatedAnnealing,
}


@dataclass(frozen=True)
class RunSummary:
    """Summary of a production run. Returned by execute_run."""

    state_code: str
    state_name: str
    n_districts: int
    block_count: int
    total_population: int
    algorithm: str
    total_internal_boundary_km: float
    max_abs_deviation_pct: float
    runtime_seconds: float
    refine_moves: int
    refine_improvement_pct: float
    output_paths: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "state_code": self.state_code,
            "state_name": self.state_name,
            "n_districts": self.n_districts,
            "block_count": self.block_count,
            "total_population": self.total_population,
            "algorithm": self.algorithm,
            "total_internal_boundary_km": self.total_internal_boundary_km,
            "max_abs_deviation_pct": self.max_abs_deviation_pct,
            "runtime_seconds": self.runtime_seconds,
            "refine_moves": self.refine_moves,
            "refine_improvement_pct": self.refine_improvement_pct,
            "output_paths": self.output_paths,
        }


def execute_run(
    state_code: str,
    output_dir: Path,
    *,
    n_districts: int | None = None,
    algorithm: str = "splitline",
    seed: int = 42,
    angle_steps: int = 180,
    objective: str = "realized",
    refine_after: bool = True,
    tolerance: float = 0.005,
    log: logging.Logger | None = None,
) -> RunSummary:
    """Run the production pipeline for one state and write its output bundle.

    Production default is splitline (realized objective) + KL refinement
    at 0.5% population tolerance.
    """
    if log is None:
        log = get_logger()
    state_code = state_code.upper()
    n = n_districts if n_districts is not None else districts_for_state(state_code)

    log.info("Loading %s blocks…", state_code)
    state = load_state(state_code)
    log.info(
        "Loaded %s: %d blocks, total population %d",
        state.name,
        state.block_count,
        state.total_population,
    )

    algo_cls = ALGORITHMS[algorithm]
    if algorithm == "splitline":
        algo = algo_cls(angle_steps=angle_steps, objective=objective)
    elif algorithm == "metis":
        algo = algo_cls(tolerance=tolerance)
    elif algorithm == "annealing":
        algo = algo_cls(tolerance=tolerance)
    else:
        algo = algo_cls()

    edges = lengths = None
    needs_edges = (
        algorithm in {"metis", "annealing"}
        or (algorithm == "splitline" and objective == "realized")
        or refine_after
    )
    if needs_edges:
        log.info("Building/loading block adjacency graph…")
        edges, lengths = get_adjacency(state.code, state.blocks)
        log.info("Adjacency: %d edges", len(edges))

    log.info("Running %s (objective=%s) for %d districts…", algorithm, objective, n)
    started = time.perf_counter()
    districts = algo.run(
        state.geometry,
        state.blocks,
        n_districts=n,
        seed=seed,
        edges=edges,
        edge_lengths=lengths,
    )
    elapsed = time.perf_counter() - started
    log.info("Algorithm finished in %.2fs", elapsed)

    refine_moves = 0
    refine_improvement_pct = 0.0
    if refine_after and edges is not None and n > 1:
        log.info("Applying KL refinement…")
        refine_started = time.perf_counter()
        assignments = _assignments_from_districts(state.blocks, districts)
        pops = state.blocks["pop"].to_numpy().astype(np.int64)
        refined, stats = kl_refine(
            assignments=assignments,
            pops=pops,
            edges=edges,
            edge_lengths=lengths,
            tolerance=tolerance,
        )
        refine_elapsed = time.perf_counter() - refine_started
        refine_moves = stats.moves_applied
        refine_improvement_pct = stats.improvement_pct
        log.info(
            "KL refinement: %d moves, %.2f%% improvement (%.2fs)",
            stats.moves_applied,
            stats.improvement_pct,
            refine_elapsed,
        )

        # Repair any non-contiguous fragments that splitline produced and KL
        # could not legally undo. Absorbs small fragments into adjacent
        # districts where balance allows; logs fragments too large to fix.
        log.info("Checking district contiguity…")
        repaired, fragment_reports = repair_contiguity(
            assignments=refined,
            pops=pops,
            edges=edges,
            edge_lengths=lengths,
            tolerance=tolerance,
        )
        if fragment_reports:
            for r in fragment_reports:
                log.info(
                    "  fragment: district %d, %d blocks, %d people → %s",
                    r.district,
                    r.fragment_size_blocks,
                    r.fragment_population,
                    r.action,
                )
        else:
            log.info("  no fragments detected")

        districts = _dissolve_districts(state.blocks, repaired, state.geometry.crs)
        elapsed += time.perf_counter() - refine_started

    final_algorithm_name = (
        algo.name + ("+kl" if refine_after and edges is not None and n > 1 else "")
    )
    info = RunInfo(
        state_code=state.code,
        state_name=state.name,
        algorithm=final_algorithm_name,
        seed=seed,
        runtime_seconds=elapsed,
        git_commit=current_git_commit(),
    )

    log.info("Writing outputs to %s", output_dir)
    paths = write_outputs(output_dir, districts, info)
    for kind, path in paths.items():
        log.info("  %s: %s", kind, path)

    # Read back the metrics so the summary stays in sync with what was written.
    metrics_path = paths["metrics"]
    metrics = json.loads(Path(metrics_path).read_text())

    return RunSummary(
        state_code=state.code,
        state_name=state.name,
        n_districts=n,
        block_count=state.block_count,
        total_population=state.total_population,
        algorithm=final_algorithm_name,
        total_internal_boundary_km=metrics["total_internal_boundary_km"],
        max_abs_deviation_pct=metrics["population"]["max_abs_deviation_pct"],
        runtime_seconds=elapsed,
        refine_moves=refine_moves,
        refine_improvement_pct=refine_improvement_pct,
        output_paths={k: str(v) for k, v in paths.items()},
    )


def _dissolve_districts(
    blocks: gpd.GeoDataFrame, assignments: np.ndarray, crs
) -> gpd.GeoDataFrame:
    blocks = blocks.copy()
    blocks["district_id"] = assignments
    dissolved = blocks.dissolve(by="district_id", aggfunc={"pop": "sum"}).reset_index()
    dissolved = gpd.GeoDataFrame(dissolved, geometry="geometry", crs=crs)
    return dissolved[["district_id", "pop", "geometry"]]
