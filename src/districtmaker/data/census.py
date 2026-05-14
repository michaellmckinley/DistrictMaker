"""Census TIGER + decennial data fetch with disk cache.

Uses pygris to download TIGER/Line shapefiles. The 2020 block shapefiles
include POP20 (total population) as a bundled attribute, so no separate
Census API call is required.

Cache layout under DISTRICTMAKER_CACHE_DIR (default: ./data/processed/):
    <state>-state-<year>.parquet
    <state>-blocks-<year>.parquet
"""
from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
import pygris


def cache_dir() -> Path:
    return Path(os.environ.get("DISTRICTMAKER_CACHE_DIR", "data/processed"))


def get_state_geometry(state_code: str, year: int = 2020) -> gpd.GeoDataFrame:
    """Return the single-row state outline GeoDataFrame for the given USPS code."""
    cache = _cache_path(state_code, "state", year)
    if cache.exists():
        return gpd.read_parquet(cache)

    states = pygris.states(year=year, cb=False)
    state = states[states["STUSPS"] == state_code.upper()].copy()
    if state.empty:
        raise ValueError(f"Unknown state code: {state_code!r}")

    cache.parent.mkdir(parents=True, exist_ok=True)
    state.to_parquet(cache)
    return state


def get_blocks(state_code: str, year: int = 2020) -> gpd.GeoDataFrame:
    """Return all Census blocks for a state, including the POP20 column."""
    cache = _cache_path(state_code, "blocks", year)
    if cache.exists():
        return gpd.read_parquet(cache)

    blocks = pygris.blocks(state=state_code.upper(), year=year)
    if "POP20" not in blocks.columns:
        raise RuntimeError(
            f"Expected POP20 in pygris.blocks output for {state_code} {year}; "
            f"got columns: {sorted(blocks.columns)}"
        )

    cache.parent.mkdir(parents=True, exist_ok=True)
    blocks.to_parquet(cache)
    return blocks


def _cache_path(state_code: str, layer: str, year: int) -> Path:
    return cache_dir() / f"{state_code.lower()}-{layer}-{year}.parquet"
