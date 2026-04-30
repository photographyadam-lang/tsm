# tsm/commands/init_phase.py — Initialize a phase (Phase 4, P4-T02)
#
# Implements §7.2 phase initialisation logic.
#
# Public API:
#   init_phase(ctx: LoadedProject, phase_id: str) -> list[PendingWrite]
#   HELP_TEXT: str
#
# Constraints (§7.2):
#   - Match phase_id case-insensitively against Phase.id slugs
#   - Phase must exist and have at least one non-complete task
#   - Active task selection: first task in file order whose hard_deps
#     list is empty or all deps are complete in ctx.phases
#   - Build 1 PendingWrite for SESSIONSTATE.md only (no TASKS.md writes)
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


# ── Public API ──────────────────────────────────────────────────────────────


def init_phase(ctx: LoadedProject, phase_id: str) -> list[PendingWrite]:
    """Initialise a phase by setting its active task and populating up_next.

    Precondition checks per §7.2:
        - Phase exists (raises ``ValueError`` if not).
        - Phase has at least one non-complete task (raises ``ValueError``
          if all tasks are already complete).

    Active task selection (§7.2): the first task in file order whose
    ``hard_deps`` list is empty OR all deps are complete in
    ``ctx.phases``.  If no such task exists, ``active_task`` is set to
    ``None`` and the §7.2 warning is printed.

    Args:
        ctx: The loaded project state.
        phase_id: Case-insensitive ``Phase.id`` slug to initialise.

    Returns:
        A list containing one ``PendingWrite`` for SESSIONSTATE.md with
        the full reconstructed session state.

    Raises:
        ValueError: If the phase ID is not found or all tasks in the
            phase are already complete.
    """
    # ── Match phase_id case-insensitively ────────────────────────────────
    matched_phase = None
    for phase in ctx.phases:
        if phase.id.lower() == phase_id.lower():
            matched_phase = phase
            break

    if matched_phase is None:
        available = ", ".join(p.id for p in ctx.phases)
        raise ValueError(
            f"Phase '{phase_id}' not found. "
            f"Available phases: {available}"
        )

    # ── Precondition: at least one non-complete task ─────────────────────
    non_complete_tasks = [
        t for t in matched_phase.tasks if t.status != TaskStatus.COMPLETE
    ]
    if not non_complete_tasks:
        raise ValueError(
            f"All tasks in phase '{matched_phase.name}' are already "
            f"complete. Cannot initialise a completed phase."
        )

    pc = ctx.project_context

    # ── Active task selection (first task with deps met) ─────────────────
    selected_task = _select_first_ready_task(
        matched_phase.tasks, ctx.phases
    )

    if selected_task is not None:
        new_active_task = selected_task
        new_active_task_raw = selected_task.raw_block
    else:
        new_active_task = None
        new_active_task_raw = "[none]"
        print(
            "Warning: No task in this phase has all hard deps met. "
            "active_task set to [none]."
        )

    # ── up_next: all non-complete tasks in the phase (excluding selected) ─
    up_next_tasks = [
        t
        for t in matched_phase.tasks
        if t.status != TaskStatus.COMPLETE
        and (selected_task is None or t.id != selected_task.id)
    ]

    # ── Build new SessionState ───────────────────────────────────────────
    new_session = SessionState(
        last_updated=datetime.now(),
        active_phase_name=matched_phase.name,
        active_phase_spec=f"`{Path(pc.tasks_path).name}`",
        active_task=new_active_task,
        active_task_raw=new_active_task_raw,
        up_next=up_next_tasks,
        completed=[],  # §7.2: clear completed table on phase init
        out_of_scope_raw=ctx.session.out_of_scope_raw,
    )

    # ── Render and stage SESSIONSTATE.md ─────────────────────────────────
    session_content = render_sessionstate(new_session)
    shadow_dir = pc.shadow_dir.rstrip("/\\")
    session_shadow = str(Path(shadow_dir) / "SESSIONSTATE.md")

    _write_stage(session_content, session_shadow)

    # ── Build PendingWrite ───────────────────────────────────────────────
    summary_lines = [
        f"Initialise phase: {matched_phase.name}",
    ]
    if selected_task is not None:
        summary_lines.append(
            f"Set {selected_task.id} as active task"
        )
    else:
        summary_lines.append(
            "No ready task — active_task set to [none]"
        )

    return [
        PendingWrite(
            target_file="SESSIONSTATE.md",
            shadow_path=session_shadow,
            live_path=pc.sessionstate_path,
            backup_path=pc.backup_dir,
            summary_lines=summary_lines,
        ),
    ]


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
tsm init-phase — Initialise a phase and set its active task.

Preconditions:
  - A project root must exist (TASKS.md and SESSIONSTATE.md must be present).
  - The specified phase must exist and must have at least one task that is
    not already marked Complete.

Active task selection:
  The first task in file order whose hard_deps list is empty or whose all
  dependencies are already Complete is promoted as the active task.  If no
  task in the phase has all deps met, active_task is set to [none] and a
  warning is displayed.

Writes:
  1. SESSIONSTATE.md — sets the active phase name, active task (or [none]),
     populates up_next with all non-active pending tasks in the phase,
     clears the completed tasks table, and updates the Last updated timestamp.

Example:
  tsm init-phase phase-2-fixture-beta
  tsm init-phase "Phase 2 — Fixture Beta"
  tsm init-phase --yes phase-2-fixture-beta
"""
