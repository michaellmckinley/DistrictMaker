"""Verify pymetis actually plumbs ctype through to METIS.

If RM and SHEM produce identical assignments on a synthetic graph with
known structure, ctype is being silently ignored and Q12's structural
diversification thesis cannot be tested via this knob. The plan stops.
"""
import numpy as np
import pymetis


def run_with_ctype(ctype_value: int, seed: int = 42) -> np.ndarray:
    # Synthetic 100-node graph: a 10x10 grid where each node connects
    # to its 4 neighbors. Large enough that METIS actually coarsens;
    # small enough to run in milliseconds.
    n = 100
    rows = cols = 10
    edges = []
    weights = []
    for r in range(rows):
        for c in range(cols):
            node = r * cols + c
            if c + 1 < cols:
                edges.append((node, r * cols + c + 1))
                weights.append(1)
            if r + 1 < rows:
                edges.append((node, (r + 1) * cols + c))
                weights.append(1)
    # Build CSR
    adj = [[] for _ in range(n)]
    adj_w = [[] for _ in range(n)]
    for (u, v), w in zip(edges, weights):
        adj[u].append(v); adj_w[u].append(w)
        adj[v].append(u); adj_w[v].append(w)
    xadj = np.zeros(n + 1, dtype=np.int64)
    for i, neigh in enumerate(adj):
        xadj[i + 1] = xadj[i] + len(neigh)
    adjncy = np.array([v for neigh in adj for v in neigh], dtype=np.int64)
    eweights = np.array([w for ws in adj_w for w in ws], dtype=np.int64)

    adjacency = pymetis.CSRAdjacency(adj_starts=xadj, adjacent=adjncy)
    options = pymetis.Options()
    options.seed = seed
    options.ncuts = 1
    options.niter = 10
    options.ctype = ctype_value
    _, membership = pymetis.part_graph(
        nparts=4,
        adjacency=adjacency,
        vweights=np.ones(n, dtype=np.int64),
        eweights=eweights,
        recursive=False,
        options=options,
    )
    return np.asarray(membership, dtype=np.int64)


def main() -> int:
    METIS_CTYPE_RM = 0
    METIS_CTYPE_SHEM = 1

    a = run_with_ctype(METIS_CTYPE_SHEM, seed=42)
    b = run_with_ctype(METIS_CTYPE_RM, seed=42)

    if np.array_equal(a, b):
        print("FAIL: SHEM and RM produced bit-identical assignments.")
        print("pymetis is silently ignoring options.ctype.")
        print("Q12 cannot be tested via this knob. Stop the plan.")
        return 1

    diff = int(np.sum(a != b))
    print(f"PASS: SHEM and RM differ on {diff}/{len(a)} node assignments.")
    print("ctype is plumbed through. Proceed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
