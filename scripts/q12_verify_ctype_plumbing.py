"""Verify pymetis actually plumbs ctype through to METIS.

If RM and SHEM produce identical assignments on a graph that genuinely
exercises the coarsening choice, ctype is being silently ignored and
Q12's structural diversification thesis cannot be tested via this knob.
The plan stops.

Fixture: random Erdős–Rényi-style graph with varied edge weights. The
original 10x10 uniform-weight grid was too symmetric — SHEM's "pick the
heaviest neighbor" degenerates when all weights are equal, producing
the same matching as RM and a false negative. Varied weights are what
actually distinguishes the two coarsening schemes.
"""
import numpy as np
import pymetis


def build_random_weighted_graph(n: int = 200, p: float = 0.1, seed: int = 0):
    """Random graph with varied edge weights — exercises coarsening choice."""
    rng = np.random.default_rng(seed)
    adj: list[list[int]] = [[] for _ in range(n)]
    adj_w: list[list[int]] = [[] for _ in range(n)]
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                w = int(rng.integers(1, 100))
                adj[u].append(v); adj_w[u].append(w)
                adj[v].append(u); adj_w[v].append(w)
    xadj = np.zeros(n + 1, dtype=np.int64)
    for i, neigh in enumerate(adj):
        xadj[i + 1] = xadj[i] + len(neigh)
    adjncy = np.array([v for neigh in adj for v in neigh], dtype=np.int64)
    eweights = np.array([w for ws in adj_w for w in ws], dtype=np.int64)
    return n, xadj, adjncy, eweights


def run_with_ctype(graph, ctype_value: int, seed: int = 42) -> np.ndarray:
    n, xadj, adjncy, eweights = graph
    adjacency = pymetis.CSRAdjacency(adj_starts=xadj, adjacent=adjncy)
    options = pymetis.Options()
    options.seed = seed
    options.ncuts = 1
    options.niter = 10
    options.ctype = ctype_value
    _, membership = pymetis.part_graph(
        nparts=5,
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

    graph = build_random_weighted_graph(n=200, p=0.1, seed=0)
    n = graph[0]

    # Check across 5 seeds: if SHEM and RM ever differ, ctype is plumbed.
    any_diff = False
    for s in range(42, 47):
        a = run_with_ctype(graph, METIS_CTYPE_SHEM, seed=s)
        b = run_with_ctype(graph, METIS_CTYPE_RM, seed=s)
        diff = int(np.sum(a != b))
        print(f"  seed={s}: SHEM/RM diff = {diff}/{n}")
        if diff > 0:
            any_diff = True

    if not any_diff:
        print()
        print("FAIL: SHEM and RM produced bit-identical assignments across all seeds.")
        print("pymetis is silently ignoring options.ctype.")
        print("Q12 cannot be tested via this knob. Stop the plan.")
        return 1

    print()
    print("PASS: ctype is plumbed through to METIS. Proceed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
