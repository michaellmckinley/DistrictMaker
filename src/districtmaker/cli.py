"""districtmaker CLI."""
from __future__ import annotations

from pathlib import Path

import click

from districtmaker.experiments import run_state_experiments
from districtmaker.output.writer import get_logger
from districtmaker.pipeline import ALGORITHMS as _ALGORITHMS, execute_run
from districtmaker.validate import TIERS, run_tier, write_tier_summary


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
def validate(
    tier: str | None,
    states: str | None,
    output_dir: Path,
    force: bool,
    tolerance: float,
    seed: int,
    full_artifacts: bool,
) -> None:
    """Run the production pipeline across a tier or list of states."""
    log = get_logger()
    if (tier is None) == (states is None):
        raise click.UsageError("Provide exactly one of --tier or --states")

    state_list = None
    if states:
        state_list = [s.strip().upper() for s in states.split(",") if s.strip()]

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
    log.info("Wrote tier summary:")
    for kind, path in paths.items():
        log.info("  %s: %s", kind, path)

    ok = sum(1 for r in results if r.status == "ok")
    failed = sum(1 for r in results if r.status == "failed")
    skipped = sum(1 for r in results if r.status == "skipped")
    log.info("Done: %d ok, %d failed, %d skipped (of %d)", ok, failed, skipped, len(results))


if __name__ == "__main__":
    cli()
