# tsm/commands/task.py — Task CRUD commands (Phase 7, P7-T05)
#
# Implements §15.3 task CRUD operations.
#
# Public API:
#   task_add(ctx, phase_id, title, after_task_id=None, interactive=False) -> list[PendingWrite]
#   task_edit(ctx, task_id, field, value, interactive=False) -> list[PendingWrite]
#   task_move(ctx, task_id, phase_id, after_task_id=None) -> list[PendingWrite]
#   task_remove(ctx, task_id, force=False) -> list[PendingWrite]
#   HELP_TEXT: str
#
# Each function:
#   1. Applies the intended transformation to an in-memory copy of ctx.phases
#      to produce the proposed state.
#   2. Calls check_deps() on the proposed state.
#   3. Builds PendingWrite for TASKS.md using structural writer functions
#      from P7-T03a/T03b.
#
# Constraints (§15.3):
#   - task_edit uses update_task_status() for the status field and
#     update_task_field() for all other fields — never update_task_field() for status.
#   - Dep gate runs on the proposed state (post-edit in-memory model),
#     not the current live state.
#   - All functions return list[PendingWrite]; they do not call shadow.apply.

from datetime import datetime
from pathlib import Path
import re

from tsm.deps import check_deps, get_dependents
from tsm.models import (
    LoadedProject,
    PendingWrite,
    Phase,
    Task,
    TaskComplexity,
    TaskStatus,
)
from tsm.writers.session_writer import render_sessionstate, write_session_file
from tsm.writers.tasks_writer import (
    insert_task_block,
    remove_task_block,
    reorder_task_blocks,
    update_task_field,
    update_task_status,
    write_tasks_file,
)


# ── Public API ──────────────────────────────────────────────────────────────


def task_add(
    ctx: LoadedProject,
    phase_id: str,
    title: str,
    after_task_id: str | None = None,
    interactive: bool = False,
) -> list[PendingWrite]:
    """Add a new task to the specified phase.

    Auto-generates a task ID using the §14 algorithm: scans existing task
    IDs in the target phase to determine the prefix (the part before ``-T``),
    then appends ``-T<next-number>`` zero-padded to 2 digits.

    If *interactive* is ``True``, launches ``TaskFormOverlay`` (P7-T06) —
    currently raises ``NotImplementedError`` since P7-T06 is not yet built.

    The proposed state (including the new task) is validated via
    ``check_deps()`` before staging.

    Args:
        ctx: The loaded project state.
        phase_id: Phase ID slug to add the task to (matched case-insensitively).
        title: The task title (appears after the ``·`` separator in the heading).
        after_task_id: Insert after this existing task ID.  ``None`` inserts
            at the beginning of the task section.
        interactive: If ``True``, launch interactive form (not yet implemented).

    Returns:
        A list of ``PendingWrite`` objects (TASKS.md).

    Raises:
        ValueError: If *phase_id* is not found, or if dep check fails.
        NotImplementedError: If *interactive* is ``True`` (P7-T06 not built).
    """
    if interactive:
        raise NotImplementedError(
            "Interactive task_add (TaskFormOverlay) is not yet implemented. "
            "Use non-interactive mode with explicit field values."
        )

    pc = ctx.project_context

    # ── Find the phase (case-insensitive) ────────────────────────────────
    matched_phase = _find_phase_by_id(ctx.phases, phase_id)
    if matched_phase is None:
        available = ", ".join(p.id for p in ctx.phases)
        raise ValueError(
            f"Phase '{phase_id}' not found. Available phases: {available}"
        )

    # ── Auto-generate task ID ────────────────────────────────────────────
    task_id = _generate_task_id(matched_phase.tasks, matched_phase.name, phase_id)

    # ── Build proposed state (in-memory copy) ───────────────────────────
    new_task = Task(
        id=task_id,
        title=title,
        status=TaskStatus.PENDING,
        complexity=TaskComplexity.UNSET,
        what="Description for {0}.".format(title),
        prerequisite="None.",
        hard_deps=[],
        files=[],
        reviewer="Skip",
        key_constraints=[],
        done_when="- {0} is complete.".format(task_id),
        phase_id=matched_phase.id,
        subphase=None,
        raw_block="",
    )

    proposed_phases = _build_proposed_phases_with_added_task(
        ctx.phases, matched_phase.id, new_task, after_task_id
    )

    # ── Dep gate on proposed state ──────────────────────────────────────
    dep_errors = check_deps(proposed_phases)
    if dep_errors:
        raise ValueError(
            "Dep integrity check failed for proposed state:\n"
            + "\n".join(f"  - {e}" for e in dep_errors)
        )

    # ── Read current TASKS.md content ───────────────────────────────────
    tasks_path = Path(pc.tasks_path)
    content = tasks_path.read_text(encoding="utf-8")

    # ── Build task block string and insert ──────────────────────────────
    task_block = _build_task_block(
        task_id=task_id,
        title=title,
        status="Pending",
        complexity="unset",
        what=new_task.what,
        prerequisite="None.",
        hard_deps="",
        files="",
        reviewer="Skip",
        key_constraints="",
        done_when=new_task.done_when,
    )
    new_content = insert_task_block(content, task_block, matched_phase.id, after_task_id)

    # ── Stage TASKS.md ──────────────────────────────────────────────────
    shadow_dir = pc.shadow_dir.rstrip("/\\")
    tasks_shadow = str(Path(shadow_dir) / "TASKS.md")
    write_tasks_file(new_content, tasks_shadow)

    # ── Build PendingWrite ──────────────────────────────────────────────
    summary_lines = [
        f"Add task: {task_id} - {title}",
        f"  Phase: {matched_phase.name} (id: {matched_phase.id})",
    ]
    if after_task_id:
        summary_lines.append(f"  Insert after: {after_task_id}")
    else:
        summary_lines.append("  Insert at start of task section")

    return [
        PendingWrite(
            target_file="TASKS.md",
            shadow_path=tasks_shadow,
            live_path=pc.tasks_path,
            backup_path=pc.backup_dir,
            summary_lines=summary_lines,
        ),
    ]


def task_edit(
    ctx: LoadedProject,
    task_id: str,
    field: str,
    value: str,
    interactive: bool = False,
) -> list[PendingWrite]:
    """Edit a single field on an existing task.

    Uses ``update_task_status()`` for the ``"status"`` field and
    ``update_task_field()`` for all other fields.  When editing ``hard_deps``,
    the dep gate runs on the proposed in-memory state (after applying the
    edit) before staging.

    If *interactive* is ``True``, launches ``TaskFormOverlay`` (P7-T06) —
    currently raises ``NotImplementedError`` since P7-T06 is not yet built.

    Args:
        ctx: The loaded project state.
        task_id: The task ID to edit.
        field: The field name to edit (e.g. ``"status"``, ``"What"``,
            ``"hard_deps"``, ``"Complexity"``, etc.).  Case-insensitive
            matching.
        value: The new value for the field.
        interactive: If ``True``, launch interactive form (not yet implemented).

    Returns:
        A list of ``PendingWrite`` objects (TASKS.md).

    Raises:
        ValueError: If *task_id* is not found, or if dep check fails.
        NotImplementedError: If *interactive* is ``True`` (P7-T06 not built).
    """
    if interactive:
        raise NotImplementedError(
            "Interactive task_edit (TaskFormOverlay) is not yet implemented. "
            "Use non-interactive mode with explicit field values."
        )

    pc = ctx.project_context

    # ── Find the task in the current state ──────────────────────────────
    matched_task = _find_task_by_id(ctx.phases, task_id)
    if matched_task is None:
        all_ids = _collect_all_task_ids(ctx.phases)
        raise ValueError(
            f"Task '{task_id}' not found. Available task IDs: "
            f"{', '.join(sorted(all_ids))}"
        )

    # ── Normalise field name ────────────────────────────────────────────
    normalised_field = _normalise_field_name(field)

    # ── Special handling for hard_deps edit: run dep gate on proposed state ──
    if normalised_field == "hard_deps":
        _validate_hard_deps_edit(ctx, matched_task, normalised_field, value, task_id)

    # ── Read current TASKS.md content ───────────────────────────────────
    tasks_path = Path(pc.tasks_path)
    content = tasks_path.read_text(encoding="utf-8")

    # ── Apply the edit ──────────────────────────────────────────────────
    if normalised_field == "status":
        new_content = update_task_status(content, task_id, value)
    else:
        new_content = update_task_field(content, task_id, normalised_field, value)

    # ── Stage TASKS.md ──────────────────────────────────────────────────
    shadow_dir = pc.shadow_dir.rstrip("/\\")
    tasks_shadow = str(Path(shadow_dir) / "TASKS.md")
    write_tasks_file(new_content, tasks_shadow)

    # ── Build PendingWrite ──────────────────────────────────────────────
    summary_lines = [
        f"Edit task: {task_id}",
        f"  Field: {normalised_field}",
        f"  New value: {value}",
    ]

    return [
        PendingWrite(
            target_file="TASKS.md",
            shadow_path=tasks_shadow,
            live_path=pc.tasks_path,
            backup_path=pc.backup_dir,
            summary_lines=summary_lines,
        ),
    ]


def task_move(
    ctx: LoadedProject,
    task_id: str,
    target_phase_id: str,
    after_task_id: str | None = None,
) -> list[PendingWrite]:
    """Move a task to a different phase or reorder within its current phase.

    If the task is currently the active task or appears in up_next in
    SESSIONSTATE.md, the result includes a SESSIONSTATE.md ``PendingWrite``
    that updates ``active_task_raw`` and/or ``up_next`` accordingly.

    The proposed state (after moving the task) is validated via
    ``check_deps()`` before staging.

    Args:
        ctx: The loaded project state.
        task_id: The task ID to move.
        target_phase_id: The phase ID slug to move the task into.  If this
            is the same as the task's current phase, the task is reordered
            within that phase.
        after_task_id: Insert after this task ID in the target phase.
            ``None`` inserts at the beginning.

    Returns:
        A list of ``PendingWrite`` objects (TASKS.md and optionally
        SESSIONSTATE.md).

    Raises:
        ValueError: If *task_id* or *target_phase_id* is not found, or if
            dep check fails.
    """
    pc = ctx.project_context

    # ── Find the task and its current phase ─────────────────────────────
    matched_task = _find_task_by_id(ctx.phases, task_id)
    if matched_task is None:
        all_ids = _collect_all_task_ids(ctx.phases)
        raise ValueError(
            f"Task '{task_id}' not found. Available task IDs: "
            f"{', '.join(sorted(all_ids))}"
        )

    source_phase = _find_phase_by_task_id(ctx.phases, task_id)
    if source_phase is None:
        raise ValueError(
            f"Task '{task_id}' not found in any phase — this should not happen."
        )

    target_phase = _find_phase_by_id(ctx.phases, target_phase_id)
    if target_phase is None:
        available = ", ".join(p.id for p in ctx.phases)
        raise ValueError(
            f"Phase '{target_phase_id}' not found. Available phases: {available}"
        )

    within_same_phase = source_phase.id == target_phase.id
    proposed_phases = _build_proposed_phases_for_move(
        ctx.phases, task_id, target_phase.id, after_task_id, within_same_phase
    )

    # ── Dep gate on proposed state ──────────────────────────────────────
    dep_errors = check_deps(proposed_phases)
    if dep_errors:
        raise ValueError(
            "Dep integrity check failed for proposed state:\n"
            + "\n".join(f"  - {e}" for e in dep_errors)
        )

    # ── Read current TASKS.md content ───────────────────────────────────
    tasks_path = Path(pc.tasks_path)
    content = tasks_path.read_text(encoding="utf-8")

    # ── Apply the move ──────────────────────────────────────────────────
    if within_same_phase:
        # Reorder within the same phase: get current task order, move task_id
        current_task_ids = [t.id for t in source_phase.tasks]
        remaining = [tid for tid in current_task_ids if tid != task_id]
        if after_task_id is None:
            new_order = [task_id] + remaining
        else:
            insert_idx = remaining.index(after_task_id) + 1
            new_order = remaining[:insert_idx] + [task_id] + remaining[insert_idx:]
        new_content = reorder_task_blocks(content, source_phase.id, new_order)
    else:
        # Move between phases: remove from source, insert into target
        content = remove_task_block(content, task_id)

        task_block = _extract_task_block_from_raw(matched_task.raw_block)
        new_content = insert_task_block(
            content, task_block, target_phase.id, after_task_id
        )

    # ── Stage TASKS.md ──────────────────────────────────────────────────
    shadow_dir = pc.shadow_dir.rstrip("/\\")
    tasks_shadow = str(Path(shadow_dir) / "TASKS.md")
    write_tasks_file(new_content, tasks_shadow)

    # ── Build PendingWrites ─────────────────────────────────────────────
    pending_writes: list[PendingWrite] = []

    if within_same_phase:
        summary_lines = [
            f"Move task: {task_id} within phase {source_phase.name}",
        ]
    else:
        summary_lines = [
            f"Move task: {task_id}",
            f"  From: {source_phase.name}",
            f"  To: {target_phase.name}",
        ]

    if after_task_id:
        summary_lines.append(f"  After: {after_task_id}")
    else:
        summary_lines.append("  Position: start of task section")

    pending_writes.append(
        PendingWrite(
            target_file="TASKS.md",
            shadow_path=tasks_shadow,
            live_path=pc.tasks_path,
            backup_path=pc.backup_dir,
            summary_lines=summary_lines,
        ),
    )

    # ── If task is active or in up_next, update SESSIONSTATE.md ─────────
    session_pw = _build_session_update_for_move(ctx, task_id, target_phase_id)
    if session_pw is not None:
        pending_writes.append(session_pw)

    return pending_writes


def task_remove(
    ctx: LoadedProject,
    task_id: str,
    force: bool = False,
) -> list[PendingWrite]:
    """Remove a task from its phase.

    Validates via ``check_deps()`` on the proposed state (post-removal).
    Without ``--force``, raises ``ValueError`` if dependency errors are
    found.  With ``--force``, proceeds and lists dangling deps in the
    confirm summary.

    Args:
        ctx: The loaded project state.
        task_id: The task ID to remove.
        force: If ``True``, proceed despite dep errors (``--force`` flag).

    Returns:
        A list of ``PendingWrite`` objects (TASKS.md).

    Raises:
        ValueError: If *task_id* is not found, or if dep errors are present
            and *force* is ``False``.
    """
    pc = ctx.project_context

    # ── Find the task ───────────────────────────────────────────────────
    matched_task = _find_task_by_id(ctx.phases, task_id)
    if matched_task is None:
        all_ids = _collect_all_task_ids(ctx.phases)
        raise ValueError(
            f"Task '{task_id}' not found. Available task IDs: "
            f"{', '.join(sorted(all_ids))}"
        )

    matched_phase = _find_phase_by_task_id(ctx.phases, task_id)
    if matched_phase is None:
        raise ValueError(
            f"Task '{task_id}' not found in any phase — this should not happen."
        )

    # ── Build proposed state (post-removal) ─────────────────────────────
    proposed_phases = _build_proposed_phases_for_remove(ctx.phases, task_id)

    # ── Dep gate on proposed state ──────────────────────────────────────
    dep_errors = check_deps(proposed_phases)

    if dep_errors and not force:
        raise ValueError(
            "Cannot remove task: dependency errors detected.\n"
            + "\n".join(f"  - {e}" for e in dep_errors)
            + "\nUse --force to remove despite dangling dependencies."
        )

    # ── Read current TASKS.md content ───────────────────────────────────
    tasks_path = Path(pc.tasks_path)
    content = tasks_path.read_text(encoding="utf-8")

    # ── Remove the task block ──────────────────────────────────────────
    new_content = remove_task_block(content, task_id)

    # ── Stage TASKS.md ──────────────────────────────────────────────────
    shadow_dir = pc.shadow_dir.rstrip("/\\")
    tasks_shadow = str(Path(shadow_dir) / "TASKS.md")
    write_tasks_file(new_content, tasks_shadow)

    # ── Build PendingWrite ──────────────────────────────────────────────
    summary_lines = [
        f"Remove task: {task_id} ({matched_task.title})",
        f"  Phase: {matched_phase.name}",
    ]
    if dep_errors and force:
        summary_lines.append(
            "  ⚠ Force mode: proceeding despite dangling dependencies"
        )
        for err in dep_errors:
            summary_lines.append(f"    ↪ {err}")

    return [
        PendingWrite(
            target_file="TASKS.md",
            shadow_path=tasks_shadow,
            live_path=pc.tasks_path,
            backup_path=pc.backup_dir,
            summary_lines=summary_lines,
        ),
    ]


# ── Internal helpers — ID generation ───────────────────────────────────────


def _generate_task_id(
    existing_tasks: list[Task], phase_name: str, phase_id: str
) -> str:
    """Auto-generate a task ID using the §14 algorithm.

    Scans existing task IDs in the phase to determine the prefix pattern
    (the part before ``-T<num>``).  If tasks exist, extract the prefix from
    an existing task ID and find the next available number.

    If no tasks exist, derive the prefix from the phase name:
      - Take the last word (or two words) from the phase display name
      - Extract uppercase initials

    The number component is zero-padded to 2 digits.

    Args:
        existing_tasks: The list of existing tasks in the target phase.
        phase_name: The phase display name (e.g. ``"Phase 3 — New Phase"``).
        phase_id: The phase slug ID.

    Returns:
        A unique task ID string (e.g. ``"NP-T01"``, ``"P3-T01"``).
    """
    if existing_tasks:
        # Extract prefix from the first existing task ID
        first_id = existing_tasks[0].id
        prefix = _extract_id_prefix(first_id)
        max_num = _max_task_number(existing_tasks)
        next_num = max_num + 1
    else:
        # No existing tasks — derive prefix from phase name
        prefix = _derive_prefix_from_phase_name(phase_name, phase_id)
        next_num = 1

    return f"{prefix}-T{next_num:02d}"


def _extract_id_prefix(task_id: str) -> str:
    """Extract the prefix portion from a task ID like ``FA-T01`` → ``FA``.

    The prefix is everything before ``-T`` followed by digits.
    """
    match = re.match(r"^(.+)-T\d+$", task_id)
    if match:
        return match.group(1)
    # Fallback: return everything before the last hyphen
    if "-" in task_id:
        return task_id.rsplit("-", 1)[0]
    return task_id


def _max_task_number(tasks: list[Task]) -> int:
    """Find the maximum numeric suffix among task IDs in the list.

    Looks for the ``-T<number>`` pattern and returns the highest number found.
    Returns 0 if no tasks have a numeric suffix.
    """
    max_num = 0
    for t in tasks:
        match = re.search(r"-T(\d+)$", t.id)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    return max_num


def _derive_prefix_from_phase_name(phase_name: str, phase_id: str) -> str:
    """Derive a task ID prefix from the phase name.

    Tries to extract initials from the phase name (e.g. "Phase 3 — New Phase"
    → initials of words after the dash → "NP").  Falls back to the phase_id
    slug uppercased if no suitable pattern is found.

    For production-style names like "Phase 3 — Foundation", extracts
    uppercase letters from the descriptive part → "F".  For two-word
    descriptive parts like "New Phase", takes both initials → "NP".
    """
    # Try to get meaningful initials from the description after "—"
    if "—" in phase_name:
        desc = phase_name.split("—", 1)[1].strip()
    else:
        desc = phase_name

    # Remove leading "Phase N" if present
    desc = re.sub(r"^Phase\s+\d+\s*", "", desc).strip()

    if not desc:
        # Fallback to phase_id uppercased initials
        parts = phase_id.replace("-", " ")
        initials = "".join(word[0].upper() for word in parts.split() if word)
        return initials if initials else phase_id.upper()

    # Take first letter of each word in the descriptive part
    words = [w for w in desc.split() if w]
    initials = "".join(w[0].upper() for w in words if w[0].isalpha())

    if not initials:
        # Fallback to phase_id uppercased
        initials = phase_id.upper()

    return initials


# ── Internal helpers — proposed state builders ────────────────────────────


def _build_proposed_phases_with_added_task(
    phases: list[Phase],
    phase_id: str,
    new_task: Task,
    after_task_id: str | None,
) -> list[Phase]:
    """Build a deep-ish copy of *phases* with *new_task* inserted.

    Returns the proposed state for dep-check purposes.  Only the task
    list is modified; other Phase fields are copied by reference (safe
    because we never mutate them).
    """
    proposed: list[Phase] = []
    for p in phases:
        if p.id == phase_id:
            new_tasks = list(p.tasks)
            if after_task_id is None:
                new_tasks.insert(0, new_task)
            else:
                insert_idx = -1
                for i, t in enumerate(new_tasks):
                    if t.id == after_task_id:
                        insert_idx = i + 1
                        break
                if insert_idx == -1:
                    raise ValueError(
                        f"Task '{after_task_id}' not found in phase '{phase_id}'"
                    )
                new_tasks.insert(insert_idx, new_task)
            proposed.append(
                Phase(
                    id=p.id,
                    name=p.name,
                    status=p.status,
                    description=p.description,
                    tasks=new_tasks,
                    dependency_graph_raw=p.dependency_graph_raw,
                )
            )
        else:
            proposed.append(p)
    return proposed


def _build_proposed_phases_for_move(
    phases: list[Phase],
    task_id: str,
    target_phase_id: str,
    after_task_id: str | None,
    within_same_phase: bool,
) -> list[Phase]:
    """Build the proposed state after moving *task_id* to *target_phase_id*.

    Returns the proposed state for dep-check purposes.
    """
    # Find the task to move
    task_to_move = _find_task_by_id(phases, task_id)
    if task_to_move is None:
        raise ValueError(f"Task '{task_id}' not found")

    proposed: list[Phase] = []
    for p in phases:
        if p.id == target_phase_id and within_same_phase:
            # Reorder within phase
            current_ids = [t.id for t in p.tasks]
            remaining = [tid for tid in current_ids if tid != task_id]
            if after_task_id is None:
                new_order_ids = [task_id] + remaining
            else:
                insert_idx = remaining.index(after_task_id) + 1
                new_order_ids = (
                    remaining[:insert_idx] + [task_id] + remaining[insert_idx:]
                )
            id_to_task = {t.id: t for t in p.tasks}
            new_tasks = [id_to_task[tid] for tid in new_order_ids]
            proposed.append(
                Phase(
                    id=p.id,
                    name=p.name,
                    status=p.status,
                    description=p.description,
                    tasks=new_tasks,
                    dependency_graph_raw=p.dependency_graph_raw,
                )
            )
        elif p.id == target_phase_id and not within_same_phase:
            # Insert into target phase
            new_tasks = list(p.tasks)
            if after_task_id is None:
                new_tasks.insert(0, task_to_move)
            else:
                insert_idx = -1
                for i, t in enumerate(new_tasks):
                    if t.id == after_task_id:
                        insert_idx = i + 1
                        break
                if insert_idx == -1:
                    raise ValueError(
                        f"Task '{after_task_id}' not found in phase '{p.id}'"
                    )
                new_tasks.insert(insert_idx, task_to_move)
            proposed.append(
                Phase(
                    id=p.id,
                    name=p.name,
                    status=p.status,
                    description=p.description,
                    tasks=new_tasks,
                    dependency_graph_raw=p.dependency_graph_raw,
                )
            )
        else:
            # Remove from source phase if moving between phases
            if not within_same_phase and _phase_has_task(p, task_id):
                new_tasks = [t for t in p.tasks if t.id != task_id]
                proposed.append(
                    Phase(
                        id=p.id,
                        name=p.name,
                        status=p.status,
                        description=p.description,
                        tasks=new_tasks,
                        dependency_graph_raw=p.dependency_graph_raw,
                    )
                )
            else:
                proposed.append(p)

    return proposed


def _build_proposed_phases_for_remove(
    phases: list[Phase], task_id: str
) -> list[Phase]:
    """Build the proposed state after removing *task_id* from its phase.

    Returns the proposed state for dep-check purposes.
    """
    proposed: list[Phase] = []
    for p in phases:
        if _phase_has_task(p, task_id):
            new_tasks = [t for t in p.tasks if t.id != task_id]
            proposed.append(
                Phase(
                    id=p.id,
                    name=p.name,
                    status=p.status,
                    description=p.description,
                    tasks=new_tasks,
                    dependency_graph_raw=p.dependency_graph_raw,
                )
            )
        else:
            proposed.append(p)
    return proposed


# ── Internal helpers — validation ─────────────────────────────────────────


def _validate_hard_deps_edit(
    ctx: LoadedProject,
    matched_task: Task,
    normalised_field: str,
    value: str,
    task_id: str,
) -> None:
    """Validate hard_deps edit by running dep gate on proposed state.

    Parses the new *value* string into a list of dep IDs and builds a
    proposed in-memory state with the updated hard_deps, then runs
    ``check_deps()``.  Raises ``ValueError`` if dep issues are found.
    """
    # Parse hard_deps from the value string
    value_stripped = value.strip()
    if not value_stripped or value_stripped.lower() in (
        "none",
        "none.",
        "\u2014",
        "",
    ):
        new_hard_deps: list[str] = []
    else:
        new_hard_deps = [d.strip() for d in value_stripped.split(",") if d.strip()]

    # Build proposed state with updated hard_deps
    proposed_phases: list[Phase] = []
    for p in ctx.phases:
        new_tasks = []
        for t in p.tasks:
            if t.id == task_id:
                new_tasks.append(
                    Task(
                        id=t.id,
                        title=t.title,
                        status=t.status,
                        complexity=t.complexity,
                        what=t.what,
                        prerequisite=t.prerequisite,
                        hard_deps=new_hard_deps,
                        files=t.files,
                        reviewer=t.reviewer,
                        key_constraints=t.key_constraints,
                        done_when=t.done_when,
                        phase_id=t.phase_id,
                        subphase=t.subphase,
                        raw_block=t.raw_block,
                    )
                )
            else:
                new_tasks.append(t)
        proposed_phases.append(
            Phase(
                id=p.id,
                name=p.name,
                status=p.status,
                description=p.description,
                tasks=new_tasks,
                dependency_graph_raw=p.dependency_graph_raw,
            )
        )

    dep_errors = check_deps(proposed_phases)
    if dep_errors:
        raise ValueError(
            "Dep integrity check failed for proposed state after hard_deps edit:\n"
            + "\n".join(f"  - {e}" for e in dep_errors)
        )


# ── Internal helpers — SESSIONSTATE.md updates for task_move ──────────────


def _build_session_update_for_move(
    ctx: LoadedProject,
    task_id: str,
    target_phase_id: str,
) -> PendingWrite | None:
    """Build a SESSIONSTATE.md PendingWrite if *task_id* is the active task
    or appears in up_next.

    Returns ``None`` if no session update is needed.
    """
    pc = ctx.project_context
    needs_session_update = False

    new_active_task_raw = ctx.session.active_task_raw
    new_up_next = list(ctx.session.up_next)
    new_active_task = ctx.session.active_task

    # ── Check if task_id is the active task ─────────────────────────────
    if ctx.session.active_task is not None and ctx.session.active_task.id == task_id:
        needs_session_update = True
        # The active task raw_block should be updated to reflect the new
        # phase context.  We find the task in the new proposed state
        # (via ctx.phases since we haven't staged yet) and use its raw_block.
        moved_task = _find_task_by_id(ctx.phases, task_id)
        if moved_task is not None:
            new_active_task_raw = moved_task.raw_block
            new_active_task = moved_task

    # ── Check if task_id is in up_next ──────────────────────────────────
    if any(t.id == task_id for t in ctx.session.up_next):
        needs_session_update = True
        new_up_next = [t for t in ctx.session.up_next if t.id != task_id]

    if not needs_session_update:
        return None

    # ── Build updated SessionState ──────────────────────────────────────
    from tsm.models import SessionState

    new_session = SessionState(
        last_updated=datetime.now(),
        active_phase_name=ctx.session.active_phase_name,
        active_phase_spec=ctx.session.active_phase_spec,
        active_task=new_active_task,
        active_task_raw=new_active_task_raw,
        up_next=new_up_next,
        completed=ctx.session.completed,
        out_of_scope_raw=ctx.session.out_of_scope_raw,
    )

    session_content = render_sessionstate(new_session)

    shadow_dir = pc.shadow_dir.rstrip("/\\")
    session_shadow = str(Path(shadow_dir) / "SESSIONSTATE.md")
    write_session_file(session_content, session_shadow)

    summary_lines = [
        f"Update SESSIONSTATE.md for task move of {task_id}",
    ]
    if ctx.session.active_task is not None and ctx.session.active_task.id == task_id:
        summary_lines.append("  Active task moved — raw_block updated")
    if any(t.id == task_id for t in ctx.session.up_next):
        summary_lines.append("  Task removed from up_next")

    return PendingWrite(
        target_file="SESSIONSTATE.md",
        shadow_path=session_shadow,
        live_path=pc.sessionstate_path,
        backup_path=pc.backup_dir,
        summary_lines=summary_lines,
    )


# ── Internal helpers — block building ────────────────────────────────────


def _build_task_block(
    task_id: str,
    title: str,
    status: str,
    complexity: str,
    what: str,
    prerequisite: str,
    hard_deps: str,
    files: str,
    reviewer: str,
    key_constraints: str,
    done_when: str,
) -> str:
    """Build a complete task block string for insertion into TASKS.md.

    Returns a string that can be passed to ``insert_task_block()``.
    """
    lines: list[str] = []
    lines.append(f"### {task_id} · {title}")
    lines.append("")
    lines.append(f"**Status:** {status}")
    lines.append(f"**Complexity:** {complexity}")
    lines.append(f"**What:** {what}")
    lines.append(f"**Prerequisite:** {prerequisite}")

    if hard_deps.strip():
        lines.append(f"**Hard deps:** {hard_deps}")
    else:
        lines.append("**Hard deps:** None")

    if files.strip():
        lines.append(f"**Files:** {files}")
    else:
        lines.append("**Files:**")

    lines.append(f"**Reviewer:** {reviewer}")

    if key_constraints.strip():
        lines.append("**Key constraints:**")
        for constraint in key_constraints.split("\n"):
            stripped = constraint.strip()
            if stripped:
                if stripped.startswith("- "):
                    lines.append(stripped)
                else:
                    lines.append(f"- {stripped}")

    lines.append(f"**Done when:**")
    for dw_line in done_when.split("\n"):
        stripped = dw_line.strip()
        if stripped:
            lines.append(stripped)

    lines.append("")
    return "\n".join(lines)


def _extract_task_block_from_raw(raw_block: str) -> str:
    """Extract the raw task block content from a ``Task.raw_block``.

    If the raw block already has a trailing newline, it is preserved.
    This produces a string suitable for ``insert_task_block()``.
    """
    # The raw block from TASKS.md parser already contains the full
    # ### heading and all field lines.  Ensure it ends with a newline
    # so it works with insert_task_block's splitting logic.
    if raw_block and not raw_block.endswith("\n"):
        raw_block += "\n"
    return raw_block


# ── Internal helpers — lookup ────────────────────────────────────────────


def _find_phase_by_id(phases: list[Phase], phase_id: str) -> Phase | None:
    """Find a phase by ID (case-insensitive)."""
    for p in phases:
        if p.id.lower() == phase_id.lower():
            return p
    return None


def _find_phase_by_task_id(phases: list[Phase], task_id: str) -> Phase | None:
    """Find the phase that contains the task with *task_id*."""
    for p in phases:
        for t in p.tasks:
            if t.id == task_id:
                return p
    return None


def _find_task_by_id(phases: list[Phase], task_id: str) -> Task | None:
    """Find a task by ID across all phases."""
    for p in phases:
        for t in p.tasks:
            if t.id == task_id:
                return t
    return None


def _collect_all_task_ids(phases: list[Phase]) -> set[str]:
    """Collect all task IDs from all phases."""
    ids: set[str] = set()
    for p in phases:
        for t in p.tasks:
            ids.add(t.id)
    return ids


def _phase_has_task(phase: Phase, task_id: str) -> bool:
    """Return ``True`` if *phase* contains a task with *task_id*."""
    return any(t.id == task_id for t in phase.tasks)


def _normalise_field_name(field: str) -> str:
    """Normalise a user-provided field name to the canonical form.

    Maps various input forms to the field names expected by
    ``update_task_status()`` and ``update_task_field()``.

    Examples:
      "Status" / "status" / "STATUS" → "status" (special cased)
      "What" / "what" → "What"
      "Hard deps" / "hard_deps" / "hard-deps" → "hard_deps"
    """
    lower = field.lower().replace(" ", "_").replace("-", "_")

    # Map known variants
    if lower == "status":
        return "status"
    if lower in ("what",):
        return "What"
    if lower in ("done_when", "donewhen"):
        return "Done when"
    if lower in ("key_constraints", "keyconstraints", "key constraints"):
        return "Key constraints"
    if lower in ("hard_deps", "harddeps", "hard deps"):
        return "hard_deps"
    if lower in ("complexity",):
        return "Complexity"
    if lower in ("prerequisite", "prereq"):
        return "Prerequisite"
    if lower in ("files",):
        return "Files"
    if lower in ("reviewer",):
        return "Reviewer"
    if lower in ("title",):
        return "title"

    # Capitalise first letter as a default
    return field[0].upper() + field[1:] if field else field


# ── HELP_TEXT ──────────────────────────────────────────────────────────────

HELP_TEXT = """\
tsm task — Task CRUD commands (add, edit, move, remove).

Subcommands:
  tsm task add <phase-id> <title> [--after <task-id>]
    Add a new task to a phase.  A task ID is auto-generated.  If --after is
    omitted, the task is inserted at the beginning of the task section (before
    the Dependency graph block).

  tsm task edit <task-id> --field <name> --value <value>
    Edit a single field on a task.  Use update_task_status() for the status
    field and update_task_field() for all other fields.  --field accepts:
    status, What, Done when, Key constraints, hard_deps, Complexity,
    Prerequisite, Files, Reviewer.

  tsm task move <task-id> --phase <phase-id> [--after <task-id>]
    Move a task to a different phase or reorder within the same phase.  If
    --phase is omitted or equals the current phase, the task is reordered
    within its current phase.

  tsm task remove <task-id> [--force]
    Remove a task from its phase.  Without --force, removal is blocked if any
    other tasks depend on this task.  With --force, removal proceeds and
    dangling dependencies are listed in the summary.

Preconditions:
  - A project root must exist (TASKS.md and SESSIONSTATE.md must be present).
  - The specified phase ID must exist (for add, move).
  - The specified task ID must exist (for edit, move, remove).
  - For remove without --force: no dangling deps from other tasks.
  - For hard_deps edit: dep gate validates proposed state for cycles, dangling
    refs, and self-references before staging.

Writes:
  1. TASKS.md — updated task block (add, edit, move, remove).
  2. SESSIONSTATE.md — updated if the moved task is active or in up_next (move only).

Example:
  tsm task add phase-7-foo "Implement widget"
  tsm task add phase-7-foo "Add tests" --after P7-T05
  tsm task edit P7-T10 --field What --value "New description"
  tsm task edit P7-T10 --field status --value "Active"
  tsm task edit P7-T10 --field hard_deps --value "P7-T01, P7-T02"
  tsm task move P7-T10 --phase phase-7-foo --after P7-T09
  tsm task remove P7-T10
  tsm task remove P7-T10 --force
"""
