"""Block adjacency graph: edges + shared-boundary lengths.

The realized internal boundary length of a partition is the sum of
edge lengths whose endpoints lie in different districts. Precomputing
the adjacency graph once turns the per-cut cost from O(N log N)
(dissolve) into O(E) (vectorized side comparison + masked sum).

States with islands or geographic exclaves (HI, ME, MA, MI, KY's
Madrid Bend, etc.) produce a disconnected real-adjacency graph. We
augment with **synthetic water edges**: every block in a non-largest
component gets one edge to its nearest block (by centroid Euclidean
distance) in the largest component. Synthetic edges carry weight 0,
so they make the graph connected for the partitioner without
contributing anything to the realized-boundary objective. Coastline
remains uncounted — only lines the algorithm actually drew between
adjacent land blocks contribute to the cost.

For an ~80k-block state like Idaho, the graph has ~250k edges and
fits comfortably in memory; precomputation takes about a minute and
is cached as a .npz alongside the parquet block cache. Cache filename
embeds a schema version (v2 introduced synthetic edges).
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import scipy.sparse as sp
import scipy.sparse.csgraph as csg
import shapely
from scipy.spatial import cKDTree

from districtmaker.data.census import cache_dir


_CACHE_VERSION = 2


def get_adjacency(
    state_code: str,
    blocks: gpd.GeoDataFrame,
    year: int = 2020,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (edges, lengths) for the state's blocks. Cached to disk.

    edges: (E, 2) int64 array of 0-indexed block positions (i < j)
    lengths: (E,) float64 array of shared-boundary lengths in the
             blocks GeoDataFrame's CRS units
    """
    cache = _cache_path(state_code, year)
    if cache.exists():
        with np.load(cache) as data:
            return data["edges"], data["lengths"]

    edges, lengths = compute_adjacency(blocks)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, edges=edges, lengths=lengths)
    return edges, lengths


def compute_adjacency(blocks: gpd.GeoDataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Compute the block adjacency graph with shared-boundary lengths.

    Two blocks are adjacent iff their boundaries share a line segment of
    positive length. Point-only touches contribute no edge.

    If the resulting graph is disconnected (state has islands or
    exclaves), append synthetic weight-zero edges connecting every
    non-mainland block to its nearest mainland block by centroid
    Euclidean distance.
    """
    blocks = blocks.reset_index(drop=True)
    n = len(blocks)
    if n < 2:
        return np.zeros((0, 2), dtype=np.int64), np.zeros((0,), dtype=np.float64)

    real_edges, real_lengths = _compute_real_adjacency(blocks, n)

    if real_edges.shape[0] == 0:
        return real_edges, real_lengths

    synth_edges, synth_lengths = _compute_synthetic_water_edges(blocks, real_edges, n)
    if synth_edges.shape[0] == 0:
        return real_edges, real_lengths

    edges = np.vstack([real_edges, synth_edges]).astype(np.int64)
    lengths = np.concatenate([real_lengths, synth_lengths]).astype(np.float64)
    return edges, lengths


def _compute_real_adjacency(
    blocks: gpd.GeoDataFrame, n: int
) -> tuple[np.ndarray, np.ndarray]:
    """Shared-land-edge adjacency only. Returns (edges, lengths)."""
    geoms = blocks.geometry.values

    left = blocks[["geometry"]].copy()
    left["_lidx"] = np.arange(n)
    right = blocks[["geometry"]].copy()
    right["_ridx"] = np.arange(n)
    joined = gpd.sjoin(left, right, predicate="touches", how="inner")
    a = joined["_lidx"].to_numpy()
    b = joined["_ridx"].to_numpy()

    keep = a < b
    a = a[keep]
    b = b[keep]
    if a.size == 0:
        return np.zeros((0, 2), dtype=np.int64), np.zeros((0,), dtype=np.float64)

    bdry_a = shapely.boundary(geoms[a])
    bdry_b = shapely.boundary(geoms[b])
    shared = shapely.intersection(bdry_a, bdry_b)
    lengths = shapely.length(shared)

    positive = lengths > 0
    a = a[positive]
    b = b[positive]
    lengths = lengths[positive]

    return np.column_stack([a, b]).astype(np.int64), lengths.astype(np.float64)


def _compute_synthetic_water_edges(
    blocks: gpd.GeoDataFrame, real_edges: np.ndarray, n: int
) -> tuple[np.ndarray, np.ndarray]:
    """For each block not in the largest component, add a weight-0 edge to
    its nearest block in the largest component. Returns (edges, lengths).

    Weight-zero is the design choice: synthetic edges connect the graph
    for partitioning and contiguity logic without charging water gaps
    against the realized-boundary objective. Coastline is not something
    the algorithm draws, so it should not contribute to the cut cost.
    """
    row = np.concatenate([real_edges[:, 0], real_edges[:, 1]])
    col = np.concatenate([real_edges[:, 1], real_edges[:, 0]])
    graph = sp.csr_matrix((np.ones(len(row), dtype=np.int8), (row, col)), shape=(n, n))
    n_components, labels = csg.connected_components(graph, directed=False)

    if n_components <= 1:
        return np.zeros((0, 2), dtype=np.int64), np.zeros((0,), dtype=np.float64)

    unique, counts = np.unique(labels, return_counts=True)
    mainland_label = unique[counts.argmax()]
    mainland_mask = labels == mainland_label
    mainland_idx = np.where(mainland_mask)[0]
    island_idx = np.where(~mainland_mask)[0]

    if mainland_idx.size == 0 or island_idx.size == 0:
        return np.zeros((0, 2), dtype=np.int64), np.zeros((0,), dtype=np.float64)

    centroids = blocks.geometry.centroid
    cx = centroids.x.to_numpy()
    cy = centroids.y.to_numpy()

    mainland_pts = np.column_stack([cx[mainland_idx], cy[mainland_idx]])
    island_pts = np.column_stack([cx[island_idx], cy[island_idx]])

    tree = cKDTree(mainland_pts)
    _dist, nearest_local = tree.query(island_pts, k=1)
    nearest_global = mainland_idx[nearest_local]

    a = np.minimum(island_idx, nearest_global)
    b = np.maximum(island_idx, nearest_global)
    edges = np.column_stack([a, b]).astype(np.int64)
    lengths = np.zeros(len(edges), dtype=np.float64)
    return edges, lengths


def _cache_path(state_code: str, year: int) -> Path:
    return cache_dir() / f"{state_code.lower()}-edges-{year}-v{_CACHE_VERSION}.npz"
