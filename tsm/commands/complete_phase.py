# tsm/commands/complete_phase.py — Complete the current phase (Phase 4, P4-T03)
#
# Implements §7.4 phase completion logic.
#
# Public API:
#   complete_phase(ctx: LoadedProject) -> list[PendingWrite]
#   HELP_TEXT: str
#
# Constraints (§7.4):
#   - Precondition: all tasks in the current phase must have status complete;
#     if not, abort with ValueError listing incomplete task IDs
#   - Next phase detection: iterate ctx.phases in order, find the first phase
#     after the current one with status != complete; if none, next phase is [none]
#   - Build 3 PendingWrite objects: SESSIONSTATE.md, TASKS.md, TASKS-COMPLETED.md
#   - TASKS.md write must use update_phase_status() — not update_task_status()
#   - HELP_TEXT must be a module-level string constant

from datetime import datetime
from pathlib import Path

from tsm.models import (
    LoadedProject,
    PendingWrite,
    SessionState,
    Task,
    TaskStatus,
)
from tsm.writers.completed_writer import append_phase_marker
from tsm.writers.session_writer import render_sessionstate
from tsm.writers.tasks_writer import update_phase_status


# ── Public API ──────────────────────────────────────────────────────────────


def complete_phase(ctx: LoadedProject) -> list[PendingWrite]:
    """Complete the current phase and rotate to the next phase.

    Precondition (§7.4):
        All tasks in the current phase (matched by
        ``ctx.session.active_phase_name``) must have status ``COMPLETE``
        in ``ctx.phases``.  Raises ``ValueError`` listing any incomplete
        task IDs if this precondition is not met.

    Next phase detection:
        Iterates ``ctx.phases`` in order, finds the first phase after the
        current one with ``status != "\\u2705 Complete"``.  If no such phase
        exists, the next phase is ``[none]``.

    Returns:
        A list of three ``PendingWrite`` objects:
        (1) SESSIONSTATE.md — full reconstruction rotated to the next phase
            with new active task, up_next populated, completed list cleared.
        (2) TASKS.md — update_phase_status() call targeting the completed
            phase's ``# ...`` heading ``**Status:**`` line.
        (3) TASKS-COMPLETED.md — append_phase_marker() call inserting a
            ``**Phase complete: YYYY-MM-DD**`` line after the last task row.

    Raises:
        ValueError: If any task in the current phase is not complete.
    """
    # ── Find the current phase object ────────────────────────────────────
    current_phase = None
    for phase in ctx.phases:
        if phase.name == ctx.session.active_phase_name:
            current_phase = phase
            break

    if current_phase is None:
        raise ValueError(
            f"Current phase '{ctx.session.active_phase_name}' not found "
            f"in project phases."
        )

    # ── Precondition: all tasks in current phase must be complete ────────
    incomplete_tasks = [
        t for t in current_phase.tasks if t.status != TaskStatus.COMPLETE
    ]
    if incomplete_tasks:
        incomplete_ids = ", ".join(t.id for t in incomplete_tasks)
        raise ValueError(
            f"Cannot complete phase '{current_phase.name}': "
            f"the following tasks are not yet complete: {incomplete_ids}"
        )

    # ── Next phase detection ─────────────────────────────────────────────
    current_idx = -1
    for i, phase in enumerate(ctx.phases):
        if phase.name == ctx.session.active_phase_name:
            current_idx = i
            break

    next_phase = None
    if current_idx >= 0:
        for phase in ctx.phases[current_idx + 1 :]:
            if phase.status != "✅ Complete":
                next_phase = phase
                break

    pc = ctx.project_context

    # ── Active task and up_next for the next phase ───────────────────────
    if next_phase is not None:
        selected_task = _select_first_ready_task(
            next_phase.tasks, ctx.phases
        )
        if selected_task is not None:
            new_active_task = selected_task
            new_active_task_raw = selected_task.raw_block
        else:
            new_active_task = None
            new_active_task_raw = "[none]"
            print(
                "Warning: No task in the next phase has all hard deps met. "
                "active_task set to [none]."
            )

        up_next_tasks = [
            t
            for t in next_phase.tasks
            if t.status != TaskStatus.COMPLETE
            and (selected_task is None or t.id != selected_task.id)
        ]
    else:
        new_active_task = None
        new_active_task_raw = "[none]"
        up_next_tasks = []

    # ── Build next phase name / spec ─────────────────────────────────────
    if next_phase is not None:
        next_phase_name = next_phase.name
        next_phase_spec = f"`{Path(pc.tasks_path).name}`"
    else:
        next_phase_name = "[none]"
        next_phase_spec = "[none]"

    # ── Build new SessionState ───────────────────────────────────────────
    new_session = SessionState(
        last_updated=datetime.now(),
        active_phase_name=next_phase_name,
        active_phase_spec=next_phase_spec,
        active_task=new_active_task,
        active_task_raw=new_active_task_raw,
        up_next=up_next_tasks,
        completed=[],  # §7.4: clear completed list on phase rotation
        out_of_scope_raw=ctx.session.out_of_scope_raw,
    )

    # ── Read live TASKS.md content ───────────────────────────────────────
    tasks_content = Path(pc.tasks_path).read_text(encoding="utf-8")

    # ── Update TASKS.md phase status ─────────────────────────────────────
    # CRITICAL: use update_phase_status (not update_task_status) per §7.4
    updated_tasks_content = update_phase_status(
        tasks_content, current_phase.name, "✅ Complete"
    )

    # ── Append phase marker to TASKS-COMPLETED.md ────────────────────────
    today = datetime.now().strftime("%Y-%m-%d")
    shadow_dir = pc.shadow_dir.rstrip("/\\")
    completed_shadow = str(Path(shadow_dir) / "TASKS-COMPLETED.md")

    append_phase_marker(
        path=Path(pc.tasks_completed_path),
        shadow_path=completed_shadow,
        phase_name=current_phase.name,
        date=today,
    )

    # ── Render SESSIONSTATE.md ───────────────────────────────────────────
    session_content = render_sessionstate(new_session)

    # ── Build shadow paths ───────────────────────────────────────────────
    session_shadow = str(Path(shadow_dir) / "SESSIONSTATE.md")
    tasks_shadow = str(Path(shadow_dir) / "TASKS.md")

    # ── Write staged content ─────────────────────────────────────────────
    _write_stage(session_content, session_shadow)
    _write_stage(updated_tasks_content, tasks_shadow)

    # ── Build PendingWrite objects ───────────────────────────────────────
    pending_writes = [
        PendingWrite(
            target_file="SESSIONSTATE.md",
            shadow_path=session_shadow,
            live_path=pc.sessionstate_path,
            backup_path=pc.backup_dir,
            summary_lines=[
                f"Complete phase: {current_phase.name}",
                f"Rotate to phase: {next_phase_name}",
            ],
        ),
        PendingWrite(
            target_file="TASKS.md",
            shadow_path=tasks_shadow,
            live_path=pc.tasks_path,
            backup_path=pc.backup_dir,
            summary_lines=[
                f"Update TASKS.md — set {current_phase.name} "
                f"status to \\u2705 Complete",
            ],
        ),
        PendingWrite(
            target_file="TASKS-COMPLETED.md",
            shadow_path=completed_shadow,
            live_path=pc.tasks_completed_path,
            backup_path=pc.backup_dir,
            summary_lines=[
                f"Append phase complete marker for {current_phase.name}",
            ],
        ),
    ]

    return pending_writes


# ── Internal helpers ────────────────────────────────────────────────────────


def _select_first_ready_task(
    tasks: list[Task], phases: list,
) -> Task | None:
    """Find the first task in *tasks* whose hard deps are all met.

    A task is considered ready if:
    - Its ``hard_deps`` list is empty, OR
    - Every dep ID in ``hard_deps`` has status ``COMPLETE`` somewhere
      in *phases*.

    Tasks with status ``COMPLETE`` are skipped.

    Returns the first matching task, or ``None`` if no task is ready.
    """
    # Build a set of all complete task IDs from all phases
    complete_ids: set[str] = set()
    for phase in phases:
        for task in phase.tasks:
            if task.status == TaskStatus.COMPLETE:
                complete_ids.add(task.id)

    for candidate in tasks:
        if candidate.status == TaskStatus.COMPLETE:
            continue  # skip already-complete tasks
        if not candidate.hard_deps:  # empty list → no deps → ready
            return candidate
        if all(dep in complete_ids for dep in candidate.hard_deps):
            return candidate

    return None


def _write_stage(content: str, shadow_path: str) -> None:
    """Write *content* to *shadow_path*, creating parent directories."""
    p = Path(shadow_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ── HELP_TEXT ──────────────────────────────────────────────────────────────

HELP_TEXT = """\
tsm complete-phase — Complete the current phase and rotate to the next phase.

Preconditions:
  - A project root must exist (TASKS.md and SESSIONSTATE.md must be present).
  - All tasks in the current phase must be marked complete.  If any task
    is incomplete, the command aborts with an error listing those tasks.
  - A phase must be active (use 'tsm init-phase <phase>' first).

Writes:
  1. SESSIONSTATE.md — rotates to the next phase (or sets phase to [none]
     if no further phases remain), selects the first ready task in the new
     phase as the active task, populates up_next, and clears the completed
     list.
  2. TASKS.md — updates the completed phase's **Status:** line to
     "\\u2705 Complete" using targeted phase-level replacement.
  3. TASKS-COMPLETED.md — appends a "**Phase complete: YYYY-MM-DD**"
     marker after the last task row in the completed phase's section.

The next phase is determined by scanning ctx.phases in order and finding
the first phase after the current one whose status is not already
"\\u2705 Complete".  If none exists, the project's active phase becomes
[none].

Example:
  tsm complete-phase
"""
