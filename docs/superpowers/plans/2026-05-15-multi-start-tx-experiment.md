# Multi-start TX Experiment Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for inline execution (recommended for this plan; the work is mostly operational, not code). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a 20-trial × 2-algorithm multi-start experiment on Texas using the shipped `districtmaker multi-start` CLI; interpret results; produce a dated writeup that resolves Q15 in `docs/open-questions.md`.

**Architecture:** This plan assumes the code in `docs/superpowers/plans/2026-05-15-multi-start-code.md` is fully shipped, tested, and committed. No code changes happen here. The plan exercises the new CLI end-to-end, captures telemetry, and produces the scientific writeup.

**Tech Stack:** Shipped `districtmaker multi-start` CLI, `districtmaker validate-ctl` controls, a telemetry sampler script (reused from the morning's tough-tier run).

---

## Context (inlined, since the spec is not committed)

Q15 asks: does multi-start `metis+kl` close the +7.74% realized-boundary-km gap behind `splitline-realized+kl` on Texas, or is the gap structural? This experiment runs 20 trials each of `metis+kl` and `splitline-realized+kl` on TX with deterministic seeds 42–61 (`seed_i = base_seed + i`). 40 tasks total. Expected wall clock at `--cpu 75` on a 24-core / 192 GB host: **~3–3.5 hours**, with `splitline-realized+kl` (~4900s per trial on TX under parallel load) dominating.

Trial-00-seed-42 of each algorithm must reproduce the existing leader-ledger result bit-exactly (`splitline-realized+kl` = 8323.94 km, `metis+kl` = 8967.86 km). This is the determinism regression check.

The Q15 verdict is one of three:

- **Gap closed by seed variation** — best `metis+kl` trial within 0.5% of `splitline-realized+kl` best.
- **Gap structural** — every `metis+kl` trial at least 2% behind the `splitline-realized+kl` worst.
- **Partially closed** — neither of the above; report the actual overlap region.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `outputs/_multi-start/2026-05-15-TX/` | Create | Experiment root. Holds `.scheduler_state.json`, `_validate.log`, `_telemetry.csv`, 40 trial dirs, `distributions.json`, per-algo `best.json`, `_summary.md`. |
| `outputs/_multi-start/2026-05-15-TX/_sampler.py` | Create | Telemetry sampler (copied from the tough-tier run pattern, adapted for this output path). |
| `docs/multi-start-tx-2026-05-15.md` | Create | Dated convergence-style writeup with the Q15 verdict. Filename uses the actual launch date; if the run spans midnight, use the day the run *started*. |
| `docs/open-questions.md` | Modify | Update Q15 with the verdict (one of the three outcomes above). Mark the question RESOLVED (or PARTIALLY RESOLVED if "Partially closed"). |

---

## Task 1: Pre-flight checks

**Files:** none modified. Read-only verification.

- [ ] **Step 1: Confirm Plan A is shipped (CLI exists)**

Run: `districtmaker multi-start --help`

Expected: help text appears, listing `--state`, `--algorithms`, `--trials`, `--base-seed`, `--cpu`, `--max-workers`, `--poll-seconds`, `--tolerance`, `--output`, `--full-artifacts/--light-artifacts`, `--force/--skip-existing`.

If the command is missing: stop. Plan A is not shipped. Return to Plan A execution.

- [ ] **Step 2: Confirm full test suite passes**

Run: `pytest -v`

Expected: all tests pass, including `tests/test_multi_start.py` (9 tests from Plan A + 1 integration smoke = 10).

If anything fails: stop. Plan A has regressions. Investigate before running the real experiment.

- [ ] **Step 3: Confirm no `validate` or `multi-start` run is currently active**

Run: `ps aux | grep -E '[d]istrictmaker (validate|multi-start)( |$)' | grep -v -- '-ctl'`

Expected: no output (no rows).

If a row appears: identify the output dir from the command line. Either let it finish before launching this experiment, or coordinate with the operator. Do not launch concurrently — both runs would compete for the same CPU and `validate-ctl` controls would become ambiguous.

- [ ] **Step 4: Confirm disk space**

Run: `df -h .`

Expected: at least 5 GB free in the working volume (the experiment will write ~1 GB).

- [ ] **Step 5: Confirm host resources match expectations**

Run: `sysctl -n hw.memsize hw.ncpu`

Expected: memory ≥ 64 GB (192 GB on the dev box), CPU cores ≥ 8 (24 on the dev box).

If less: re-evaluate the `--cpu` cap. On a 16-core box, `--cpu 75` still gives ~12 cores active, which is fine. On <8 cores, the experiment will take substantially longer than the 3-hour estimate — note this and consider lowering N or splitting the algorithms across two runs.

---

## Task 2: Determinism cross-check (1 trial, ~5 min)

Before committing to a 3-hour run, smoke-test that `multi-start` reproduces the existing leader-ledger numbers bit-exactly with seed 42.

- [ ] **Step 1: Launch a single-trial smoke run**

Run:

```bash
districtmaker multi-start \
  --state TX \
  --algorithms metis+kl \
  --trials 1 \
  --base-seed 42 \
  --cpu 75 \
  --output outputs/_multi-start/_determinism-check
```

Expected: command runs to completion (~5–6 minutes for one metis+kl trial on TX). Final line: `multi-start complete. results in outputs/_multi-start/_determinism-check/`.

- [ ] **Step 2: Verify the trial result matches the known value**

Run:

```bash
cat outputs/_multi-start/_determinism-check/TX/metis+kl/trial-00-seed-42/metrics.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['total_internal_boundary_km'])"
```

Expected output: `8967.86` (or matching to 4+ significant figures).

If the value differs: stop and investigate. Either the seed plumbing is broken or the algorithm has drifted. **Do not launch the full run** until this matches.

- [ ] **Step 3: Verify `best.json` and `distributions.json` materialized**

Run:

```bash
ls outputs/_multi-start/_determinism-check/
ls outputs/_multi-start/_determinism-check/TX/metis+kl/
```

Expected: `distributions.json` and `_summary.md` in the root; `best.json` in `TX/metis+kl/`. `best.json["trials"]` should equal 1, `best.json["trials_ok"]` should equal 1.

- [ ] **Step 4: Clean up the determinism-check output**

Run: `rm -rf outputs/_multi-start/_determinism-check`

(Keeps the experiment root tidy. The real run goes into a sibling directory.)

---

## Task 3: Launch the full multi-start run

**Files:**
- Create: `outputs/_multi-start/2026-05-15-TX/`
- Create: `outputs/_multi-start/2026-05-15-TX/_sampler.py` (copied from the existing pattern)

- [ ] **Step 1: Set up the output directory**

Run: `mkdir -p outputs/_multi-start/2026-05-15-TX`

Verify: `ls outputs/_multi-start/` should show `2026-05-15-TX/`.

Note: if today's date is not 2026-05-15 when this plan executes, **use today's date in the directory name** (and update the writeup filename in Task 8 to match). The 2026-05-15 in this plan is the date the plan was authored, not a fixed launch date.

- [ ] **Step 2: Create the telemetry sampler**

Create `outputs/_multi-start/2026-05-15-TX/_sampler.py` with this exact content (copied verbatim from the tough-tier run pattern, now invariant — exits cleanly when the run finishes):

```python
#!/usr/bin/env python3
"""5-second telemetry sampler for a districtmaker validate / multi-start run.

Writes _telemetry.csv next to itself. Exits when the controller PID
in .scheduler_state.json is gone and no districtmaker descendants remain.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import psutil

OUT = Path(__file__).resolve().parent
STATE = OUT / ".scheduler_state.json"
LOG = OUT / "_telemetry.csv"
INTERVAL = 5.0


def controller_pid() -> int | None:
    try:
        return int(json.loads(STATE.read_text())["pid"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
        return None


def districtmaker_procs(controller_pid: int | None) -> list[psutil.Process]:
    if controller_pid is None:
        return []
    try:
        root = psutil.Process(controller_pid)
    except psutil.NoSuchProcess:
        return []
    procs = [root]
    try:
        procs.extend(root.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return procs


def main() -> None:
    fresh = not LOG.exists()
    f = LOG.open("a", newline="")
    w = csv.writer(f)
    if fresh:
        w.writerow([
            "timestamp", "elapsed_s",
            "cpu_pct", "mem_used_gb", "mem_avail_gb",
            "dm_proc_count", "dm_total_rss_gb", "dm_max_rss_gb",
            "controller_alive",
        ])
        f.flush()

    psutil.cpu_percent(interval=None)
    start = time.time()

    while True:
        cpu = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        mem_used_gb = (vm.total - vm.available) / 1024**3
        mem_avail_gb = vm.available / 1024**3

        ctl = controller_pid()
        procs = districtmaker_procs(ctl)
        rss_list = []
        for p in procs:
            try:
                rss_list.append(p.memory_info().rss)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        total_rss_gb = sum(rss_list) / 1024**3 if rss_list else 0.0
        max_rss_gb = max(rss_list) / 1024**3 if rss_list else 0.0

        alive = bool(ctl and psutil.pid_exists(ctl))

        w.writerow([
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            f"{time.time() - start:.1f}",
            f"{cpu:.1f}",
            f"{mem_used_gb:.2f}",
            f"{mem_avail_gb:.2f}",
            len(procs),
            f"{total_rss_gb:.2f}",
            f"{max_rss_gb:.2f}",
            int(alive),
        ])
        f.flush()

        if ctl is not None and not alive and not procs:
            break

        time.sleep(INTERVAL)

    f.close()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Launch the multi-start run in the background**

Run:

```bash
nohup districtmaker multi-start \
  --state TX \
  --algorithms metis+kl,splitline-realized+kl \
  --trials 20 \
  --base-seed 42 \
  --cpu 75 \
  --output outputs/_multi-start/2026-05-15-TX \
  > outputs/_multi-start/2026-05-15-TX/_validate.log 2>&1 &
echo "controller PID: $!"
```

Expected: a PID printed to stdout; `_validate.log` begins filling.

- [ ] **Step 4: Wait briefly and confirm the state file appeared**

Run: `sleep 4 && ls outputs/_multi-start/2026-05-15-TX/`

Expected: `.scheduler_state.json` and `_validate.log` exist.

Run: `cat outputs/_multi-start/2026-05-15-TX/.scheduler_state.json`

Expected: JSON with `target_cpu_pct: 75.0`, `paused: false`, `freeze: false`, and a numeric `pid`.

If `.scheduler_state.json` is missing after 5 seconds: check `_validate.log` for errors. Common causes — invalid args, missing pymetis, output path conflict. Triage from the log.

- [ ] **Step 5: Launch the telemetry sampler in the background**

Run:

```bash
nohup python3 outputs/_multi-start/2026-05-15-TX/_sampler.py \
  > outputs/_multi-start/2026-05-15-TX/_sampler.log 2>&1 &
echo "sampler PID: $!"
```

Expected: a PID printed; after ~7 seconds, `_telemetry.csv` contains a header and at least one data row.

Verify: `sleep 8 && tail -3 outputs/_multi-start/2026-05-15-TX/_telemetry.csv`

Expected: 3 rows of CSV with non-zero `dm_proc_count` (the run is fanning out workers).

---

## Task 4: Mid-run observability

**Files:** none modified. Observation only.

The run takes ~3 hours. During that time:

- [ ] **Step 1: Periodic status checks**

Run any time:

```bash
districtmaker validate-ctl status --output outputs/_multi-start/2026-05-15-TX
```

Expected fields: `controller pid`, `started_at`, `target_cpu_pct: 75.0`, `paused: False`, `freeze: False`, `state version: N` (increments on every control mutation; will stay at 0 unless you change something).

- [ ] **Step 2: Telemetry spot checks**

Run: `tail -3 outputs/_multi-start/2026-05-15-TX/_telemetry.csv`

Expected: rows showing `cpu_pct` hovering near 75 (the cap), `dm_proc_count` between 1 and ~18 (controller + workers), `mem_avail_gb` well above 0, `controller_alive=1`.

- [ ] **Step 3: Track completions**

Run: `grep "completed" outputs/_multi-start/2026-05-15-TX/_validate.log | wc -l`

Expected progression: starts at 0, climbs to 40 total over ~3 hours. `metis+kl` trials finish first (~5 min each); `splitline-realized+kl` trials are the long pole (~80 min each).

- [ ] **Step 4: If something goes wrong**

| Symptom | Action |
|---|---|
| Operator interrupts needed | `districtmaker validate-ctl pause --output outputs/_multi-start/2026-05-15-TX` (drains in-flight) |
| CPU needed back instantly | `districtmaker validate-ctl freeze --output outputs/_multi-start/2026-05-15-TX` (SIGSTOP, holds RAM) |
| Resume | `districtmaker validate-ctl resume --output outputs/_multi-start/2026-05-15-TX` |
| One trial appears stuck (>2× expected runtime) | Check the trial's `run.log` in its trial dir. Stuck `pymetis` is rare but possible; let it run unless it exceeds 3× expected. |
| Controller crashes mid-run | `_validate.log` will end abruptly, `_telemetry.csv` will show `controller_alive=0`. Relaunch with the same command — `--skip-existing` semantics will resume from the last completed trial. |

---

## Task 5: Post-run verification

**Files:** read-only.

- [ ] **Step 1: Confirm the run completed cleanly**

Run: `tail -5 outputs/_multi-start/2026-05-15-TX/_validate.log`

Expected: the last `completed ...` line is for one of the `splitline-realized+kl` trials (the slowest algorithm). No `failed` entries unless intentional.

Run: `tail -3 outputs/_multi-start/2026-05-15-TX/_telemetry.csv`

Expected: final row shows `dm_proc_count=0`, `controller_alive=0` (sampler self-terminated when controller exited).

- [ ] **Step 2: Confirm all 40 trials produced metrics**

Run:

```bash
find outputs/_multi-start/2026-05-15-TX -name metrics.json | wc -l
```

Expected: `40`.

If fewer than 40: identify the missing trial(s):

```bash
for algo in metis+kl splitline-realized+kl; do
  for i in $(seq 0 19); do
    seed=$((42 + i))
    pad=$(printf "%02d" $i)
    dir="outputs/_multi-start/2026-05-15-TX/TX/$algo/trial-$pad-seed-$seed"
    if [ ! -f "$dir/metrics.json" ]; then
      echo "MISSING: $dir"
    fi
  done
done
```

For each missing trial, inspect `run.log` (if any) in the trial dir. Common causes: pymetis transient errors, KL convergence failures. Re-run the missing trials by re-invoking the same `multi-start` command — `--skip-existing` (the default) will only run the gaps.

- [ ] **Step 3: Confirm aggregator outputs exist**

Run:

```bash
ls outputs/_multi-start/2026-05-15-TX/
ls outputs/_multi-start/2026-05-15-TX/TX/metis+kl/best.json
ls outputs/_multi-start/2026-05-15-TX/TX/splitline-realized+kl/best.json
```

Expected: `distributions.json`, `_summary.md` in the root; `best.json` in each algorithm dir.

If `_summary.md` or `distributions.json` is missing: the aggregator didn't run (likely because the CLI command died before reaching the aggregation step). Re-run the aggregator manually:

```bash
python3 -c "
from pathlib import Path
from districtmaker.multi_start import aggregate_results
aggregate_results(
    output_dir=Path('outputs/_multi-start/2026-05-15-TX'),
    state='TX',
    algorithms=('metis+kl', 'splitline-realized+kl'),
    trials=20,
    base_seed=42,
)
"
```

- [ ] **Step 4: Determinism cross-check on trial-00**

Run:

```bash
python3 -c "
import json
m = json.load(open('outputs/_multi-start/2026-05-15-TX/TX/metis+kl/trial-00-seed-42/metrics.json'))
s = json.load(open('outputs/_multi-start/2026-05-15-TX/TX/splitline-realized+kl/trial-00-seed-42/metrics.json'))
print(f'metis+kl trial-00:                {m[\"total_internal_boundary_km\"]:.2f} km (expected 8967.86)')
print(f'splitline-realized+kl trial-00:   {s[\"total_internal_boundary_km\"]:.2f} km (expected 8323.94)')
"
```

Expected: both lines match within 0.01 km of the expected values. This is the bit-exact regression check the spec requires.

If either diverges: stop and investigate. The experiment is invalid until determinism is re-established.

---

## Task 6: Inspect aggregator outputs

**Files:** read-only.

- [ ] **Step 1: Read the per-algorithm best.json files**

Run:

```bash
cat outputs/_multi-start/2026-05-15-TX/TX/metis+kl/best.json
echo "---"
cat outputs/_multi-start/2026-05-15-TX/TX/splitline-realized+kl/best.json
```

Capture for the writeup (Task 8):

- `metis+kl`: `trials_ok / trials`, `best.boundary_km`, `best.seed`, full `distribution` block (`min`, `max`, `mean`, `median`, `std`, `std_pct`).
- `splitline-realized+kl`: same fields.

- [ ] **Step 2: Read `_summary.md`**

Run: `cat outputs/_multi-start/2026-05-15-TX/_summary.md`

Expected content: distribution table per algorithm + best-of-N saturation table at N=1, 2, 5, 10, 20.

- [ ] **Step 3: Compute the key comparisons by hand (for the writeup)**

The aggregator gives raw numbers. The writeup needs derived quantities:

```bash
python3 <<'EOF'
import json
m = json.load(open("outputs/_multi-start/2026-05-15-TX/TX/metis+kl/best.json"))
s = json.load(open("outputs/_multi-start/2026-05-15-TX/TX/splitline-realized+kl/best.json"))

m_best = m["best"]["boundary_km"]
s_best = s["best"]["boundary_km"]
m_worst = m["distribution"]["max"]
s_worst = s["distribution"]["max"]

gap_best_to_best = 100.0 * (m_best - s_best) / s_best
print(f"metis+kl best ({m_best:.2f}) vs splitline-realized+kl best ({s_best:.2f}): {gap_best_to_best:+.2f}%")

# Overlap test: does any metis+kl trial reach within 0.5% of splitline+kl best?
threshold_05 = s_best * 1.005
hits = [t for t in json.load(
    open("outputs/_multi-start/2026-05-15-TX/distributions.json")
)["results"]["metis+kl"] if t["status"] == "ok" and t["boundary_km"] <= threshold_05]
print(f"metis+kl trials within 0.5% of splitline+kl best: {len(hits)} / 20")

# Structural test: are all metis+kl trials at least 2% behind splitline+kl worst?
all_above_2pct = all(
    100.0 * (t["boundary_km"] - s_worst) / s_worst >= 2.0
    for t in json.load(
        open("outputs/_multi-start/2026-05-15-TX/distributions.json")
    )["results"]["metis+kl"] if t["status"] == "ok"
)
print(f"all metis+kl trials >= 2% behind splitline+kl worst: {all_above_2pct}")
EOF
```

Capture the three output lines for the verdict in Task 7.

---

## Task 7: Form the Q15 verdict

This is the only step in the plan that requires judgment, not mechanical execution. The verdict drives the writeup framing.

- [ ] **Step 1: Apply the verdict decision tree**

Using the numbers from Task 6 Step 3:

| Condition | Verdict |
|---|---|
| `metis+kl trials within 0.5% of splitline+kl best: ≥1 / 20` | **Gap closed by seed variation.** Some seed of `metis+kl` reaches the `splitline-realized+kl` basin. Q15's "small-margin / seed-explained" branch fired. |
| `all metis+kl trials >= 2% behind splitline+kl worst: True` | **Gap structural.** Every seed of `metis+kl` lands ≥2% above every `splitline-realized+kl` trial — METIS's basin is unreachable from `splitline-realized`'s by seed alone. Q15's "structural" branch fired. |
| Neither | **Partially closed.** Best `metis+kl` is closer than the single-trial baseline suggested, but the distributions don't overlap. Report the actual gap-closure (e.g. "from +7.74% to +X%"). |

- [ ] **Step 2: Note the splitline-realized+kl distribution width**

A near-zero `std_pct` on `splitline-realized+kl` confirms the spec's hypothesis: the splitline pass is deterministic, only KL polish is randomized, so the distribution is narrow. If `std_pct > 1%`, that's a finding worth flagging — it means KL polish is doing more than expected on top of the splitline structure.

---

## Task 8: Write the dated convergence writeup

**Files:**
- Create: `docs/multi-start-tx-2026-05-15.md` (use today's date if different from the plan's authoring date)

- [ ] **Step 1: Draft the writeup**

Template:

```markdown
# Multi-start on Texas — 2026-05-15

**Question (Q15 in `docs/open-questions.md`):** Is the +7.74% gap
between `metis+kl` and `splitline-realized+kl` on Texas seed-explained,
or structural?

**Verdict:** [Gap closed / Gap structural / Partially closed] — one
sentence summary.

## Setup

- State: TX (38 districts).
- Algorithms: `metis+kl`, `splitline-realized+kl`.
- Trials: 20 each; seeds 42–61 (`seed_i = base_seed + i`).
- Compute: 24-core / 192 GB host, `--cpu 75`, no `--max-workers`.
- Run started 2026-05-15 at HH:MM:SS UTC; wall-clock ~H hours.

## Distributions

| Algorithm | Trials OK | Best (km) | Worst (km) | Mean (km) | Median (km) | Std (km) | Std (%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `metis+kl` | 20 / 20 | XXX | XXX | XXX | XXX | XXX | XXX |
| `splitline-realized+kl` | 20 / 20 | XXX | XXX | XXX | XXX | XXX | XXX |

Fill from `_summary.md` and the `best.json` files.

## Saturation curve

(Insert the best-of-N table from `_summary.md` directly.)

## Q15 verdict

Three paragraphs:

1. **The numerical answer.** What the best-of-N comparison shows. Use
   the precise comparison output from Task 6 Step 3: "X of 20 metis+kl
   trials reached within 0.5% of splitline-realized+kl's best of YYY
   km." or "All 20 metis+kl trials landed at least Z% above
   splitline-realized+kl's worst."

2. **What this implies.** If structural: METIS's multilevel coarsening
   cannot reach the basin splitline-realized's recursive halving finds
   at 38 districts. Multi-start METIS is not the right lever here;
   Q12 (structural-option diversification) or multi-start
   splitline-realized are the more promising follow-ons.
   If closed: the gap was seed-explained and METIS at 20 restarts is
   competitive with splitline-realized at TX scale — the single-trial
   leader ledger is misleading at this district count.
   If partial: report the actual gap closure and note the gray area.

3. **The splitline-realized+kl distribution.** Report its `std_pct`.
   Near-zero confirms determinism of the splitline pass; non-trivial
   would be a finding for Q16 (is KL polish always net-positive?).

## What this experiment did NOT settle

- Whether structural-option diversification (Q12) would help.
- Whether the same pattern holds on CA (52 districts) — the only other
  state where `splitline-realized+kl` won the leader ledger.
- Whether multi-start `splitline-realized+kl` distributions shift
  meaningfully across other states.

## Saturation observation (Q11)

Comment on whether the best-of-N curve plateaus by N=10 or keeps
improving through N=20. The spec hypothesized "logarithmic improvement,
plateau after a handful" — confirm or refute against the actual table.

## Artifacts

- Raw per-trial metrics: `outputs/_multi-start/2026-05-15-TX/distributions.json`
- Per-algorithm bests: `outputs/_multi-start/2026-05-15-TX/TX/<algo>/best.json`
- Aggregator writeup: `outputs/_multi-start/2026-05-15-TX/_summary.md`
- Telemetry trace: `outputs/_multi-start/2026-05-15-TX/_telemetry.csv`
- Controller log: `outputs/_multi-start/2026-05-15-TX/_validate.log`
```

- [ ] **Step 2: Fill in the template using values from Tasks 5–7**

Replace every `XXX` with real numbers. Use 2 decimal places for km, 3 for percentages. Write the verdict paragraphs in plain prose against the realized boundary objective — no aesthetic commentary on district shape.

---

## Task 9: Update `docs/open-questions.md`

**Files:**
- Modify: `docs/open-questions.md` (the Q15 section)

- [ ] **Step 1: Locate the Q15 section**

Run: `grep -n "^### 15\." docs/open-questions.md`

Expected: one line, e.g. `### 15. Why does splitline-realized+kl ...`. Note the line number for the edit.

- [ ] **Step 2: Append a "Resolved" subsection to Q15**

After the existing Q15 content (before `### 16.`), append:

```markdown

**Resolved — YYYY-MM-DD (multi-start TX experiment).** [One-paragraph
synthesis of the verdict.] Full writeup at
[`multi-start-tx-2026-05-15.md`](multi-start-tx-2026-05-15.md). The
single-trial leader ledger remains the operational source of truth
until multi-start lands on more states.
```

Replace `YYYY-MM-DD` with the run's launch date and adjust the
multi-start writeup filename to match Task 8.

If the verdict was "Partially closed", phrase it as "Partially
resolved" and surface the open follow-on.

---

## Task 10: Commit the writeup and Q15 update

**Files:**
- New (staged): `docs/multi-start-tx-2026-05-15.md`
- Modified (staged): `docs/open-questions.md`

- [ ] **Step 1: Verify the diff is what you expect**

Run:

```bash
git status
git diff docs/open-questions.md
git diff --stat docs/
```

Expected: one new file (`docs/multi-start-tx-2026-05-15.md`), one modified file (`docs/open-questions.md`). No other staged or unstaged changes should be present from this plan.

- [ ] **Step 2: Stage and commit**

Run:

```bash
git add docs/multi-start-tx-2026-05-15.md docs/open-questions.md
git commit -m "$(cat <<'EOF'
Resolve Q15 with multi-start TX experiment

20 trials each of metis+kl and splitline-realized+kl on Texas with
seeds 42-61 [report the verdict in one sentence: structural / closed /
partial].

[One sentence on the splitline-realized+kl distribution width
(std_pct) and what it implies for Q16.]

Run artifacts at outputs/_multi-start/2026-05-15-TX/ (not committed —
~1 GB of trial outputs, summarized in the docs writeup).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

Adapt the commit body to the actual verdict before committing. Do not commit until the verdict text matches the writeup.

- [ ] **Step 3: Confirm clean state**

Run: `git status`

Expected: `nothing to commit, working tree clean`.

---

## What This Plan Deliberately Does NOT Do

- No code changes. All code is shipped by Plan A.
- No update to `outputs/summary.md` (the cross-state leader ledger). The single-trial ledger remains the source of truth until multi-start lands on more states; the format question for distributions-in-ledger is a separate decision.
- No experiment on any state other than TX, no experiment on `metis` (bare) or other algorithms, no Q12 (structural-option) exploration. Each of those is its own future experiment with its own plan.
- No commit of the `outputs/_multi-start/2026-05-15-TX/` artifacts themselves (~1 GB). The committed writeup is the durable record; the raw artifacts stay local.
