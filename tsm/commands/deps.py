# tsm/commands/deps.py — Dependency inspection command (Phase 7, P7-T02)
#
# Read-only — no PendingWrite, no shadow, no confirmation.
# Four modes per §16.3:
#   tsm deps <task-id>       detail for one task
#   tsm deps --tree          full ASCII dependency tree (default for bare invocation)
#   tsm deps --blocked       list tasks with unmet deps only
#   tsm deps --check         validate all deps; exit 1 if issues found
#
# Public API:
#   deps_command(ctx, task_id=None, tree=False, blocked=False, check=False) -> None
#   HELP_TEXT: str

from tsm.deps import (
    build_dep_graph,
    check_deps,
    get_blocked_tasks,
    get_dep_chain,
    get_dependents,
)
from tsm.models import (
    LoadedProject,
    Phase,
    Task,
    TaskStatus,
)


# ── Status display helpers ───────────────────────────────────────────────────

_STATUS_TEXT: dict[TaskStatus, str] = {
    TaskStatus.COMPLETE: "✅ Complete",
    TaskStatus.ACTIVE: "▶ Active",
    TaskStatus.PENDING: "· Pending",
    TaskStatus.BLOCKED: "🔒 Blocked",
    TaskStatus.NEEDS_REVIEW: "⚠️ Needs review",
    TaskStatus.IN_PROGRESS: "▶ In progress",
}

_STATUS_ICON: dict[TaskStatus, str] = {
    TaskStatus.COMPLETE: "✅",
    TaskStatus.ACTIVE: "▶",
    TaskStatus.PENDING: "·",
    TaskStatus.BLOCKED: "🔒",
    TaskStatus.NEEDS_REVIEW: "⚠️",
    TaskStatus.IN_PROGRESS: "▶",
}

_SEP = "─" * 60


def _find_task(phases: list[Phase], task_id: str) -> Task | None:
    """Locate a task by ID across all phases."""
    for phase in phases:
        for task in phase.tasks:
            if task.id == task_id:
                return task
    return None


def _status_label(status: TaskStatus) -> str:
    return _STATUS_TEXT.get(status, f"· {status.value}")


def _status_icon(status: TaskStatus) -> str:
    return _STATUS_ICON.get(status, "·")


# ── Mode: single task detail ─────────────────────────────────────────────────


def _show_task_detail(ctx: LoadedProject, task_id: str) -> None:
    """Print dependencies-for and required-by for a single task (§16.3)."""
    task = _find_task(ctx.phases, task_id)
    if task is None:
        print(f"❌ Unknown task ID: {task_id}")
        return

    print(_SEP)
    print(f"  Dependencies for {task.id}")
    print(_SEP)

    # Depends on
    print("  Depends on:")
    deps = get_dep_chain(ctx.phases, task_id)
    # Also show direct hard_deps in order
    direct_deps = task.hard_deps
    if direct_deps:
        for dep_id in direct_deps:
            dep_task = _find_task(ctx.phases, dep_id)
            if dep_task:
                print(f"    {dep_id}  {_status_label(dep_task.status)}")
            else:
                print(f"    {dep_id}  ❌ Unknown")
    else:
        print("    (none)")

    print()
    print("  Required by:")
    dependents = get_dependents(ctx.phases, task_id)
    if dependents:
        for dep_id in dependents:
            dep_task = _find_task(ctx.phases, dep_id)
            if dep_task:
                print(f"    {dep_id}  {_status_label(dep_task.status)}")
            else:
                print(f"    {dep_id}  (unknown)")
    else:
        print("    (none)")

    # Status line
    print()
    blocked = get_blocked_tasks(ctx.phases)
    is_blocked = any(t.id == task_id for t in blocked)
    if is_blocked:
        print("  Status:   🔒 Blocked")
        for dep_id in task.hard_deps:
            dep_task = _find_task(ctx.phases, dep_id)
            if dep_task and dep_task.status != TaskStatus.COMPLETE:
                print(
                    f"              {dep_id} is "
                    f"{_status_label(dep_task.status)} "
                    f"(must be Complete)"
                )
    else:
        print("  Status:   ✅ All deps met — ready to start")
    print(_SEP)


# ── Mode: tree ───────────────────────────────────────────────────────────────


def _show_tree(ctx: LoadedProject) -> None:
    """Print the full ASCII dependency tree (§16.3)."""
    print(_SEP)
    print("  Dependency Tree")
    print(_SEP)
    print()

    all_tasks: list[Task] = []
    for phase in ctx.phases:
        for task in phase.tasks:
            all_tasks.append(task)

    # Compute title display length for alignment
    max_title_len = max(len(task.title) for task in all_tasks) if all_tasks else 0

    for phase in ctx.phases:
        for task in phase.tasks:
            icon = _status_icon(task.status)
            deps_str = ""
            if task.hard_deps:
                deps_str = "  ← " + ", ".join(task.hard_deps)
            title_padded = task.title.ljust(max_title_len)
            print(f"  {task.id}  {title_padded}  {icon}{deps_str}")
        print()  # blank line between phases

    blocked_count = len(get_blocked_tasks(ctx.phases))
    cycles = _detect_cycle_count(ctx.phases)
    total = len(all_tasks)
    print(_SEP)
    print(f"  {total} tasks  |  {blocked_count} blocked  |  {cycles} cycles")
    print(_SEP)


def _detect_cycle_count(phases: list[Phase]) -> int:
    """Return the number of cycles (0 or 1 — detect_cycles returns at most one)."""
    from tsm.deps import detect_cycles

    cycle = detect_cycles(phases)
    return 1 if cycle else 0


# ── Mode: blocked ────────────────────────────────────────────────────────────


def _show_blocked(ctx: LoadedProject) -> None:
    """Print only tasks with unmet deps (§16.3)."""
    blocked = get_blocked_tasks(ctx.phases)
    print(_SEP)
    print(f"  Blocked tasks ({len(blocked)})")
    print(_SEP)
    for task in blocked:
        print(f"  {task.id}  {task.title}")
        waiting: list[str] = []
        for dep_id in task.hard_deps:
            dep_task = _find_task(ctx.phases, dep_id)
            if dep_task and dep_task.status != TaskStatus.COMPLETE:
                waiting.append(f"{dep_id} ({_status_label(dep_task.status)})")
        if waiting:
            print(f"          Waiting on: {', '.join(waiting)}")
    print(_SEP)


# ── Mode: check ──────────────────────────────────────────────────────────────


def _show_check(ctx: LoadedProject) -> None:
    """Validate all deps and print results (§16.3).

    Raises PreconditionError if issues are found so the CLI can exit 1.
    """
    errors = check_deps(ctx.phases)
    total = sum(len(phase.tasks) for phase in ctx.phases)
    if not errors:
        print(f"✅ No dependency issues found. ({total} tasks checked)")
    else:
        print(f"❌ {len(errors)} dependency issues found:")
        print()
        # Format errors per §16.3
        graph = build_dep_graph(ctx.phases)
        for err in errors:
            # Parse error message to extract task ID
            if "Self-reference:" in err:
                # "Self-reference: task <id> lists itself in hard_deps"
                task_id = err.split("task ")[1].split(" ")[0]
                task = _find_task(ctx.phases, task_id)
                title = task.title if task else "(unknown)"
                print(f"  {task_id}  {title}")
                print(f"          {err.split('—')[1].strip() if '—' in err else err}")
            elif "Dangling dep:" in err:
                # "Dangling dep: task <id> depends on <dep> which does not exist"
                parts = err.split()
                task_id = parts[2]  # after "task"
                dep_id = parts[4]  # after "depends", before "on"
                if dep_id == "on":
                    dep_id = parts[5]
                task = _find_task(ctx.phases, task_id)
                title = task.title if task else "(unknown)"
                print(
                    f"  {task_id}  {title}"
                )
                print(
                    f"          Hard deps references \"{dep_id}\""
                    f" — task does not exist"
                )
            elif "Cycle detected:" in err:
                # "Cycle detected: A → B → A"
                cycle_path = err.split("Cycle detected: ")[1]
                # Try to find the first task ID in the cycle
                first_id = cycle_path.split(" → ")[0]
                task = _find_task(ctx.phases, first_id)
                title = task.title if task else "(unknown)"
                print(
                    f"  {first_id}  {title}"
                )
                print(
                    f"          Cycle detected: {cycle_path}"
                )
            else:
                # Fallback: print raw error
                print(f"  {err}")

        from tsm.__main__ import PreconditionError

        raise PreconditionError(
            f"{len(errors)} dependency issue(s) found"
        )


# ── Public API ───────────────────────────────────────────────────────────────


def deps_command(
    ctx: LoadedProject,
    task_id: str | None = None,
    tree: bool = False,
    blocked: bool = False,
    check: bool = False,
) -> None:
    """Dependency inspection command (§16.3).

    Read-only — no PendingWrite, no shadow, no confirmation.

    Args:
        ctx: The loaded project state.
        task_id: If given, show detail for this single task.
        tree: If True, show the full ASCII dependency tree.
        blocked: If True, show only tasks with unmet deps.
        check: If True, validate all deps and exit 1 on issues.

    Bare invocation (all flags False) defaults to ``--tree``.
    """
    # Bare invocation → default to tree
    if task_id is None and not tree and not blocked and not check:
        tree = True

    if task_id is not None:
        _show_task_detail(ctx, task_id)
    elif tree:
        _show_tree(ctx)
    elif blocked:
        _show_blocked(ctx)
    elif check:
        _show_check(ctx)


# ── HELP_TEXT ────────────────────────────────────────────────────────────────

HELP_TEXT = """tsm deps — Dependency inspection

Inspect and validate task dependency relationships.

USAGE:
  tsm deps                         Show full dependency tree (same as --tree)
  tsm deps <task-id>               Show dependencies for one task
  tsm deps --tree                  Show full ASCII dependency tree
  tsm deps --blocked               Show only tasks with unmet dependencies
  tsm deps --check                 Validate all dependencies; exit 1 on issues

MODES:
  task-id    Prints what the given task depends on (depends-on) and what
             depends on it (required-by), with status icons.

  --tree     Prints all tasks organised by phase, with dependency arrows
             pointing to each task's hard deps. Summary line shows total
             task count, blocked count, and cycle count.

  --blocked  Lists tasks whose hard deps include at least one task that is
             not yet complete, along with what they are waiting on.

  --check    Runs full validation: no dangling deps, no cycles, no
             self-references. Prints "✅ No dependency issues found." on
             success; prints issues and exits with code 1 on failure.

OUTPUT FORMAT (§16.3):
  Uses box-drawing separators (─), status emoji icons (✅ ▶ · 🔒 ⚠️),
  and consistent indentation for all output modes.

EXIT CODES:
  0  Success (or no issues found in --check mode)
  1  Dependency issues found (--check mode) or unknown task ID

EXAMPLES:
  tsm deps P1-T03
  tsm deps --tree
  tsm deps --blocked
  tsm deps --check"""
