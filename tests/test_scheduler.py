"""Tests for src/districtmaker/scheduler.py — control-file state and CPU observer."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from districtmaker.scheduler import CpuObserver, SchedulerState, mutate, read_state, write_state


def test_state_round_trip(tmp_path: Path) -> None:
    """A SchedulerState written to disk reads back equal."""
    original = SchedulerState(
        target_cpu_pct=42.5,
        max_workers=3,
        paused=True,
        freeze=False,
        pid=12345,
        started_at="2026-05-15T18:00:00+00:00",
        version=7,
    )
    write_state(tmp_path, original)
    loaded = read_state(tmp_path)
    assert loaded == original


def test_mutate_applies_change_and_increments_version(tmp_path: Path) -> None:
    write_state(tmp_path, SchedulerState(target_cpu_pct=50.0, version=1))

    after = mutate(tmp_path, lambda s: SchedulerState(**{**s.__dict__, "target_cpu_pct": 80.0}))

    assert after.target_cpu_pct == 80.0
    assert after.version == 2
    assert read_state(tmp_path) == after


def test_mutate_creates_file_with_defaults_when_absent(tmp_path: Path) -> None:
    """First mutation on a fresh output dir bootstraps a default state."""
    after = mutate(tmp_path, lambda s: SchedulerState(**{**s.__dict__, "paused": True}))

    assert after.paused is True
    assert after.target_cpu_pct == 50.0   # default carried through
    assert after.version == 1


def test_concurrent_mutates_do_not_lose_updates(tmp_path: Path) -> None:
    """Two concurrent threads each call mutate; both increments must land.

    Without locking, a read-modify-write race can drop one update. With
    fcntl.flock, version should monotonically reach 2 and both flag
    transitions must be visible in the final state.
    """
    write_state(tmp_path, SchedulerState())

    def bump_cpu() -> None:
        mutate(tmp_path, lambda s: SchedulerState(**{**s.__dict__, "target_cpu_pct": s.target_cpu_pct + 1}))

    threads = [threading.Thread(target=bump_cpu) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = read_state(tmp_path)
    assert final.target_cpu_pct == 52.0   # 50 + 1 + 1, no lost update
    assert final.version == 2


class FakeClock:
    """Manually-advanced monotonic clock for CpuObserver tests."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_cpu_observer_returns_zero_before_any_sample() -> None:
    obs = CpuObserver(sampler=lambda: 99.0, now=FakeClock(), window_seconds=5.0)
    assert obs.current() == 0.0


def test_cpu_observer_averages_within_window() -> None:
    clock = FakeClock()
    samples = iter([10.0, 20.0, 60.0])
    obs = CpuObserver(sampler=lambda: next(samples), now=clock, window_seconds=5.0)

    obs.update(); clock.t += 1.0
    obs.update(); clock.t += 1.0
    obs.update()

    assert obs.current() == pytest.approx(30.0)   # mean of 10, 20, 60


def test_cpu_observer_drops_samples_outside_window() -> None:
    clock = FakeClock()
    samples = iter([90.0, 10.0, 20.0])
    obs = CpuObserver(sampler=lambda: next(samples), now=clock, window_seconds=5.0)

    obs.update()              # t=0, 90%
    clock.t = 6.0             # advance past the window
    obs.update()              # t=6, 10%
    clock.t = 6.5
    obs.update()              # t=6.5, 20%

    # The 90% sample at t=0 is now older than 5s, must be evicted.
    assert obs.current() == pytest.approx(15.0)
