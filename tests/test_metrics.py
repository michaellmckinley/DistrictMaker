"""Tests for the metrics module."""
from __future__ import annotations

import math

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from districtmaker.metrics.boundaries import total_internal_boundary_length
from districtmaker.metrics.compactness import (
    convex_hull_ratio,
    polsby_popper,
    reock,
    schwartzberg,
)
from districtmaker.metrics.population import (
    PopulationReport,
    ideal_population,
    population_deviation,
)


# --- internal boundary length ---------------------------------------------------


def _grid_squares(n_per_side: int) -> list[Polygon]:
    return [
        Polygon([(x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)])
        for x in range(n_per_side)
        for y in range(n_per_side)
    ]


def test_internal_boundary_two_adjacent_squares_equals_one():
    # Two unit squares sharing the vertical edge x=1
    gdf = gpd.GeoDataFrame(
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
        ]
    )
    assert total_internal_boundary_length(gdf) == pytest.approx(1.0)


def test_internal_boundary_2x2_grid_equals_four():
    # Four unit squares in a 2x2 grid: 4 internal edges of length 1 each.
    gdf = gpd.GeoDataFrame(geometry=_grid_squares(2))
    assert total_internal_boundary_length(gdf) == pytest.approx(4.0)


def test_internal_boundary_disjoint_squares_equals_zero():
    gdf = gpd.GeoDataFrame(
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(5, 5), (6, 5), (6, 6), (5, 6)]),
        ]
    )
    assert total_internal_boundary_length(gdf) == 0.0


def test_internal_boundary_squares_touching_at_a_point_equals_zero():
    # These two squares touch only at the corner (1, 1).
    gdf = gpd.GeoDataFrame(
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(1, 1), (2, 1), (2, 2), (1, 2)]),
        ]
    )
    assert total_internal_boundary_length(gdf) == 0.0


def test_internal_boundary_single_district_equals_zero():
    gdf = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])])
    assert total_internal_boundary_length(gdf) == 0.0


# --- compactness ----------------------------------------------------------------


def _approx_circle(radius: float = 1.0, resolution: int = 256) -> Polygon:
    return Point(0, 0).buffer(radius, quad_segs=resolution)


def test_polsby_popper_circle_is_near_one():
    assert polsby_popper(_approx_circle()) == pytest.approx(1.0, abs=1e-3)


def test_polsby_popper_unit_square_is_pi_over_four():
    sq = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    assert polsby_popper(sq) == pytest.approx(math.pi / 4)


def test_polsby_popper_thin_rectangle_is_small():
    long_rect = Polygon([(0, 0), (100, 0), (100, 1), (0, 1)])
    assert polsby_popper(long_rect) < 0.05


def test_schwartzberg_circle_is_near_one():
    assert schwartzberg(_approx_circle()) == pytest.approx(1.0, abs=1e-3)


def test_schwartzberg_is_reciprocal_sqrt_polsby_popper():
    sq = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    assert schwartzberg(sq) == pytest.approx(1 / math.sqrt(polsby_popper(sq)))


def test_reock_circle_is_near_one():
    # Both the input "circle" and shapely's minimum bounding circle are
    # polygon approximations; the ratio can sit slightly above or below 1.
    assert reock(_approx_circle()) == pytest.approx(1.0, rel=0.01)


def test_reock_square_is_near_two_over_pi():
    # Analytic: A / (pi * r^2) where r = sqrt(2)/2  →  2/pi ≈ 0.6366.
    # Shapely's minimum_bounding_circle is a polygonal approximation, so
    # tolerate ~1% relative error.
    sq = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    expected = 2 / math.pi
    assert reock(sq) == pytest.approx(expected, rel=0.01)


def test_convex_hull_ratio_convex_shape_is_one():
    sq = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    assert convex_hull_ratio(sq) == pytest.approx(1.0)


def test_convex_hull_ratio_concave_shape_is_less_than_one():
    # L-shape: a unit square with a quarter cut out
    l_shape = Polygon([(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)])
    assert 0 < convex_hull_ratio(l_shape) < 1


# --- population -----------------------------------------------------------------


def test_ideal_population_divides_total_by_district_count():
    assert ideal_population(1_000_000, 4) == 250_000


def test_ideal_population_rejects_nonpositive_districts():
    with pytest.raises(ValueError):
        ideal_population(1000, 0)


def test_population_deviation_balanced_districts_is_zero():
    gdf = gpd.GeoDataFrame({"pop": [1000, 1000, 1000, 1000]}, geometry=[None] * 4)
    report = population_deviation(gdf, ideal_population=1000)
    assert report.max_abs_deviation_pct == 0
    assert report.range_pct == 0


def test_population_deviation_reports_per_district_signed_deviations():
    gdf = gpd.GeoDataFrame({"pop": [990, 1010]}, geometry=[None, None])
    report = population_deviation(gdf, ideal_population=1000)
    assert report.deviations_pct == pytest.approx([-1.0, 1.0])
    assert report.max_abs_deviation_pct == pytest.approx(1.0)
    assert report.range_pct == pytest.approx(2.0)


def test_population_deviation_returns_serializable_dict():
    gdf = gpd.GeoDataFrame({"pop": [500, 500]}, geometry=[None, None])
    report = population_deviation(gdf, ideal_population=500)
    d = report.to_dict()
    assert isinstance(d, dict)
    assert set(d.keys()) == {
        "ideal",
        "per_district",
        "deviations_pct",
        "max_abs_deviation_pct",
        "range_pct",
    }


def test_population_deviation_rejects_nonpositive_ideal():
    gdf = gpd.GeoDataFrame({"pop": [100]}, geometry=[None])
    with pytest.raises(ValueError):
        population_deviation(gdf, ideal_population=0)


def test_population_deviation_returns_population_report_dataclass():
    gdf = gpd.GeoDataFrame({"pop": [1000, 1000]}, geometry=[None, None])
    report = population_deviation(gdf, ideal_population=1000)
    assert isinstance(report, PopulationReport)
