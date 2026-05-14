"""Algorithm protocol and shared types."""
from __future__ import annotations

from typing import Protocol

import geopandas as gpd


class Algorithm(Protocol):
    """A redistricting algorithm.

    Implementations partition a state's blocks into exactly `n_districts`
    contiguous (best-effort) districts and return a GeoDataFrame with one
    row per district.

    Returned columns:
        district_id: int — 0-indexed district number
        pop: int        — sum of block populations assigned to the district
        geometry: shapely polygon — dissolved block geometry
    """

    name: str

    def run(
        self,
        state_geometry: gpd.GeoDataFrame,
        blocks: gpd.GeoDataFrame,
        n_districts: int,
        seed: int = 42,
    ) -> gpd.GeoDataFrame: ...
