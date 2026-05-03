# tsm/deps.py — Dependency engine (Phase 7, P7-T01)
#
# Six public functions for dependency analysis and validation.
# All functions accept list[Phase] and derive state purely from
# Task.hard_deps fields — no file I/O, no imports from command modules.
#
# Implements §16.1 and §16.2 pre-write gate contract.

from tsm.models import Phase, Task, TaskStatus


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_dep_graph(phases: list[Phase]) -> dict[str, list[str]]:
    """Build an adjacency dict mapping each task ID to its hard_deps.

    Returns {task_id: [dep_id, ...]} for every task across all phases.
    Tasks with no hard deps have an empty list.
    """
    graph: dict[str, list[str]] = {}
    for phase in phases:
        for task in phase.tasks:
            graph[task.id] = list(task.hard_deps)  # defensive copy
    return graph


def get_dependents(phases: list[Phase], task_id: str) -> list[str]:
    """Return task IDs whose hard_deps include *task_id*.

    This is the inverse of build_dep_graph — it answers "what depends on me?"
    """
    dependents: list[str] = []
    for phase in phases:
        for task in phase.tasks:
            if task_id in task.hard_deps:
                dependents.append(task.id)
    return dependents


def get_dep_chain(phases: list[Phase], task_id: str) -> list[str]:
    """Return the full transitive ancestor chain for *task_id*.

    Uses DFS traversal to produce a list where furthest ancestors
    appear first, culminating in immediate hard deps.

    Example: if P1-T03 depends on P1-T02 which depends on P1-T01,
    get_dep_chain(phases, "P1-T03") -> ["P1-T01", "P1-T02"].
    """
    graph = build_dep_graph(phases)
    visited: set[str] = set()
    chain: list[str] = []

    def _dfs(node: str) -> None:
        for dep_id in graph.get(node, []):
            if dep_id not in visited:
                visited.add(dep_id)
                _dfs(dep_id)
                chain.append(dep_id)

    _dfs(task_id)
    return chain


def get_blocked_tasks(phases: list[Phase]) -> list[Task]:
    """Return tasks where at least one hard dep is not ✅ Complete.

    Builds a set of all complete task IDs, then filters all tasks
    whose hard_deps contain any ID not in that set.
    """
    complete_ids: set[str] = set()
    for phase in phases:
        for task in phase.tasks:
            if task.status == TaskStatus.COMPLETE:
                complete_ids.add(task.id)

    blocked: list[Task] = []
    for phase in phases:
        for task in phase.tasks:
            if not task.hard_deps:
                continue
            for dep_id in task.hard_deps:
                if dep_id not in complete_ids:
                    blocked.append(task)
                    break  # one unmet dep is enough
    return blocked


def check_deps(phases: list[Phase]) -> list[str]:
    """Validate the dependency graph for integrity issues.

    Checks performed:
      1. Self-references — a task that lists itself in hard_deps.
      2. Dangling references — a hard_dep ID that does not match any
         task ID in *phases*.
      3. Cycles — detected via detect_cycles().

    Returns a list of human-readable error strings (empty list = clean).
    Never raises.
    """
    errors: list[str] = []
    all_task_ids: set[str] = set()
    for phase in phases:
        for task in phase.tasks:
            all_task_ids.add(task.id)

    graph = build_dep_graph(phases)

    # 1. Self-references
    for task_id, deps in graph.items():
        if task_id in deps:
            errors.append(
                f"Self-reference: task {task_id} lists itself in hard_deps"
            )

    # 2. Dangling references
    for task_id, deps in graph.items():
        for dep_id in deps:
            if dep_id == task_id:
                continue  # already reported above
            if dep_id not in all_task_ids:
                errors.append(
                    f"Dangling dep: task {task_id} depends on {dep_id} "
                    f"which does not exist"
                )

    # 3. Cycles
    cycle = detect_cycles(phases)
    if cycle:
        errors.append(
            f"Cycle detected: {' → '.join(cycle)}"
        )

    return errors


def detect_cycles(phases: list[Phase]) -> list[str]:
    """Detect a directed cycle in the dependency graph using DFS.

    Uses the standard visited + recursion-stack approach. On finding a
    back-edge to a node currently on the recursion stack, reconstructs
    and returns the cycle path.

    Returns the cycle path as a list of task IDs (e.g. ["A", "B", "A"])
    if a cycle exists, or an empty list if the graph is acyclic.
    """
    graph = build_dep_graph(phases)
    visited: set[str] = set()
    rec_stack: set[str] = set()
    parent: dict[str, str | None] = {}

    def _dfs(node: str) -> list[str]:
        visited.add(node)
        rec_stack.add(node)

        for neighbour in graph.get(node, []):
            if neighbour not in visited:
                parent[neighbour] = node
                result = _dfs(neighbour)
                if result:
                    return result
            elif neighbour in rec_stack:
                # Back-edge found — reconstruct cycle
                cycle: list[str] = [neighbour, node]
                cur = node
                while cur != neighbour and parent.get(cur) is not None:
                    cur = parent[cur]  # type: ignore[assignment]
                    cycle.append(cur)
                cycle.reverse()
                return cycle

        rec_stack.remove(node)
        return []

    for task_id in graph:
        if task_id not in visited:
            result = _dfs(task_id)
            if result:
                return result

    return []
