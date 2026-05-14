"""Tests for the data ingestion layer."""
from __future__ import annotations

from unittest.mock import patch

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from districtmaker.data import census
from districtmaker.data.loader import CONUS_EPSG, StateData, load_state


def _fake_state_gdf() -> gpd.GeoDataFrame:
    # A square covering roughly the Idaho bounding box, in EPSG:4269 (lat/lon)
    return gpd.GeoDataFrame(
        {"NAME": ["Testlandia"], "STATEFP": ["99"], "STUSPS": ["TT"]},
        geometry=[Polygon([(-117, 42), (-111, 42), (-111, 49), (-117, 49)])],
        crs="EPSG:4269",
    )


def _fake_blocks_gdf(n_per_side: int = 6, pop_per_block: int = 100) -> gpd.GeoDataFrame:
    geom = []
    geoid = []
    for ix in range(n_per_side):
        for iy in range(n_per_side):
            x0 = -117 + ix
            y0 = 42 + iy
            geom.append(Polygon([(x0, y0), (x0 + 1, y0), (x0 + 1, y0 + 1), (x0, y0 + 1)]))
            geoid.append(f"99000000{ix:02d}{iy:02d}")
    n = len(geom)
    return gpd.GeoDataFrame(
        {
            "GEOID20": geoid,
            "POP20": [pop_per_block] * n,
            "STATEFP": ["99"] * n,
            "COUNTYFP": ["001"] * n,
        },
        geometry=geom,
        crs="EPSG:4269",
    )


def test_load_state_returns_state_data():
    with patch.object(census, "get_state_geometry", return_value=_fake_state_gdf()), \
         patch.object(census, "get_blocks", return_value=_fake_blocks_gdf()):
        state = load_state("TT")

    assert isinstance(state, StateData)
    assert state.code == "TT"
    assert state.name == "Testlandia"
    assert state.fips == "99"


def test_load_state_normalizes_population_column():
    with patch.object(census, "get_state_geometry", return_value=_fake_state_gdf()), \
         patch.object(census, "get_blocks", return_value=_fake_blocks_gdf(n_per_side=6, pop_per_block=100)):
        state = load_state("TT")

    assert "pop" in state.blocks.columns
    assert "POP20" not in state.blocks.columns
    assert state.blocks["pop"].dtype.kind in {"i", "u"}
    assert state.block_count == 36
    assert state.total_population == 3600


def test_load_state_reprojects_to_requested_crs():
    with patch.object(census, "get_state_geometry", return_value=_fake_state_gdf()), \
         patch.object(census, "get_blocks", return_value=_fake_blocks_gdf()):
        state = load_state("TT", crs=CONUS_EPSG)

    assert state.geometry.crs.to_epsg() == CONUS_EPSG
    assert state.blocks.crs.to_epsg() == CONUS_EPSG


def test_get_state_geometry_raises_on_unknown_code(tmp_path, monkeypatch):
    monkeypatch.setenv("DISTRICTMAKER_CACHE_DIR", str(tmp_path))
    empty = gpd.GeoDataFrame(
        {"STUSPS": ["AA"], "NAME": ["Other"], "STATEFP": ["00"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4269",
    )
    with patch("districtmaker.data.census.pygris.states", return_value=empty), \
         pytest.raises(ValueError, match="Unknown state code"):
        census.get_state_geometry("ZZ")


def test_get_blocks_raises_when_pop20_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DISTRICTMAKER_CACHE_DIR", str(tmp_path))
    no_pop = _fake_blocks_gdf().drop(columns=["POP20"])
    with patch("districtmaker.data.census.pygris.blocks", return_value=no_pop), \
         pytest.raises(RuntimeError, match="Expected POP20"):
        census.get_blocks("TT")


def test_get_state_geometry_uses_disk_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("DISTRICTMAKER_CACHE_DIR", str(tmp_path))
    fake_states = _fake_state_gdf()
    with patch("districtmaker.data.census.pygris.states", return_value=fake_states) as mock_fetch:
        first = census.get_state_geometry("TT")
        second = census.get_state_geometry("TT")

    assert mock_fetch.call_count == 1
    assert len(first) == len(second) == 1
    assert (tmp_path / "tt-state-2020.parquet").exists()


@pytest.mark.network
def test_load_state_integration_wyoming():
    """Real fetch against Census TIGER. Skipped by default — run with `pytest -m network`."""
    state = load_state("WY")
    assert state.code == "WY"
    assert state.name == "Wyoming"
    assert state.block_count > 50_000
    assert state.total_population > 500_000  # Wyoming ≈ 577k in 2020
