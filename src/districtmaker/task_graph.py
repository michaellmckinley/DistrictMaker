"""DAG of (state, algorithm) tasks for the parallel experiment runner.

An `ExperimentPlan` declares which states and algorithms to run; `build_graph`
expands it into a `TaskGraph` of individual tasks. Each algorithm becomes
one task per state; each state additionally gets a finalization task
(identified by `algorithm == "_finalize"`) that depends on every algorithm
task for that state and is responsible for computing `leader.json` /
`leader.md` after all algorithms have run.

For v1, intra-state algorithm tasks have no dependencies between each other
(each task is self-contained — see `compare.algorithm_dependencies`), so
the only edges in the graph are *algorithm-task → finalization-task* for
the same state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal

TaskStatus = Literal["pending", "running", "done", "failed"]

from districtmaker.compare import ALGORITHM_NAMES, algorithm_dependencies

FINALIZATION_ALGORITHM = "_finalize"


@dataclass(frozen=True)
class Task:
    state_code: str
    algorithm: str

    @property
    def is_finalization(self) -> bool:
        return self.algorithm == FINALIZATION_ALGORITHM


@dataclass(frozen=True)
class ExperimentPlan:
    states: tuple[str, ...]
    algorithms: tuple[str, ...] = ALGORITHM_NAMES


@dataclass
class TaskGraph:
    tasks: list[Task] = field(default_factory=list)
    dependencies: dict[Task, frozenset[Task]] = field(default_factory=dict)
    statuses: dict[Task, TaskStatus] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for t in self.tasks:
            self.statuses.setdefault(t, "pending")

    def status(self, task: Task) -> TaskStatus:
        return self.statuses[task]

    def ready_tasks(self) -> list[Task]:
        return [t for t in self.tasks if self._is_ready(t)]

    def _is_ready(self, task: Task) -> bool:
        if self.statuses[task] != "pending":
            return False
        return all(self.statuses[dep] in ("done", "failed") for dep in self.dependencies[task])

    def mark_running(self, task: Task) -> None:
        if self.statuses[task] != "pending":
            raise ValueError(f"cannot mark running: {task} is {self.statuses[task]}")
        self.statuses[task] = "running"

    def mark_done(self, task: Task) -> None:
        self.statuses[task] = "done"

    def mark_failed(self, task: Task, error: str) -> None:
        self.statuses[task] = "failed"

    def all_done(self) -> bool:
        return all(s in ("done", "failed") for s in self.statuses.values())


def build_graph(plan: ExperimentPlan) -> TaskGraph:
    tasks: list[Task] = []
    deps: dict[Task, frozenset[Task]] = {}

    for state in plan.states:
        algorithm_tasks_for_state: list[Task] = []
        for algo in plan.algorithms:
            # Validate algorithm name (also future-proofs for v2 deps lookup).
            algorithm_dependencies(algo)
            t = Task(state, algo)
            tasks.append(t)
            deps[t] = frozenset()
            algorithm_tasks_for_state.append(t)

        finalize = Task(state, FINALIZATION_ALGORITHM)
        tasks.append(finalize)
        deps[finalize] = frozenset(algorithm_tasks_for_state)

    return TaskGraph(tasks=tasks, dependencies=deps)
