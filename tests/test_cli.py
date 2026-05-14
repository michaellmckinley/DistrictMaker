"""Tests for the CLI."""
from __future__ import annotations

import json
from unittest.mock import patch

import geopandas as gpd
import pytest
from click.testing import CliRunner
from shapely.geometry import Polygon

from districtmaker.apportionment import DISTRICTS_2020, districts_for_state
from districtmaker.cli import cli
from districtmaker.data.loader import StateData


def _fake_state_data() -> StateData:
    state_geom = gpd.GeoDataFrame(
        {"NAME": ["Testlandia"], "STATEFP": ["99"], "STUSPS": ["TT"]},
        geometry=[Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])],
        crs="EPSG:5070",
    )
    blocks_geom = []
    for ix in range(10):
        for iy in range(10):
            blocks_geom.append(
                Polygon([(ix, iy), (ix + 1, iy), (ix + 1, iy + 1), (ix, iy + 1)])
            )
    blocks = gpd.GeoDataFrame(
        {"pop": [100] * 100, "GEOID20": [f"99{i:08d}" for i in range(100)]},
        geometry=blocks_geom,
        crs="EPSG:5070",
    )
    return StateData(
        code="TT", name="Testlandia", fips="99", geometry=state_geom, blocks=blocks
    )


# --- apportionment lookup -------------------------------------------------------


def test_apportionment_table_sums_to_435():
    assert sum(DISTRICTS_2020.values()) == 435


def test_apportionment_lookup_known_states():
    assert districts_for_state("ID") == 2
    assert districts_for_state("IA") == 4
    assert districts_for_state("CA") == 52
    assert districts_for_state("wy") == 1  # case-insensitive


def test_apportionment_lookup_unknown_raises():
    with pytest.raises(ValueError):
        districts_for_state("ZZ")


# --- CLI end-to-end -------------------------------------------------------------


def test_cli_run_writes_outputs(tmp_path):
    runner = CliRunner()
    with patch("districtmaker.pipeline.load_state", return_value=_fake_state_data()):
        result = runner.invoke(
            cli,
            [
                "run",
                "--state", "TT",
                "--algorithm", "splitline",
                "--districts", "2",
                "--output", str(tmp_path / "out"),
                "--angle-steps", "8",
                "--objective", "chord",  # avoid adjacency cache I/O in tests
                "--no-refine",           # KL refinement also needs the adjacency graph
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    out = tmp_path / "out"
    assert (out / "districts.geojson").exists()
    assert (out / "districts.png").exists()
    assert (out / "metrics.json").exists()
    assert (out / "run.log").exists()

    metrics = json.loads((out / "metrics.json").read_text())
    assert metrics["state"] == "TT"
    assert metrics["algorithm"] == "splitline"
    assert metrics["districts"] == 2


def test_cli_realized_objective_uses_adjacency(tmp_path, monkeypatch):
    monkeypatch.setenv("DISTRICTMAKER_CACHE_DIR", str(tmp_path / "cache"))
    runner = CliRunner()
    with patch("districtmaker.pipeline.load_state", return_value=_fake_state_data()):
        result = runner.invoke(
            cli,
            [
                "run",
                "--state", "TT",
                "--districts", "2",
                "--output", str(tmp_path / "out"),
                "--angle-steps", "8",
                "--objective", "realized",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "cache" / "tt-edges-2020-v2.npz").exists()


def test_cli_default_runs_splitline_plus_kl(tmp_path, monkeypatch):
    """Production default: splitline-realized with KL refinement post-process."""
    monkeypatch.setenv("DISTRICTMAKER_CACHE_DIR", str(tmp_path / "cache"))
    runner = CliRunner()
    with patch("districtmaker.pipeline.load_state", return_value=_fake_state_data()):
        result = runner.invoke(
            cli,
            [
                "run",
                "--state", "TT",
                "--districts", "2",
                "--output", str(tmp_path / "out"),
                "--angle-steps", "8",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    metrics = json.loads((tmp_path / "out" / "metrics.json").read_text())
    assert metrics["algorithm"] == "splitline+kl"


def test_cli_uses_apportionment_when_districts_not_given(tmp_path):
    # Patch the apportionment lookup so the fake state code resolves to 2.
    runner = CliRunner()
    with patch("districtmaker.pipeline.load_state", return_value=_fake_state_data()), \
         patch("districtmaker.pipeline.districts_for_state", return_value=2):
        result = runner.invoke(
            cli,
            [
                "run",
                "--state", "TT",
                "--output", str(tmp_path / "out"),
                "--angle-steps", "8",
                "--objective", "chord",
                "--no-refine",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    metrics = json.loads((tmp_path / "out" / "metrics.json").read_text())
    assert metrics["districts"] == 2


def test_cli_rejects_unknown_algorithm(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            "--state", "ID",
            "--algorithm", "bogus",
            "--output", str(tmp_path / "out"),
        ],
    )
    assert result.exit_code != 0
    assert "bogus" in result.output.lower() or "invalid" in result.output.lower()


def test_cli_compare_writes_experiment_record(tmp_path, monkeypatch):
    monkeypatch.setenv("DISTRICTMAKER_CACHE_DIR", str(tmp_path / "cache"))
    runner = CliRunner()
    with patch("districtmaker.experiments.load_state", return_value=_fake_state_data()):
        result = runner.invoke(
            cli,
            [
                "compare",
                "--state", "TT",
                "--districts", "2",
                "--output", str(tmp_path / "out"),
                "--angle-steps", "8",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    out = tmp_path / "out"
    assert (out / "leader.json").exists()
    assert (out / "leader.md").exists()
    assert (out / "experiments").is_dir()
    # The leader's bundle is promoted to the state root.
    assert (out / "districts.geojson").exists()
    leader = json.loads((out / "leader.json").read_text())
    assert leader["leader"] is not None
    assert leader["state"]["code"] == "TT"


def test_cli_compare_exits_nonzero_when_no_leader(tmp_path):
    from districtmaker.experiments import LeaderReport

    runner = CliRunner()
    with patch(
        "districtmaker.cli.run_state_experiments",
        return_value=LeaderReport(leader=None, criterion="test", ranking=[]),
    ):
        result = runner.invoke(
            cli,
            [
                "compare",
                "--state", "TT",
                "--districts", "2",
                "--output", str(tmp_path / "out"),
            ],
        )
    assert result.exit_code != 0
    assert "No experiment succeeded" in result.output
