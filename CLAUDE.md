# DistrictMaker — Claude Operating Manual

This file teaches Claude Code how to drive DistrictMaker's parallel
experiment runner from natural language. It loads automatically when
working anywhere under this repository.

If you are reading this as Claude: the operator will speak about the
parallel run conversationally ("pause this test," "scale back to 20%,"
"what's the status?"). Translate those into the right
`districtmaker validate-ctl` invocation against the correct output
directory **without asking which output dir each time**. Auto-discover
it using the procedure below.

---

## What the parallel runner is

`districtmaker validate --cpu N ...` runs the production pipeline across
a tier or list of states under a target CPU-percentage cap. While the
run is in progress, a JSON control file at
`<output>/.scheduler_state.json` holds the operator's intent — target
CPU cap, optional hard worker ceiling, pause and freeze flags. The
runner polls this file on each scheduler tick (default ~3 s) and adjusts
behavior accordingly.

`districtmaker validate-ctl` is the subgroup that mutates that file.
Subcommands: `set-cpu`, `set-max-workers`, `pause`, `freeze`, `resume`,
`status`. Every subcommand takes `--output PATH`.

Source of truth on the running run: the `.scheduler_state.json` file
itself. Its `pid` field is the controller PID.

---

## Discovery — finding the right `--output`

Use **both** paths below and prefer whichever returns a unique live
match. If neither finds a live run, say so plainly — do not guess.

### Path 1 — live process

```bash
ps aux | grep -E '[d]istrictmaker validate( |$)' | grep -v validate-ctl
```

Parse the `--output <path>` arg from the matching command line. This is
the most reliable signal that a run is actually executing.

### Path 2 — scheduler state files

Scan likely roots for `.scheduler_state.json`, then verify each
`pid` is alive:

```bash
find ~/Projects/DistrictMaker/DistrictMaker/outputs \
     ~/Projects/DistrictMaker -name '.scheduler_state.json' \
     -not -path '*/node_modules/*' 2>/dev/null
```

For each hit, read the file, extract `pid`, and probe it:

```bash
kill -0 <pid> 2>/dev/null && echo alive || echo dead
```

(Equivalent in Python: `os.kill(pid, 0)` — `OSError` means dead.)

### Resolving multiple matches

- **One live match across both paths** → use it.
- **Multiple live runs** → list them (output dir, pid, started_at,
  paused/freeze flags) and ask the operator which one.
- **Stale state file, no live pid** → the run has ended; tell the
  operator and offer to show the summary at `<output>/summary.json` or
  `<output>/summary.md`.
- **Nothing found** → say "I don't see a running validate run." Do not
  invent an output directory.

Once a live `--output` is resolved, reuse it for the rest of the
conversation unless the operator switches context.

---

## Natural Language → Command Patterns

Match the operator's intent, fill in the discovered `--output`, then
run the command. Echo back the new state from stdout.

| Operator says | Command |
|---|---|
| "What's the status?" / "How's it going?" / "Where are we?" | `districtmaker validate-ctl status --output <dir>` |
| "Pause this test" / "Stop dispatching new states" / "Let the in-flight ones finish then hold" | `districtmaker validate-ctl pause --output <dir>` |
| "Freeze it" / "Freeze for 15 minutes" / "I need the CPU back right now" | `districtmaker validate-ctl freeze --output <dir>` *(then offer to set a reminder/timer for the duration the operator named — does not auto-resume)* |
| "Resume" / "Unfreeze" / "Pick it back up" | `districtmaker validate-ctl resume --output <dir>` |
| "Scale back to 20%" / "Cap CPU at 35" / "Use no more than half" | `districtmaker validate-ctl set-cpu --pct <N> --output <dir>` |
| "Cap concurrency at 4" / "No more than 3 workers" | `districtmaker validate-ctl set-max-workers --workers <N> --output <dir>` |
| "Drop the worker ceiling" / "Unlimited workers" / "Let CPU cap drive concurrency" | `districtmaker validate-ctl set-max-workers --unlimited --output <dir>` |
| "Crank it" / "Run flat out" / "Use all the CPU" | `districtmaker validate-ctl set-cpu --pct 95 --output <dir>` *(95 not 100 — leaves headroom for the controller and OS; confirm if operator really meant 100)* |

`set-cpu --pct` accepts a float in `[1.0, 100.0]`. Reject values outside
that range before issuing the command.

---

## `pause` vs `freeze` — choose the right one

This distinction matters and is the most common point of confusion.

**`pause` (drain).** Sets `paused=true`. The controller stops
dispatching new tasks; in-flight workers finish naturally. Frees CPU
and memory gradually as each task completes. Use when the operator
wants to wind the run down cleanly — for a context switch lasting
longer than the longest in-flight task (TX/CA can take 2–3 hours each
on the big algorithms).

**`freeze` (SIGSTOP).** Sets `freeze=true`. The controller sends
SIGSTOP to every live worker — **instantaneous** pause that holds RAM.
Frozen workers consume 0% CPU but still hold their resident memory; on
a 4-worker freeze with large states, expect ~30 GB resident until
resume. Use when interactive work needs the CPU back **right now** and
waiting hours for drain is not viable.

Decision rule:
- "I need this back in seconds" → `freeze`.
- "I'm done for the day, wind it down" → `pause`.
- If the operator says "pause" but the context implies urgency (e.g.
  "I need to do something right now"), confirm: "Drain or freeze? Drain
  finishes in-flight tasks first (could be hours); freeze stops every
  worker instantly but holds the RAM."

Both clear via `resume`.

---

## `--max-workers` rule of thumb

`--max-workers` is a hard ceiling on concurrent tasks, useful when
**memory** rather than CPU is the binding constraint. The
production-pipeline algorithms peak at very different memory profiles
per state. Calibration:

- **TX / CA-class states**: ~8–10 GB each during `metis+kl` and
  `splitline-realized+kl`. On a 32 GB machine, 3 concurrent large-state
  jobs is the safe ceiling; 4 risks swap.
- **Mid-tier states**: 1–3 GB each. Concurrency is CPU-bound, not
  memory-bound.
- **Small states**: negligible memory; the CPU cap drives concurrency.

When the operator runs a tier that includes TX or CA and the host has
≤32 GB RAM, suggest `--max-workers 3` if it isn't already set. After
the big states finish, offer to clear the ceiling via
`set-max-workers --unlimited` so smaller states can fan out.

---

## Guard rails

- **Confirm before destructive actions.** `pause` and `freeze` are
  reversible; do not confirm those. But before anything that could lose
  work (killing the controller, removing the output directory, deleting
  `.scheduler_state.json`), require an explicit confirmation from the
  operator.
- **Never SIGKILL the controller.** If the operator wants to stop the
  run entirely, prefer `pause` + Ctrl-C in their terminal, or
  `freeze` + a clean shutdown. SIGKILL leaves stale `.scheduler_state.json`
  and orphaned worker processes. If the operator insists on SIGKILL,
  surface this trade-off first.
- **Don't guess at `--output`.** If discovery returns nothing live, say
  "I don't see a running validate run" rather than picking a directory.
- **Don't extend the surface.** `validate-ctl` is a thin control file
  mutator. Do not propose new subcommands, new flags, or wrapper
  scripts. If the operator wants behavior that isn't there, surface it
  as a feature request, don't improvise.
- **`set-cpu --pct 100` is rarely what they want.** The controller and
  OS need headroom. If the operator says "use everything," confirm
  whether 95 is acceptable.

---

## Notes

- The control file uses an `fcntl` exclusive lock and bumps `version`
  on every successful write. After mutating, the new `version` is
  echoed to stdout — surface it back to the operator so they can
  confirm the change took.
- `status` also reads `<output>/summary.json` if present, showing
  `ok / failed / total` state counts. This is the cheapest progress
  check.
- The controller polls on `--poll-seconds` (default 3.0). Changes via
  `validate-ctl` take effect on the next tick — there can be a brief
  lag between the command returning and observable behavior.
- Sequential `validate` runs (no `--cpu`) do not create a scheduler
  state file. `validate-ctl` is meaningless for them; if discovery
  finds a `validate` process but no `.scheduler_state.json`, tell the
  operator it's running sequentially and the controls don't apply.
