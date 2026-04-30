# tsm/writers/tasks_writer.py — Targeted status replacement (Phase 3, P3-T03)
#
# Two public functions for line-level status updates on TASKS.md content.
# Both operate on raw string content — never re-serialize from the data model.
#
# Constraints (§9.2):
#   - Targeted line replacement only; all bytes outside the replaced **Status:**
#     line must be identical before and after.
#   - Never call session_writer.render_sessionstate() on TASKS.md content.

from pathlib import Path


# ── Public API ──────────────────────────────────────────────────────────────


def update_task_status(content: str, task_id: str, new_status: str) -> str:
    """Replace the ``**Status:**`` line inside the task block identified by
    ``task_id``, returning the full content with only that one line changed.

    The task block begins at ``### <task_id> ·`` and ends at the next ``### ``
    heading, the next ``---`` thematic break, or end-of-file.

    Raises ``ValueError`` if ``task_id`` cannot be found in ``content``.
    """
    lines = content.splitlines(keepends=True)
    target_idx = _find_task_status_line(lines, task_id)

    if target_idx == -1:
        raise ValueError(f"Task '{task_id}' not found in content")

    lines[target_idx] = _replace_status_value(lines[target_idx], new_status)
    return "".join(lines)


def update_phase_status(
    content: str, phase_heading_text: str, new_status: str
) -> str:
    """Replace the ``**Status:**`` line inside the phase header identified by
    ``phase_heading_text`` (the text after ``# `` on an H1 heading line),
    returning the full content with only that one line changed.

    The phase header block runs from the matching ``# <heading>`` line down to
    the first ``---`` thematic break or the next ``# `` heading (any level).

    Raises ``ValueError`` if ``phase_heading_text`` cannot be found in
    ``content``.
    """
    lines = content.splitlines(keepends=True)
    target_idx = _find_phase_status_line(lines, phase_heading_text)

    if target_idx == -1:
        raise ValueError(
            f"Phase heading '{phase_heading_text}' not found in content"
        )

    lines[target_idx] = _replace_status_value(lines[target_idx], new_status)
    return "".join(lines)


def write_tasks_file(content: str, shadow_path: str) -> None:
    """Write ``content`` to ``shadow_path`` (typically under ``.tsm/shadow/``).
    Creates parent directories if they do not exist.
    """
    p = Path(shadow_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ── Internal helpers ────────────────────────────────────────────────────────


def _find_task_status_line(lines: list[str], task_id: str) -> int:
    """Scan *lines* for the ``**Status:**`` line inside the task block whose
    header is ``### <task_id> ·``.

    Returns the index into *lines*, or -1 if not found.
    """
    in_block = False
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n\r")

        if not in_block:
            # Look for a task header matching this ID.
            if _matches_task_header(stripped, task_id):
                in_block = True
            continue

        # Inside a task block — check for boundaries.
        if stripped.startswith("---") or stripped.startswith("### "):
            break  # block ended without finding the status line

        if "**Status:**" in stripped:
            return i

    return -1


def _find_phase_status_line(
    lines: list[str], phase_heading_text: str
) -> int:
    """Scan *lines* for the ``**Status:**`` line inside the phase header
    identified by ``# <phase_heading_text>``.

    The phase header block runs from the matching H1 down to the first
    ``---`` or next ``# `` (any level).

    Returns the index into *lines*, or -1 if not found.
    """
    in_block = False
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n\r")

        if not in_block:
            # Look for an H1 heading (#  but not ## or ###).
            if stripped.startswith("# ") and not stripped.startswith("## "):
                heading_text = stripped[2:].strip()
                if heading_text == phase_heading_text.strip():
                    in_block = True
            continue

        # Inside a phase header — check for boundaries.
        if stripped.startswith("---") or stripped.startswith("# "):
            break  # block ended without finding the status line

        if "**Status:**" in stripped:
            return i

    return -1


def _matches_task_header(stripped: str, task_id: str) -> bool:
    """Return ``True`` if *stripped* is a ``### <task_id> · <title>`` line."""
    if not stripped.startswith("### "):
        return False
    header = stripped[4:]  # content after "### "
    if "·" not in header:
        return False
    tid = header.split("·", 1)[0].strip()
    return tid == task_id


def _replace_status_value(line: str, new_status: str) -> str:
    """Replace the value portion of a ``**Status:**`` line, preserving the
    original indentation (if any) and line ending.
    """
    col = line.find("**Status:**")
    # Everything up to and including "**Status:**" is kept; after that we
    # replace with " <new_status>" + original line ending.
    before = line[:col] + "**Status:**"
    ending = line[len(line.rstrip("\n\r")):]
    return f"{before} {new_status}{ending}"
