"""Tier validation: run the full experiment record across a batch of states.

States are bucketed (in conversation, not on disk) by what each batch
exposes - see TIERS below.

`run_tier` iterates the chosen tier, calls `run_state_experiments` per
state with exception handling, and merges the results into a single
accumulating leader ledger (`summary.json` + `summary.md`) at the output
root. Already-completed states (those with a `leader.json` under their
subdirectory) are skipped unless `force=True`.

The summary is a running ledger across all `validate` invocations into
the same output dir - each state appears once, updated to its latest
result, plus an append-only `runs` log capturing each invocation.
"""
from __future__ import annotations

import json
import logging
import multiprocessing as mp
import os
import queue as queue_mod
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from districtmaker.apportionment import districts_for_state
from districtmaker.experiments import (
    LeaderReport,
    finalize_state,
    run_single_algorithm_task,
    run_state_experiments,
)
from districtmaker.output.writer import get_logger
from districtmaker.scheduler import (
    DEFAULT_POLL_SECONDS,
    CpuObserver,
    SchedulerState,
    read_state,
    write_state,
)
from districtmaker.task_graph import (
    ExperimentPlan,
    Task,
    TaskGraph,
    build_graph,
)


TIERS: dict[str, list[str]] = {
    "easy": [
        "ID", "MT", "NH", "WV",
        "NE", "NM",
        "AR", "IA", "KS", "NV", "UT",
        "OK",
        "KY",
        "AL",
        "AZ", "IN", "TN",
        "CO", "MN", "MO", "WI",
    ],
    "middle": [
        "HI", "ME", "RI",
        "CT",
        "MS",
        "OR",
        "MD",
        "MA",
        "WA",
        "VA",
        "NJ",
        "SC", "LA",
        "GA",
    ],
    "tough": [
        "MI", "NC",
        "OH", "IL", "PA",
        "NY",
        "FL",
        "TX",
        "CA",
    ],
}


@dataclass(frozen=True)
class StateResult:
    state_code: str
    status: str  # "ok" | "failed" | "skipped"
    error: str | None = None
    summary: dict | None = None
    elapsed_seconds: float = 0.0


def _summary_from_report(state_code: str, report: LeaderReport) -> dict:
    """Flatten a LeaderReport into the per-state ledger row."""
    ok = [e for e in report.ranking if e.status == "ok"]
    failed = [e for e in report.ranking if e.status == "failed"]
    leader = ok[0] if ok else None
    runner_up = ok[1] if len(ok) > 1 else None
    return {
        "state_code": state_code,
        "leader": report.leader,
        "leader_boundary_km": leader.total_internal_boundary_km if leader else None,
        "runner_up": runner_up.experiment if runner_up else None,
        "gap_to_runner_up_pct": runner_up.gap_to_leader_pct if runner_up else None,
        "experiments_ok": len(ok),
        "experiments_failed": len(failed),
    }


def _skip_result_from_leader_json(state_code: str, leader_json: Path) -> StateResult:
    """Build a StateResult for a state skipped because its leader.json exists.

    A cached leader.json with ``"leader": null`` means every experiment
    failed — that is a failure, not a skippable success.
    """
    existing = json.loads(leader_json.read_text())
    if existing.get("leader") is None:
        return StateResult(
            state_code=state_code,
            status="failed",
            error="no experiment succeeded (cached leader.json)",
        )
    ranking = existing.get("ranking", [])
    ok_entries = [e for e in ranking if e.get("status") == "ok"]
    leader = ok_entries[0] if ok_entries else None
    runner_up = ok_entries[1] if len(ok_entries) > 1 else None
    return StateResult(
        state_code=state_code,
        status="skipped",
        summary={
            "state_code": state_code,
            "leader": existing.get("leader"),
            "leader_boundary_km": (
                leader.get("total_internal_boundary_km") if leader else None
            ),
            "runner_up": runner_up.get("experiment") if runner_up else None,
            "gap_to_runner_up_pct": (
                runner_up.get("gap_to_leader_pct") if runner_up else None
            ),
            "experiments_ok": len(ok_entries),
            "experiments_failed": len(ranking) - len(ok_entries),
        },
    )


def run_tier(
    tier_name: str | None,
    states: list[str] | None,
    output_dir: Path,
    *,
    force: bool = False,
    tolerance: float = 0.005,
    seed: int = 42,
    full_artifacts: bool = False,
    log=None,
) -> list[StateResult]:
    """Run the full experiment record on every state in `tier_name` or `states`.

    Exactly one of `tier_name` and `states` should be provided.
    """
    if log is None:
        log = get_logger()
    if (tier_name is None) == (states is None):
        raise ValueError("Provide exactly one of tier_name or states")

    if tier_name is not None:
        if tier_name not in TIERS:
            raise ValueError(f"Unknown tier {tier_name!r}; valid: {sorted(TIERS)}")
        targets = TIERS[tier_name]
    else:
        targets = [s.upper() for s in states]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[StateResult] = []
    for state_code in targets:
        state_dir = output_dir / state_code
        if not force and (state_dir / "leader.json").exists():
            log.info("[%s] SKIP (already completed at %s)", state_code, state_dir)
            results.append(
                _skip_result_from_leader_json(state_code, state_dir / "leader.json")
            )
            continue

        log.info("[%s] running...", state_code)
        started = time.perf_counter()
        try:
            report = run_state_experiments(
                state_code=state_code,
                output_dir=state_dir,
                tolerance=tolerance,
                seed=seed,
                full_artifacts=full_artifacts,
                log=log,
            )
            elapsed = time.perf_counter() - started
            if report.leader is None:
                log.error("[%s] FAILED: no experiment succeeded", state_code)
                results.append(StateResult(
                    state_code=state_code,
                    status="failed",
                    error="no experiment succeeded",
                    elapsed_seconds=elapsed,
                ))
            else:
                results.append(StateResult(
                    state_code=state_code,
                    status="ok",
                    summary=_summary_from_report(state_code, report),
                    elapsed_seconds=elapsed,
                ))
                log.info("[%s] OK  leader %s, %.1fs", state_code, report.leader, elapsed)
        except Exception as exc:
            elapsed = time.perf_counter() - started
            log.error("[%s] FAILED: %s: %s", state_code, type(exc).__name__, exc)
            results.append(StateResult(
                state_code=state_code,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                elapsed_seconds=elapsed,
            ))

    return results


def tier_for(state_code: str) -> str | None:
    """Look up which tier a state belongs to, or None if not in any tier."""
    for tier_name, codes in TIERS.items():
        if state_code in codes:
            return tier_name
    return None


def _load_or_init_ledger(output_dir: Path) -> tuple[Path, Path, dict]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "summary.json"
    md_path = output_dir / "summary.md"
    if json_path.exists():
        ledger = json.loads(json_path.read_text())
    else:
        ledger = {"state_results": {}, "runs": []}
    ledger.setdefault("state_results", {})
    ledger.setdefault("runs", [])
    return json_path, md_path, ledger


def _flush_ledger(json_path: Path, md_path: Path, ledger: dict) -> None:
    state_results = ledger["state_results"]
    ledger["state_results"] = dict(sorted(state_results.items()))
    ledger["ok_count"] = sum(1 for v in state_results.values() if v["status"] == "ok")
    ledger["failed_count"] = sum(
        1 for v in state_results.values() if v["status"] == "failed"
    )
    ledger["state_count"] = len(state_results)
    json_path.write_text(json.dumps(ledger, indent=2))
    md_path.write_text(_render_markdown(ledger))


def update_state_in_summary(output_dir: Path, result: StateResult) -> dict[str, Path]:
    """Merge a single `StateResult` into the leader ledger.

    Used by the parallel runner after each state's finalization task
    completes. Does **not** touch the `runs` log — that is appended once
    per invocation via `append_tier_run`.
    """
    json_path, md_path, ledger = _load_or_init_ledger(output_dir)
    canonical_status = "ok" if result.status == "skipped" else result.status
    ledger["state_results"][result.state_code] = {
        "state_code": result.state_code,
        "status": canonical_status,
        "error": result.error,
        "tier": tier_for(result.state_code),
        "elapsed_seconds": result.elapsed_seconds,
        **(result.summary or {}),
    }
    _flush_ledger(json_path, md_path, ledger)
    return {"json": json_path, "markdown": md_path}


def append_tier_run(
    output_dir: Path,
    tier_name: str | None,
    results: list[StateResult],
) -> dict[str, Path]:
    """Append a single entry to the ledger's `runs` log summarizing this
    invocation. Called once per `run_experiment` / `run_tier` invocation."""
    json_path, md_path, ledger = _load_or_init_ledger(output_dir)
    ledger["runs"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tier": tier_name,
        "states_attempted": [r.state_code for r in results],
        "ok": [r.state_code for r in results if r.status == "ok"],
        "failed": [r.state_code for r in results if r.status == "failed"],
        "skipped": [r.state_code for r in results if r.status == "skipped"],
    })
    _flush_ledger(json_path, md_path, ledger)
    return {"json": json_path, "markdown": md_path}


def write_tier_summary(
    output_dir: Path,
    results: list[StateResult],
    tier_name: str | None,
) -> dict[str, Path]:
    """Backward-compatible convenience: update every state then append a run.

    New code should call `update_state_in_summary` and `append_tier_run`
    directly so per-state ledger updates can interleave with parallel
    state completions.
    """
    for r in results:
        update_state_in_summary(output_dir, r)
    return append_tier_run(output_dir, tier_name, results)


def _render_markdown(ledger: dict) -> str:
    state_results: dict = ledger.get("state_results", {})
    runs: list = ledger.get("runs", [])

    lines = [
        "# DistrictMaker leader ledger",
        "",
        f"- Total states tracked: {len(state_results)}",
        f"- OK: {ledger.get('ok_count', 0)}",
        f"- Failed: {ledger.get('failed_count', 0)}",
        f"- Validate invocations recorded: {len(runs)}",
        "",
        "## Per-state leader",
        "",
        "| Tier | State | Status | Leader | Leader boundary (km) | Runner-up | Gap to runner-up | Runtime (s) |",
        "|---|---|---|---|---:|---|---:|---:|",
    ]

    tier_order = {"easy": 0, "middle": 1, "tough": 2, None: 3}
    sorted_states = sorted(
        state_results.values(),
        key=lambda v: (tier_order.get(v.get("tier"), 99), v["state_code"]),
    )
    for v in sorted_states:
        tier = v.get("tier") or "-"
        if v["status"] == "failed":
            err = (v.get("error") or "").replace("|", "\\|")
            lines.append(
                f"| {tier} | {v['state_code']} | FAILED | - | - | - | - | "
                f"{v.get('elapsed_seconds', 0):.1f} ({err}) |"
            )
            continue
        km = v.get("leader_boundary_km")
        gap = v.get("gap_to_runner_up_pct")
        km_s = f"{km:.2f}" if km is not None else "-"
        gap_s = f"+{gap:.2f}%" if gap is not None else "-"
        runtime = v.get("elapsed_seconds", 0)
        lines.append(
            f"| {tier} | {v['state_code']} | {v['status']} | "
            f"{v.get('leader', '-')} | {km_s} | {v.get('runner_up', '-')} | "
            f"{gap_s} | {runtime:.1f} |"
        )

    if runs:
        lines += [
            "", "## Run history", "",
            "| Timestamp | Tier | Attempted | OK | Failed | Skipped |",
            "|---|---|---:|---:|---:|---:|",
        ]
        for run in runs:
            lines.append(
                f"| {run['timestamp']} | {run.get('tier') or 'custom'} | "
                f"{len(run.get('states_attempted', []))} | "
                f"{len(run.get('ok', []))} | "
                f"{len(run.get('failed', []))} | "
                f"{len(run.get('skipped', []))} |"
            )

    return "\n".join(lines) + "\n"


# --- parallel runner ------------------------------------------------------------


def decide_dispatch(
    graph: TaskGraph,
    *,
    live: set[Task],
    sched: SchedulerState,
    observed_cpu: float,
) -> list[Task]:
    """Pure scheduling decision: which (if any) ready task to start now.

    Returns at most one task per tick — the controller calls this each
    poll cycle so concurrency ramps gradually (avoiding spike-then-throttle
    oscillation). Returns `[]` if dispatch is blocked by pause/freeze/CPU/
    max-workers, or if no ready task is available.
    """
    if sched.paused or sched.freeze:
        return []
    if observed_cpu >= sched.target_cpu_pct:
        return []
    if sched.max_workers is not None and len(live) >= sched.max_workers:
        return []
    ready = graph.ready_tasks()
    if not ready:
        return []
    return [ready[0]]


@dataclass(frozen=True)
class _TaskMessage:
    """Result envelope posted by a worker on the result queue."""
    task: Task
    status: str           # "ok" | "failed"
    error: str | None = None
    state_summary: dict | None = None      # set for "_finalize" tasks
    elapsed_seconds: float = 0.0


def _worker_main(
    task: Task,
    state_output_dir: str,
    n_districts: int | None,
    seed: int,
    angle_steps: int,
    tolerance: float,
    full_artifacts: bool,
    result_q: "mp.Queue[_TaskMessage]",
) -> None:
    """Module-level worker entry point (picklable for multiprocessing).

    Algorithm tasks run a single (state, algorithm); finalization tasks
    aggregate that state's per-experiment results into leader.json/leader.md
    and report back a state-level summary the controller folds into the
    cross-state ledger.
    """
    started = time.perf_counter()
    try:
        if task.is_finalization:
            state_info = {
                "code": task.state_code,
                "name": task.state_code,
                "fips": "00",
                "n_districts": n_districts,
            }
            try:
                from districtmaker.data.loader import load_state
                state = load_state(task.state_code)
                state_info["name"] = state.name
                state_info["fips"] = state.fips
                if n_districts is None:
                    state_info["n_districts"] = districts_for_state(task.state_code)
            except Exception:
                pass
            report = finalize_state(
                state_code=task.state_code,
                state_output_dir=Path(state_output_dir),
                state_info=state_info,
                seed=seed,
                full_artifacts=full_artifacts,
            )
            summary = _leader_report_to_summary(report)
            elapsed = time.perf_counter() - started
            result_q.put(_TaskMessage(
                task=task,
                status="ok" if report.leader is not None else "failed",
                error=None if report.leader is not None else "no successful experiments",
                state_summary=summary,
                elapsed_seconds=elapsed,
            ))
        else:
            run_single_algorithm_task(
                state_code=task.state_code,
                algorithm=task.algorithm,
                state_output_dir=Path(state_output_dir),
                n_districts=n_districts,
                seed=seed,
                angle_steps=angle_steps,
                tolerance=tolerance,
                full_artifacts=full_artifacts,
            )
            elapsed = time.perf_counter() - started
            result_q.put(_TaskMessage(task=task, status="ok", elapsed_seconds=elapsed))
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - started
        result_q.put(_TaskMessage(
            task=task,
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
            elapsed_seconds=elapsed,
        ))


def _leader_report_to_summary(report: LeaderReport) -> dict:
    """Translate a LeaderReport into the state_results row shape."""
    if report.leader is None:
        return {
            "leader": None,
            "leader_boundary_km": None,
            "runner_up": None,
            "gap_to_runner_up_pct": None,
            "experiments_ok": sum(1 for e in report.ranking if e.status == "ok"),
            "experiments_failed": sum(1 for e in report.ranking if e.status == "failed"),
        }
    ranked_ok = [e for e in report.ranking if e.status == "ok" and e.rank is not None]
    leader = ranked_ok[0]
    runner_up = ranked_ok[1] if len(ranked_ok) >= 2 else None
    return {
        "leader": leader.experiment,
        "leader_boundary_km": leader.total_internal_boundary_km,
        "runner_up": runner_up.experiment if runner_up else None,
        "gap_to_runner_up_pct": runner_up.gap_to_leader_pct if runner_up else None,
        "experiments_ok": sum(1 for e in report.ranking if e.status == "ok"),
        "experiments_failed": sum(1 for e in report.ranking if e.status == "failed"),
    }


def run_experiment(
    plan: ExperimentPlan,
    output_dir: Path,
    *,
    initial_cpu_pct: float = 50.0,
    max_workers: int | None = None,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    force: bool = False,
    seed: int = 42,
    angle_steps: int = 180,
    tolerance: float = 0.005,
    full_artifacts: bool = False,
    tier_name: str | None = None,
    log: logging.Logger | None = None,
    _cpu_observer: CpuObserver | None = None,
) -> list[StateResult]:
    """Parallel, CPU-governed experiment runner.

    Builds the task graph from `plan`, writes an initial scheduler state
    file, then loops: poll scheduler file, drain result queue, dispatch
    ready tasks subject to CPU/worker caps. Each completed finalization
    task immediately updates `summary.json`. At the end, appends a single
    `runs` entry covering the whole invocation.
    """
    if log is None:
        log = get_logger()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    targets = list(plan.states)
    if not force:
        targets = [s for s in targets if not (output_dir / s / "leader.json").exists()]
    effective_plan = ExperimentPlan(states=tuple(targets), algorithms=plan.algorithms)
    graph = build_graph(effective_plan)

    write_state(output_dir, SchedulerState(
        target_cpu_pct=initial_cpu_pct,
        max_workers=max_workers,
        pid=os.getpid(),
        started_at=datetime.now(timezone.utc).isoformat(),
    ))

    cpu = _cpu_observer if _cpu_observer is not None else CpuObserver()
    result_q: "mp.Queue[_TaskMessage]" = mp.Queue()
    live: dict[Task, mp.Process] = {}
    last_freeze = False
    state_results: dict[str, StateResult] = {}

    while not graph.all_done():
        try:
            sched = read_state(output_dir)
        except FileNotFoundError:
            sched = SchedulerState(target_cpu_pct=initial_cpu_pct)

        # Freeze edge transitions
        if sched.freeze and not last_freeze:
            for p in live.values():
                try:
                    os.kill(p.pid, signal.SIGSTOP)
                except ProcessLookupError:
                    pass
        elif not sched.freeze and last_freeze:
            for p in live.values():
                try:
                    os.kill(p.pid, signal.SIGCONT)
                except ProcessLookupError:
                    pass
        last_freeze = sched.freeze

        cpu.update()

        # Dispatch
        picks = decide_dispatch(graph, live=set(live), sched=sched, observed_cpu=cpu.current())
        for task in picks:
            n_districts = (
                districts_for_state(task.state_code)
                if not task.is_finalization
                else None
            )
            state_dir = output_dir / task.state_code
            p = mp.Process(
                target=_worker_main,
                args=(task, str(state_dir), n_districts, seed, angle_steps,
                      tolerance, full_artifacts, result_q),
                name=f"dm-{task.state_code}-{task.algorithm}",
            )
            p.start()
            live[task] = p
            graph.mark_running(task)
            log.info("dispatched %s/%s (pid %s)", task.state_code, task.algorithm, p.pid)

        # Drain results (poll_seconds doubles as sleep)
        deadline = time.monotonic() + poll_seconds
        while time.monotonic() < deadline:
            try:
                msg: _TaskMessage = result_q.get(timeout=max(0.05, deadline - time.monotonic()))
            except queue_mod.Empty:
                break
            proc = live.pop(msg.task, None)
            if proc is not None:
                proc.join()
            if msg.status == "ok":
                graph.mark_done(msg.task)
            else:
                graph.mark_failed(msg.task, msg.error or "")
            log.info(
                "completed %s/%s status=%s elapsed=%.1fs",
                msg.task.state_code, msg.task.algorithm,
                msg.status, msg.elapsed_seconds,
            )
            if msg.task.is_finalization:
                status = "ok" if msg.status == "ok" else "failed"
                sr = StateResult(
                    state_code=msg.task.state_code,
                    status=status,
                    error=msg.error,
                    summary=msg.state_summary,
                    elapsed_seconds=msg.elapsed_seconds,
                )
                state_results[msg.task.state_code] = sr
                update_state_in_summary(output_dir, sr)

        # Reap crashed workers (process died without posting a result)
        for task, proc in list(live.items()):
            if not proc.is_alive():
                proc.join()
                if graph.status(task) == "running":
                    graph.mark_failed(task, f"worker exited code={proc.exitcode}")
                    log.warning(
                        "%s/%s worker died (exit=%s)",
                        task.state_code, task.algorithm, proc.exitcode,
                    )
                    if task.is_finalization:
                        state_results[task.state_code] = StateResult(
                            state_code=task.state_code,
                            status="failed",
                            error=f"worker exited code={proc.exitcode}",
                            summary=None,
                        )
                        update_state_in_summary(output_dir, state_results[task.state_code])
                live.pop(task, None)

    results = list(state_results.values())
    append_tier_run(output_dir, tier_name, results)
    return results
