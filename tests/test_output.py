"""Tests for the output writer and map renderer."""
from __future__ import annotations

import json

import geopandas as gpd
from shapely.geometry import Polygon

from districtmaker.output.writer import RunInfo, write_outputs


def _two_district_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "district_id": [0, 1],
            "pop": [1000, 1000],
        },
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
        ],
        crs="EPSG:5070",
    )


def test_write_outputs_creates_all_five_artifacts(tmp_path):
    districts = _two_district_gdf()
    run = RunInfo(
        state_code="TT",
        state_name="Testlandia",
        algorithm="splitline",
        seed=42,
        runtime_seconds=1.23,
    )
    paths = write_outputs(tmp_path, districts, run)

    assert paths["geojson"].exists()
    assert paths["shapefile"].exists()
    assert paths["png"].exists()
    assert paths["metrics"].exists()
    assert paths["log"].exists()

    # Shapefile has companion files
    assert paths["shapefile"].with_suffix(".dbf").exists()
    assert paths["shapefile"].with_suffix(".shx").exists()


def test_metrics_json_has_expected_structure(tmp_path):
    districts = _two_district_gdf()
    run = RunInfo(
        state_code="TT",
        state_name="Testlandia",
        algorithm="splitline",
        seed=42,
        runtime_seconds=1.23,
    )
    paths = write_outputs(tmp_path, districts, run)

    metrics = json.loads(paths["metrics"].read_text())
    assert metrics["state"] == "TT"
    assert metrics["state_name"] == "Testlandia"
    assert metrics["algorithm"] == "splitline"
    assert metrics["districts"] == 2
    assert metrics["seed"] == 42
    assert "total_internal_boundary_km" in metrics
    assert "population" in metrics
    assert "compactness" in metrics
    assert set(metrics["compactness"].keys()) == {
        "polsby_popper",
        "reock",
        "schwartzberg",
        "convex_hull_ratio",
    }
    assert len(metrics["compactness"]["polsby_popper"]) == 2


def test_metrics_json_reports_balanced_population_as_zero_deviation(tmp_path):
    districts = _two_district_gdf()  # 1000 each → ideal 1000 → deviation 0
    run = RunInfo("TT", "Testlandia", "splitline", 42, 0.5)
    paths = write_outputs(tmp_path, districts, run)
    metrics = json.loads(paths["metrics"].read_text())
    assert metrics["population"]["max_abs_deviation_pct"] == 0


def test_run_log_records_parameters(tmp_path):
    districts = _two_district_gdf()
    run = RunInfo("TT", "Testlandia", "splitline", 7, 12.345, git_commit="abc1234")
    paths = write_outputs(tmp_path, districts, run)
    log = paths["log"].read_text()
    assert "seed 7" in log
    assert "algorithm splitline" in log
    assert "state TT (Testlandia)" in log
    assert "runtime_seconds 12.345" in log
    assert "git_commit abc1234" in log


def test_geojson_round_trips_through_geopandas(tmp_path):
    districts = _two_district_gdf()
    run = RunInfo("TT", "Testlandia", "splitline", 42, 0.5)
    paths = write_outputs(tmp_path, districts, run)
    reloaded = gpd.read_file(paths["geojson"])
    assert len(reloaded) == 2
    assert set(reloaded["district_id"].tolist()) == {0, 1}
    assert reloaded["pop"].sum() == 2000


def test_write_outputs_formats_subset_skips_geojson_and_shapefile(tmp_path):
    districts = _two_district_gdf()
    run = RunInfo(
        state_code="TT",
        state_name="Testlandia",
        algorithm="metis+kl",
        seed=42,
        runtime_seconds=1.23,
    )
    paths = write_outputs(tmp_path, districts, run, formats={"png", "metrics", "log"})

    assert set(paths) == {"png", "metrics", "log"}
    assert paths["png"].exists()
    assert paths["metrics"].exists()
    assert paths["log"].exists()
    assert not (tmp_path / "districts.geojson").exists()
    assert not (tmp_path / "districts.shp").exists()


def test_write_outputs_formats_none_writes_all_five(tmp_path):
    districts = _two_district_gdf()
    run = RunInfo(
        state_code="TT",
        state_name="Testlandia",
        algorithm="splitline+kl",
        seed=42,
        runtime_seconds=1.23,
    )
    paths = write_outputs(tmp_path, districts, run)
    assert set(paths) == {"geojson", "shapefile", "png", "metrics", "log"}
    for p in paths.values():
        assert p.exists()
