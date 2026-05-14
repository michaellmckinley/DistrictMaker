"""Per-state experiment record: run every algorithm, write the artifact
folders, and compute the current leader.

`outputs/<XX>/` layout produced here:

    outputs/TN/
      leader.json            # ranking + current leader + criterion
      leader.md              # human-readable
      districts.{geojson,shp,png,...}  # the leader's full bundle
      metrics.json           # the leader's metrics
      run.log                # the leader's log
      experiments/
        metis+kl/            # full or light bundle per --full-artifacts
          districts.png, metrics.json, run.log
        splitline-realized+kl/ ...
        splitline-chord/     # FAILED → only run.log

The structure is intentionally a directory per experiment so multi-start
can later add `experiments/<name>/trials/trial-NN/` without restructuring.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from districtmaker.apportionment import districts_for_state
from districtmaker.compare import AlgoResult, run_all
from districtmaker.data.adjacency import get_adjacency
from districtmaker.data.loader import load_state
from districtmaker.output.writer import (
    RunInfo,
    current_git_commit,
    get_logger,
    write_outputs,
)

CRITERION = (
    "shortest realized internal boundary; "
    "ties broken by lower max population deviation"
)


@dataclass(frozen=True)
class RankEntry:
    rank: int | None
    experiment: str
    status: str  # "ok" | "failed"
    total_internal_boundary_km: float | None
    max_abs_deviation_pct: float | None
    runtime_seconds: float
    refine_iterations: int
    refine_improvement_pct: float
    gap_to_leader_pct: float | None
    error: str | None

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "experiment": self.experiment,
            "status": self.status,
            "total_internal_boundary_km": self.total_internal_boundary_km,
            "max_abs_deviation_pct": self.max_abs_deviation_pct,
            "runtime_seconds": self.runtime_seconds,
            "refine_iterations": self.refine_iterations,
            "refine_improvement_pct": self.refine_improvement_pct,
            "gap_to_leader_pct": self.gap_to_leader_pct,
            "error": self.error,
        }


@dataclass(frozen=True)
class LeaderReport:
    leader: str | None
    criterion: str
    ranking: list[RankEntry]

    def to_dict(self) -> dict:
        return {
            "leader": self.leader,
            "criterion": self.criterion,
            "ranking": [e.to_dict() for e in self.ranking],
        }


def compute_leader(results: list[AlgoResult]) -> LeaderReport:
    """Rank experiment results and identify the current leader.

    Leader = shortest realized internal boundary among succeeded results,
    ties broken by lower max population deviation. Failed results are
    appended with rank=None and gap=None.
    """
    succeeded = [r for r in results if r.succeeded]
    ranked = sorted(
        succeeded,
        key=lambda r: (r.total_internal_boundary_km, r.max_abs_deviation_pct),
    )
    leader_km = ranked[0].total_internal_boundary_km if ranked else None

    entries: list[RankEntry] = []
    for i, r in enumerate(ranked):
        gap = (
            (r.total_internal_boundary_km - leader_km) / leader_km * 100
            if leader_km is not None
            else 0.0
        )
        entries.append(RankEntry(
            rank=i + 1,
            experiment=r.name,
            status="ok",
            total_internal_boundary_km=r.total_internal_boundary_km,
            max_abs_deviation_pct=r.max_abs_deviation_pct,
            runtime_seconds=r.runtime_seconds,
            refine_iterations=r.refine_iterations,
            refine_improvement_pct=r.refine_improvement_pct,
            gap_to_leader_pct=gap,
            error=None,
        ))
    for r in results:
        if r.succeeded:
            continue
        entries.append(RankEntry(
            rank=None,
            experiment=r.name,
            status="failed",
            total_internal_boundary_km=None,
            max_abs_deviation_pct=None,
            runtime_seconds=r.runtime_seconds,
            refine_iterations=0,
            refine_improvement_pct=0.0,
            gap_to_leader_pct=None,
            error=r.error,
        ))

    return LeaderReport(
        leader=ranked[0].name if ranked else None,
        criterion=CRITERION,
        ranking=entries,
    )


_LIGHT_FORMATS = {"png", "metrics", "log"}
_FULL_FORMATS = {"geojson", "shapefile", "png", "metrics", "log"}


def write_state_record(
    output_dir: Path,
    results: list[AlgoResult],
    state_info: dict,
    seed: int,
    *,
    full_artifacts: bool = False,
    git_commit: str | None = None,
) -> LeaderReport:
    """Write the full per-state experiment record and return the leader report.

    Layout written under `output_dir`:
      experiments/<name>/  — light bundle (png+metrics+log) per succeeded
                             experiment, or just run.log if it failed.
                             Adds geojson+shapefile when full_artifacts=True.
      leader.json / leader.md — ranking + current leader.
      districts.* / metrics.json / run.log — the leader's FULL bundle,
                             written directly to the state root.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    experiments_dir = output_dir / "experiments"
    exp_formats = _FULL_FORMATS if full_artifacts else _LIGHT_FORMATS

    for r in results:
        exp_dir = experiments_dir / r.name
        exp_dir.mkdir(parents=True, exist_ok=True)
        if r.succeeded:
            info = RunInfo(
                state_code=state_info["code"],
                state_name=state_info["name"],
                algorithm=r.name,
                seed=seed,
                runtime_seconds=r.runtime_seconds,
                git_commit=git_commit,
            )
            write_outputs(exp_dir, r.districts, info, formats=exp_formats)
        else:
            _write_failure_log(exp_dir, r, state_info, seed)

    report = compute_leader(results)

    if report.leader is not None:
        leader_result = next(r for r in results if r.name == report.leader)
        info = RunInfo(
            state_code=state_info["code"],
            state_name=state_info["name"],
            algorithm=leader_result.name,
            seed=seed,
            runtime_seconds=leader_result.runtime_seconds,
            git_commit=git_commit,
        )
        write_outputs(output_dir, leader_result.districts, info, formats=_FULL_FORMATS)

    _write_leader_files(output_dir, report, state_info)
    return report


def _write_failure_log(
    exp_dir: Path, result: AlgoResult, state_info: dict, seed: int
) -> None:
    lines = [
        f"state {state_info['code']} ({state_info['name']})",
        f"algorithm {result.name}",
        f"seed {seed}",
        f"runtime_seconds {result.runtime_seconds:.3f}",
        "status FAILED",
        f"error {result.error}",
    ]
    (exp_dir / "run.log").write_text("\n".join(lines) + "\n")


def _write_leader_files(
    output_dir: Path, report: LeaderReport, state_info: dict
) -> None:
    payload = {
        "state": state_info,
        "leader": report.leader,
        "criterion": report.criterion,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trials_per_experiment": 1,
        "ranking": [e.to_dict() for e in report.ranking],
    }
    (output_dir / "leader.json").write_text(json.dumps(payload, indent=2))
    (output_dir / "leader.md").write_text(_render_leader_md(report, state_info))


def _render_leader_md(report: LeaderReport, state_info: dict) -> str:
    name = state_info.get("name", state_info.get("code", "?"))
    leader = report.leader or "— none (all experiments failed)"
    lines = [
        f"# {name} — current leader: {leader}",
        "",
        f"- State: {state_info.get('code')} ({name})",
        f"- Districts: {state_info.get('n_districts')}",
        f"- Criterion: {report.criterion}",
        "- Trials per experiment: 1 (single-run; will change as multi-start lands)",
        "",
        "## Ranking",
        "",
        "| Rank | Experiment | Status | Boundary (km) | Gap to leader | Max dev (%) | Runtime (s) |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    for e in report.ranking:
        if e.status == "failed":
            err = (e.error or "").replace("|", "\\|")
            lines.append(
                f"| — | {e.experiment} | FAILED | — | — | — | "
                f"{e.runtime_seconds:.1f} ({err}) |"
            )
            continue
        lines.append(
            f"| {e.rank} | {e.experiment} | ok | "
            f"{e.total_internal_boundary_km:.2f} | "
            f"+{e.gap_to_leader_pct:.2f}% | "
            f"{e.max_abs_deviation_pct:.4f} | {e.runtime_seconds:.1f} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def run_state_experiments(
    state_code: str,
    output_dir: Path,
    *,
    n_districts: int | None = None,
    seed: int = 42,
    angle_steps: int = 180,
    tolerance: float = 0.005,
    full_artifacts: bool = False,
    log: logging.Logger | None = None,
) -> LeaderReport:
    """Run every algorithm on one state and write its experiment record.

    This is the shared per-state entry point: the `compare` CLI command and
    the `validate` batch driver both call it. Loads the state, builds the
    adjacency graph, runs `compare.run_all`, then `write_state_record`.
    """
    if log is None:
        log = get_logger()
    state_code = state_code.upper()
    n = n_districts if n_districts is not None else districts_for_state(state_code)

    log.info("[%s] loading blocks…", state_code)
    state = load_state(state_code)
    log.info(
        "[%s] %d blocks, population %d",
        state_code,
        state.block_count,
        state.total_population,
    )

    log.info("[%s] building/loading adjacency graph…", state_code)
    edges, lengths = get_adjacency(state.code, state.blocks)

    log.info("[%s] running all experiments (%d districts)…", state_code, n)
    results = run_all(
        state.geometry,
        state.blocks,
        n_districts=n,
        edges=edges,
        edge_lengths=lengths,
        seed=seed,
        angle_steps=angle_steps,
        tolerance=tolerance,
    )

    state_info = {
        "code": state.code,
        "name": state.name,
        "fips": state.fips,
        "n_districts": n,
        "block_count": state.block_count,
        "total_population": state.total_population,
    }
    report = write_state_record(
        output_dir,
        results,
        state_info,
        seed,
        full_artifacts=full_artifacts,
        git_commit=current_git_commit(),
    )
    if report.leader is not None:
        leader = next(e for e in report.ranking if e.experiment == report.leader)
        log.info(
            "[%s] leader: %s (%.2f km)",
            state_code,
            report.leader,
            leader.total_internal_boundary_km,
        )
    else:
        log.warning("[%s] no experiment succeeded", state_code)
    return report
