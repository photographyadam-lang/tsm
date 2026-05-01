# tsm/commands/vibe_check.py — Integrity validation (Phase 4, P4-T04)
#
# Implements §7.5 vibe-check logic (13 validation rules VC-01 through VC-13).
#
# Public API:
#   run_vibe_check(ctx: LoadedProject) -> tuple[list[str], list[str], str]
#   vibe_check(ctx: LoadedProject) -> None
#   HELP_TEXT: str
#
# Constraints (§7.5):
#   - Read-only command — prints directly to stdout, no PendingWrite
#   - VC-11 fires for missing required fields (Status, What, Prerequisite,
#     Hard deps, Files, Reviewer, Done when) but NOT for absent
#     Key constraints (§4.1.9)
#   - VC-13 fires only for Active and Up next tasks — suppressed for
#     completed tasks
#   - VC-12 uses datetime subtraction (timedelta > 7 days), not date
#     comparison
#   - HELP_TEXT must be a module-level string constant

from datetime import datetime, timezone
from pathlib import Path

from tsm.models import (
    LoadedProject,
    Task,
    TaskStatus,
    TaskComplexity,
)


# ── Public API ──────────────────────────────────────────────────────────────


def run_vibe_check(
    ctx: LoadedProject,
) -> tuple[list[str], list[str], str]:
    """Run all 13 validation rules and return structured results.

    Args:
        ctx: The loaded project state.

    Returns:
        A tuple ``(errors, warnings, timestamp_str)`` where ``errors`` and
        ``warnings`` are lists of formatted message strings suitable for
        display in either the CLI or the TUI.
    """
    errors: list[str] = []
    warnings: list[str] = []

    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%dT%H:%M")

    # ── Collect data ──────────────────────────────────────────────────────

    # All tasks from all phases (flat list)
    all_tasks: list[Task] = []
    for phase in ctx.phases:
        all_tasks.extend(phase.tasks)

    # All task IDs (with counts for duplicate detection)
    task_id_counts: dict[str, int] = {}
    for task in all_tasks:
        task_id_counts[task.id] = task_id_counts.get(task.id, 0) + 1

    # Set of all unique task IDs
    all_task_ids: set[str] = set(task_id_counts.keys())

    # Build a lookup: task_id -> Task for the first occurrence
    task_by_id: dict[str, Task] = {}
    for task in all_tasks:
        if task.id not in task_by_id:
            task_by_id[task.id] = task

    # Build a set of complete task IDs
    complete_ids: set[str] = {
        t.id for t in all_tasks if t.status == TaskStatus.COMPLETE
    }

    # ── VC-01: Duplicate task IDs ─────────────────────────────────────────
    for task_id, count in task_id_counts.items():
        if count > 1:
            errors.append(
                f"VC-01  TASKS.md\n"
                f"       Duplicate task ID: {task_id} appears {count} times"
            )

    # ── VC-02: Dangling hard dep references ───────────────────────────────
    for task in all_tasks:
        for dep in task.hard_deps:
            if dep not in all_task_ids:
                errors.append(
                    f"VC-02  TASKS.md · {task.id}\n"
                    f"       Hard dep '{dep}' references a task ID that "
                    f"does not exist in TASKS.md"
                )

    # ── VC-03: Active task has status complete ────────────────────────────
    if ctx.session.active_task is not None:
        active_id = ctx.session.active_task.id
        # Check if the active task ID appears as complete in any phase
        active_task_in_phases = task_by_id.get(active_id)
        if active_task_in_phases is not None:
            if active_task_in_phases.status == TaskStatus.COMPLETE:
                errors.append(
                    f"VC-03  SESSIONSTATE.md · ## Active task\n"
                    f"       {active_id} has status '{_status_display(active_task_in_phases.status)}' "
                    f"in TASKS.md but is set as active task"
                )

    # ── VC-04: Up next task has status complete ───────────────────────────
    for up_next_task in ctx.session.up_next:
        task_in_phases = task_by_id.get(up_next_task.id)
        if task_in_phases is not None:
            if task_in_phases.status == TaskStatus.COMPLETE:
                errors.append(
                    f"VC-04  SESSIONSTATE.md · ## Up next\n"
                    f"       {up_next_task.id} has status "
                    f"'{_status_display(task_in_phases.status)}' in TASKS.md "
                    f"but is listed in Up next"
                )

    # ── VC-05: Up next task has unmet hard deps ───────────────────────────
    for up_next_task in ctx.session.up_next:
        unmet: list[str] = []
        for dep in up_next_task.hard_deps:
            if dep not in complete_ids:
                dep_status = ""
                dep_task = task_by_id.get(dep)
                if dep_task is not None:
                    dep_status = f" ({_status_display(dep_task.status)})"
                unmet.append(f"{dep}{dep_status}")
        if unmet:
            warnings.append(
                f"VC-05  SESSIONSTATE.md · Up next\n"
                f"       {up_next_task.id} has unmet hard dep(s): "
                f"{', '.join(unmet)}"
            )

    # ── VC-06: Active task is blank or [none] ─────────────────────────────
    if ctx.session.active_task is None:
        warnings.append(
            f"VC-06  SESSIONSTATE.md\n"
            f"       ## Active task is [none] or blank"
        )

    # ── VC-07: Active phase is blank or [none] ────────────────────────────
    phase_name = (ctx.session.active_phase_name or "").strip()
    if not phase_name or phase_name.lower() == "[none]":
        warnings.append(
            f"VC-07  SESSIONSTATE.md\n"
            f"       ## Active phase is [none] or blank"
        )

    # ── VC-08: Phase structure table ref with no matching # section ───────
    phase_names_in_sections: set[str] = set()
    for phase in ctx.phases:
        phase_names_in_sections.add(phase.name)

    for overview_row in ctx.phase_overview:
        if overview_row.phase_name not in phase_names_in_sections:
            errors.append(
                f"VC-08  TASKS.md · ## Phase structure\n"
                f"       Phase '{overview_row.phase_name}' is listed in the "
                f"phase structure table but has no matching # section"
            )

    # ── VC-09: Task with Active/In progress status not matching session ───
    if ctx.session.active_task is not None:
        session_active_id = ctx.session.active_task.id
        for task in all_tasks:
            if task.status in (TaskStatus.ACTIVE, TaskStatus.IN_PROGRESS):
                if task.id != session_active_id:
                    warnings.append(
                        f"VC-09  TASKS.md · {task.id}\n"
                        f"       Task has status "
                        f"'{_status_display(task.status)}' in TASKS.md but "
                        f"does not match ## Active task "
                        f"({session_active_id}) in SESSIONSTATE.md"
                    )

    # ── VC-10: TASKS-COMPLETED.md contains task ID not in TASKS.md ────────
    completed_ids_in_log: list[str] = _extract_completed_task_ids(
        Path(ctx.project_context.tasks_completed_path)
    )
    for cid in completed_ids_in_log:
        if cid not in all_task_ids:
            errors.append(
                f"VC-10  TASKS-COMPLETED.md\n"
                f"       Task ID '{cid}' not found in TASKS.md"
            )

    # ── VC-11: Missing required fields (NOT Key constraints) ──────────────
    # Required fields per spec: Status, What, Prerequisite, Hard deps,
    # Files, Reviewer, Done when.  Key constraints absence is valid (§4.1.9).
    for task in all_tasks:
        missing = _check_missing_required_fields(task)
        if missing:
            warnings.append(
                f"VC-11  TASKS.md · {task.id}\n"
                f"       Missing required field(s): {', '.join(missing)}"
            )

    # ── VC-12: Last updated > 7 days ago (datetime arithmetic) ────────────
    last_updated = ctx.session.last_updated
    if last_updated is not None:
        # Ensure both are naive datetimes for subtraction
        if last_updated.tzinfo is not None:
            last_updated = last_updated.replace(tzinfo=None)
        delta = now - last_updated
        if delta.days > 7:
            days_ago = delta.days
            last_str = last_updated.strftime("%Y-%m-%dT%H:%M")
            warnings.append(
                f"VC-12  SESSIONSTATE.md\n"
                f"       Last updated {last_str} — {days_ago} days ago"
            )

    # ── VC-13: Active or Up next task has complexity: unset ───────────────
    # Active task
    if ctx.session.active_task is not None:
        if ctx.session.active_task.complexity == TaskComplexity.UNSET:
            warnings.append(
                f"VC-13  SESSIONSTATE.md · ## Active task\n"
                f"       {ctx.session.active_task.id} complexity is unset "
                f"— model not yet assessed"
            )
    # Up next tasks
    for up_next_task in ctx.session.up_next:
        if up_next_task.complexity == TaskComplexity.UNSET:
            warnings.append(
                f"VC-13  SESSIONSTATE.md · Up next\n"
                f"       {up_next_task.id} complexity is unset — "
                f"model not yet assessed"
            )

    return errors, warnings, timestamp_str


def vibe_check(ctx: LoadedProject) -> None:
    """Run all 13 validation rules and print results to stdout.

    Args:
        ctx: The loaded project state.
    """
    errors, warnings, timestamp_str = run_vibe_check(ctx)
    _print_report(errors, warnings, timestamp_str)


# ── Internal helpers ────────────────────────────────────────────────────────


def _status_display(status: TaskStatus) -> str:
    """Return a human-readable status string for display in VC messages."""
    mapping = {
        TaskStatus.COMPLETE: "✅ Complete",
        TaskStatus.ACTIVE: "Active",
        TaskStatus.PENDING: "Pending",
        TaskStatus.BLOCKED: "Blocked",
        TaskStatus.NEEDS_REVIEW: "Needs Review",
        TaskStatus.IN_PROGRESS: "In Progress",
    }
    return mapping.get(status, status.value)


def _check_missing_required_fields(task: Task) -> list[str]:
    """Check a task block for missing required fields.

    Required: Status, Complexity, What, Prerequisite, Hard deps, Files,
    Reviewer, Done when.

    Key constraints absence is NOT a violation (§4.1.9).

    Returns a list of missing field names (empty if all present).
    """
    missing: list[str] = []

    # Status — always present via parser, but check raw_block for safety
    if not task.what.strip():
        missing.append("What")
    if not task.prerequisite.strip():
        missing.append("Prerequisite")
    if task.hard_deps is None:
        missing.append("Hard deps")
    if not task.files:
        missing.append("Files")
    if not task.reviewer.strip():
        missing.append("Reviewer")
    if not task.done_when.strip():
        missing.append("Done when")

    return missing


def _extract_completed_task_ids(path: Path) -> list[str]:
    """Extract task IDs from the TASKS-COMPLETED.md pipe-delimited table.

    Returns a list of task ID strings found in the file, or an empty list
    if the file does not exist.
    """
    ids: list[str] = []
    if not path.exists():
        return ids

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ids

    for line in content.splitlines():
        line = line.strip()
        # Look for pipe-delimited rows — first column is the task ID
        if line.startswith("|") and line.endswith("|"):
            parts = [p.strip() for p in line.split("|")]
            # Skip header/separator rows
            if len(parts) >= 2 and parts[1] and not parts[1].startswith("-"):
                candidate = parts[1]
                # Task IDs look like P1-T01, FA-T01, etc.
                if candidate and " " not in candidate:
                    ids.append(candidate)

    return ids


def _print_report(errors: list[str], warnings: list[str], timestamp: str) -> None:
    """Print the vibe-check report to stdout in the §7.5 format."""
    separator = "─" * 29
    header = f"  Vibe Check — {timestamp}"

    print(separator)
    print(header)
    print(separator)
    print()

    if not errors and not warnings:
        print("  ✅ No errors found.  ✅ No warnings.")
        print()
        print(separator)
        return

    # Count line
    error_count = len(errors)
    warning_count = len(warnings)

    if error_count > 0:
        count_line = f"  ❌ {error_count} error"
        if error_count > 1:
            count_line += "s"
        if warning_count > 0:
            count_line += f"   ⚠️  {warning_count} warning"
            if warning_count > 1:
                count_line += "s"
    else:
        count_line = f"  ✅ No errors found."
        count_line += f"   ⚠️  {warning_count} warning"
        if warning_count > 1:
            count_line += "s"

    print(count_line)
    print()

    # ERRORS section
    if errors:
        print("  ERRORS")
        print("  " + "─" * 7)
        for err in errors:
            print(f"  {err}")
            print()

    # WARNINGS section
    if warnings:
        print("  WARNINGS")
        print("  " + "─" * 9)
        for warn in warnings:
            print(f"  {warn}")
            print()

    print(separator)


# ── HELP_TEXT ──────────────────────────────────────────────────────────────

HELP_TEXT = """\
tsm vibe-check — Validate integrity of TASKS.md and SESSIONSTATE.md.

Usage: tsm vibe-check

Read-only. Runs 13 validation rules (VC-01 through VC-13) across all three
workflow files and prints any errors or warnings found.

Validation rules:
  VC-01  Error     Duplicate task IDs in TASKS.md
  VC-02  Error     Hard dep references a nonexistent task ID
  VC-03  Error     Active task has status Complete in TASKS.md
  VC-04  Error     Up-next task has status Complete in TASKS.md
  VC-05  Warning   Up-next task has unmet hard deps
  VC-06  Warning   Active task is [none] or blank
  VC-07  Warning   Active phase is [none] or blank
  VC-08  Error     Phase structure table ref with no matching section
  VC-09  Warning   Task with Active/In-Progress status not matching session
  VC-10  Error     TASKS-COMPLETED.md contains unknown task ID
  VC-11  Warning   Task block missing a required field
  VC-12  Warning   Last updated is more than 7 days ago
  VC-13  Warning   Active/up-next task has complexity: unset

Preconditions:
  - A project root must exist (TASKS.md and SESSIONSTATE.md must be present).

No files are written.
"""
