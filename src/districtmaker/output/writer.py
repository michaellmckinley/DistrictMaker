"""Write a complete run bundle: GeoJSON + Shapefile + PNG + metrics + log."""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd

from districtmaker import __version__
from districtmaker.metrics.boundaries import total_internal_boundary_length
from districtmaker.metrics.compactness import (
    convex_hull_ratio,
    polsby_popper,
    reock,
    schwartzberg,
)
from districtmaker.metrics.population import ideal_population, population_deviation
from districtmaker.viz.maps import render_districts


_VALID_FORMATS = {"geojson", "shapefile", "png", "metrics", "log"}


@dataclass(frozen=True)
class RunInfo:
    state_code: str
    state_name: str
    algorithm: str
    seed: int
    runtime_seconds: float
    git_commit: str | None = None


def write_outputs(
    output_dir: Path,
    districts: gpd.GeoDataFrame,
    run: RunInfo,
    formats: set[str] | None = None,
) -> dict[str, Path]:
    """Write the requested artifacts and return a name->path map.

    Artifacts (all written when `formats` is None):
        districts.geojson — district polygons          (key "geojson")
        districts.shp     — ESRI shapefile (+ companions) (key "shapefile")
        districts.png     — static map                  (key "png")
        metrics.json      — objective + compactness + population summary (key "metrics")
        run.log           — parameters, runtime, library versions (key "log")

    Pass `formats` as a subset of {"geojson","shapefile","png","metrics","log"}
    to write only those. The metrics dict is always computed (cheap, and the
    log depends on it); only the metrics.json file is gated by the set.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    selected = (
        set(_VALID_FORMATS)
        if formats is None
        else set(formats)
    )
    if unknown := selected - _VALID_FORMATS:
        raise ValueError(
            f"Unknown format key(s): {unknown!r}. Valid: {_VALID_FORMATS!r}"
        )

    geojson = output_dir / "districts.geojson"
    shp = output_dir / "districts.shp"
    png = output_dir / "districts.png"
    metrics_path = output_dir / "metrics.json"
    log_path = output_dir / "run.log"

    metrics = _build_metrics(districts, run)

    paths: dict[str, Path] = {}
    if "geojson" in selected:
        districts.to_file(geojson, driver="GeoJSON")
        paths["geojson"] = geojson
    if "shapefile" in selected:
        districts.to_file(shp, driver="ESRI Shapefile")
        paths["shapefile"] = shp
    if "png" in selected:
        title = f"{run.state_name} — {run.algorithm} — {len(districts)} districts"
        render_districts(districts, png, title=title)
        paths["png"] = png
    if "metrics" in selected:
        metrics_path.write_text(json.dumps(metrics, indent=2))
        paths["metrics"] = metrics_path
    if "log" in selected:
        log_path.write_text(_build_log(run, metrics))
        paths["log"] = log_path

    return paths


def _build_metrics(districts: gpd.GeoDataFrame, run: RunInfo) -> dict:
    total_pop = int(districts["pop"].sum())
    n = len(districts)
    ideal = ideal_population(total_pop, n)
    pop_report = population_deviation(districts, ideal_population=ideal)

    boundary_m = total_internal_boundary_length(districts)
    pp = [polsby_popper(g) for g in districts.geometry]
    rk = [reock(g) for g in districts.geometry]
    sb = [schwartzberg(g) for g in districts.geometry]
    ch = [convex_hull_ratio(g) for g in districts.geometry]

    return {
        "state": run.state_code,
        "state_name": run.state_name,
        "algorithm": run.algorithm,
        "districts": n,
        "total_internal_boundary_km": boundary_m / 1000.0,
        "population": pop_report.to_dict(),
        "compactness": {
            "polsby_popper": pp,
            "reock": rk,
            "schwartzberg": sb,
            "convex_hull_ratio": ch,
        },
        "runtime_seconds": run.runtime_seconds,
        "seed": run.seed,
        "districtmaker_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_log(run: RunInfo, metrics: dict) -> str:
    lines = [
        f"districtmaker {__version__}",
        f"python {sys.version.split()[0]}",
        f"generated_at {metrics['generated_at']}",
        f"state {run.state_code} ({run.state_name})",
        f"algorithm {run.algorithm}",
        f"districts {metrics['districts']}",
        f"seed {run.seed}",
        f"runtime_seconds {run.runtime_seconds:.3f}",
        f"git_commit {run.git_commit or 'unknown'}",
        f"max_abs_deviation_pct {metrics['population']['max_abs_deviation_pct']:.6f}",
        f"total_internal_boundary_km {metrics['total_internal_boundary_km']:.6f}",
    ]
    return "\n".join(lines) + "\n"


def get_logger(name: str = "districtmaker") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def current_git_commit() -> str | None:
    """Short HEAD hash of the repository containing this file, or None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            cwd=Path(__file__).resolve().parent,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except (FileNotFoundError, OSError):
        pass
    return None
