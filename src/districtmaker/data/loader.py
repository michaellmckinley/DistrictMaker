"""Assemble state geometry + populated blocks for algorithms to consume."""
from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd

from districtmaker.data import census


CONUS_EPSG = 5070  # Albers Equal Area, valid for the lower 48.


@dataclass(frozen=True)
class StateData:
    code: str
    name: str
    fips: str
    geometry: gpd.GeoDataFrame
    blocks: gpd.GeoDataFrame

    @property
    def total_population(self) -> int:
        return int(self.blocks["pop"].sum())

    @property
    def block_count(self) -> int:
        return len(self.blocks)


def load_state(state_code: str, year: int = 2020, crs: int = CONUS_EPSG) -> StateData:
    """Load state geometry and populated blocks reprojected to `crs`.

    The default CRS is EPSG:5070 (CONUS Albers Equal Area), suitable for
    area and length measurements anywhere in the lower 48. For Alaska or
    Hawaii, pass an appropriate equal-area CRS.
    """
    state_geom = census.get_state_geometry(state_code, year=year).to_crs(epsg=crs)
    blocks = census.get_blocks(state_code, year=year).to_crs(epsg=crs)

    blocks = blocks.rename(columns={"POP20": "pop"})
    blocks["pop"] = blocks["pop"].astype(int)

    state_row = state_geom.iloc[0]
    return StateData(
        code=state_code.upper(),
        name=str(state_row["NAME"]),
        fips=str(state_row["STATEFP"]),
        geometry=state_geom,
        blocks=blocks,
    )
