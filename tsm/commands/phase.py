# tsm/commands/phase.py — Phase CRUD commands (Phase 7, P7-T04)
#
# Implements §15.2 phase CRUD operations.
#
# Public API:
#   phase_add(ctx, name, after_phase_id=None, status="Pending") -> list[PendingWrite]
#   phase_edit(ctx, phase_id, name=None, status=None) -> list[PendingWrite]
#   phase_move(ctx, phase_id, after_phase_id) -> list[PendingWrite]
#   phase_remove(ctx, phase_id, force=False) -> list[PendingWrite]
#   HELP_TEXT: str
#
# Each function:
#   1. Applies the intended transformation to an in-memory copy of ctx.phases
#      to produce the proposed state.
#   2. Calls check_deps() on the proposed state.
#   3. For remove without --force: aborts if check_deps returns errors.
#   4. Builds PendingWrite for TASKS.md using structural writer functions
#      from P7-T03a/T03b.
#
# Constraints (§15.2):
#   - phase_move calls reorder_phase_blocks.
#   - phase_remove with --force proceeds despite dep errors and lists
#     dangling deps in confirm summary.
#   - All functions return list[PendingWrite]; they do not call shadow.apply.

from pathlib import Path

from tsm.deps import check_deps
from tsm.models import (
    LoadedProject,
    PendingWrite,
    Phase,
    PhaseOverviewRow,
    slugify_phase_name,
)
from tsm.writers.tasks_writer import (
    insert_phase_block,
    remove_phase_block,
    reorder_phase_blocks,
    update_phase_structure_table,
    write_tasks_file,
)


# ── Public API ──────────────────────────────────────────────────────────────


def phase_add(
    ctx: LoadedProject,
    name: str,
    after_phase_id: str | None = None,
    status: str = "Pending",
) -> list[PendingWrite]:
    """Add a new phase.

    Creates a new H1 phase block and adds a corresponding row to the
    Phase structure table.  The proposed state (including the new phase)
    is validated via ``check_deps()`` before staging.

    Args:
        ctx: The loaded project state.
        name: The display name for the new phase (e.g. ``"Phase 7 — Foo"``).
        after_phase_id: ``Phase.id`` slug of the phase after which to
            insert.  ``None`` appends at end.
        status: Initial phase status (default ``"Pending"``).

    Returns:
        A list of ``PendingWrite`` objects (TASKS.md for the new block
        and the updated structure table).

    Raises:
        ValueError: If ``after_phase_id`` is not found.
    """
    pc = ctx.project_context

    # ── Generate a unique phase ID ──────────────────────────────────────
    existing_slugs = [p.id for p in ctx.phases]
    phase_id = slugify_phase_name(name, existing_slugs)

    # ── Build proposed state (in-memory copy) ───────────────────────────
    new_phase = Phase(
        id=phase_id,
        name=name,
        status=status,
        description="",
        tasks=[],
        dependency_graph_raw="",
    )

    proposed_phases = list(ctx.phases)
    if after_phase_id is None:
        proposed_phases.append(new_phase)
    else:
        insert_idx = -1
        for i, p in enumerate(proposed_phases):
            if p.id == after_phase_id:
                insert_idx = i + 1
                break
        if insert_idx == -1:
            raise ValueError(
                f"Phase '{after_phase_id}' not found. "
                f"Available phases: {', '.join(existing_slugs)}"
            )
        proposed_phases.insert(insert_idx, new_phase)

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

    # ── Build phase block string and insert ─────────────────────────────
    phase_block = _build_phase_block(name, status)
    new_content = insert_phase_block(content, phase_block, after_phase_id)

    # ── Build new overview and update Phase structure table ─────────────
    new_row = PhaseOverviewRow(
        phase_name=name,
        description="",
        status=status,
    )
    new_overview = list(ctx.phase_overview)
    if after_phase_id is None:
        new_overview.append(new_row)
    else:
        # Find position in overview matching the after_phase_id phase name
        after_name = _find_phase_name_by_id(ctx.phases, after_phase_id)
        after_idx = -1
        for i, row in enumerate(new_overview):
            if row.phase_name == after_name:
                after_idx = i
                break
        if after_idx != -1:
            new_overview.insert(after_idx + 1, new_row)
        else:
            new_overview.append(new_row)

    new_content = update_phase_structure_table(new_content, new_overview)

    # ── Stage TASKS.md ─────────────────────────────────────────────────
    shadow_dir = pc.shadow_dir.rstrip("/\\")
    tasks_shadow = str(Path(shadow_dir) / "TASKS.md")
    write_tasks_file(new_content, tasks_shadow)

    # ── Build PendingWrite ──────────────────────────────────────────────
    summary_lines = [
        f"Add phase: {name} (id: {phase_id})",
    ]
    if after_phase_id:
        summary_lines.append(f"Insert after: {after_phase_id}")
    else:
        summary_lines.append("Append at end of file")
    summary_lines.append("Update Phase structure table with new row")

    return [
        PendingWrite(
            target_file="TASKS.md",
            shadow_path=tasks_shadow,
            live_path=pc.tasks_path,
            backup_path=pc.backup_dir,
            summary_lines=summary_lines,
        ),
    ]


def phase_edit(
    ctx: LoadedProject,
    phase_id: str,
    name: str | None = None,
    status: str | None = None,
) -> list[PendingWrite]:
    """Edit a phase's name and/or status.

    Updates the H1 heading text (if *name* is provided) and/or the
    ``**Status:**`` line in the phase header, plus the corresponding
    row in the Phase structure table.

    Args:
        ctx: The loaded project state.
        phase_id: Phase ID slug to edit (matched case-insensitively).
        name: New display name (``None`` = no change).
        status: New status string (``None`` = no change).

    Returns:
        A list of ``PendingWrite`` objects (TASKS.md).

    Raises:
        ValueError: If ``phase_id`` is not found, or if neither *name*
            nor *status* is provided.
    """
    if name is None and status is None:
        raise ValueError(
            "At least one of 'name' or 'status' must be provided."
        )

    pc = ctx.project_context

    # ── Find the phase (case-insensitive) ────────────────────────────────
    matched_phase = None
    for p in ctx.phases:
        if p.id.lower() == phase_id.lower():
            matched_phase = p
            break
    if matched_phase is None:
        available = ", ".join(p.id for p in ctx.phases)
        raise ValueError(
            f"Phase '{phase_id}' not found. Available phases: {available}"
        )

    # ── Build proposed state and run dep gate ───────────────────────────
    dep_errors = check_deps(ctx.phases)
    if dep_errors:
        raise ValueError(
            "Dep integrity check failed:\n"
            + "\n".join(f"  - {e}" for e in dep_errors)
        )

    # ── Read current TASKS.md content ───────────────────────────────────
    tasks_path = Path(pc.tasks_path)
    content = tasks_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    # ── Update heading text if name changed ─────────────────────────────
    new_phase_name = matched_phase.name
    if name is not None:
        new_phase_name = name
        lines = _replace_phase_heading(lines, matched_phase.id, name)

    # ── Update status line in phase header if status changed ────────────
    if status is not None:
        lines = _replace_phase_status_line(lines, matched_phase.id, status)

    content = "".join(lines)

    # ── Update Phase structure table ────────────────────────────────────
    new_overview = list(ctx.phase_overview)
    for i, row in enumerate(new_overview):
        if row.phase_name == matched_phase.name:
            new_overview[i] = PhaseOverviewRow(
                phase_name=new_phase_name if name else row.phase_name,
                description=row.description,
                status=status if status else row.status,
            )
            break

    content = update_phase_structure_table(content, new_overview)

    # ── Stage TASKS.md ─────────────────────────────────────────────────
    shadow_dir = pc.shadow_dir.rstrip("/\\")
    tasks_shadow = str(Path(shadow_dir) / "TASKS.md")
    write_tasks_file(content, tasks_shadow)

    # ── Build PendingWrite ──────────────────────────────────────────────
    summary_lines = [f"Edit phase: {matched_phase.id}"]
    if name is not None:
        summary_lines.append(
            f"  Rename: '{matched_phase.name}' → '{name}'"
        )
    if status is not None:
        summary_lines.append(
            f"  Status: {matched_phase.status} → {status}"
        )
    summary_lines.append("  Update Phase structure table row")

    return [
        PendingWrite(
            target_file="TASKS.md",
            shadow_path=tasks_shadow,
            live_path=pc.tasks_path,
            backup_path=pc.backup_dir,
            summary_lines=summary_lines,
        ),
    ]


def phase_move(
    ctx: LoadedProject,
    phase_id: str,
    after_phase_id: str,
) -> list[PendingWrite]:
    """Move a phase to a new position.

    Reorders H1 blocks and updates the Phase structure table.

    Args:
        ctx: The loaded project state.
        phase_id: Phase ID slug to move.
        after_phase_id: Phase ID slug after which to place the moved
            phase.

    Returns:
        A list of ``PendingWrite`` objects (TASKS.md).

    Raises:
        ValueError: If either phase ID is not found.
    """
    pc = ctx.project_context

    # ── Validate both IDs exist ──────────────────────────────────────────
    existing_ids = [p.id for p in ctx.phases]
    if phase_id not in existing_ids:
        raise ValueError(
            f"Phase '{phase_id}' not found. Available phases: "
            f"{', '.join(existing_ids)}"
        )
    if after_phase_id not in existing_ids:
        raise ValueError(
            f"Phase '{after_phase_id}' not found. Available phases: "
            f"{', '.join(existing_ids)}"
        )

    # ── Build proposed state (in-memory) ────────────────────────────────
    proposed_phases = [p for p in ctx.phases if p.id != phase_id]
    after_idx = -1
    for i, p in enumerate(proposed_phases):
        if p.id == after_phase_id:
            after_idx = i
            break
    phase_to_move = next(p for p in ctx.phases if p.id == phase_id)
    proposed_phases.insert(after_idx + 1, phase_to_move)

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

    # ── Reorder H1 blocks ──────────────────────────────────────────────
    ordered_ids = [p.id for p in proposed_phases]
    content = reorder_phase_blocks(content, ordered_ids)

    # ── Update Phase structure table ────────────────────────────────────
    name_map = {p.id: p.name for p in ctx.phases}
    desc_map = {row.phase_name: row.description for row in ctx.phase_overview}
    status_map = {row.phase_name: row.status for row in ctx.phase_overview}
    new_overview = []
    for p in proposed_phases:
        pname = p.name
        new_overview.append(
            PhaseOverviewRow(
                phase_name=pname,
                description=desc_map.get(pname, ""),
                status=status_map.get(pname, p.status),
            )
        )

    content = update_phase_structure_table(content, new_overview)

    # ── Stage TASKS.md ─────────────────────────────────────────────────
    shadow_dir = pc.shadow_dir.rstrip("/\\")
    tasks_shadow = str(Path(shadow_dir) / "TASKS.md")
    write_tasks_file(content, tasks_shadow)

    # ── Build PendingWrite ──────────────────────────────────────────────
    summary_lines = [
        f"Move phase: {phase_id}",
        f"  New position: after {after_phase_id}",
        "  Update Phase structure table",
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


def phase_remove(
    ctx: LoadedProject,
    phase_id: str,
    force: bool = False,
) -> list[PendingWrite]:
    """Remove a phase and all its tasks.

    Validates via ``check_deps()`` on the proposed state (post-removal).
    Without ``--force``, raises ``ValueError`` if dependency errors are
    found.  With ``--force``, proceeds and lists dangling deps in the
    confirm summary.

    Args:
        ctx: The loaded project state.
        phase_id: Phase ID slug to remove.
        force: If ``True``, proceed despite dep errors (``--force`` flag).

    Returns:
        A list of ``PendingWrite`` objects (TASKS.md).

    Raises:
        ValueError: If ``phase_id`` is not found, or if dep errors are
            present and ``force`` is ``False``.
    """
    pc = ctx.project_context

    # ── Find the phase ───────────────────────────────────────────────────
    matched_phase = None
    for p in ctx.phases:
        if p.id == phase_id:
            matched_phase = p
            break
    if matched_phase is None:
        available = ", ".join(p.id for p in ctx.phases)
        raise ValueError(
            f"Phase '{phase_id}' not found. Available phases: {available}"
        )

    phase_task_ids = [t.id for t in matched_phase.tasks]

    # ── Build proposed state (post-removal) ─────────────────────────────
    proposed_phases = [p for p in ctx.phases if p.id != phase_id]

    # ── Dep gate on proposed state ──────────────────────────────────────
    dep_errors = check_deps(proposed_phases)

    if dep_errors and not force:
        raise ValueError(
            "Cannot remove phase: dependency errors detected.\n"
            + "\n".join(f"  - {e}" for e in dep_errors)
            + "\nUse --force to remove despite dangling dependencies."
        )

    # ── Read current TASKS.md content ───────────────────────────────────
    tasks_path = Path(pc.tasks_path)
    content = tasks_path.read_text(encoding="utf-8")

    # ── Remove the phase block ──────────────────────────────────────────
    content = remove_phase_block(content, phase_id)

    # ── Update Phase structure table ────────────────────────────────────
    new_overview = [
        row
        for row in ctx.phase_overview
        if row.phase_name != matched_phase.name
    ]
    content = update_phase_structure_table(content, new_overview)

    # ── Stage TASKS.md ─────────────────────────────────────────────────
    shadow_dir = pc.shadow_dir.rstrip("/\\")
    tasks_shadow = str(Path(shadow_dir) / "TASKS.md")
    write_tasks_file(content, tasks_shadow)

    # ── Build PendingWrite ──────────────────────────────────────────────
    summary_lines = [
        f"Remove phase: {phase_id} ({matched_phase.name})",
        f"  Tasks removed: {len(phase_task_ids)}",
    ]
    if phase_task_ids:
        summary_lines.append(
            f"  Task IDs: {', '.join(phase_task_ids)}"
        )
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


# ── Internal helpers ────────────────────────────────────────────────────────


def _build_phase_block(name: str, status: str) -> str:
    """Build a minimal phase block string for a new phase.

    Includes the H1 heading, status line, description placeholder,
    a ``## <Phase> tasks`` subheading, and trailing ``---``.
    """
    return (
        f"# {name}\n"
        f"\n"
        f"**Status:** {status}\n"
        f"\n"
        f"Description for {name}.\n"
        f"\n"
        f"---\n"
        f"\n"
        f"## {name} tasks\n"
        f"\n"
        f"---\n"
    )


def _replace_phase_heading(
    lines: list[str], phase_id: str, new_name: str
) -> list[str]:
    """Replace the H1 heading for the phase identified by *phase_id*."""
    seen_slugs: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n\r")
        if stripped.startswith("# ") and not stripped.startswith("## "):
            heading_text = stripped[2:].strip()
            # Skip the document title — first H1 in the file is always
            # the document title, not a phase heading.
            slug = slugify_phase_name(heading_text, seen_slugs)
            seen_slugs.append(slug)
            if slug == phase_id:
                ending = line[len(line.rstrip("\n\r")):]
                lines[i] = f"# {new_name}{ending}"
                return lines

    raise ValueError(f"Phase '{phase_id}' not found in content")


def _replace_phase_status_line(
    lines: list[str], phase_id: str, new_status: str
) -> list[str]:
    """Replace the ``**Status:**`` line in the phase header."""
    seen_slugs: list[str] = []
    in_block = False
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n\r")
        if not in_block:
            if stripped.startswith("# ") and not stripped.startswith("## "):
                heading_text = stripped[2:].strip()
                slug = slugify_phase_name(heading_text, seen_slugs)
                seen_slugs.append(slug)
                if slug == phase_id:
                    in_block = True
            continue

        # Inside the phase header block — stop at --- or next # heading
        if stripped.startswith("---") or stripped.startswith("# "):
            break

        if "**Status:**" in stripped:
            col = stripped.find("**Status:**")
            before = stripped[:col] + "**Status:**"
            ending = line[len(line.rstrip("\n\r")):]
            lines[i] = f"{before} {new_status}{ending}"
            return lines

    raise ValueError(
        f"Phase '{phase_id}' not found or has no **Status:** line"
    )


def _find_phase_name_by_id(phases: list[Phase], phase_id: str) -> str:
    """Find the phase name for a given phase ID."""
    for p in phases:
        if p.id == phase_id:
            return p.name
    return phase_id  # fallback


# ── HELP_TEXT ──────────────────────────────────────────────────────────────

HELP_TEXT = """\
tsm phase — Phase CRUD commands (add, edit, move, remove).

Subcommands:
  tsm phase add <name> [--after <phase-id>] [--status <status>]
    Add a new phase.  If --after is omitted, the phase is appended at the end.
    Default status is "Pending".

  tsm phase edit <phase-id> [--name <name>] [--status <status>]
    Edit a phase's display name and/or status.  At least one of --name or
    --status must be provided.

  tsm phase move <phase-id> --after <phase-id>
    Move a phase to a new position.

  tsm phase remove <phase-id> [--force]
    Remove a phase and all its tasks.  Without --force, removal is blocked
    if any tasks outside the phase depend on tasks within it.  With --force,
    removal proceeds and dangling dependencies are listed in the summary.

Preconditions:
  - A project root must exist (TASKS.md and SESSIONSTATE.md must be present).
  - The specified phase ID must exist (for edit, move, remove).
  - For remove without --force: no dangling deps from other tasks.

Writes:
  1. TASKS.md — updated phase block and Phase structure table.

Example:
  tsm phase add "Phase 7 — Foo" --after phase-6-bar
  tsm phase edit phase-7-foo --name "Phase 7 — Foo Updated" --status "Complete"
  tsm phase move phase-7-foo --after phase-3-baz
  tsm phase remove phase-7-foo
  tsm phase remove phase-7-foo --force
"""
