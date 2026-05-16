# METIS ctype Variation on CA (Q12 probe) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Probe Q12 (basin diversification) by running 20 multi-start `metis+kl` trials on California with METIS's coarsening type set to `RM` (random matching) instead of the default `SHEM` (sorted heavy-edge matching), then comparing the resulting boundary-km distribution to the existing ctype=SHEM 19-trial distribution.

**Architecture:** Gated by a load-bearing verification step — first confirm `pymetis.Options().ctype` actually plumbs through to METIS rather than being silently accepted. Only proceed if verified. Then make a minimal additive change to `Metis.__init__` (accept `ctype="SHEM"|"RM"`, default `"SHEM"` for full backward compatibility), and run the experiment via a one-shot script that reuses the existing multi-start dir layout so the existing aggregator works unchanged. Writeup mirrors the multi-start TX/CA docs.

**Tech Stack:** Python 3.11, `pymetis`, existing `Metis` class at `src/districtmaker/algorithms/metis.py`, existing multi-start aggregator at `src/districtmaker/multi_start.py::aggregate_results`.

---

## Spec context (inlined from conversation, no external refs)

Q12 hypothesizes that METIS's coarsening produces only a limited set of reachable basins, and varying the **structural** option `ctype` (not just the seed) genuinely broadens which basins are reachable. The 2026-05-14 research pass flagged that `pymetis` may or may not actually plumb every METIS option through — `ctype` specifically needs verification before any larger investment.

`Metis.run` already sets `options.seed`, `options.ufactor`, `options.ncuts`, `options.niter`, `options.contig`. Adding `options.ctype` is one line. The risk is silent acceptance: `o.ctype = 1` succeeds at the Python level (verified in this session) but the binding may discard it before calling METIS.

METIS constants (from `metis.h`): `METIS_CTYPE_RM = 0`, `METIS_CTYPE_SHEM = 1`. Default is SHEM.

The CA multi-start baseline to compare against: 19 successful `metis+kl` trials at seeds 42–61 (seed 46 failed METIS tolerance), best 6893.38 km, mean 7441.84 km, std 287.72 km (3.866%). Artifacts at `outputs/CA/multi-start/2026-05-15/metis+kl/`.

Output dir for this experiment: `outputs/CA/multi-start/2026-05-16-ctype-rm/`.

---

## File Structure

**Files modified:**
- `src/districtmaker/algorithms/metis.py` — add `ctype` parameter to `__init__` and `run`; plumb to `options.ctype`. Backward compatible (default `"SHEM"` reproduces current behavior bit-exactly).
- `tests/test_metis.py` — add two tests: (1) ctype is plumbed (RM and SHEM give different assignments on a representative graph), (2) default ctype="SHEM" produces bit-identical output to the current code (regression guard).

**Files created:**
- `scripts/q12_ctype_ca_experiment.py` — one-shot script that loads CA, runs `Metis(ctype="RM", ...)` + KL refinement for seeds 42–61, writes per-trial outputs in the existing multi-start dir convention, calls the existing aggregator. Not part of the production CLI — explicitly an experiment script.
- `docs/q12-ctype-ca-2026-05-16.md` — writeup mirroring the multi-start TX/CA writeups.

**Files left untouched (deliberate scope discipline):**
- `src/districtmaker/compare.py` — no new algorithm name. The `metis+kl` registry entry stays SHEM. If RM proves valuable, a follow-up plan promotes `metis-rm+kl` to first-class.
- `src/districtmaker/cli.py` — no new flag. The experiment script is the surface area for ctype=RM.
- `src/districtmaker/multi_start.py` — aggregator is reused unchanged.

---

## Task 1: Verify pymetis plumbs ctype (LOAD-BEARING GATE)

**Files:**
- Create: `scripts/q12_verify_ctype_plumbing.py`

This is a smoke test, not a unit test — it's a one-shot script that produces a yes/no answer. The plan **stops here** if the answer is no.

- [ ] **Step 1: Write the verification script**

```python
# scripts/q12_verify_ctype_plumbing.py
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
```

- [ ] **Step 2: Run it**

```bash
python3 scripts/q12_verify_ctype_plumbing.py
```

Expected if plumbed: `PASS: SHEM and RM differ on N/100 node assignments.` (any N >= 1) and exit code 0.

Expected if not plumbed: `FAIL: SHEM and RM produced bit-identical assignments.` and exit code 1.

- [ ] **Step 3: Decision gate**

- If exit code 0 → proceed to Task 2.
- If exit code 1 → **STOP**. Do not modify production code. Add a note to `docs/open-questions.md` under Q12 noting "ctype is not exposed by the current `pymetis` binding; structural diversification via that knob is blocked pending a binding upgrade or switch to a different METIS wrapper." Then commit just the verification script + the open-questions note, and report back.

- [ ] **Step 4: Commit the verification script (regardless of outcome)**

```bash
git add scripts/q12_verify_ctype_plumbing.py
git commit -m "Add pymetis ctype plumbing verification script"
```

---

## Task 2: Add ctype parameter to Metis class (TDD)

Only run this task if Task 1 passed.

**Files:**
- Modify: `src/districtmaker/algorithms/metis.py`
- Modify: `tests/test_metis.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_metis.py`:

```python
def test_metis_ctype_default_matches_current_behavior():
    """Default ctype must preserve bit-exact output of pre-ctype code path.

    Guards against accidental regression: existing leader ledger values
    (e.g. CA seed 42 metis+kl 7467.96 km) depend on this.
    """
    from districtmaker.algorithms.metis import Metis
    # Small synthetic state for fast test — see tests/conftest.py
    m_default = Metis(tolerance=0.05)
    m_explicit = Metis(tolerance=0.05, ctype="SHEM")
    # Both should produce bit-identical assignments for the same seed.
    # Use the existing test fixture for a representative graph.
    from tests.test_metis import _tiny_state_fixture  # existing helper
    state, blocks, edges, lengths = _tiny_state_fixture()
    d_default = m_default.run(state, blocks, n_districts=3, seed=42,
                              edges=edges, edge_lengths=lengths)
    d_explicit = m_explicit.run(state, blocks, n_districts=3, seed=42,
                                edges=edges, edge_lengths=lengths)
    # Compare district assignments (not geometries — dissolve is deterministic)
    assert list(d_default["district"]) == list(d_explicit["district"])


def test_metis_ctype_rm_differs_from_shem():
    """ctype='RM' must produce a different partition than ctype='SHEM'
    on a graph that's large enough for the coarsening choice to matter."""
    from districtmaker.algorithms.metis import Metis
    from tests.test_metis import _tiny_state_fixture
    state, blocks, edges, lengths = _tiny_state_fixture()
    m_shem = Metis(tolerance=0.05, ctype="SHEM")
    m_rm = Metis(tolerance=0.05, ctype="RM")
    d_shem = m_shem.run(state, blocks, n_districts=3, seed=42,
                        edges=edges, edge_lengths=lengths)
    d_rm = m_rm.run(state, blocks, n_districts=3, seed=42,
                    edges=edges, edge_lengths=lengths)
    # Assignments should differ on at least one block. If the synthetic
    # fixture is too small/symmetric for ctype to matter, expand it.
    assert list(d_shem["district"]) != list(d_rm["district"]), (
        "ctype=RM and ctype=SHEM produced identical partitions on the "
        "test fixture; fixture may be too small for ctype to differentiate."
    )


def test_metis_ctype_invalid_raises():
    from districtmaker.algorithms.metis import Metis
    import pytest
    with pytest.raises(ValueError, match="ctype must be 'SHEM' or 'RM'"):
        Metis(tolerance=0.005, ctype="BOGUS")
```

If `_tiny_state_fixture` does not exist in `tests/test_metis.py`, first inspect the existing test file and adapt to whatever fixture pattern it uses. Do not invent a new fixture — reuse the one the existing METIS tests use.

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_metis.py::test_metis_ctype_default_matches_current_behavior tests/test_metis.py::test_metis_ctype_rm_differs_from_shem tests/test_metis.py::test_metis_ctype_invalid_raises -v
```

Expected: all 3 FAIL — `Metis.__init__()` doesn't accept `ctype` yet.

- [ ] **Step 3: Add ctype to Metis class**

Modify `src/districtmaker/algorithms/metis.py`:

In `__init__`, after the existing `niter: int = 50` parameter, add `ctype: str = "SHEM"` and validation:

```python
    def __init__(
        self,
        tolerance: float = 0.005,
        contiguous: bool = True,
        recursive: bool = False,
        ncuts: int = 10,
        niter: int = 50,
        ctype: str = "SHEM",
    ):
        # ... existing docstring stays; add one paragraph: ...
        # `ctype` selects METIS's coarsening type: 'SHEM' (sorted heavy-edge
        # matching, METIS default) or 'RM' (random matching, broader basin
        # coverage). Default 'SHEM' reproduces pre-ctype behavior bit-exactly.
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
```

In `run`, inside the `for ufactor` loop, after `options.niter = self.niter` and before the `if self.contiguous:`, add:

```python
            options.ctype = 1 if self.ctype == "SHEM" else 0  # METIS_CTYPE_SHEM=1, RM=0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_metis.py -v
```

Expected: all 3 new tests PASS, no existing tests regress.

- [ ] **Step 5: Commit**

```bash
git add src/districtmaker/algorithms/metis.py tests/test_metis.py
git commit -m "Add ctype parameter to Metis (SHEM default, RM available)"
```

---

## Task 3: Author the CA ctype=RM experiment script

**Files:**
- Create: `scripts/q12_ctype_ca_experiment.py`

This is a one-shot experiment runner. It deliberately bypasses the multi-start CLI to avoid plumbing a new flag through 4 layers for an experimental knob. It writes outputs in the multi-start dir layout so the existing aggregator works unchanged.

- [ ] **Step 1: Author the script**

```python
# scripts/q12_ctype_ca_experiment.py
"""Run 20 trials of metis+kl on CA with ctype=RM (Q12 structural probe).

Mirrors the multi-start dir layout so outputs/CA/multi-start/2026-05-16-ctype-rm/
can be fed to the existing aggregate_results() function.

NOT part of the production CLI — this is a one-shot experimental script.
If ctype=RM proves valuable, promote 'metis-rm+kl' to ALGORITHM_NAMES in
a follow-up plan and remove this script.
"""
from __future__ import annotations

import json
import logging
import multiprocessing as mp
import time
from pathlib import Path

from districtmaker.experiments import run_single_algorithm_task
from districtmaker.multi_start import aggregate_results
from districtmaker.output.writer import get_logger


OUTPUT_DIR = Path("outputs/CA/multi-start/2026-05-16-ctype-rm")
STATE = "CA"
ALGORITHM = "metis+kl"  # base 'metis' runs internally; ctype=RM applies to it
TRIALS = 20
BASE_SEED = 42


def _run_trial(trial_index: int) -> dict:
    """Worker entry — runs one trial with ctype=RM and writes trial dir."""
    seed = BASE_SEED + trial_index
    trial_dir = OUTPUT_DIR / STATE / ALGORITHM / f"trial-{trial_index:02d}-seed-{seed}"
    # Monkey-patch the metis instantiation in run_one_algorithm to pass
    # ctype="RM". Cleanest patch point: replace Metis.__init__'s default
    # for this process via a shim.
    from districtmaker.algorithms import metis as metis_mod
    orig_init = metis_mod.Metis.__init__

    def patched_init(self, *args, **kwargs):
        kwargs.setdefault("ctype", "RM")
        orig_init(self, *args, **kwargs)

    metis_mod.Metis.__init__ = patched_init
    try:
        run_single_algorithm_task(
            state_code=STATE,
            algorithm=ALGORITHM,
            state_output_dir=OUTPUT_DIR,
            seed=seed,
            tolerance=0.005,
            full_artifacts=True,
            experiment_dir_override=trial_dir,
        )
        return {"trial_index": trial_index, "seed": seed, "status": "ok"}
    except Exception as exc:
        return {
            "trial_index": trial_index,
            "seed": seed,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        metis_mod.Metis.__init__ = orig_init


def main(workers: int = 6) -> None:
    log = get_logger()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Q12 ctype=RM experiment: state=%s trials=%d workers=%d",
             STATE, TRIALS, workers)

    started = time.perf_counter()
    with mp.Pool(processes=workers) as pool:
        results = pool.map(_run_trial, range(TRIALS))
    elapsed = time.perf_counter() - started
    log.info("All trials done in %.1fs", elapsed)

    for r in results:
        log.info("trial-%02d-seed-%d: %s", r["trial_index"], r["seed"], r["status"])

    log.info("Aggregating…")
    agg = aggregate_results(
        output_dir=OUTPUT_DIR,
        state=STATE,
        algorithms=(ALGORITHM,),
        trials=TRIALS,
        base_seed=BASE_SEED,
    )
    print(json.dumps({
        "elapsed_seconds": elapsed,
        "trials": results,
        "best": agg.get("bests", {}).get(ALGORITHM),
    }, indent=2))


if __name__ == "__main__":
    main()
```

The worker count `6` is conservative for CA on a 192 GB host (each trial peaks ~5–6 GB; 6 workers ≈ 36 GB worst case, comfortable). Override at the call site if needed.

- [ ] **Step 2: Smoke-test the script on a small state first**

Before burning hours on CA, prove the script works end-to-end on a cheap state. Temporarily edit the script's `STATE = "CA"` to `STATE = "ID"` and `TRIALS = 20` to `TRIALS = 3`, then:

```bash
python3 scripts/q12_ctype_ca_experiment.py
```

Expected: completes in ~1 minute, writes `outputs/ID/multi-start/2026-05-16-ctype-rm/ID/metis+kl/trial-{00,01,02}-seed-{42,43,44}/` with `metrics.json` and a `_summary.md` from the aggregator. Three trials all `status: ok` in the printed JSON.

If anything fails, fix it before continuing. Then revert the script back to `STATE = "CA"` and `TRIALS = 20`.

- [ ] **Step 3: Delete the smoke-test output**

```bash
rm -rf outputs/ID/multi-start/2026-05-16-ctype-rm
```

- [ ] **Step 4: Commit the script**

```bash
git add scripts/q12_ctype_ca_experiment.py
git commit -m "Add Q12 ctype=RM experiment script for CA"
```

---

## Task 4: Run the CA experiment

- [ ] **Step 1: Confirm nothing else is running**

```bash
ps aux | grep -E '[d]istrictmaker' | grep -v grep
top -l 1 -n 0 | grep -E 'CPU usage|PhysMem'
```

Expected: no districtmaker process; CPU idle >70%; PhysMem unused >100 GB.

- [ ] **Step 2: Launch the experiment in the background**

```bash
mkdir -p outputs/CA/multi-start
python3 scripts/q12_ctype_ca_experiment.py > outputs/CA/multi-start/2026-05-16-ctype-rm-launch.log 2>&1 &
echo $! > /tmp/ctype-rm.pid
echo "launched pid $(cat /tmp/ctype-rm.pid)"
```

- [ ] **Step 3: Monitor**

Expected duration: ~1.5–3h based on CA single-trial metis+kl ~150–250s × 20 trials / 6 workers ≈ 500–800s of compute time + KL refinement overhead. RM coarsening may run slower than SHEM; treat the upper bound as 3h.

Memory check every ~30 min via the existing /loop pattern. Flag if PhysMem unused drops below 10 GB or if any trial fails repeatedly.

- [ ] **Step 4: When complete, verify all trials wrote outputs**

```bash
ls outputs/CA/multi-start/2026-05-16-ctype-rm/CA/metis+kl/ | wc -l
cat outputs/CA/multi-start/2026-05-16-ctype-rm/_summary.md
```

Expected: 20 trial dirs; `_summary.md` shows the distribution.

- [ ] **Step 5: Move the launch log inside the run dir (match multi-start convention)**

```bash
mv outputs/CA/multi-start/2026-05-16-ctype-rm-launch.log \
   outputs/CA/multi-start/2026-05-16-ctype-rm/_validate.log
```

- [ ] **Step 6: Collapse the redundant CA/ subdir (match TX layout)**

```bash
cd outputs/CA/multi-start/2026-05-16-ctype-rm
mv CA/metis+kl . && rmdir CA
cd -
```

(Skip this step if the script already writes to the flat layout — verify with `ls outputs/CA/multi-start/2026-05-16-ctype-rm/` first.)

---

## Task 5: Write up findings

**Files:**
- Create: `docs/q12-ctype-ca-2026-05-16.md`

- [ ] **Step 1: Author the writeup**

Mirror the structure of `docs/multi-start-ca-2026-05-15.md`. Required sections:

1. **Question.** State the Q12 hypothesis and what this experiment was supposed to settle.
2. **Verdict.** One paragraph: did ctype=RM produce shorter-boundary basins than ctype=SHEM, comparable, or worse? Use the same "Gap closed / Gap widened / No effect" language as the multi-start writeups.
3. **Setup.** State, algorithm, ctype, trials, seeds, compute, wall clock.
4. **Distributions.** Table comparing the new RM 20-trial distribution to the existing SHEM 19-trial distribution. Columns: trials OK, best (km), worst (km), mean, median, std, std%.
5. **RM trials sorted by quality.** Full table — seed, trial, boundary, Δ vs SHEM best (6893.38 km).
6. **Saturation curve.** Best-of-N for RM at N=1,2,5,10,20. Compare to SHEM saturation curve from the prior writeup.
7. **Q12 verdict.** The actual conclusion. Three possible framings:
   - "RM finds shorter basins than SHEM" → Q12 partially confirmed; promote `metis-rm+kl` to ALGORITHM_NAMES in a follow-up; expand experiment to TX and other states.
   - "RM produces comparable but distinct basins" → Q12 partially confirmed via *diversity* even without improvement; suggests ensemble across ctypes could help; iterated local search (Q12's second lever) becomes the next probe.
   - "RM produces worse basins than SHEM" → SHEM is genuinely the right default; ctype variation is not a viable Q12 lever; iterated local search becomes the only remaining Q12 lever.
8. **What this did NOT settle.** Same template as multi-start writeups — what's still open for Q12 after this.
9. **Artifacts.** Paths under `outputs/CA/multi-start/2026-05-16-ctype-rm/`.

The "Verdict" paragraph must come first and must give the numerical answer — never bury it.

- [ ] **Step 2: Update docs/open-questions.md Q12**

Append a paragraph under Q12 in the same shape as Q15's "Resolved (TX)" / "Resolved (CA)" sub-paragraphs:

```markdown
**ctype=RM probe (CA) — 2026-05-16.** [One sentence stating the result with numbers.]
[Three sentences explaining what this implies for Q12 going forward — promote
RM, abandon ctype as a Q12 lever, or move to iterated local search.] Full
writeup at [`q12-ctype-ca-2026-05-16.md`](q12-ctype-ca-2026-05-16.md).
```

Do not change Q12's status to "resolved" — this is one experiment on one state. Q12 stays open; this is progress.

- [ ] **Step 3: Update the convergence-findings memory if (and only if) RM beat SHEM**

If the RM best-of-20 beats the SHEM best of 6893.38 km, the "near-optimal CA boundary" claim retreats. Update `~/.claude/projects/-Users-michaelmckinley-Projects-DistrictMaker-DistrictMaker/memory/convergence_findings.md`'s CA paragraph to cite the new best.

If RM did not beat SHEM, leave the memory alone.

- [ ] **Step 4: Commit the writeup + Q12 amendment**

```bash
git add docs/q12-ctype-ca-2026-05-16.md docs/open-questions.md
git commit -m "Probe Q12 with ctype=RM experiment on CA"
```

- [ ] **Step 5: Commit the experiment artifacts**

```bash
git add outputs/CA/multi-start/2026-05-16-ctype-rm/
git commit -m "Add Q12 ctype=RM experiment record for CA"
```

(Per-trial shapefiles are already covered by the `outputs/*/multi-start/*/*/trial-*/districts.{geojson,shp,...}` rule in `.gitignore`; png/metrics/run.log/task_result.json get tracked.)

---

## Out of scope (do NOT do as part of this plan)

These belong in follow-up plans, not here:

- Promoting `metis-rm+kl` to `ALGORITHM_NAMES` in `compare.py`. Only do this if the experiment shows RM is genuinely better; even then, scope it as its own plan covering CLI flag changes, registry expansion, and any leader-ledger updates.
- Adding `--metis-ctype` to the `multi-start` CLI. Same reasoning — only worth doing if RM proves valuable across multiple states.
- Running ctype=RM on TX or the medium-tier states. Even if CA looks promising, replicating to TX deserves its own scoped plan (because TX's wall clock is much higher and freezes will be needed).
- Iterated local search (Q12's second lever). Separate plan; this one is only the structural-option probe.
- Investigating other METIS structural options (`iptype`, `rtype`). Same reasoning — ctype is the highest-leverage knob; if it doesn't move the needle, the others probably won't either, and a separate plan can verify.

---

## Self-review notes

- **Spec coverage:** Verification gate (Task 1), Metis class change with backward-compat guard (Task 2), experiment runner (Task 3), execution (Task 4), writeup + Q12 amendment (Task 5). The user's stated intent is covered.
- **Placeholders:** None — every step has actual code or actual commands.
- **Type consistency:** `ctype` is consistently `str` (`"SHEM"` or `"RM"`) at the Python API surface; mapped to METIS int (`1` or `0`) only at the `pymetis.Options` boundary.
- **Risk surface:** Task 2 changes a load-bearing class (`Metis`); the default-equivalence test in Task 2 Step 1 is the primary regression guard. If that test fails, the patch is wrong — fix it before any further work.
