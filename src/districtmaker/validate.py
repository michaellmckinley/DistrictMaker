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
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from districtmaker.experiments import LeaderReport, run_state_experiments
from districtmaker.output.writer import get_logger


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


def write_tier_summary(
    output_dir: Path,
    results: list[StateResult],
    tier_name: str | None,
) -> dict[str, Path]:
    """Merge `results` into the running leader-ledger `summary.{json,md}`.

    Shared across all `validate` invocations into the same output dir.
    Each state appears once, updated to its latest result. An append-only
    `runs` log records each invocation.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "summary.json"
    md_path = output_dir / "summary.md"

    if json_path.exists():
        ledger = json.loads(json_path.read_text())
    else:
        ledger = {"state_results": {}, "runs": []}

    state_results: dict = ledger.setdefault("state_results", {})
    runs: list = ledger.setdefault("runs", [])

    for r in results:
        # "skipped" is a run-time fact (we didn't re-execute this iteration);
        # the canonical state is "ok" because the outputs already exist.
        canonical_status = "ok" if r.status == "skipped" else r.status
        state_results[r.state_code] = {
            "state_code": r.state_code,
            "status": canonical_status,
            "error": r.error,
            "tier": tier_for(r.state_code),
            "elapsed_seconds": r.elapsed_seconds,
            **(r.summary or {}),
        }

    runs.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tier": tier_name,
        "states_attempted": [r.state_code for r in results],
        "ok": [r.state_code for r in results if r.status == "ok"],
        "failed": [r.state_code for r in results if r.status == "failed"],
        "skipped": [r.state_code for r in results if r.status == "skipped"],
    })

    ledger["state_results"] = dict(sorted(state_results.items()))
    ledger["runs"] = runs
    ledger["ok_count"] = sum(1 for v in state_results.values() if v["status"] == "ok")
    ledger["failed_count"] = sum(
        1 for v in state_results.values() if v["status"] == "failed"
    )
    ledger["state_count"] = len(state_results)

    json_path.write_text(json.dumps(ledger, indent=2))
    md_path.write_text(_render_markdown(ledger))
    return {"json": json_path, "markdown": md_path}


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
