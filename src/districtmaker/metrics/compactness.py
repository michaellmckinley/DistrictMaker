"""Per-district compactness metrics.

These are *validation* metrics, not the objective. The objective is the
total internal boundary length (see boundaries.py). Compactness metrics
exist here so we can compare algorithm output against enacted maps using
the scores the academic and legal literature expects to see.

All functions take a single Shapely geometry (Polygon or MultiPolygon)
and return a float.
"""
from __future__ import annotations

import math

import shapely
from shapely.geometry.base import BaseGeometry


def polsby_popper(geom: BaseGeometry) -> float:
    """4·pi·A / P^2. Range [0, 1]; a circle scores 1."""
    perimeter = geom.length
    if perimeter == 0:
        return 0.0
    return 4 * math.pi * geom.area / (perimeter ** 2)


def schwartzberg(geom: BaseGeometry) -> float:
    """Perimeter divided by the circumference of an equal-area circle.

    Range [1, inf); a circle scores 1. Algebraically 1/sqrt(polsby_popper).
    """
    area = geom.area
    if area <= 0:
        return float("inf")
    equiv_circumference = 2 * math.pi * math.sqrt(area / math.pi)
    return geom.length / equiv_circumference


def reock(geom: BaseGeometry) -> float:
    """A / area of minimum bounding circle. Range [0, 1]; a circle scores 1.

    Shapely's minimum_bounding_circle returns a polygonal approximation of
    the disk, so the score for a perfect square is ~0.64 (vs. the analytic
    2/pi ≈ 0.6366) with a relative error of around 0.6%.
    """
    mbc = shapely.minimum_bounding_circle(geom)
    if mbc.area == 0:
        return 0.0
    return geom.area / mbc.area


def convex_hull_ratio(geom: BaseGeometry) -> float:
    """A / area of convex hull. Range [0, 1]; a convex shape scores 1."""
    hull = geom.convex_hull
    if hull.area == 0:
        return 0.0
    return geom.area / hull.area
