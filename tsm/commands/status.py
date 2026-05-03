# tsm/commands/status.py — Print session status (Phase 4, P4-T05)
#
# Implements §7.6 status display logic.
#
# Public API:
#   status(ctx: LoadedProject) -> None
#   HELP_TEXT: str
#
# Constraints (§7.6):
#   - Read-only command — prints directly to stdout, no PendingWrite
#   - Prints all 5 sections: Phase, Spec, Updated, Active task, Up next,
#     Completed
#   - Active task block shows Complexity value and Hard dep status icons
#   - HELP_TEXT must be a module-level string constant

from datetime import datetime
from pathlib import Path

from tsm.models import (
    LoadedProject,
    Task,
    TaskComplexity,
    TaskStatus,
)


# ── Public API ──────────────────────────────────────────────────────────────


def status(ctx: LoadedProject) -> None:
    """Print the current session status to stdout in the §7.6 format.

    Args:
        ctx: The loaded project state.
    """
    session = ctx.session

    # ── Build status lines ────────────────────────────────────────────────

    # Phase line
    phase_status = _phase_status_str(ctx)
    phase_line = f"  Phase:       {session.active_phase_name} ({phase_status})"

    # Spec line
    spec_line = f"  Spec:        {session.active_phase_spec}"

    # Updated line
    last_updated = session.last_updated
    if isinstance(last_updated, datetime):
        updated_str = last_updated.strftime("%Y-%m-%dT%H:%M")
    else:
        updated_str = str(last_updated)
    updated_line = f"  Updated:     {updated_str}"

    # Active task block
    active_lines: list[str] = []
    if session.active_task is not None:
        active = session.active_task
        # Task ID and title
        active_lines.append(
            f"  Active task: {active.id} — {active.title}"
        )
        # Complexity
        complexity_str = _complexity_display(active.complexity)
        complexity_hint = _complexity_hint(active.complexity)
        active_lines.append(
            f"               Complexity: {complexity_str}{complexity_hint}"
        )
        # Hard deps
        if active.hard_deps:
            dep_icons = _dep_status_icons(active.hard_deps, ctx.phases)
            active_lines.append(f"               Hard deps:  {dep_icons}")
        else:
            active_lines.append(f"               Hard deps:  (none)")
        # Reviewer
        reviewer = active.reviewer or "(none)"
        active_lines.append(f"               Reviewer:   {reviewer}")

    # Up next line
    up_next_tasks = session.up_next
    if up_next_tasks:
        up_next_parts: list[str] = []
        for task in up_next_tasks:
            cx = _complexity_short(task.complexity)
            up_next_parts.append(f"{task.id} ({cx})")
        up_next_summary = ", ".join(up_next_parts)
        up_next_line = (
            f"  Up next:     {up_next_summary}"
            f"  ({len(up_next_tasks)} task{'s' if len(up_next_tasks) != 1 else ''})"
        )
    else:
        up_next_line = "  Up next:     (none)"

    # Orphaned-task warning: detect non-complete tasks in the active phase
    # that are missing from the session's up_next (e.g. added to TASKS.md
    # after phase init, before advance could pick them up).
    orphaned = _check_orphaned_up_next(ctx)
    orphaned_warning_line = ""
    if orphaned:
        orphaned_ids = ", ".join(t.id for t in orphaned)
        orphaned_warning_line = (
            f"  \u26a0\ufe0f  Warning: {len(orphaned)} task(s) missing from "
            f"up_next: {orphaned_ids}\n"
            f"     Run 'tsm repair --session' to fix."
        )

    # Completed line
    completed_tasks = session.completed
    if completed_tasks:
        completed_ids = ", ".join(t.id for t in completed_tasks)
        completed_line = (
            f"  Completed:   {completed_ids}"
            f"  ({len(completed_tasks)} task{'s' if len(completed_tasks) != 1 else ''} this phase)"
        )
    else:
        completed_line = "  Completed:   (none)"

    # Phase overview — all phases with status
    phase_overview_lines = _build_phase_overview(ctx)

    # ── Print output ──────────────────────────────────────────────────────

    separator = "─" * 29
    print(separator)
    print("  Session Status")
    print(separator)
    print(phase_line)
    print(spec_line)
    print(updated_line)
    print()

    if active_lines:
        for line in active_lines:
            print(line)
    else:
        print("  Active task: [none]")

    print()
    print(up_next_line)
    if orphaned_warning_line:
        print(orphaned_warning_line)
    print(completed_line)
    print()

    # Phase overview block
    if phase_overview_lines:
        for line in phase_overview_lines:
            print(line)

    print(separator)


# ── Internal helpers ────────────────────────────────────────────────────────


def _build_phase_overview(ctx: LoadedProject) -> list[str]:
    """Build a list of lines showing all phases with their status.

    Uses ``ctx.phases`` (parsed from TASKS.md) for task-count details and
    ``ctx.phase_overview`` for the ordered phase list.  The current active
    phase is highlighted with ``← current``.

    Returns an empty list if there are no phases.
    """
    if not ctx.phases:
        return []

    active_name = ctx.session.active_phase_name
    lines: list[str] = []
    lines.append("  Phases:")
    lines.append("  " + "─" * 55)

    for phase in ctx.phases:
        total = len(phase.tasks)
        complete = sum(1 for t in phase.tasks if t.status == TaskStatus.COMPLETE)
        status_label = phase.status.lower().replace("_", " ")
        is_current = phase.name == active_name
        marker = "  ← current" if is_current else ""
        lines.append(
            f"    {phase.id:<40s} {status_label:<14s}"
            f"({complete}/{total} tasks){marker}"
        )

    lines.append("")
    return lines


def _phase_status_str(ctx: LoadedProject) -> str:
    """Return the human-readable status string for the active phase.

    Looks up the active phase by name in ``ctx.phases`` and returns its
    status (e.g. "in progress", "pending", "complete").
    """
    active_name = ctx.session.active_phase_name
    if not active_name or active_name.lower() == "[none]":
        return "not set"

    for phase in ctx.phases:
        if phase.name == active_name:
            return phase.status.lower()

    # Fallback: if the phase isn't in phases, use session info
    return "in progress"


def _complexity_display(complexity: TaskComplexity) -> str:
    """Return the display string for a complexity value."""
    if complexity == TaskComplexity.HIGH:
        return "high"
    elif complexity == TaskComplexity.MEDIUM:
        return "med"
    elif complexity == TaskComplexity.LOW:
        return "low"
    else:
        return "unset"


def _complexity_hint(complexity: TaskComplexity) -> str:
    """Return the hint string shown after complexity in the active task block.

    Only shown for high (← use large model) and unset (← not yet assessed).
    """
    if complexity == TaskComplexity.HIGH:
        return "  ← use large model"
    elif complexity == TaskComplexity.UNSET:
        return "  ← not yet assessed"
    else:
        return ""


def _complexity_short(complexity: TaskComplexity) -> str:
    """Return the short label for a complexity value (for Up next display)."""
    if complexity == TaskComplexity.HIGH:
        return "high"
    elif complexity == TaskComplexity.MEDIUM:
        return "med"
    elif complexity == TaskComplexity.LOW:
        return "low"
    else:
        return "unset"


def _dep_status_icons(dep_ids: list[str], phases: list) -> str:
    """Build a hard-dep display string with status icons.

    For each dep ID, looks up the task in *phases* and appends the
    appropriate status icon.

    Returns a string like ``"U-C1 ✅, U-D1 🔒"``.
    """
    # Build a lookup: task_id -> status
    dep_status: dict[str, TaskStatus] = {}
    for phase in phases:
        for task in phase.tasks:
            if task.id in dep_ids:
                dep_status[task.id] = task.status

    parts: list[str] = []
    for dep_id in dep_ids:
        status = dep_status.get(dep_id)
        icon = _status_icon(status) if status is not None else "❓"
        parts.append(f"{dep_id} {icon}")

    return ", ".join(parts)


def _status_icon(status: TaskStatus) -> str:
    """Return the status icon for a task status."""
    mapping = {
        TaskStatus.COMPLETE: "✅",
        TaskStatus.ACTIVE: "▶️",
        TaskStatus.PENDING: "⏳",
        TaskStatus.BLOCKED: "🔒",
        TaskStatus.NEEDS_REVIEW: "👁️",
        TaskStatus.IN_PROGRESS: "🔄",
    }
    return mapping.get(status, "❓")


def _check_orphaned_up_next(ctx: LoadedProject) -> list[Task]:
    """Find non-complete tasks in the active phase missing from
    ``ctx.session.up_next``.

    These are tasks that were added to ``TASKS.md`` (or whose status was
    changed to pending) *after* the phase was initialised — the session's
    ``up_next`` is a one-time snapshot taken during ``init_phase()``.

    Returns a list of orphaned :class:`Task` objects (empty if none found).
    """
    active_phase_name = ctx.session.active_phase_name
    if not active_phase_name or active_phase_name.lower() == "[none]":
        return []

    # Locate the active phase in parsed phases
    active_phase = None
    for phase in ctx.phases:
        if phase.name == active_phase_name:
            active_phase = phase
            break
    if active_phase is None:
        return []

    # Build lookup sets from the session
    up_next_ids = {t.id for t in ctx.session.up_next}
    active_task_id = (
        ctx.session.active_task.id
        if ctx.session.active_task is not None
        else None
    )
    completed_ids = {t.id for t in ctx.session.completed}

    # Collect orphaned tasks
    orphaned: list[Task] = []
    for task in active_phase.tasks:
        if task.status == TaskStatus.COMPLETE:
            continue
        if task.id in up_next_ids:
            continue
        if task.id == active_task_id:
            continue
        if task.id in completed_ids:
            continue
        orphaned.append(task)

    return orphaned


# ── HELP_TEXT ──────────────────────────────────────────────────────────────

HELP_TEXT = """\
tsm status — Print current session state.

Usage: tsm status

Read-only. Prints a structured summary of the current session state to stdout,
including the active phase, spec reference, last updated timestamp, active
task details (with complexity and hard dep status icons), up-next task list,
and completed task count.

Preconditions:
  - A project root must exist (TASKS.md and SESSIONSTATE.md must be present).

No files are written.

Example:
  tsm status
"""
