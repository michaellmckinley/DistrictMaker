"""Static map rendering for district outputs."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt


def render_districts(
    districts: gpd.GeoDataFrame,
    output_path: Path,
    title: str | None = None,
    figsize: tuple[float, float] = (10, 10),
    dpi: int = 150,
) -> Path:
    """Render a district map to PNG.

    Districts are colored by `district_id`; centroids are labeled with the
    district number. The figure is saved to `output_path` and closed.
    """
    fig, ax = plt.subplots(figsize=figsize)
    districts.plot(
        ax=ax,
        column="district_id",
        cmap="tab20",
        edgecolor="black",
        linewidth=0.8,
        categorical=True,
        legend=False,
    )

    for _, row in districts.iterrows():
        c = row.geometry.representative_point()
        ax.annotate(
            str(int(row["district_id"])),
            xy=(c.x, c.y),
            ha="center",
            va="center",
            fontsize=14,
            fontweight="bold",
            color="white",
            bbox=dict(boxstyle="circle,pad=0.3", fc="black", ec="white", lw=1),
        )

    if title:
        ax.set_title(title)
    ax.set_axis_off()
    ax.set_aspect("equal")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return output_path
