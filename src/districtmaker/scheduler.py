"""Control-file state for the cooperative experiment runner.

The runner (`run_experiment` in `validate.py`) polls a JSON file at
`<output>/.scheduler_state.json` to learn the operator's intent —
target CPU percentage, optional hard worker ceiling, pause and freeze
flags. The `validate-ctl` subcommands mutate this file; the runner
reads it on each scheduler tick and adjusts behavior accordingly.

Functions in this module are pure I/O and process observation; they do
not import anything DistrictMaker-specific and have no side effects
beyond the control file.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from collections import deque
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable

import psutil

SCHEDULER_FILE = ".scheduler_state.json"
DEFAULT_POLL_SECONDS = 3.0


@dataclass(frozen=True)
class SchedulerState:
    target_cpu_pct: float = 50.0
    max_workers: int | None = None
    paused: bool = False
    freeze: bool = False
    pid: int | None = None
    started_at: str = ""
    version: int = 0


def _path(output_dir: Path) -> Path:
    return Path(output_dir) / SCHEDULER_FILE


def write_state(output_dir: Path, state: SchedulerState) -> None:
    """Write `state` to the scheduler file atomically."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = _path(output_dir)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(asdict(state), indent=2))
    os.replace(tmp, target)


def read_state(output_dir: Path) -> SchedulerState:
    """Read the scheduler file; raise FileNotFoundError if absent."""
    data = json.loads(_path(output_dir).read_text())
    return SchedulerState(**data)


def mutate(
    output_dir: Path, fn: Callable[[SchedulerState], SchedulerState]
) -> SchedulerState:
    """Read-modify-write the scheduler state under an exclusive lock.

    Bootstraps a default state if the file is absent. Bumps `version`
    on every successful write. The lock is held only across the
    read-modify-write; concurrent callers serialize naturally.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    lock_path = output_dir / (SCHEDULER_FILE + ".lock")
    with open(lock_path, "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            current = read_state(output_dir)
        except FileNotFoundError:
            current = SchedulerState()
        proposed = fn(current)
        next_state = replace(proposed, version=current.version + 1)
        write_state(output_dir, next_state)
        return next_state


def _default_cpu_sampler() -> float:
    """Total system CPU percent since the previous call (psutil semantics)."""
    return psutil.cpu_percent(interval=None)


class CpuObserver:
    """Sliding-window average of system CPU percent.

    The controller calls `update()` once per scheduler tick and consults
    `current()` when deciding whether to dispatch a new task. Samples
    older than `window_seconds` are evicted on each `update`.

    `sampler` and `now` are injected for testability.
    """

    def __init__(
        self,
        *,
        sampler: Callable[[], float] = _default_cpu_sampler,
        now: Callable[[], float] = time.monotonic,
        window_seconds: float = 5.0,
    ) -> None:
        self._sampler = sampler
        self._now = now
        self._window = window_seconds
        self._samples: deque[tuple[float, float]] = deque()

    def update(self) -> None:
        pct = self._sampler()
        t = self._now()
        self._samples.append((t, pct))
        cutoff = t - self._window
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def current(self) -> float:
        if not self._samples:
            return 0.0
        return sum(pct for _, pct in self._samples) / len(self._samples)
