"""Tests for the tier validation driver."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from districtmaker.cli import cli
from districtmaker.experiments import LeaderReport, RankEntry
from districtmaker.validate import TIERS, run_tier, write_tier_summary


# --- tier definitions -----------------------------------------------------------


def test_tiers_partition_into_three_buckets():
    assert set(TIERS) == {"easy", "middle", "tough"}


def test_tiers_contain_distinct_states():
    seen: set[str] = set()
    for code in [c for codes in TIERS.values() for c in codes]:
        assert code not in seen, f"{code} appears in multiple tiers"
        seen.add(code)


def test_easy_tier_includes_idaho_and_iowa():
    assert "ID" in TIERS["easy"]
    assert "IA" in TIERS["easy"]


def test_tough_tier_includes_the_user_named_four():
    for code in {"CA", "TX", "FL", "NY"}:
        assert code in TIERS["tough"], f"{code} missing from tough tier"


# --- helpers --------------------------------------------------------------------


def _fake_report(code: str, leader_km: float = 1000.0) -> LeaderReport:
    return LeaderReport(
        leader="metis+kl",
        criterion="test criterion",
        ranking=[
            RankEntry(
                rank=1, experiment="metis+kl", status="ok",
                total_internal_boundary_km=leader_km, max_abs_deviation_pct=0.01,
                runtime_seconds=2.0, refine_iterations=10, refine_improvement_pct=5.0,
                gap_to_leader_pct=0.0, error=None,
            ),
            RankEntry(
                rank=2, experiment="splitline-realized+kl", status="ok",
                total_internal_boundary_km=leader_km * 1.1, max_abs_deviation_pct=0.02,
                runtime_seconds=1.5, refine_iterations=8, refine_improvement_pct=4.0,
                gap_to_leader_pct=10.0, error=None,
            ),
            RankEntry(
                rank=None, experiment="splitline-chord", status="failed",
                total_internal_boundary_km=None, max_abs_deviation_pct=None,
                runtime_seconds=0.3, refine_iterations=0, refine_improvement_pct=0.0,
                gap_to_leader_pct=None, error="RuntimeError: No valid cut found",
            ),
        ],
    )


# --- run_tier behavior ----------------------------------------------------------


def test_run_tier_invokes_run_state_experiments_per_state(tmp_path):
    with patch("districtmaker.validate.run_state_experiments") as mock_run:
        mock_run.side_effect = lambda state_code, output_dir, **kw: _fake_report(state_code)
        results = run_tier(tier_name=None, states=["AA", "BB", "CC"], output_dir=tmp_path)
    assert mock_run.call_count == 3
    assert [r.state_code for r in results] == ["AA", "BB", "CC"]
    assert all(r.status == "ok" for r in results)


def test_run_tier_captures_per_state_failures(tmp_path):
    def fake_run(state_code, output_dir, **kw):
        if state_code == "BB":
            raise RuntimeError("boom")
        return _fake_report(state_code)

    with patch("districtmaker.validate.run_state_experiments", side_effect=fake_run):
        results = run_tier(tier_name=None, states=["AA", "BB", "CC"], output_dir=tmp_path)

    assert [r.status for r in results] == ["ok", "failed", "ok"]
    assert results[1].error == "RuntimeError: boom"


def test_run_tier_marks_state_failed_when_no_leader(tmp_path):
    """A state where every experiment failed has leader=None -> status 'failed'."""
    no_leader = LeaderReport(leader=None, criterion="test", ranking=[])
    with patch("districtmaker.validate.run_state_experiments", return_value=no_leader):
        results = run_tier(tier_name=None, states=["AA"], output_dir=tmp_path)
    assert results[0].status == "failed"


def test_run_tier_skips_already_completed_states(tmp_path):
    # Pre-create AA's leader.json so it gets skipped.
    aa_dir = tmp_path / "AA"
    aa_dir.mkdir()
    (aa_dir / "leader.json").write_text(json.dumps({
        "state": {"code": "AA", "name": "AAlandia", "n_districts": 2},
        "leader": "metis+kl",
        "ranking": [{
            "rank": 1, "experiment": "metis+kl", "status": "ok",
            "total_internal_boundary_km": 5.0, "gap_to_leader_pct": 0.0,
        }],
    }))

    with patch("districtmaker.validate.run_state_experiments") as mock_run:
        mock_run.side_effect = lambda state_code, output_dir, **kw: _fake_report(state_code)
        results = run_tier(tier_name=None, states=["AA", "BB"], output_dir=tmp_path)

    assert mock_run.call_count == 1
    assert [r.status for r in results] == ["skipped", "ok"]


def test_run_tier_force_overrides_skip(tmp_path):
    aa_dir = tmp_path / "AA"
    aa_dir.mkdir()
    (aa_dir / "leader.json").write_text(json.dumps({
        "state": {"code": "AA", "name": "AAlandia", "n_districts": 2},
        "leader": "metis+kl",
        "ranking": [{
            "rank": 1, "experiment": "metis+kl", "status": "ok",
            "total_internal_boundary_km": 5.0, "gap_to_leader_pct": 0.0,
        }],
    }))

    with patch("districtmaker.validate.run_state_experiments") as mock_run:
        mock_run.side_effect = lambda state_code, output_dir, **kw: _fake_report(state_code)
        results = run_tier(tier_name=None, states=["AA"], output_dir=tmp_path, force=True)

    assert mock_run.call_count == 1
    assert results[0].status == "ok"


def test_run_tier_marks_cached_null_leader_state_failed(tmp_path):
    """A cached leader.json with leader=null is a failure, not a skippable OK."""
    aa_dir = tmp_path / "AA"
    aa_dir.mkdir()
    (aa_dir / "leader.json").write_text(json.dumps({
        "state": {"code": "AA", "name": "AAlandia", "n_districts": 2},
        "leader": None,
        "ranking": [
            {"rank": None, "experiment": "splitline-chord", "status": "failed",
             "error": "RuntimeError: No valid cut found"},
        ],
    }))

    with patch("districtmaker.validate.run_state_experiments") as mock_run:
        results = run_tier(tier_name=None, states=["AA"], output_dir=tmp_path)

    # AA was not re-run (leader.json exists) but is classified failed, not skipped.
    assert mock_run.call_count == 0
    assert results[0].status == "failed"


def test_run_tier_requires_exactly_one_of_tier_or_states(tmp_path):
    with pytest.raises(ValueError):
        run_tier(tier_name=None, states=None, output_dir=tmp_path)
    with pytest.raises(ValueError):
        run_tier(tier_name="easy", states=["AA"], output_dir=tmp_path)


def test_run_tier_rejects_unknown_tier(tmp_path):
    with pytest.raises(ValueError, match="Unknown tier"):
        run_tier(tier_name="bogus", states=None, output_dir=tmp_path)


# --- summary writing ------------------------------------------------------------


def test_write_tier_summary_emits_leader_ledger(tmp_path):
    with patch("districtmaker.validate.run_state_experiments") as mock_run:
        mock_run.side_effect = lambda state_code, output_dir, **kw: _fake_report(state_code)
        results = run_tier(tier_name=None, states=["AA", "BB"], output_dir=tmp_path)
    paths = write_tier_summary(tmp_path, results, tier_name="custom")

    assert paths["json"].name == "summary.json"
    assert paths["markdown"].name == "summary.md"

    data = json.loads(paths["json"].read_text())
    assert data["state_count"] == 2
    assert data["ok_count"] == 2
    assert data["failed_count"] == 0
    assert set(data["state_results"]) == {"AA", "BB"}
    assert data["state_results"]["AA"]["leader"] == "metis+kl"
    assert data["state_results"]["AA"]["leader_boundary_km"] == 1000.0
    assert data["state_results"]["AA"]["runner_up"] == "splitline-realized+kl"
    assert data["state_results"]["AA"]["gap_to_runner_up_pct"] == 10.0

    md = paths["markdown"].read_text()
    assert "leader ledger" in md.lower()
    assert "AA" in md and "BB" in md
    assert "metis+kl" in md


def test_write_tier_summary_accumulates_across_invocations(tmp_path):
    def fake(state_code, output_dir, **kw):
        return _fake_report(state_code)

    with patch("districtmaker.validate.run_state_experiments", side_effect=fake):
        first = run_tier(tier_name=None, states=["ID", "IA"], output_dir=tmp_path)
        write_tier_summary(tmp_path, first, tier_name="easy")
        second = run_tier(tier_name=None, states=["HI", "ME"], output_dir=tmp_path)
        write_tier_summary(tmp_path, second, tier_name="middle")

    data = json.loads((tmp_path / "summary.json").read_text())
    assert set(data["state_results"]) == {"ID", "IA", "HI", "ME"}
    assert data["state_count"] == 4
    assert data["ok_count"] == 4
    assert len(data["runs"]) == 2
    assert data["runs"][0]["tier"] == "easy"
    assert data["runs"][1]["tier"] == "middle"


def test_write_tier_summary_updates_state_in_place(tmp_path):
    def first_run(state_code, output_dir, **kw):
        return _fake_report(state_code)

    def second_run(state_code, output_dir, **kw):
        raise RuntimeError("regressed")

    with patch("districtmaker.validate.run_state_experiments", side_effect=first_run):
        r1 = run_tier(tier_name=None, states=["ID"], output_dir=tmp_path)
        write_tier_summary(tmp_path, r1, tier_name="easy")

    data = json.loads((tmp_path / "summary.json").read_text())
    assert data["state_results"]["ID"]["status"] == "ok"

    with patch("districtmaker.validate.run_state_experiments", side_effect=second_run):
        r2 = run_tier(tier_name=None, states=["ID"], output_dir=tmp_path, force=True)
        write_tier_summary(tmp_path, r2, tier_name="easy")

    data = json.loads((tmp_path / "summary.json").read_text())
    assert data["state_results"]["ID"]["status"] == "failed"
    assert data["state_count"] == 1
    assert data["failed_count"] == 1
    assert data["ok_count"] == 0


def test_write_tier_summary_skipped_state_keeps_ok_status(tmp_path):
    aa_dir = tmp_path / "AA"
    aa_dir.mkdir()
    (aa_dir / "leader.json").write_text(json.dumps({
        "state": {"code": "AA", "name": "AAlandia", "n_districts": 2},
        "leader": "metis+kl",
        "ranking": [{
            "rank": 1, "experiment": "metis+kl", "status": "ok",
            "total_internal_boundary_km": 5.0, "gap_to_leader_pct": 0.0,
        }],
    }))

    with patch("districtmaker.validate.run_state_experiments") as mock_run:
        mock_run.side_effect = lambda state_code, output_dir, **kw: _fake_report(state_code)
        results = run_tier(tier_name=None, states=["AA"], output_dir=tmp_path)
        write_tier_summary(tmp_path, results, tier_name=None)

    data = json.loads((tmp_path / "summary.json").read_text())
    assert data["state_results"]["AA"]["status"] == "ok"
    sr = data["state_results"]["AA"]
    assert sr["leader"] == "metis+kl"
    assert sr["leader_boundary_km"] == 5.0
    assert sr["experiments_ok"] == 1
    assert sr["experiments_failed"] == 0


def test_write_tier_summary_handles_failures(tmp_path):
    def fake_run(state_code, output_dir, **kw):
        raise RuntimeError("nope")
    with patch("districtmaker.validate.run_state_experiments", side_effect=fake_run):
        results = run_tier(tier_name=None, states=["AA"], output_dir=tmp_path)
    paths = write_tier_summary(tmp_path, results, tier_name="easy")
    md = paths["markdown"].read_text()
    assert "FAILED" in md
    assert "RuntimeError" in md
    failed_line = next(
        ln for ln in md.splitlines() if "FAILED" in ln and ln.strip().startswith("|")
    )
    assert failed_line.rstrip().endswith("|")
    assert failed_line.count("|") == 9  # 8 columns => 9 pipe delimiters


# --- CLI integration ------------------------------------------------------------


def test_cli_validate_runs_a_state_list(tmp_path):
    runner = CliRunner()
    with patch("districtmaker.validate.run_state_experiments") as mock_run:
        mock_run.side_effect = lambda state_code, output_dir, **kw: _fake_report(state_code)
        result = runner.invoke(
            cli,
            ["validate", "--states", "AA,BB,CC", "--output", str(tmp_path / "out")],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "out" / "summary.json").exists()
    assert (tmp_path / "out" / "summary.md").exists()
    summary = json.loads((tmp_path / "out" / "summary.json").read_text())
    assert set(summary["state_results"]) == {"AA", "BB", "CC"}


def test_cli_validate_rejects_both_tier_and_states(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "validate",
            "--tier", "easy",
            "--states", "AA",
            "--output", str(tmp_path / "out"),
        ],
    )
    assert result.exit_code != 0


def test_cli_validate_requires_one_of_tier_or_states(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "validate",
            "--output", str(tmp_path / "out"),
        ],
    )
    assert result.exit_code != 0
