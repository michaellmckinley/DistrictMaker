"""Population balance metrics.

The legal/practical question is "how far does the worst district stray from
the ideal?" — that's `max_abs_deviation_pct`. The range metric is reported
because Karcher v. Daggett cites it.
"""
from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd


@dataclass(frozen=True)
class PopulationReport:
    ideal: float
    per_district: list[int]
    deviations_pct: list[float]
    max_abs_deviation_pct: float
    range_pct: float

    def to_dict(self) -> dict:
        return {
            "ideal": self.ideal,
            "per_district": self.per_district,
            "deviations_pct": self.deviations_pct,
            "max_abs_deviation_pct": self.max_abs_deviation_pct,
            "range_pct": self.range_pct,
        }


def population_deviation(
    districts: gpd.GeoDataFrame,
    ideal_population: float,
    pop_col: str = "pop",
) -> PopulationReport:
    """Summarize how far each district strays from the ideal population.

    Deviations are signed percentages: positive = over-populated.
    """
    if ideal_population <= 0:
        raise ValueError("ideal_population must be positive")

    pops = [int(p) for p in districts[pop_col].tolist()]
    deviations = [(p - ideal_population) / ideal_population * 100 for p in pops]
    return PopulationReport(
        ideal=ideal_population,
        per_district=pops,
        deviations_pct=deviations,
        max_abs_deviation_pct=max(abs(d) for d in deviations),
        range_pct=max(deviations) - min(deviations),
    )


def ideal_population(total_population: int, n_districts: int) -> float:
    """Ideal per-district population: total / n_districts."""
    if n_districts <= 0:
        raise ValueError("n_districts must be positive")
    return total_population / n_districts
