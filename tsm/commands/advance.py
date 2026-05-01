# tsm/commands/advance.py — Advance active task (Phase 4, P4-T01)
#
# Implements §7.3 task advancement logic.
#
# Public API:
#   advance(ctx: LoadedProject, commit_message: str = "") -> list[PendingWrite]
#   confirm_summary(pending_writes: list[PendingWrite]) -> str
#   HELP_TEXT: str
#
# Constraints (§7.3):
#   - advance() returns PendingWrite objects — it must not call shadow.apply()
#     itself; the caller (CLI or TUI) applies after confirmation
#   - The "just-advanced task counts as complete for dep resolution" logic
#     lives exclusively here — not in the writer or parser
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
from tsm.writers.session_writer import render_sessionstate
from tsm.writers.tasks_writer import update_task_status
from tsm.writers.completed_writer import append_task_row


# ── Public API ──────────────────────────────────────────────────────────────


def advance(
    ctx: LoadedProject, commit_message: str = ""
) -> list[PendingWrite]:
    """Advance the current active task and promote the next ready task.

    Precondition:
        ``ctx.session.active_task`` must not be ``None`` — raises
        ``ValueError`` with a clear message if it is.

    Args:
        ctx: The loaded project state.
        commit_message: Optional commit message to record in the
            TASKS-COMPLETED.md row and the SESSIONSTATE.md completed list.

    Returns:
        A list of three ``PendingWrite`` objects:
        (1) SESSIONSTATE.md — full reconstruction with updated completed
            list, promoted active task, and trimmed up_next.
        (2) TASKS.md — targeted status-line update for the advanced task.
        (3) TASKS-COMPLETED.md — appended row for the completed task.

    Raises:
        ValueError: If ``ctx.session.active_task`` is ``None``.
    """
    # ── Precondition check ───────────────────────────────────────────────
    if ctx.session.active_task is None:
        raise ValueError(
            "Cannot advance: no active task is set. "
            "Use 'tsm init-phase <phase>' to activate a phase first."
        )

    active_task = ctx.session.active_task
    pc = ctx.project_context

    # ── Read live TASKS.md content for targeted status update ────────────
    tasks_content = Path(pc.tasks_path).read_text(encoding="utf-8")

    # ── Promote next task from up_next ───────────────────────────────────
    # Defensive: ensure the active task isn't in up_next (shouldn't happen
    # in a clean session, but guards against session state corruption where
    # the active task appears in both ## Active task and ## Up next).
    filtered_up_next = [t for t in ctx.session.up_next if t.id != active_task.id]

    promoted_candidate = _find_next_ready_task(
        filtered_up_next, active_task.id, ctx.phases
    )

    # When promoting from up_next, the task object from the session parser
    # has raw_block="".  We need the real raw_block from the TASKS.md parser
    # (ctx.phases) so that active_task_raw can be emitted verbatim into
    # SESSIONSTATE.md.
    promoted_task: Task | None = None
    if promoted_candidate is not None:
        promoted_task = _find_task_in_phases(ctx.phases, promoted_candidate.id)
        if promoted_task is None:
            promoted_task = promoted_candidate  # fallback

    # Build the new completed list entry for the task being advanced
    completed_entry = Task(
        id=active_task.id,
        title=active_task.title,
        status=TaskStatus.COMPLETE,
        complexity=active_task.complexity,
        what=commit_message or "advanced",
        prerequisite="",
        hard_deps=[],
        files=[],
        reviewer="",
        key_constraints=[],
        done_when="",
        phase_id="",
        subphase=None,
        raw_block="",
    )

    # Build updated completed list (append the advanced task)
    new_completed = list(ctx.session.completed) + [completed_entry]

    # Build updated up_next (remove the promoted task if found, then
    # defensively strip the active task too).
    new_up_next = list(ctx.session.up_next)
    if promoted_task is not None:
        new_up_next = [t for t in new_up_next if t.id != promoted_task.id]
    # Defensive: ensure the active task never lingers in up_next
    new_up_next = [t for t in new_up_next if t.id != active_task.id]

    # Build new active_task / active_task_raw
    if promoted_task is not None:
        new_active_task = promoted_task
        new_active_task_raw = promoted_task.raw_block
    else:
        new_active_task = None
        new_active_task_raw = "[none]"

        if not filtered_up_next:
            # No more tasks remain in up_next — this was the last task
            # in the phase's current work queue.
            print(
                "The last task in this phase has been advanced. "
                "Use 'tsm complete-phase' to mark the phase as complete "
                "and rotate to the next phase."
            )
        else:
            print(
                "Warning: No task in up_next has all hard deps met. "
                "active_task set to [none]."
            )

    # ── Build updated SessionState for SESSIONSTATE.md ───────────────────
    new_session = SessionState(
        last_updated=datetime.now(),
        active_phase_name=ctx.session.active_phase_name,
        active_phase_spec=ctx.session.active_phase_spec,
        active_task=new_active_task,
        active_task_raw=new_active_task_raw,
        up_next=new_up_next,
        completed=new_completed,
        out_of_scope_raw=ctx.session.out_of_scope_raw,
    )

    # ── Render SESSIONSTATE.md content ───────────────────────────────────
    session_content = render_sessionstate(new_session)

    # ── Update TASKS.md status line ──────────────────────────────────────
    updated_tasks_content = update_task_status(
        tasks_content, active_task.id, "✅ Complete"
    )

    # ── Append row to TASKS-COMPLETED.md ─────────────────────────────────
    # append_task_row writes to shadow_path and returns the content.
    # It needs the live path to read existing content.
    phase_name_for_completed = ctx.session.active_phase_name

    # Build shadow paths
    shadow_dir = pc.shadow_dir.rstrip("/\\")
    session_shadow = str(Path(shadow_dir) / "SESSIONSTATE.md")
    tasks_shadow = str(Path(shadow_dir) / "TASKS.md")
    completed_shadow = str(Path(shadow_dir) / "TASKS-COMPLETED.md")

    append_task_row(
        path=Path(pc.tasks_completed_path),
        shadow_path=completed_shadow,
        phase_name=phase_name_for_completed,
        task_id=active_task.id,
        title=active_task.title,
        complexity=active_task.complexity.value
        if active_task.complexity
        else "unset",
        commit=commit_message or "advanced",
        notes="",
    )

    # ── Build PendingWrite objects ───────────────────────────────────────
    summary_lines_session = [
        f"Update SESSIONSTATE.md — mark {active_task.id} complete",
    ]
    if promoted_task is not None:
        summary_lines_session.append(
            f"Promote {promoted_task.id} as new active task"
        )
    elif not filtered_up_next:
        summary_lines_session.append(
            "All tasks in up_next processed — active_task set to [none]"
        )
    else:
        summary_lines_session.append(
            "No ready task in up_next — active_task set to [none]"
        )

    pending_writes = [
        PendingWrite(
            target_file="SESSIONSTATE.md",
            shadow_path=session_shadow,
            live_path=pc.sessionstate_path,
            backup_path=pc.backup_dir,
            summary_lines=summary_lines_session,
        ),
        PendingWrite(
            target_file="TASKS.md",
            shadow_path=tasks_shadow,
            live_path=pc.tasks_path,
            backup_path=pc.backup_dir,
            summary_lines=[
                f"Update TASKS.md — set {active_task.id} status to ✅ Complete",
            ],
        ),
        PendingWrite(
            target_file="TASKS-COMPLETED.md",
            shadow_path=completed_shadow,
            live_path=pc.tasks_completed_path,
            backup_path=pc.backup_dir,
            summary_lines=[
                f"Append {active_task.id} row to TASKS-COMPLETED.md",
            ],
        ),
    ]

    # Write staged content for session and tasks (completed_writer already wrote its own)
    _write_stage(session_content, session_shadow)
    _write_stage(updated_tasks_content, tasks_shadow)

    return pending_writes


def confirm_summary(pending_writes: list[PendingWrite]) -> str:
    """Return a human-readable summary of pending writes for display before
    confirmation.

    Matches the §7.3 confirm output format.
    """
    lines: list[str] = []
    lines.append("─" * 43)
    lines.append("  Pending changes — review before applying")
    lines.append("─" * 43)
    lines.append("")

    for pw in pending_writes:
        lines.append(f"  {pw.target_file}:")
        for sl in pw.summary_lines:
            lines.append(f"    {sl}")
        lines.append("")

    return "\n".join(lines)


# ── Internal helpers ────────────────────────────────────────────────────────


def _find_task_in_phases(phases: list, task_id: str) -> Task | None:
    """Find a ``Task`` by ID across all phases.

    Returns the first matching task, or ``None`` if not found.
    """
    for phase in phases:
        for task in phase.tasks:
            if task.id == task_id:
                return task
    return None


def _find_next_ready_task(
    up_next: list[Task],
    just_advanced_id: str,
    phases: list,
) -> Task | None:
    """Find the first task in *up_next* whose hard deps are all met.

    A hard dep is considered met if:
    - It has status ``COMPLETE`` in *phases*, OR
    - It equals *just_advanced_id* (the task being advanced this turn).

    Returns the first matching task, or ``None`` if no task is ready.
    """
    # Build a set of all complete task IDs from all phases
    complete_ids: set[str] = set()
    for phase in phases:
        for task in phase.tasks:
            if task.status == TaskStatus.COMPLETE:
                complete_ids.add(task.id)

    # The just-advanced task also counts as complete for dep resolution
    complete_ids.add(just_advanced_id)

    for candidate in up_next:
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
tsm advance — Advance the current active task and promote the next ready task.

Preconditions:
  - A project root must exist (TASKS.md and SESSIONSTATE.md must be present).
  - An active task must be set (via 'tsm init-phase' or previous advance).

Writes:
  1. SESSIONSTATE.md — marks the current active task as completed, promotes
     the next ready task from up_next (or sets active_task to [none] if no
     task's hard deps are met), removes the promoted task from up_next, and
     updates the Last updated timestamp.
  2. TASKS.md — changes the advanced task's **Status:** line to ✅ Complete.
  3. TASKS-COMPLETED.md — appends a new row for the completed task.

The "just-advanced task" counts as meeting hard deps for the purpose of
selecting the next task.  This means you can advance a task even if the
next task's hard deps include the task you are completing.

Example:
  tsm advance
  tsm advance "P4-T01: advance module complete"
  tsm advance --yes
"""
