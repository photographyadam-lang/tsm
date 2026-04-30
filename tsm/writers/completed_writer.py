# tsm/writers/completed_writer.py — Append writer (Phase 3, P3-T05)
#
# Two public functions:
#   append_task_row(...) -> str
#   append_phase_marker(...) -> str
#
# Constraints (§9.4):
#   - Both functions write to shadow_path, never to the live file.
#   - append_task_row on a new path creates the header structure.
#   - append_task_row appends to the last matching ## phase section.
#   - Only the last occurrence of a ## phase section is used.
#   - append_phase_marker inserts after the last data row.

from pathlib import Path


# ── Public API ──────────────────────────────────────────────────────────────


def append_task_row(
    path: Path,
    shadow_path: str,
    phase_name: str,
    task_id: str,
    title: str,
    complexity: str,
    commit: str,
    notes: str,
) -> str:
    """Append a task row to the specified phase section in
    TASKS-COMPLETED.md.

    If *path* does not exist, the file is created with the standard header
    (``# Completed Tasks Log\\n\\n---\\n``).  If the ``## <phase_name>``
    section does not exist, it is created at the end of the file complete
    with the 5-column table header and separator.  If the section already
    exists, the new row is inserted after the last data row in that section.

    Args:
        path: Path to the live TASKS-COMPLETED.md file.
        shadow_path: Path under ``.tsm/shadow/`` to write staged content to.
        phase_name: Text after ``## `` identifying the phase section.
        task_id: Task ID for the new row.
        title: Task title / description.
        complexity: Complexity value.
        commit: Commit hash or message.
        notes: Additional notes.

    Returns:
        The full reconstructed content string.

    Raises:
        OSError: If the shadow path cannot be written.
    """
    # Load or create base content
    if path.exists():
        content = path.read_text(encoding="utf-8")
    else:
        content = "# Completed Tasks Log\n\n---\n"

    new_row = f"| {task_id} | {title} | {complexity} | {commit} | {notes} |"
    phase_heading = f"## {phase_name}"

    lines = content.splitlines(keepends=True)

    section = _find_last_phase_section(lines, phase_heading)

    if section is None:
        # Phase section does not exist — append at end with full table header.
        content = content.rstrip("\n") + "\n\n"
        content += f"{phase_heading}\n\n"
        content += f"| Task | Description | Complexity | Commit | Notes |\n"
        content += f"|------|-------------|------------|--------|-------|\n"
        content += f"{new_row}\n"
    else:
        start_idx, end_idx = section
        insert_pos = _find_table_end(lines, start_idx, end_idx)
        lines.insert(insert_pos, f"{new_row}\n")
        content = "".join(lines)

    _write_file(content, shadow_path)
    return content


def append_phase_marker(
    path: Path,
    shadow_path: str,
    phase_name: str,
    date: str,
) -> str:
    """Append a ``**Phase complete: YYYY-MM-DD**`` line after the last
    data row in the specified phase section.

    Args:
        path: Path to the live TASKS-COMPLETED.md file.
        shadow_path: Path under ``.tsm/shadow/`` to write staged content to.
        phase_name: Text after ``## `` identifying the phase section.
        date: Completion date string in ``YYYY-MM-DD`` format.

    Returns:
        The full reconstructed content string.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the phase section cannot be found in the file.
        OSError: If the shadow path cannot be written.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Cannot append phase marker: {path} does not exist"
        )

    content = path.read_text(encoding="utf-8")
    phase_heading = f"## {phase_name}"
    lines = content.splitlines(keepends=True)

    section = _find_last_phase_section(lines, phase_heading)
    if section is None:
        raise ValueError(
            f"Phase section '{phase_name}' not found in {path}"
        )

    start_idx, end_idx = section
    marker = f"**Phase complete: {date}**"
    insert_pos = _find_table_end(lines, start_idx, end_idx)
    lines.insert(insert_pos, f"{marker}\n")
    content = "".join(lines)

    _write_file(content, shadow_path)
    return content


# ── Internal helpers ────────────────────────────────────────────────────────


def _find_last_phase_section(
    lines: list[str], phase_heading: str
) -> tuple[int, int] | None:
    """Find the last occurrence of a ``## <name>`` section in *lines*.

    Returns ``(start_idx, end_idx)`` where *start_idx* is the line index
    of the phase heading and *end_idx* is the exclusive end (the index of
    the next ``## `` heading or ``len(lines)``).  Returns ``None`` if no
    such heading is found.
    """
    last_start = -1
    for i, line in enumerate(lines):
        if line.strip() == phase_heading:
            last_start = i

    if last_start == -1:
        return None

    end = len(lines)
    for i in range(last_start + 1, len(lines)):
        if lines[i].strip().startswith("## "):
            end = i
            break

    return (last_start, end)


def _find_table_end(
    lines: list[str], section_start: int, section_end: int
) -> int:
    """Find the line index where a new row or marker should be inserted.

    Scans backwards from *section_end* (exclusive) to find the last
    non-blank line, then returns one past its index.  If the section is
    empty (no non-blank lines after the heading), returns *section_end*.
    """
    for i in range(section_end - 1, section_start, -1):
        if lines[i].strip():
            return i + 1
    return section_end


def _write_file(content: str, shadow_path: str) -> None:
    """Write *content* to *shadow_path*, creating parent directories if
    they do not exist."""
    p = Path(shadow_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
