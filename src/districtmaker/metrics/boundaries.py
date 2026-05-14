"""The objective: total length of boundaries shared between adjacent districts.

This is *not* the sum of district perimeters — the state's external boundary
is not counted. Only the cuts that the algorithm chooses contribute. See
docs/metrics.md for the framing argument.
"""
from __future__ import annotations

import geopandas as gpd


def total_internal_boundary_length(districts: gpd.GeoDataFrame) -> float:
    """Sum of lengths of boundaries shared between every pair of districts.

    Length is measured in the units of the GeoDataFrame's CRS. For maps in
    EPSG:5070 (CONUS Albers), that's meters.

    Districts that meet only at a point contribute 0. Districts that share
    an edge contribute the edge length. Districts that share no boundary
    contribute 0.
    """
    geoms = list(districts.geometry)
    total = 0.0
    for i in range(len(geoms)):
        boundary_i = geoms[i].boundary
        for j in range(i + 1, len(geoms)):
            shared = boundary_i.intersection(geoms[j].boundary)
            total += shared.length
    return total
