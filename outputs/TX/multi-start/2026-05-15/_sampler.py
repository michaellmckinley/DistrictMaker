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
