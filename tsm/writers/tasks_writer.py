# tsm/writers/tasks_writer.py — Targeted status replacement (Phase 3, P3-T03)
#                          and structural operations (Phase 7, P7-T03a/T03b)
#
# Phase 3 (P3-T03): line-level status updates via update_task_status and
#   update_phase_status — targeted single-line replacement on TASKS.md content.
# Phase 7a (P7-T03a): structural insert/remove/field-replace operations.
# Phase 7b (P7-T03b): block reorder operations (reorder_phase_blocks,
#   reorder_task_blocks). All content within blocks preserved byte-for-byte.
#
# Constraints (§9.2):
#   - Targeted line replacement only; all bytes outside the replaced **Status:**
#     line must be identical before and after.
#   - Never call session_writer.render_sessionstate() on TASKS.md content.
#   - Structural operations operate on raw string content; never re-serialize
#     from the data model.

from pathlib import Path
import re

from tsm.models import slugify_phase_name, PhaseOverviewRow


# ── Public API — P3-T03 (status-only updates) ──────────────────────────────


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


# ── Public API — P7-T03a (structural insert/remove/field-replace) ──────────


def insert_phase_block(
    content: str, phase_block: str, after_phase_id: str | None = None
) -> str:
    """Insert a new H1 phase block at the correct position.

    If ``after_phase_id`` is ``None``, the block is appended at the end of
    the file.  Otherwise it is inserted immediately *before* the next H1
    phase heading after the matching phase.

    The new **phase_block** should be a complete phase block including the
    ``# Heading`` line, content, and any trailing ``---`` separator.

    Raises ``ValueError`` if ``after_phase_id`` is not ``None`` and no
    matching phase is found.
    """
    lines = content.splitlines(keepends=True)
    phase_lines = phase_block.splitlines(keepends=True)
    h1_indices = _find_phase_h1_indices(lines)

    if after_phase_id is None:
        # Append at end – preserve the terminating newline
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        return "".join(lines + phase_lines)

    # Locate the phase whose slug matches after_phase_id
    target_pos = -1
    for idx, (line_idx, pid) in enumerate(h1_indices):
        if pid == after_phase_id:
            # Insert before the *next* H1 (or EOF)
            if idx + 1 < len(h1_indices):
                target_pos = h1_indices[idx + 1][0]
            else:
                target_pos = len(lines)
            break

    if target_pos == -1:
        raise ValueError(f"Phase '{after_phase_id}' not found in content")

    new_lines = lines[:target_pos] + phase_lines + lines[target_pos:]
    return "".join(new_lines)


def remove_phase_block(content: str, phase_id: str) -> str:
    """Remove the H1 phase block identified by ``phase_id`` (slug) and all
    content until the next H1 heading or end-of-file.

    Raises ``ValueError`` if ``phase_id`` is not found.
    """
    lines = content.splitlines(keepends=True)
    h1_indices = _find_phase_h1_indices(lines)

    target_start = -1
    target_end = -1
    for idx, (line_idx, pid) in enumerate(h1_indices):
        if pid == phase_id:
            target_start = line_idx
            if idx + 1 < len(h1_indices):
                target_end = h1_indices[idx + 1][0]
            else:
                target_end = len(lines)
            break

    if target_start == -1:
        raise ValueError(f"Phase '{phase_id}' not found in content")

    new_lines = lines[:target_start] + lines[target_end:]
    return "".join(new_lines)


def insert_task_block(
    content: str,
    task_block: str,
    phase_id: str,
    after_task_id: str | None = None,
) -> str:
    """Insert a new ``### <id> · <title>`` task block within the phase
    identified by ``phase_id``.

    The block is inserted **before** the ``### Dependency graph`` block
    within the target phase.  If ``after_task_id`` is provided the new
    block is placed immediately after that task; otherwise it is placed
    at the beginning of the task section (after the ``## <Phase> tasks``
    subheading).

    Raises ``ValueError`` if the phase or ``after_task_id`` is not found.
    """
    lines = content.splitlines(keepends=True)
    task_lines = task_block.splitlines(keepends=True)

    # Locate the phase boundaries
    phase_start, phase_end = _find_phase_by_id(lines, phase_id)

    # Within the phase, find the ### Dependency graph line (must come last)
    dep_graph_line = -1
    for i in range(phase_start, phase_end):
        stripped = lines[i].rstrip("\n\r")
        if stripped == "### Dependency graph":
            dep_graph_line = i
            break

    if dep_graph_line == -1:
        # No dep graph block – insert before the end of the phase
        dep_graph_line = phase_end

    # If after_task_id is given, find the end of that task's block
    if after_task_id is not None:
        insert_at = -1
        for i in range(phase_start, dep_graph_line):
            if _matches_task_header(lines[i].rstrip("\n\r"), after_task_id):
                # Scan to the end of this task block (next ### or --- or dep graph)
                j = i + 1
                while j < dep_graph_line:
                    s = lines[j].rstrip("\n\r")
                    if s.startswith("### ") or s.startswith("---"):
                        break
                    j += 1
                insert_at = j
                break

        if insert_at == -1:
            raise ValueError(
                f"Task '{after_task_id}' not found in phase '{phase_id}'"
            )
    else:
        # Insert at start of the task section – before the first ### task heading.
        # Skip past any --- separators and ## subheadings to find the first task.
        insert_at = phase_start
        for i in range(phase_start + 1, dep_graph_line):
            stripped = lines[i].rstrip("\n\r")
            if stripped.startswith("### "):
                insert_at = i
                break
            # Continue scanning past --- and ## subheadings (like "## Phase X tasks")
            if stripped.startswith("---") or stripped.startswith("## "):
                # Skip any blank lines that follow
                j = i + 1
                while j < dep_graph_line and not lines[j].rstrip("\n\r"):
                    j += 1
                if j < dep_graph_line and lines[j].rstrip("\n\r").startswith("### "):
                    insert_at = j
                    break
                # If the next non-blank is not a task, keep scanning
                i = j - 1  # will be incremented by range()

    new_lines = lines[:insert_at] + task_lines + lines[insert_at:]
    return "".join(new_lines)


def remove_task_block(content: str, task_id: str) -> str:
    """Remove the ``### <task_id> ·`` task block from the content.

    Removes from the ``###`` header line through to the next ``###``,
    ``---``, ``### Dependency graph``, or end-of-file.

    Raises ``ValueError`` if ``task_id`` is not found.
    """
    lines = content.splitlines(keepends=True)

    # Find the task header line
    task_start = -1
    for i, line in enumerate(lines):
        if _matches_task_header(line.rstrip("\n\r"), task_id):
            task_start = i
            break

    if task_start == -1:
        raise ValueError(f"Task '{task_id}' not found in content")

    # Find the end of this task block
    task_end = task_start + 1
    while task_end < len(lines):
        s = lines[task_end].rstrip("\n\r")
        if s.startswith("### ") or s.startswith("---"):
            break
        task_end += 1

    new_lines = lines[:task_start] + lines[task_end:]
    return "".join(new_lines)


def update_phase_structure_table(
    content: str, rows: list[PhaseOverviewRow]
) -> str:
    """Rewrite the ``## Phase structure`` pipe table with the given rows.

    Only the data rows (lines 3+) of the table are replaced; the header
    separator and column heading are preserved.  All content outside the
    table is untouched.

    Raises ``ValueError`` if the ``## Phase structure`` section cannot be
    found.
    """
    lines = content.splitlines(keepends=True)

    # Find the ## Phase structure heading
    ps_idx = -1
    for i, line in enumerate(lines):
        if line.rstrip("\n\r") == "## Phase structure":
            ps_idx = i
            break

    if ps_idx == -1:
        raise ValueError("'## Phase structure' section not found in content")

    # The table starts right after the heading (usually 1 blank line then | Phase | ...)
    table_start = -1
    for i in range(ps_idx + 1, len(lines)):
        stripped = lines[i].rstrip("\n\r")
        if stripped.startswith("|"):
            table_start = i
            break

    if table_start == -1:
        raise ValueError("No table found under '## Phase structure'")

    # Find the end of the table (next non-blank non-pipe line, or ---)
    table_end = table_start
    while table_end < len(lines):
        s = lines[table_end].rstrip("\n\r")
        if s.startswith("---"):
            break
        if s and not s.startswith("|") and not s.startswith(" "):
            # Check if we've already moved past table rows
            if table_end > table_start:
                break
        table_end += 1

    # Build new row lines
    new_rows = []
    for row in rows:
        new_rows.append(
            f"| **{row.phase_name}** | {row.description} | {row.status} |\n"
        )

    # Preserve header and separator lines, replace data rows
    new_lines = (
        lines[: table_start + 2]  # header row + separator row
        + new_rows
        + lines[table_end:]
    )
    return "".join(new_lines)


def update_task_field(
    content: str, task_id: str, field_name: str, new_value: str
) -> str:
    """Replace a task field using the §9.4a multi-line targeted replacement
    algorithm.

    ``field_name`` is the label text (e.g. ``"What"``, ``"Done when"``,
    ``"Key constraints"``).  For **single-line** fields the value is set on
    the same line after ``**:``.  For **multi-line** fields (``What``,
    ``Done when``, ``Key constraints``) the field content from the label
    through to the next field label or block boundary is replaced.

    **Key constraints** special handling:
    - Empty ``new_value`` removes the ``**Key constraints:**`` block entirely.
    - Non-empty ``new_value`` when the field is absent inserts before
      ``**Done when:**``.

    Raises ``ValueError`` if ``task_id`` is not found.
    """
    lines = content.splitlines(keepends=True)

    # Locate the task block
    task_start = -1
    for i, line in enumerate(lines):
        if _matches_task_header(line.rstrip("\n\r"), task_id):
            task_start = i
            break

    if task_start == -1:
        raise ValueError(f"Task '{task_id}' not found in content")

    # Find the end of the task block
    task_end = task_start + 1
    while task_end < len(lines):
        s = lines[task_end].rstrip("\n\r")
        if s.startswith("### ") or s.startswith("---"):
            break
        task_end += 1

    # Build the label we're looking for
    label = f"**{field_name}:**"

    # Locate the field within the task block
    field_line = -1
    for i in range(task_start, task_end):
        if lines[i].rstrip("\n\r").startswith(label):
            field_line = i
            break

    # ── Special case: Key constraints removal ──
    if field_name == "Key constraints" and new_value == "" and field_line != -1:
        # Remove the field block line and any bullet lines beneath it
        remove_end = field_line + 1
        while remove_end < task_end:
            s = lines[remove_end].rstrip("\n\r")
            if s.startswith("**") or s.startswith("---") or s.startswith("### "):
                break
            if s.startswith("- "):
                remove_end += 1
            else:
                break
        new_lines = lines[:field_line] + lines[remove_end:]
        return "".join(new_lines)

    # ── Special case: Key constraints insertion (absent field) ──
    if field_name == "Key constraints" and new_value != "" and field_line == -1:
        # Insert before **Done when:**
        done_when_line = -1
        for i in range(task_start, task_end):
            if lines[i].rstrip("\n\r").startswith("**Done when:**"):
                done_when_line = i
                break
        if done_when_line == -1:
            raise ValueError(
                f"Cannot insert Key constraints: **Done when:** not found "
                f"in task '{task_id}'"
            )
        # Build the field block
        field_block_lines = [f"**Key constraints:**\n"]
        for constraint in new_value.split("\n"):
            stripped = constraint.strip()
            if stripped:
                field_block_lines.append(f"- {stripped}\n")
        new_lines = (
            lines[:done_when_line]
            + field_block_lines
            + lines[done_when_line:]
        )
        return "".join(new_lines)

    # ── Field not found (and not the Key constraints insert case) ──
    if field_line == -1:
        raise ValueError(
            f"Field '{field_name}' not found in task '{task_id}'"
        )

    # ── Single-line field replacement ──
    # Single-line fields have value after ": " on the same line
    if field_name not in ("What", "Done when", "Key constraints"):
        line = lines[field_line]
        col = line.find(label)
        before = line[:col] + label
        ending = line[len(line.rstrip("\n\r")):]
        lines[field_line] = f"{before} {new_value}{ending}"
        return "".join(lines)

    # ── Multi-line field replacement ──
    # Find the end of this field block (next **field:** or boundary)
    field_end = field_line + 1
    while field_end < task_end:
        s = lines[field_end].rstrip("\n\r")
        # Detect the start of any new field (**<name>:**)
        if s.startswith("**") and ":**" in s:
            break
        if s.startswith("---") or s.startswith("### "):
            break
        field_end += 1

    # Build replacement content
    if field_name == "Key constraints":
        # Key constraints: each line is "- <value>"
        field_lines = [f"**Key constraints:**\n"]
        for constraint in new_value.split("\n"):
            stripped = constraint.strip()
            if stripped.startswith("- "):
                stripped = stripped[2:]
            if stripped:
                field_lines.append(f"- {stripped}\n")
    else:
        # What or Done when: multi-line value
        # First line of content goes on the same line as the label
        value_lines = new_value.split("\n")
        field_lines = [f"{label} {value_lines[0]}\n"]
        for line_text in value_lines[1:]:
            field_lines.append(f"{line_text}\n")

    new_lines = lines[:field_line] + field_lines + lines[field_end:]
    return "".join(new_lines)


# ── Public API — P7-T03b (block reorder operations) ─────────────────────────


def reorder_phase_blocks(
    content: str, ordered_phase_ids: list[str]
) -> str:
    """Reorder all H1 phase blocks to match the given ``ordered_phase_ids``.

    All content within each phase block is preserved byte-for-byte.  Content
    before the first phase (preamble) and after the last phase (postamble)
    is left untouched.

    Raises ``ValueError`` if any ID in ``ordered_phase_ids`` does not exist,
    or if the list is shorter than the actual number of phase blocks.

    Raises ``ValueError`` if the number of IDs in ``ordered_phase_ids``
    differs from the number of phase blocks found.
    """
    lines = content.splitlines(keepends=True)
    h1_indices = _find_phase_h1_indices(lines)

    actual_ids = [pid for _, pid in h1_indices]
    if len(ordered_phase_ids) != len(actual_ids):
        raise ValueError(
            f"ordered_phase_ids has {len(ordered_phase_ids)} IDs but "
            f"content has {len(actual_ids)} phase blocks"
        )

    # Validate all IDs exist
    seen = set(actual_ids)
    for pid in ordered_phase_ids:
        if pid not in seen:
            raise ValueError(f"Phase ID '{pid}' not found in content")

    # Preamble: everything before the first phase H1
    preamble_end = h1_indices[0][0]
    preamble = "".join(lines[:preamble_end])

    # Extract each phase block (from its H1 to the next H1 or EOF)
    phase_blocks: dict[str, str] = {}
    for idx, (line_idx, pid) in enumerate(h1_indices):
        block_end = h1_indices[idx + 1][0] if idx + 1 < len(h1_indices) else len(lines)
        block_text = "".join(lines[line_idx:block_end])
        phase_blocks[pid] = block_text

    # Rebuild in the requested order
    reordered = [phase_blocks[pid] for pid in ordered_phase_ids]
    return preamble + "".join(reordered)


def reorder_task_blocks(
    content: str, phase_id: str, ordered_task_ids: list[str]
) -> str:
    """Reorder ``###`` task blocks within a single phase.

    All task block content is preserved byte-for-byte.  The
    ``### Dependency graph`` block is **always** placed last regardless of
    whether its ID appears in ``ordered_task_ids``.

    Raises ``ValueError`` if any ID in ``ordered_task_ids`` does not exist
    among the task blocks in the target phase, or if the list length differs
    from the number of non-dep-graph task blocks.
    """
    lines = content.splitlines(keepends=True)

    # Locate the phase boundaries
    phase_start, phase_end = _find_phase_by_id(lines, phase_id)

    # Within the phase, find:
    #   (a) all ### task heading indices (excluding ### Dependency graph)
    #   (b) the ### Dependency graph heading index
    task_heading_indices: list[int] = []
    dep_graph_idx = -1
    for i in range(phase_start, phase_end):
        stripped = lines[i].rstrip("\n\r")
        if stripped.startswith("### "):
            if stripped == "### Dependency graph":
                dep_graph_idx = i
            else:
                task_heading_indices.append(i)

    # Collect task IDs from the heading lines
    task_ids: list[str] = []
    for idx in task_heading_indices:
        tid = _extract_task_id(lines[idx].rstrip("\n\r"))
        task_ids.append(tid)

    if len(ordered_task_ids) != len(task_ids):
        raise ValueError(
            f"ordered_task_ids has {len(ordered_task_ids)} IDs but phase "
            f"'{phase_id}' has {len(task_ids)} task blocks"
        )

    seen = set(task_ids)
    for tid in ordered_task_ids:
        if tid not in seen:
            raise ValueError(
                f"Task ID '{tid}' not found in phase '{phase_id}'"
            )

    # ── Extract sections ──────────────────────────────────────────────

    # Content from phase_start up to the first ### task heading
    pre_task_content = "".join(lines[phase_start:task_heading_indices[0]])

    # Find standalone --- separator lines within the phase (after the
    # first task heading).  These must NOT be absorbed into any task
    # block, because the parser treats --- as an exit from TASK_BLOCK
    # to BETWEEN_PHASES, which would lose subsequent tasks.
    separator_indices: list[int] = []
    for i in range(task_heading_indices[0], phase_end):
        if lines[i].rstrip("\n\r") == "---":
            separator_indices.append(i)

    # Build the list of boundary markers within the phase:
    #   all ### positions (task headings + dep graph),
    #   plus --- separators, plus phase_end
    boundaries = task_heading_indices[:]  # all non-dep-graph task headings
    if dep_graph_idx != -1:
        boundaries.append(dep_graph_idx)
    boundaries.extend(separator_indices)
    boundaries.append(phase_end)
    # Sort and deduplicate so boundaries are in ascending order
    unique_boundaries = sorted(set(boundaries))

    # Extract each task block: from its ### to just before the next
    # boundary marker (could be another ### heading, a --- separator,
    # the dep graph heading, or phase_end)
    task_blocks: dict[str, str] = {}
    for i, hdr_idx in enumerate(task_heading_indices):
        next_boundary = phase_end
        for b in unique_boundaries:
            if b > hdr_idx:
                next_boundary = b
                break
        block_text = "".join(lines[hdr_idx:next_boundary])
        tid = _extract_task_id(lines[hdr_idx].rstrip("\n\r"))
        task_blocks[tid] = block_text

    # Suffix: everything after the last task block to phase_end.
    # The first non-task boundary after the last task heading serves as
    # the start of the suffix (e.g. --- separator or dep graph heading).
    last_task_hdr = task_heading_indices[-1]
    suffix_start = phase_end
    for b in unique_boundaries:
        if b > last_task_hdr:
            suffix_start = b
            break
    suffix = "".join(lines[suffix_start:phase_end])

    # ── Rebuild ───────────────────────────────────────────────────────
    # Include content before and after the target phase
    preamble = "".join(lines[:phase_start])
    postamble = "".join(lines[phase_end:])
    reordered_task_part = "".join(task_blocks[tid] for tid in ordered_task_ids)
    return preamble + pre_task_content + reordered_task_part + suffix + postamble


# ── Internal helpers ────────────────────────────────────────────────────────




def _find_h1_headings(lines: list[str]) -> list[tuple[int, str]]:
    """Return a list of (line_index, heading_text) for every ``# `` H1 line
    except the very first one (which is the document title).

    This ignores ``## `` and ``### `` headings.
    """
    headings: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n\r")
        if stripped.startswith("# ") and not stripped.startswith("## "):
            headings.append((i, stripped[2:].strip()))
    # The first H1 is the document title — skip it
    return headings[1:] if headings else []


def _find_phase_h1_indices(lines: list[str]) -> list[tuple[int, str]]:
    """Return a list of (line_index, phase_id_slug) for every phase H1 heading.

    Phase IDs are derived via ``slugify_phase_name()``.
    """
    result: list[tuple[int, str]] = []
    # Collect slugs already seen to handle collisions properly
    seen_slugs: list[str] = []
    for idx, heading_text in _find_h1_headings(lines):
        pid = slugify_phase_name(heading_text, seen_slugs)
        seen_slugs.append(pid)
        result.append((idx, pid))
    return result


def _find_phase_by_id(
    lines: list[str], phase_id: str
) -> tuple[int, int]:
    """Return ``(start_line, end_line)`` for the phase whose slug matches
    ``phase_id``.

    *start_line* is the ``# `` heading line.
    *end_line* is exclusive (one past the last line of the phase block).
    """
    h1_indices = _find_phase_h1_indices(lines)
    for idx, (line_idx, pid) in enumerate(h1_indices):
        if pid == phase_id:
            end = h1_indices[idx + 1][0] if idx + 1 < len(h1_indices) else len(lines)
            return line_idx, end
    raise ValueError(f"Phase '{phase_id}' not found in content")


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


def _extract_task_id(stripped: str) -> str:
    """Extract the task ID from a ``### <id> · <title>`` line.

    Returns the part before the ``·`` separator.
    """
    header = stripped[4:]  # content after "### "
    if "·" not in header:
        return header.strip()
    return header.split("·", 1)[0].strip()
