"""METIS-based graph partitioning.

Industry-standard multilevel graph partitioner: coarsen the block graph,
partition the small version, uncoarsen and refine. Minimizes the
weighted edge cut (= our realized internal boundary length) subject to a
balanced vertex-weight constraint (= our population balance).

METIS uses integer weights internally. We scale edge lengths to
millimeters (×1000, then round) to preserve fidelity.

METIS treats its ufactor as a *soft* upper bound and occasionally
exceeds it by a fraction of a step. We retry with progressively tighter
ufactor values if the achieved deviation overshoots the user's
tolerance, and raise a clear error if no setting satisfies it.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pymetis


class Metis:
    """METIS multilevel graph partitioner adapted as a districting algorithm."""

    name = "metis"

    def __init__(
        self,
        tolerance: float = 0.005,
        contiguous: bool = True,
        recursive: bool = False,
        ncuts: int = 10,
        niter: int = 50,
        ctype: str = "SHEM",
    ):
        """tolerance is the max-abs population deviation as a fraction (0.005 = 0.5%).

        Contiguity (METIS_OPTION_CONTIG) is only honored by METIS's k-way
        partitioner, not its recursive bisection. Defaults to recursive=False
        so contiguity is enforceable. Set recursive=True only if you accept
        non-contiguous districts.

        `ncuts` is METIS's internal multi-trial: it runs ncuts independent
        partitionings and keeps the best. `niter` controls how many KL/FM
        refinement passes per trial. Higher = better quality at the cost of
        runtime.

        `ctype` selects METIS's coarsening type: 'SHEM' (sorted heavy-edge
        matching, METIS default) or 'RM' (random matching, broader basin
        coverage). Default 'SHEM' reproduces pre-ctype behavior bit-exactly.
        """
        if tolerance <= 0:
            raise ValueError("tolerance must be positive")
        if contiguous and recursive:
            raise ValueError(
                "METIS contig=True is only honored by the k-way partitioner; "
                "set recursive=False or contiguous=False"
            )
        if ctype not in ("SHEM", "RM"):
            raise ValueError(f"ctype must be 'SHEM' or 'RM', got {ctype!r}")
        self.tolerance = tolerance
        self.contiguous = contiguous
        self.recursive = recursive
        self.ncuts = ncuts
        self.niter = niter
        self.ctype = ctype

    def run(
        self,
        state_geometry: gpd.GeoDataFrame,
        blocks: gpd.GeoDataFrame,
        n_districts: int,
        seed: int = 42,
        edges: np.ndarray | None = None,
        edge_lengths: np.ndarray | None = None,
    ) -> gpd.GeoDataFrame:
        if n_districts < 1:
            raise ValueError("n_districts must be >= 1")
        if state_geometry.crs != blocks.crs:
            raise ValueError("state_geometry and blocks must share a CRS")
        if edges is None or edge_lengths is None:
            raise ValueError("METIS requires edges and edge_lengths")

        n = len(blocks)
        pops = blocks["pop"].to_numpy().astype(np.int64)

        if n_districts == 1:
            assignments = np.zeros(n, dtype=np.int64)
            return _dissolve_districts(blocks, assignments, state_geometry.crs)

        xadj, adjncy, eweights = _to_csr(n, edges, edge_lengths)
        adjacency = pymetis.CSRAdjacency(adj_starts=xadj, adjacent=adjncy)

        # Start with ufactor at the user's nominal tolerance and tighten if
        # METIS overshoots. ufactor units are imbalance × 1000.
        initial_ufactor = max(1, int(self.tolerance * 1000))
        for ufactor in range(initial_ufactor, 0, -1):
            options = pymetis.Options()
            options.seed = seed
            options.ufactor = ufactor
            options.ncuts = self.ncuts
            options.niter = self.niter
            options.ctype = 1 if self.ctype == "SHEM" else 0  # METIS_CTYPE_SHEM=1, RM=0
            if self.contiguous:
                options.contig = 1

            _, membership = pymetis.part_graph(
                nparts=n_districts,
                adjacency=adjacency,
                vweights=pops,
                eweights=eweights,
                recursive=self.recursive,
                options=options,
            )

            assignments = np.asarray(membership, dtype=np.int64)
            achieved = _max_deviation(assignments, pops, n_districts)
            if achieved <= self.tolerance:
                return _dissolve_districts(blocks, assignments, state_geometry.crs)

        raise RuntimeError(
            f"METIS could not produce a partition within tolerance {self.tolerance:.4f}; "
            f"best achieved deviation was {achieved:.4f}. "
            f"Try relaxing tolerance or using a different algorithm."
        )


def _max_deviation(
    assignments: np.ndarray, pops: np.ndarray, n_districts: int
) -> float:
    """Max absolute population deviation as a fraction of ideal."""
    pops_per_d = np.bincount(assignments, weights=pops, minlength=n_districts)
    ideal = pops_per_d.sum() / n_districts
    return float(np.abs(pops_per_d - ideal).max() / ideal)


def _to_csr(
    n: int, edges: np.ndarray, edge_lengths: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert undirected edge list to METIS CSR format with integer weights.

    Each undirected (i, j) edge contributes two directed entries: i→j and j→i,
    both carrying the same weight. Weights are scaled to mm and floored at 1.
    """
    if len(edges) == 0:
        xadj = np.zeros(n + 1, dtype=np.int64)
        return xadj, np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)

    from_idx = np.concatenate([edges[:, 0], edges[:, 1]])
    to_idx = np.concatenate([edges[:, 1], edges[:, 0]])
    weights = np.concatenate([edge_lengths, edge_lengths])

    order = np.argsort(from_idx, kind="stable")
    from_idx = from_idx[order]
    to_idx = to_idx[order]
    weights = weights[order]

    int_weights = np.maximum(np.round(weights * 1000).astype(np.int64), 1)

    xadj = np.zeros(n + 1, dtype=np.int64)
    counts = np.bincount(from_idx, minlength=n)
    xadj[1:] = np.cumsum(counts)

    return xadj, to_idx.astype(np.int64), int_weights


def _dissolve_districts(
    blocks: gpd.GeoDataFrame, assignments: np.ndarray, crs
) -> gpd.GeoDataFrame:
    blocks = blocks.copy()
    blocks["district_id"] = assignments
    dissolved = blocks.dissolve(by="district_id", aggfunc={"pop": "sum"}).reset_index()
    dissolved = gpd.GeoDataFrame(dissolved, geometry="geometry", crs=crs)
    return dissolved[["district_id", "pop", "geometry"]]
