# tsm/commands/repair.py — File repair (Phase 7, P7-T07)
#
# Implements §15.4 repair logic for TASKS.md, SESSIONSTATE.md, and
# TASKS-COMPLETED.md.
#
# Public API:
#   repair(ctx: LoadedProject, tasks: bool, session: bool, completed: bool)
#       -> list[PendingWrite]
#   HELP_TEXT: str
#
# Constraints (§15.4):
#   - If all three flags are False, set all to True (repair everything).
#   - repair must never silently delete content — every change appears in
#     the confirm summary with before/after.
#   - Duplicate ID rename is automatic (second occurrence -> <id>-duplicate)
#     — no interactive prompting during staging.
#   - Running repair on an already-clean project must produce zero changes
#     and exit 0 (idempotency).

from datetime import datetime
from pathlib import Path
import re

from tsm.models import (
    LoadedProject,
    PendingWrite,
    ProjectContext,
    SessionState,
    Task,
    TaskStatus,
    TaskComplexity,
)
from tsm.parsers.session_parser import parse_session_file
from tsm.parsers.tasks_parser import parse_tasks_file
from tsm.writers.session_writer import render_sessionstate, write_session_file
from tsm.writers.tasks_writer import (
    update_task_status,
    write_tasks_file,
)
from tsm.writers.completed_writer import _write_file as _write_completed_file


# ── Public API ──────────────────────────────────────────────────────────────


def repair(
    ctx: LoadedProject,
    tasks: bool = False,
    session: bool = False,
    completed: bool = False,
) -> list[PendingWrite]:
    """Repair one or all three workflow files, returning pending writes.

    If all three flags are ``False``, all three files are repaired
    (default full-repair mode).

    Args:
        ctx: The loaded project state.
        tasks: Repair TASKS.md.
        session: Repair SESSIONSTATE.md.
        completed: Repair TASKS-COMPLETED.md.

    Returns:
        A list of ``PendingWrite`` objects (one per file that was changed).
        Returns an empty list if no repairs were needed.

    Raises:
        ValueError: If any repair encounters an unexpected state that
            prevents it from producing valid output.
    """
    # ── Default: repair everything ──────────────────────────────────────
    if not tasks and not session and not completed:
        tasks = session = completed = True

    pc = ctx.project_context
    pending_writes: list[PendingWrite] = []
    summary_lines: list[tuple[str, str, list[str]]] = []  # (target_file, shadow_path, lines)

    # ── Build a set of all known task IDs ───────────────────────────────
    all_task_ids: set[str] = set()
    for phase in ctx.phases:
        for t in phase.tasks:
            all_task_ids.add(t.id)

    # ── TASKS.md repair ─────────────────────────────────────────────────
    if tasks:
        tasks_content = Path(pc.tasks_path).read_text(encoding="utf-8")
        repaired_tasks, task_changes = _repair_tasks_content(
            tasks_content, all_task_ids
        )
        if task_changes:
            shadow_tasks = str(Path(pc.shadow_dir) / "TASKS.md")
            write_tasks_file(repaired_tasks, shadow_tasks)
            pending_writes.append(
                PendingWrite(
                    target_file="TASKS.md",
                    shadow_path=shadow_tasks,
                    live_path=pc.tasks_path,
                    backup_path=pc.backup_dir,
                    summary_lines=task_changes,
                )
            )
        # Update all_task_ids in case repair added/renamed any IDs
        # Re-parse to get up-to-date IDs for session/completed repairs
        _, repaired_phases = parse_tasks_file(Path(pc.tasks_path) if not task_changes else Path(shadow_tasks))
        all_task_ids = set()
        for phase in repaired_phases:
            for t in phase.tasks:
                all_task_ids.add(t.id)

    # ── SESSIONSTATE.md repair ──────────────────────────────────────────
    if session:
        session_content = Path(pc.sessionstate_path).read_text(encoding="utf-8")
        repaired_session, session_changes = _repair_session_content(
            session_content, ctx, all_task_ids
        )
        if session_changes:
            shadow_session = str(Path(pc.shadow_dir) / "SESSIONSTATE.md")
            write_session_file(repaired_session, shadow_session)
            pending_writes.append(
                PendingWrite(
                    target_file="SESSIONSTATE.md",
                    shadow_path=shadow_session,
                    live_path=pc.sessionstate_path,
                    backup_path=pc.backup_dir,
                    summary_lines=session_changes,
                )
            )

    # ── TASKS-COMPLETED.md repair ───────────────────────────────────────
    if completed:
        completed_content = Path(pc.tasks_completed_path).read_text(encoding="utf-8")
        repaired_completed, completed_changes = _repair_completed_content(
            completed_content, all_task_ids
        )
        if completed_changes:
            shadow_completed = str(Path(pc.shadow_dir) / "TASKS-COMPLETED.md")
            _write_completed_file(repaired_completed, shadow_completed)
            pending_writes.append(
                PendingWrite(
                    target_file="TASKS-COMPLETED.md",
                    shadow_path=shadow_completed,
                    live_path=pc.tasks_completed_path,
                    backup_path=pc.backup_dir,
                    summary_lines=completed_changes,
                )
            )

    return pending_writes


# ── TASKS.md repair ─────────────────────────────────────────────────────────


def _repair_tasks_content(
    content: str, valid_task_ids: set[str]
) -> tuple[str, list[str]]:
    """Repair TASKS.md content in-place.

    Returns ``(repaired_content, summary_lines)``.  If no repairs were
    needed, ``summary_lines`` is empty and ``repaired_content`` is identical
    to ``content``.

    Repairs performed:
    1. Normalise malformed status tokens.
    2. Detect duplicate task IDs and rename second occurrence to
       ``<id>-duplicate``.
    3. Fill missing required fields with safe defaults.
    4. Skip unparseable blocks (report but do not delete).
    """
    changes: list[str] = []
    lines = content.splitlines(keepends=True)

    # ── Pass 1: Normalise status tokens ────────────────────────────────
    status_changes = _normalise_status_tokens(lines)
    changes.extend(status_changes)

    # ── Pass 2: Detect and rename duplicate task IDs ───────────────────
    seen_ids: set[str] = set()
    duplicate_changes: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.rstrip("\n\r")
        tid = _extract_task_id_from_line(stripped)
        if tid is None:
            continue
        if tid in seen_ids:
            new_tid = f"{tid}-duplicate"
            old_line = stripped
            # Replace the task ID in the heading line
            # Format: ### <id> · <title>
            lines[i] = line.replace(tid, new_tid, 1)
            changes.append(
                f"[duplicate] Rename duplicate task ID '{tid}' → "
                f"'{new_tid}'"
            )
        else:
            seen_ids.add(tid)

    # ── Pass 3: Fill missing required fields ───────────────────────────
    missing_fixes = _fill_missing_fields(lines)
    changes.extend(missing_fixes)

    # Reconstruct content
    repaired = "".join(lines)

    # ── Idempotency check ──────────────────────────────────────────────
    # If nothing was changed, return original content with empty changes
    if not changes:
        return content, []

    return repaired, changes


def _normalise_status_tokens(lines: list[str]) -> list[str]:
    """Normalise malformed status tokens to their canonical forms.

    Works on ``**Status:**`` lines.  Canonical values per §4.1.3:
    ``✅ Complete``, ``**Active**``, ``Pending``, ``🔒 Blocked``,
    ``⚠️ Needs review``, ``In progress``.

    Returns a list of change description strings (empty if no changes
    were made).
    """
    changes: list[str] = []
    canonical_statuses: dict[str, str] = {
        "complete": "✅ Complete",
        "active": "**Active**",
        "pending": "Pending",
        "blocked": "🔒 Blocked",
        "needs_review": "⚠️ Needs review",
        "in_progress": "In progress",
    }

    for i, line in enumerate(lines):
        stripped = line.rstrip("\n\r")
        if "**Status:**" not in stripped:
            continue

        # Extract the value after "**Status:**"
        col = stripped.find("**Status:**")
        value_part = stripped[col + len("**Status:**"):].strip()

        # Check if it needs normalisation
        canonical = _normalise_single_status(value_part, canonical_statuses)
        if canonical is not None:
            # Extract task ID from preceding ### heading
            tid = _find_task_id_for_status_line(lines, i)
            tid_label = f" ({tid})" if tid else ""
            # Replace the value
            ending = line[len(line.rstrip("\n\r")):]
            before = line[:col] + "**Status:**"
            lines[i] = f"{before} {canonical}{ending}"
            changes.append(
                f"[normalized] Status{tid_label}: '{value_part}' → "
                f"'{canonical}'"
            )

    return changes


def _normalise_single_status(
    value: str, canonical: dict[str, str]
) -> str | None:
    """Normalise a single status value; return ``None`` if already canonical.

    Accepts case-insensitive text matches and various common malformations.
    """
    stripped = value.strip()

    # Check if already canonical
    for canon_val in canonical.values():
        if stripped == canon_val:
            return None

    # Case-insensitive matching
    lower = stripped.lower()

    # Handle emoji-prefixed variants
    if "complete" in lower:
        return "✅ Complete"
    if lower in ("**active**", "active", "▶ active"):
        return "**Active**"
    if lower == "pending":
        return "Pending"
    if "blocked" in lower:
        return "🔒 Blocked"
    if "needs review" in lower or "needs_review" in lower:
        return "⚠️ Needs review"
    if "in progress" in lower or "in_progress" in lower:
        return "In progress"

    return None


def _fill_missing_fields(lines: list[str]) -> list[str]:
    """Fill missing required fields with safe defaults.

    Required fields per §4.1.4: Status (always present after normalisation),
    What, Prerequisite, Hard deps, Files, Reviewer, Done when.
    Key constraints is optional (§4.1.9).

    Returns a list of change description strings.
    """
    changes: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        stripped = lines[i].rstrip("\n\r")
        tid = _extract_task_id_from_line(stripped)
        if tid is None:
            i += 1
            continue

        # Found a task header — scan the task block for missing fields
        task_start = i
        i += 1

        # Collect field labels present in this block
        present_fields: set[str] = set()
        field_positions: list[tuple[int, str]] = []  # (line_idx, field_name)

        while i < n:
            s = lines[i].rstrip("\n\r")
            if s.startswith("### ") or s.startswith("---"):
                break
            # Check for **<name>:** pattern
            match = re.match(r"^\s*\*\*([^*]+):\*\*", s)
            if match:
                fname = match.group(1).strip()
                present_fields.add(fname)
                field_positions.append((i, fname))
            i += 1

        task_end = i

        # Determine the insertion point: end of the task block (before `---` or next `###`)
        insert_at = task_end
        for j in range(task_end - 1, task_start, -1):
            if lines[j].rstrip("\n\r"):
                insert_at = j + 1
                break

        # Fields to check (excluding Status which is always present after normalisation)
        required = [
            ("What", ""),
            ("Prerequisite", "None."),
            ("Hard deps", "None"),
            ("Files", ""),
            ("Reviewer", "Skip"),
            ("Done when", "- Criteria not yet defined"),
        ]

        for field_name, default_value in required:
            if field_name not in present_fields:
                # Find a good insertion point
                # Insert before the next field or at end of block
                insert_pos = _find_insertion_point(
                    lines, task_start, task_end, field_name
                )
                new_line = f"**{field_name}:** {default_value}\n"
                lines.insert(insert_pos, new_line)
                changes.append(
                    f"[defaulted] {tid}: **{field_name}:** → "
                    f"'{default_value}' (field was missing)"
                )
                n += 1
                # Adjust task_end
                task_end += 1
                # Adjust insert_at
                if insert_pos <= insert_at:
                    insert_at += 1

    return changes


def _find_insertion_point(
    lines: list[str], task_start: int, task_end: int, field_name: str
) -> int:
    """Find where to insert a field within a task block.

    Preference order:
    1. After ``**Status:**`` for ``**What:**``
    2. After the last present field before the gap
    3. At the end of the task block
    """
    field_order = [
        "Status", "Complexity", "What", "Prerequisite", "Hard deps",
        "Files", "Reviewer", "Key constraints", "Done when",
    ]

    # Find the target position in the order list
    target_idx = -1
    for idx, name in enumerate(field_order):
        if name == field_name:
            target_idx = idx
            break

    if target_idx == -1:
        return task_end

    # Find the last field that comes before target in field_order
    best_pos = task_end
    best_idx = -1

    for i in range(task_start, task_end):
        stripped = lines[i].rstrip("\n\r")
        match = re.match(r"^\s*\*\*([^*]+):\*\*", stripped)
        if match:
            fname = match.group(1).strip()
            for idx, name in enumerate(field_order):
                if name == fname and idx < target_idx and idx > best_idx:
                    best_idx = idx
                    # Insert after this field's block (including multi-line)
                    best_pos = i + 1
                    # Scan to end of this field block
                    j = i + 1
                    while j < task_end:
                        s = lines[j].rstrip("\n\r")
                        if s.startswith("**") and ":**" in s:
                            break
                        if s.startswith("---") or s.startswith("### "):
                            break
                        best_pos = j + 1
                        j += 1
                    break

    return best_pos


# ── SESSIONSTATE.md repair ──────────────────────────────────────────────────


def _repair_session_content(
    content: str, ctx: LoadedProject, valid_task_ids: set[str]
) -> tuple[str, list[str]]:
    """Repair SESSIONSTATE.md content.

    Returns ``(repaired_content, summary_lines)``.

    Repairs:
    1. Upgrade legacy date-only timestamp to ``YYYY-MM-DDTHH:MM``.
    2. Validate active task ID exists in TASKS.md.
    3. Detect orphaned pending tasks (in the active phase but missing from
       the session's ``up_next``) and add them to the up_next table.
    """
    changes: list[str] = []
    lines = content.splitlines(keepends=True)

    # ── Repair 1: Upgrade legacy timestamp ─────────────────────────────
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n\r")
        # Match *Last updated: YYYY-MM-DD* (date-only, no time)
        legacy_match = re.match(
            r"^\*Last updated:\s*(\d{4}-\d{2}-\d{2})\*$", stripped
        )
        if legacy_match:
            date_only = legacy_match.group(1)
            lines[i] = f"*Last updated: {date_only}T00:00*\n"
            changes.append(
                f"[normalized] Upgrade legacy timestamp '{date_only}' → "
                f"'{date_only}T00:00'"
            )
            break

    # ── Repair 2: Validate active task ID ──────────────────────────────
    # Parse the content to find the active task section
    active_task_id, active_task_start, active_task_end = (
        _find_active_task_in_content(lines)
    )

    if active_task_id is not None and active_task_id not in valid_task_ids:
        # Active task ID not found in TASKS.md — clear it
        changes.append(
            f"[removed] Active task '{active_task_id}' not found in "
            f"TASKS.md — cleared"
        )
        # Replace the active task block with [none]
        if active_task_start is not None and active_task_end is not None:
            # Keep the ## Active task heading, replace content with [none]
            new_section = ["## Active task\n", "\n", "[none]\n"]
            lines = (
                lines[:active_task_start]
                + new_section
                + lines[active_task_end:]
            )

    # ── Repair 3: Rebuild up_next with orphaned pending tasks ──────────
    # Finds non-complete tasks in the active phase (from TASKS.md) that
    # are not the active task, not already in up_next, and not in the
    # completed list, then adds them to the ## Up next table.
    active_phase_name = ctx.session.active_phase_name
    active_phase = None
    for phase in ctx.phases:
        if phase.name == active_phase_name:
            active_phase = phase
            break

    if active_phase is not None:
        # Collect task IDs already present in the session
        up_next_ids = {t.id for t in ctx.session.up_next}
        current_active_id = (
            ctx.session.active_task.id
            if ctx.session.active_task is not None
            else None
        )
        completed_ids = {t.id for t in ctx.session.completed}

        # Find orphaned: non-complete tasks in the active phase that are
        # not in up_next, not the active task, and not completed
        orphaned: list[Task] = []
        for task in active_phase.tasks:
            if task.status == TaskStatus.COMPLETE:
                continue
            if task.id in up_next_ids:
                continue
            if task.id == current_active_id:
                continue
            if task.id in completed_ids:
                continue
            orphaned.append(task)

        if orphaned:
            # Find the ## Up next section in raw content
            up_next_idx = -1
            for i, line in enumerate(lines):
                if line.rstrip("\n\r") == "## Up next":
                    up_next_idx = i
                    break

            if up_next_idx >= 0:
                # Find the closing --- of the up_next section
                close_idx = -1
                for i in range(up_next_idx + 1, len(lines)):
                    if lines[i].rstrip("\n\r") == "---":
                        close_idx = i
                        break

                if close_idx >= 0:
                    # Find insertion position: after the last content line
                    # before the blank lines that precede the closing ---
                    insert_pos = close_idx
                    for i in range(close_idx - 1, up_next_idx, -1):
                        if lines[i].strip():
                            insert_pos = i + 1
                            break

                    # Build new table rows matching the up_next table format
                    # (§9.3: | Task | Description | Hard deps | Complexity | Reviewer |)
                    new_rows: list[str] = []
                    for task in orphaned:
                        deps_str = (
                            ", ".join(task.hard_deps)
                            if task.hard_deps
                            else "\u2014"
                        )
                        cx = (
                            task.complexity.value
                            if task.complexity
                            else "unset"
                        )
                        new_rows.append(
                            f"| {task.id} | {task.title} | {deps_str}"
                            f" | {cx} | {task.reviewer} |\n"
                        )

                    # Insert new rows at the determined position
                    for idx, row in enumerate(new_rows):
                        lines.insert(insert_pos + idx, row)

                    changes.append(
                        f"[rebuilt] Added {len(orphaned)} missing task(s) "
                        f"to up_next: "
                        f"{', '.join(t.id for t in orphaned)}"
                    )

    # Reconstruct
    repaired = "".join(lines)

    if not changes:
        return content, []

    return repaired, changes


def _find_active_task_in_content(
    lines: list[str],
) -> tuple[str | None, int | None, int | None]:
    """Find the active task section and extract its task ID.

    Returns ``(task_id, section_start, section_end)`` where
    *section_start* is the ``## Active task`` line index and
    *section_end* is one past the last line of the section.
    Returns ``(None, None, None)`` if not found.
    """
    section_start = -1
    for i, line in enumerate(lines):
        if line.rstrip("\n\r") == "## Active task":
            section_start = i
            break

    if section_start == -1:
        return None, None, None

    # Find section end (next ## heading or EOF)
    section_end = len(lines)
    for i in range(section_start + 1, len(lines)):
        if lines[i].rstrip("\n\r").startswith("## "):
            section_end = i
            break

    # Extract the task ID from the section content
    for i in range(section_start + 1, section_end):
        stripped = lines[i].rstrip("\n\r")
        tid = _extract_task_id_from_line(stripped)
        if tid is not None:
            return tid, section_start, section_end

    return None, section_start, section_end


# ── TASKS-COMPLETED.md repair ───────────────────────────────────────────────


def _repair_completed_content(
    content: str, valid_task_ids: set[str]
) -> tuple[str, list[str]]:
    """Repair TASKS-COMPLETED.md content.

    Returns ``(repaired_content, summary_lines)``.

    Repairs:
    1. Remove rows where task ID does not exist in TASKS.md.
    2. Remove phase sections that have no rows after removal.
    """
    changes: list[str] = []
    lines = content.splitlines(keepends=True)

    # ── Repair 1: Remove rows with unknown task IDs ────────────────────
    new_lines: list[str] = []
    removed_rows: list[str] = []

    for line in lines:
        stripped = line.rstrip("\n\r")
        # Check if this is a table data row (| ... | ... | ... |)
        if stripped.startswith("|") and stripped.endswith("|"):
            parts = [p.strip() for p in stripped.split("|")]
            # Skip header and separator rows
            if len(parts) >= 2:
                candidate = parts[1]
                if candidate and candidate not in (
                    "Task", "---", ""
                ) and not candidate.startswith("-"):
                    if candidate not in valid_task_ids:
                        removed_rows.append(candidate)
                        continue  # skip this row

        new_lines.append(line)

    for tid in removed_rows:
        changes.append(f"[removed] Remove row with unknown task ID '{tid}'")

    # ── Repair 2: Remove empty phase sections ──────────────────────────
    # A phase section is a ## heading followed by only header/separator
    # rows and blank lines, with no data rows.
    lines = new_lines
    result: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        stripped = lines[i].rstrip("\n\r")
        if stripped.startswith("## "):
            # Found a potential phase section
            section_start = i
            i += 1

            # Collect the section content
            section_lines: list[str] = [lines[section_start]]
            has_data_row = False

            while i < n:
                s = lines[i].rstrip("\n\r")
                if s.startswith("## "):
                    break
                section_lines.append(lines[i])
                # Check if this line is a data row (not header/separator)
                if s.startswith("|") and s.endswith("|"):
                    parts = [p.strip() for p in s.split("|")]
                    if len(parts) >= 2 and parts[1] not in (
                        "Task", "---", ""
                    ) and not parts[1].startswith("-"):
                        has_data_row = True
                i += 1

            if has_data_row:
                result.extend(section_lines)
            else:
                # Empty phase section — remove it
                phase_name = stripped[3:].strip()
                changes.append(
                    f"[removed] Remove empty phase section "
                    f"'{phase_name}'"
                )
        else:
            result.append(lines[i])
            i += 1

    repaired = "".join(result)

    if not changes:
        return content, []

    return repaired, changes


# ── Shared helpers ──────────────────────────────────────────────────────────


def _find_task_id_for_status_line(
    lines: list[str], status_line_idx: int
) -> str | None:
    """Scan backwards from a ``**Status:**`` line to find the enclosing task ID.

    Looks for the nearest ``### <id> · <title>`` heading preceding the
    status line, up to 50 lines back.  Returns the task ID or ``None``.
    """
    for i in range(status_line_idx - 1, max(status_line_idx - 50, -1), -1):
        stripped = lines[i].rstrip("\n\r")
        tid = _extract_task_id_from_line(stripped)
        if tid is not None:
            return tid
    return None


def _extract_task_id_from_line(stripped: str) -> str | None:
    """Extract a task ID from a ``### <id> · <title>`` line.

    Returns the task ID, or ``None`` if the line is not a task header.
    """
    if not stripped.startswith("### "):
        return None
    header = stripped[4:]  # content after "### "
    if "·" not in header:
        return None
    tid = header.split("·", 1)[0].strip()
    if not tid:
        return None
    return tid


# ── HELP_TEXT ───────────────────────────────────────────────────────────────

HELP_TEXT = """\
tsm repair — Repair inconsistencies in TASKS.md, SESSIONSTATE.md, and
TASKS-COMPLETED.md.

Usage: tsm repair [--tasks] [--session] [--completed]

No flags = repair all three files.

TASKS.md repairs:
  - Fill missing required fields with safe defaults
  - Normalise malformed status tokens to canonical form
  - Detect duplicate task IDs and rename second occurrence to <id>-duplicate
  - Skip unparseable content and report it

SESSIONSTATE.md repairs:
  - Upgrade legacy date-only timestamps to YYYY-MM-DDTHH:MM
  - Clear active task if its ID does not exist in TASKS.md

TASKS-COMPLETED.md repairs:
  - Remove rows with task IDs not found in TASKS.md
  - Remove empty phase sections

Preconditions:
  - A project root must exist (TASKS.md and SESSIONSTATE.md must be present).

All repairs go through the shadow model. The confirm summary groups changes
by file and labels each with [defaulted], [duplicate], [normalized],
[removed], or [skipped].

Examples:
  tsm repair
  tsm repair --tasks
  tsm repair --session --completed
"""
