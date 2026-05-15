"""districtmaker CLI."""
from __future__ import annotations

from pathlib import Path

import click

from districtmaker.compare import ALGORITHM_NAMES
from districtmaker.experiments import run_state_experiments
from districtmaker.multi_start import aggregate_results, build_trial_graph
from districtmaker.output.writer import get_logger
from districtmaker.pipeline import ALGORITHMS as _ALGORITHMS, execute_run
from districtmaker.scheduler import SchedulerState, mutate, read_state
from districtmaker.task_graph import ExperimentPlan
from districtmaker.validate import (
    TIERS,
    run_experiment,
    run_tier,
    write_tier_summary,
)


@click.group()
@click.version_option(package_name="districtmaker")
def cli() -> None:
    """Algorithmic redistricting from pure geometry."""


@cli.command()
@click.option("--state", "state_code", required=True, help="USPS state code, e.g. ID")
@click.option(
    "--algorithm",
    type=click.Choice(sorted(_ALGORITHMS)),
    default="splitline",
    show_default=True,
)
@click.option(
    "--output",
    "output_dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--districts",
    "n_districts",
    type=int,
    default=None,
    help="Override the 2020 apportionment count for this state.",
)
@click.option("--seed", type=int, default=42, show_default=True)
@click.option(
    "--angle-steps",
    type=int,
    default=180,
    show_default=True,
    help="Number of angles to search per split (splitline only).",
)
@click.option(
    "--objective",
    type=click.Choice(["realized", "chord"]),
    default="realized",
    show_default=True,
    help="Splitline cost: 'realized' (true block-edge boundary) or 'chord' (fast proxy).",
)
@click.option(
    "--refine/--no-refine",
    "refine_after",
    default=True,
    show_default=True,
    help="Apply KL local-search refinement after the primary algorithm (production default).",
)
@click.option(
    "--tolerance",
    type=float,
    default=0.005,
    show_default=True,
    help="Max absolute population deviation per district (fraction).",
)
def run(
    state_code: str,
    algorithm: str,
    output_dir: Path,
    n_districts: int | None,
    seed: int,
    angle_steps: int,
    objective: str,
    refine_after: bool,
    tolerance: float,
) -> None:
    """Partition STATE with a single algorithm and write an output bundle.

    A single-algorithm tool for development and debugging. Default is
    splitline + KL refinement against the realized-boundary objective.
    For the full multi-algorithm experiment record and the per-state
    leader assessment, use `compare` instead — no algorithm is the
    designated "production" method (see docs/convergence-2026-05-15.md).
    """
    execute_run(
        state_code=state_code,
        output_dir=output_dir,
        n_districts=n_districts,
        algorithm=algorithm,
        seed=seed,
        angle_steps=angle_steps,
        objective=objective,
        refine_after=refine_after,
        tolerance=tolerance,
        log=get_logger(),
    )


@cli.command()
@click.option("--state", "state_code", required=True, help="USPS state code")
@click.option(
    "--output",
    "output_dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option("--districts", "n_districts", type=int, default=None)
@click.option("--seed", type=int, default=42, show_default=True)
@click.option("--angle-steps", type=int, default=180, show_default=True)
@click.option(
    "--tolerance",
    type=float,
    default=0.005,
    show_default=True,
    help="Max absolute population deviation per district (fraction).",
)
@click.option(
    "--full-artifacts/--light-artifacts",
    default=False,
    show_default=True,
    help="Also emit geojson + shapefile into every experiment folder "
    "(default: only the leader's bundle gets those, at the state root).",
)
def compare(
    state_code: str,
    output_dir: Path,
    n_districts: int | None,
    seed: int,
    angle_steps: int,
    tolerance: float,
    full_artifacts: bool,
) -> None:
    """Run every algorithm on STATE and write the full experiment record.

    Produces `<output>/experiments/<name>/` per algorithm, a `leader.json`
    /`leader.md` assessment, and the current leader's full artifact bundle
    at the output root. This is the published-artifact path; `run` remains
    available as a single-algorithm dev/debug tool.
    """
    state_code = state_code.upper()
    log = get_logger()
    report = run_state_experiments(
        state_code,
        output_dir,
        n_districts=n_districts,
        seed=seed,
        angle_steps=angle_steps,
        tolerance=tolerance,
        full_artifacts=full_artifacts,
        log=log,
    )
    if report.leader is None:
        raise click.ClickException(f"No experiment succeeded for {state_code}")
    log.info("Wrote experiment record to %s", output_dir)
    log.info("Current leader: %s", report.leader)


@cli.command()
@click.option(
    "--tier",
    type=click.Choice(sorted(TIERS)),
    default=None,
    help="Predefined batch of states (easy, middle, tough).",
)
@click.option(
    "--states",
    default=None,
    help="Comma-separated state codes (alternative to --tier).",
)
@click.option(
    "--output",
    "output_dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--force/--skip-existing",
    default=False,
    show_default=True,
    help="Force re-run even if a state's leader.json already exists.",
)
@click.option("--tolerance", type=float, default=0.005, show_default=True)
@click.option("--seed", type=int, default=42, show_default=True)
@click.option(
    "--full-artifacts/--light-artifacts",
    default=False,
    show_default=True,
    help="Emit geojson + shapefile into every experiment folder, not just the leader's.",
)
@click.option(
    "--cpu",
    "cpu_pct",
    type=click.FloatRange(1.0, 100.0),
    default=None,
    help=(
        "Target system CPU percentage cap (1-100). When set, runs in parallel "
        "mode: tasks dispatch only while observed CPU is below the cap. "
        "Adjustable mid-flight via `validate-ctl set-cpu`. Default (unset) "
        "runs sequentially, preserving the pre-parallel behavior."
    ),
)
@click.option(
    "--max-workers",
    type=int,
    default=None,
    help=(
        "Hard ceiling on concurrent tasks (parallel mode only). Useful when "
        "memory rather than CPU is the binding constraint. TX and CA can each "
        "peak ~8-10 GB during metis+kl and splitline-realized+kl; size N to fit."
    ),
)
@click.option(
    "--algorithms",
    "algorithms_csv",
    default=None,
    help=(
        "Comma-separated subset of algorithms to run. Defaults to the full "
        f"bake-off: {', '.join(ALGORITHM_NAMES)}."
    ),
)
@click.option(
    "--poll-seconds",
    type=float,
    default=3.0,
    show_default=True,
    help="Scheduler poll interval (parallel mode only).",
)
def validate(
    tier: str | None,
    states: str | None,
    output_dir: Path,
    force: bool,
    tolerance: float,
    seed: int,
    full_artifacts: bool,
    cpu_pct: float | None,
    max_workers: int | None,
    algorithms_csv: str | None,
    poll_seconds: float,
) -> None:
    """Run the production pipeline across a tier or list of states.

    Sequential by default. Pass `--cpu N` (1-100) to run in parallel mode
    under a CPU-percentage cap that can be adjusted mid-flight via the
    `validate-ctl` subcommands.
    """
    log = get_logger()
    if (tier is None) == (states is None):
        raise click.UsageError("Provide exactly one of --tier or --states")

    if states:
        state_list = [s.strip().upper() for s in states.split(",") if s.strip()]
    else:
        state_list = list(TIERS[tier])

    if algorithms_csv:
        algorithms = tuple(s.strip() for s in algorithms_csv.split(",") if s.strip())
        for a in algorithms:
            if a not in ALGORITHM_NAMES:
                raise click.UsageError(f"unknown algorithm: {a!r}")
    else:
        algorithms = ALGORITHM_NAMES

    if cpu_pct is None:
        # Sequential path — preserves prior behavior exactly.
        results = run_tier(
            tier_name=tier,
            states=state_list,
            output_dir=output_dir,
            force=force,
            tolerance=tolerance,
            seed=seed,
            full_artifacts=full_artifacts,
            log=log,
        )
        paths = write_tier_summary(output_dir, results, tier)
    else:
        plan = ExperimentPlan(states=tuple(state_list), algorithms=algorithms)
        results = run_experiment(
            plan,
            output_dir=output_dir,
            initial_cpu_pct=cpu_pct,
            max_workers=max_workers,
            poll_seconds=poll_seconds,
            force=force,
            seed=seed,
            tolerance=tolerance,
            full_artifacts=full_artifacts,
            tier_name=tier,
            log=log,
        )
        paths = {
            "json": output_dir / "summary.json",
            "markdown": output_dir / "summary.md",
        }

    log.info("Wrote tier summary:")
    for kind, path in paths.items():
        log.info("  %s: %s", kind, path)

    ok = sum(1 for r in results if r.status == "ok")
    failed = sum(1 for r in results if r.status == "failed")
    skipped = sum(1 for r in results if r.status == "skipped")
    log.info("Done: %d ok, %d failed, %d skipped (of %d)", ok, failed, skipped, len(results))


# --- multi-start: seed-varied trials for one (state, algorithm) ---------------


def _run_multi_start_experiment(
    *, plan, output_dir, record_tier_run, seed, full_artifacts,
    state: str, algorithms: tuple[str, ...], trials: int, **kwargs,
):
    """Indirection seam for the multi-start command.

    The CLI builds its task graph directly (no ExperimentPlan fan-out),
    so it can't reuse the same call shape as `validate`. This helper
    is the single surface tests monkeypatch; in production it builds the
    trial graph and forwards to `run_experiment` with `graph_override`.
    """
    graph = build_trial_graph(state=state, algorithms=algorithms, trials=trials)
    return run_experiment(
        plan=plan,
        output_dir=output_dir,
        record_tier_run=record_tier_run,
        seed=seed,
        full_artifacts=full_artifacts,
        graph_override=graph,
        **kwargs,
    )


@cli.command("multi-start")
@click.option("--state", required=True, type=str,
              help="Single state code (e.g. TX).")
@click.option("--algorithms", required=True, type=str,
              help="Comma-separated algorithms (e.g. metis+kl,splitline-realized+kl).")
@click.option("--trials", required=True, type=int,
              help="Number of trials per algorithm.")
@click.option("--base-seed", type=int, default=42, show_default=True,
              help="seed_i = base_seed + i for i in 0..trials-1.")
@click.option("--output", required=True,
              type=click.Path(file_okay=False, path_type=Path),
              help="Output directory for this experiment.")
@click.option("--cpu", type=click.FloatRange(1.0, 100.0), default=None,
              help="Target CPU percentage cap (parallel mode). Required for multi-start.")
@click.option("--max-workers", type=int, default=None,
              help="Hard ceiling on concurrent trials.")
@click.option("--poll-seconds", type=float, default=3.0, show_default=True,
              help="Scheduler poll interval.")
@click.option("--tolerance", type=float, default=0.005, show_default=True)
@click.option("--full-artifacts/--light-artifacts", default=True, show_default=True,
              help="Default --full-artifacts: emit geojson + shapefile for every trial.")
@click.option("--force/--skip-existing", default=False, show_default=True,
              help="Re-run trials whose metrics.json already exists.")
def multi_start_cmd(
    state: str,
    algorithms: str,
    trials: int,
    base_seed: int,
    output: Path,
    cpu: float | None,
    max_workers: int | None,
    poll_seconds: float,
    tolerance: float,
    full_artifacts: bool,
    force: bool,
) -> None:
    """Run a multi-start (seed-varied) experiment for one state.

    Each algorithm runs `trials` times with seeds `base_seed`,
    `base_seed+1`, ..., `base_seed + trials - 1`. Aggregated outputs
    land in `output/`.
    """
    from districtmaker.apportionment import districts_for_state

    state = state.upper()
    try:
        districts_for_state(state)
    except (KeyError, ValueError) as exc:
        raise click.BadParameter(f"unknown state: {state}") from exc

    algos = tuple(a.strip() for a in algorithms.split(",") if a.strip())
    unknown = [a for a in algos if a not in ALGORITHM_NAMES]
    if unknown:
        raise click.BadParameter(f"unknown algorithm(s): {', '.join(unknown)}")

    if cpu is None:
        raise click.BadParameter("--cpu is required for multi-start (parallel mode)")

    if trials < 1:
        raise click.BadParameter("--trials must be >= 1")

    output.mkdir(parents=True, exist_ok=True)

    # Multi-start uses an ad-hoc graph, not an ExperimentPlan with finalize
    # tasks. We still pass an (effectively informational) plan to
    # run_experiment for compatibility — the real fan-out comes from
    # the graph the helper attaches via graph_override.
    plan = ExperimentPlan(states=(state,), algorithms=algos)

    _run_multi_start_experiment(
        plan=plan,
        output_dir=output,
        record_tier_run=False,
        seed=base_seed,
        full_artifacts=full_artifacts,
        state=state,
        algorithms=algos,
        trials=trials,
        initial_cpu_pct=cpu,
        max_workers=max_workers,
        poll_seconds=poll_seconds,
        tolerance=tolerance,
        force=force,
    )

    aggregate_results(
        output_dir=output,
        state=state,
        algorithms=algos,
        trials=trials,
        base_seed=base_seed,
    )

    click.echo(f"multi-start complete. results in {output}/")


# --- validate-ctl: mid-flight control over a running `validate --cpu` ----------


@cli.group("validate-ctl")
def validate_ctl() -> None:
    """Mid-flight control over a running parallel `validate` run.

    These subcommands edit the scheduler control file at
    `<output>/.scheduler_state.json`. The controller polls the file and
    adjusts on the next tick (default ~3 s).
    """


def _ctl_output_option() -> click.Option:
    return click.Option(
        ["--output", "output_dir"],
        required=True,
        type=click.Path(file_okay=False, path_type=Path),
        help="Output directory of the running validate invocation.",
    )


def _replace(state: SchedulerState, **kwargs) -> SchedulerState:
    from dataclasses import replace
    return replace(state, **kwargs)


@validate_ctl.command("set-cpu")
@click.option("--pct", type=click.FloatRange(1.0, 100.0), required=True)
@click.option(
    "--output", "output_dir", required=True,
    type=click.Path(file_okay=False, path_type=Path),
)
def ctl_set_cpu(pct: float, output_dir: Path) -> None:
    """Adjust the target CPU cap of a running run."""
    new = mutate(output_dir, lambda s: _replace(s, target_cpu_pct=pct))
    click.echo(f"target_cpu_pct = {new.target_cpu_pct}  (version={new.version})")


@validate_ctl.command("set-max-workers")
@click.option("--workers", type=int, default=None,
              help="New hard ceiling; pass without value or use --unlimited to clear.")
@click.option("--unlimited", is_flag=True, default=False,
              help="Clear the hard ceiling (workers controlled by CPU cap only).")
@click.option(
    "--output", "output_dir", required=True,
    type=click.Path(file_okay=False, path_type=Path),
)
def ctl_set_max_workers(workers: int | None, unlimited: bool, output_dir: Path) -> None:
    """Adjust the hard concurrency ceiling of a running run."""
    target = None if unlimited else workers
    new = mutate(output_dir, lambda s: _replace(s, max_workers=target))
    click.echo(f"max_workers = {new.max_workers}  (version={new.version})")


@validate_ctl.command("pause")
@click.option(
    "--output", "output_dir", required=True,
    type=click.Path(file_okay=False, path_type=Path),
)
def ctl_pause(output_dir: Path) -> None:
    """Stop dispatching new tasks. In-flight tasks run to completion."""
    new = mutate(output_dir, lambda s: _replace(s, paused=True))
    click.echo(f"paused (version={new.version})")


@validate_ctl.command("freeze")
@click.option(
    "--output", "output_dir", required=True,
    type=click.Path(file_okay=False, path_type=Path),
)
def ctl_freeze(output_dir: Path) -> None:
    """SIGSTOP every live worker — instantaneous pause that holds RAM.

    Use when interactive work needs the CPU for a short window and waiting
    for in-flight tasks (TX/CA can take 2-3 hours each) is not viable.
    Frozen workers consume 0% CPU but still hold their resident memory —
    on a 4-worker freeze with large states, expect ~30 GB resident until
    `validate-ctl resume`.
    """
    new = mutate(output_dir, lambda s: _replace(s, freeze=True))
    click.echo(f"frozen (version={new.version})")


@validate_ctl.command("resume")
@click.option(
    "--output", "output_dir", required=True,
    type=click.Path(file_okay=False, path_type=Path),
)
def ctl_resume(output_dir: Path) -> None:
    """Clear pause and freeze flags; resume dispatching and continue any
    frozen workers."""
    new = mutate(output_dir, lambda s: _replace(s, paused=False, freeze=False))
    click.echo(f"resumed (version={new.version})")


@validate_ctl.command("status")
@click.option(
    "--output", "output_dir", required=True,
    type=click.Path(file_okay=False, path_type=Path),
)
def ctl_status(output_dir: Path) -> None:
    """Print the current scheduler state and run progress."""
    try:
        s = read_state(output_dir)
    except FileNotFoundError:
        raise click.ClickException(f"no scheduler state at {output_dir}")
    click.echo(f"controller pid: {s.pid}")
    click.echo(f"started_at:     {s.started_at}")
    click.echo(f"target_cpu_pct: {s.target_cpu_pct}")
    click.echo(f"max_workers:    {s.max_workers}")
    click.echo(f"paused:         {s.paused}")
    click.echo(f"freeze:         {s.freeze}")
    click.echo(f"state version:  {s.version}")
    summary_path = output_dir / "summary.json"
    if summary_path.exists():
        import json
        data = json.loads(summary_path.read_text())
        click.echo(
            f"states: {data.get('ok_count', 0)} ok, "
            f"{data.get('failed_count', 0)} failed, "
            f"{data.get('state_count', 0)} total"
        )


if __name__ == "__main__":
    cli()
