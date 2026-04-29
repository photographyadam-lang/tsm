# tsm/parsers/session_parser.py — SESSIONSTATE.md section-based parser (P2-T03)
#
# Implements parse_session_file() using a section-split approach per §9.3:
# split file content on --- horizontal rule lines, identify each section
# block by its ## heading text, and parse accordingly.

import warnings
from datetime import datetime
from pathlib import Path

from tsm.models import SessionState, Task, TaskComplexity, TaskStatus


# ---------------------------------------------------------------------------
# Internal helpers — shared with tasks_parser conventions
# ---------------------------------------------------------------------------

_EMOJI_COMPLETE = "\u2705"
_EMOJI_LOCK = "\U0001F512"
_EMOJI_CROSS = "\u274C"


def _parse_status(value: str) -> TaskStatus:
    """Parse a status token string into a TaskStatus enum."""
    v = value.strip()
    if v == f"{_EMOJI_COMPLETE} Complete" or v == "Complete":
        return TaskStatus.COMPLETE
    if v == "**Active**" or v == "Active":
        return TaskStatus.ACTIVE
    if v == "Pending":
        return TaskStatus.PENDING
    if _EMOJI_LOCK in v and ("Blocked" in v or "Locked" in v):
        return TaskStatus.BLOCKED
    if _EMOJI_CROSS in v and ("Blocked" in v or "Locked" in v):
        return TaskStatus.BLOCKED
    if v in ("Blocked", "Locked"):
        return TaskStatus.BLOCKED
    if v == "Needs Review":
        return TaskStatus.NEEDS_REVIEW
    if v == "In Progress":
        return TaskStatus.IN_PROGRESS
    return TaskStatus.PENDING


def _parse_hard_deps(value: str) -> list[str]:
    """Parse a Hard deps value into a list of task ID strings."""
    v = value.strip()
    if not v or v == "None" or v == "None." or v == "\u2014" or v == "\u2013":
        return []
    return [dep.strip() for dep in v.split(",") if dep.strip()]


def _parse_complexity(value: str) -> TaskComplexity:
    """Parse a complexity value into a TaskComplexity enum."""
    v = value.strip().lower()
    if v == "high":
        return TaskComplexity.HIGH
    if v == "medium":
        return TaskComplexity.MEDIUM
    if v == "low":
        return TaskComplexity.LOW
    if v == "unset":
        return TaskComplexity.UNSET
    warnings.warn(
        f"Unknown complexity value: {value!r}, defaulting to UNSET"
    )
    return TaskComplexity.UNSET


def _strip_field_line(line: str) -> tuple[str, str] | None:
    """Split a '**FieldName:** value' line into (field_name, value).

    Returns None if the line is not a field line.
    Uses the same convention as tasks_parser._split_field_line.
    """
    s = line.strip()
    if not s.startswith("**"):
        return None
    idx = s.find(":**", 2)
    if idx == -1:
        return None
    field_name = s[2:idx]
    value = s[idx + 3:]
    if value.startswith(" "):
        value = value[1:]
    return (field_name, value)


def _parse_pipe_table_row(row_line: str) -> list[str]:
    """Split a pipe-delimited table row into stripped cell values.

    Strips leading/trailing empty cells from the outer pipes.
    """
    cells = [c.strip() for c in row_line.split("|")]
    # Remove leading empty cell (from leading |)
    if cells and cells[0] == "":
        cells = cells[1:]
    # Remove trailing empty cell (from trailing |)
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def _is_separator_row(row_line: str) -> bool:
    """Return True if the row is a pipe-table separator (|---|)."""
    return all(
        set(c.strip()).issubset({"-", ":", " "})
        for c in row_line.split("|")
        if c.strip()
    )


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------


def _split_sections(content: str) -> tuple[str, list[tuple[str, str]]]:
    """Split file content on --- divider lines.

    Returns (preamble, list_of_section_tuples) where each section tuple
    is (heading_line, block_body). The preamble is everything before the
    first --- divider (contains the *Last updated:* line).

    Sections are identified by their ## heading line found in each block.
    Blocks without a ## heading are treated as preamble extensions.
    """
    # Normalize line endings
    if "\r\n" in content:
        content = content.replace("\r\n", "\n")

    # Split on lines that are exactly "---" (may have trailing whitespace)
    lines = content.split("\n")
    blocks: list[list[str]] = []
    current_block: list[str] = []
    for line in lines:
        if line.rstrip() == "---":
            blocks.append(current_block)
            current_block = []
        else:
            current_block.append(line)
    if current_block:
        blocks.append(current_block)

    if not blocks:
        return "", []

    # First block is the preamble
    preamble = "\n".join(blocks[0])

    # Remaining blocks are sections
    sections: list[tuple[str, str]] = []
    for block_lines in blocks[1:]:
        block_text = "\n".join(block_lines)
        heading = _find_heading(block_lines)
        if heading:
            sections.append((heading, block_text))

    return preamble, sections


def _find_heading(block_lines: list[str]) -> str | None:
    """Find the first ## heading line in a block, return it stripped."""
    for line in block_lines:
        s = line.strip()
        if s.startswith("## "):
            return s
    return None


# ---------------------------------------------------------------------------
# Last updated parsing
# ---------------------------------------------------------------------------


def _parse_last_updated(preamble: str) -> datetime:
    """Parse the *Last updated:* timestamp from the preamble.

    Tries two formats per §9.5:
      1. %Y-%m-%dT%H:%M  (full datetime)
      2. %Y-%m-%d         (legacy date-only, time set to 00:00)

    Raises ValueError if no valid timestamp is found.
    """
    for line in preamble.split("\n"):
        s = line.strip()
        if "*Last updated:" in s:
            # Extract the value between "Last updated: " and trailing " *"
            value = s
            if value.startswith("*"):
                value = value[1:]
            if value.endswith("*"):
                value = value[:-1]
            value = value.strip()
            prefix = "Last updated:"
            if value.startswith(prefix):
                value = value[len(prefix):].strip()

            # Try full format first
            try:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M")
            except ValueError:
                pass

            # Try legacy date-only format
            try:
                dt = datetime.strptime(value, "%Y-%m-%d")
                return dt.replace(hour=0, minute=0)
            except ValueError:
                pass

            # If we found the line but couldn't parse, raise
            raise ValueError(
                f"Cannot parse *Last updated:* value: {value!r}"
            )

    raise ValueError("No *Last updated:* line found in preamble")


# ---------------------------------------------------------------------------
# Active phase
# ---------------------------------------------------------------------------


def _parse_active_phase(block: str) -> tuple[str, str]:
    """Parse the ## Active phase block.

    Returns (active_phase_name, active_phase_spec).
    """
    lines = block.split("\n")
    phase_name = ""
    phase_spec = ""
    for line in lines:
        s = line.strip()
        if s.startswith("## Active phase"):
            continue
        if not s:
            continue
        if s.startswith("Spec:"):
            phase_spec = s[5:].strip()
        elif not phase_name:
            phase_name = s
    return phase_name, phase_spec


# ---------------------------------------------------------------------------
# Active task
# ---------------------------------------------------------------------------


def _parse_active_task(block: str) -> tuple[Task | None, str]:
    """Parse the ## Active task block.

    Returns (active_task, active_task_raw).
    active_task_raw is the full block text verbatim.
    If the block contains only [none] or is empty, active_task is None.
    """
    raw = block  # store full block verbatim
    lines = block.split("\n")
    non_empty = [l for l in lines if l.strip()]

    # Check for [none] or empty
    if not non_empty:
        return None, raw

    # If the only non-empty content is the heading and "[none]", return None
    content_only = [
        l for l in non_empty
        if not l.strip().startswith("## ")
    ]
    if not content_only:
        return None, raw
    if len(content_only) == 1 and content_only[0].strip() == "[none]":
        return None, raw

    # Extract task ID and title from ### ID · Title heading
    task_id = ""
    title = ""
    task_status = TaskStatus.PENDING
    task_complexity = TaskComplexity.UNSET

    for line in non_empty:
        s = line.strip()
        # Look for ### heading with task ID
        if s.startswith("### "):
            rest = s[4:].strip()
            if " \u00b7 " in rest:
                parts = rest.split(" \u00b7 ", 1)
                task_id = parts[0].strip()
                title = parts[1].strip()
            elif " \u2022 " in rest:
                parts = rest.split(" \u2022 ", 1)
                task_id = parts[0].strip()
                title = parts[1].strip()
            break  # Only process first ### line

    # Parse fields inside the block
    for line in non_empty:
        s = line.strip()
        field = _strip_field_line(s)
        if field:
            fname, fvalue = field
            if fname == "Status":
                task_status = _parse_status(fvalue)
            elif fname == "Complexity":
                task_complexity = _parse_complexity(fvalue)

    if task_id:
        task = Task(
            id=task_id,
            title=title,
            status=task_status,
            complexity=task_complexity,
            what="",
            prerequisite="",
            hard_deps=[],
            files=[],
            reviewer="",
            key_constraints=[],
            done_when="",
            phase_id="",
            subphase=None,
            raw_block=raw,
        )
    else:
        task = None

    return task, raw


# ---------------------------------------------------------------------------
# Up next table
# ---------------------------------------------------------------------------


def _parse_up_next_table(block: str) -> list[Task]:
    """Parse the ## Up next pipe-delimited table.

    Supports both 5-column (with Complexity) and 4-column (without
    Complexity) tables. If Complexity column is absent, all rows get
    TaskComplexity.UNSET (§9.5).
    """
    rows: list[Task] = []
    lines = block.split("\n")

    # Find the table start
    header_line = None
    data_lines: list[str] = []
    found_header = False
    for line in lines:
        s = line.strip()
        if s.startswith("## Up next"):
            continue
        if s.startswith("|") and not found_header:
            header_line = s
            found_header = True
            continue
        if found_header:
            if s.startswith("|"):
                if _is_separator_row(s):
                    continue
                data_lines.append(s)
            elif not s:
                # blank line after table = end of table
                break

    if header_line is None:
        return rows

    # Determine column layout from header
    header_cells = _parse_pipe_table_row(header_line)
    has_complexity = "complexity" in header_cells[-2].lower() if len(header_cells) >= 2 else False

    for row_line in data_lines:
        cells = _parse_pipe_table_row(row_line)
        if len(cells) < 2:
            continue

        task_id = cells[0].strip() if len(cells) > 0 else ""
        description = cells[1].strip() if len(cells) > 1 else ""

        if has_complexity:
            # 5 columns: Task, Description, Hard deps, Complexity, Reviewer
            hard_deps_str = cells[2].strip() if len(cells) > 2 else ""
            complexity_str = cells[3].strip() if len(cells) > 3 else ""
            reviewer = cells[4].strip() if len(cells) > 4 else ""
        else:
            # 4 columns: Task, Description, Hard deps, Reviewer
            hard_deps_str = cells[2].strip() if len(cells) > 2 else ""
            complexity_str = ""
            reviewer = cells[3].strip() if len(cells) > 3 else ""

        hard_deps = _parse_hard_deps(hard_deps_str)
        complexity = _parse_complexity(complexity_str) if complexity_str else TaskComplexity.UNSET

        task = Task(
            id=task_id,
            title=description,
            status=TaskStatus.PENDING,
            complexity=complexity,
            what="",
            prerequisite="",
            hard_deps=hard_deps,
            files=[],
            reviewer=reviewer,
            key_constraints=[],
            done_when="",
            phase_id="",
            subphase=None,
            raw_block="",
        )
        rows.append(task)

    return rows


# ---------------------------------------------------------------------------
# Completed tasks table
# ---------------------------------------------------------------------------


def _parse_completed_table(block: str) -> list[Task]:
    """Parse the ## Completed tasks 3-column pipe-delimited table.

    Columns: Task, Description, Commit message.
    """
    rows: list[Task] = []
    lines = block.split("\n")

    data_lines: list[str] = []
    found_header = False
    for line in lines:
        s = line.strip()
        if s.startswith("## Completed tasks"):
            continue
        if s.startswith("|") and not found_header:
            found_header = True
            continue
        if found_header:
            if s.startswith("|"):
                if _is_separator_row(s):
                    continue
                data_lines.append(s)
            elif not s:
                break

    for row_line in data_lines:
        cells = _parse_pipe_table_row(row_line)
        if len(cells) < 1:
            continue

        task_id = cells[0].strip() if len(cells) > 0 else ""
        description = cells[1].strip() if len(cells) > 1 else ""
        commit_msg = cells[2].strip() if len(cells) > 2 else ""

        task = Task(
            id=task_id,
            title=description,
            status=TaskStatus.COMPLETE,
            complexity=TaskComplexity.UNSET,
            what=commit_msg,
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
        rows.append(task)

    return rows


# ---------------------------------------------------------------------------
# Out of scope
# ---------------------------------------------------------------------------


def _parse_out_of_scope(block: str) -> str:
    """Parse the ## Out of scope block.

    Returns the block text verbatim (including the heading).
    """
    return block


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_session_file(path: Path) -> SessionState:
    """Parse a SESSIONSTATE.md file and return a SessionState dataclass.

    Uses a section-split approach per §9.3: splits file content on ---
    horizontal rule lines to identify section blocks, identifies each
    block by its ## heading text, and parses accordingly.
    """
    content = path.read_text(encoding="utf-8")

    preamble, sections = _split_sections(content)

    last_updated = _parse_last_updated(preamble)

    # Default values
    active_phase_name = ""
    active_phase_spec = ""
    active_task: Task | None = None
    active_task_raw = ""
    up_next: list[Task] = []
    completed: list[Task] = []
    out_of_scope_raw = ""

    for heading, block in sections:
        if heading.startswith("## Active phase"):
            active_phase_name, active_phase_spec = _parse_active_phase(block)
        elif heading.startswith("## Active task"):
            active_task, active_task_raw = _parse_active_task(block)
        elif heading.startswith("## Up next"):
            up_next = _parse_up_next_table(block)
        elif heading.startswith("## Completed tasks"):
            completed = _parse_completed_table(block)
        elif heading.startswith("## Out of scope"):
            out_of_scope_raw = _parse_out_of_scope(block)

    return SessionState(
        last_updated=last_updated,
        active_phase_name=active_phase_name,
        active_phase_spec=active_phase_spec,
        active_task=active_task,
        active_task_raw=active_task_raw,
        up_next=up_next,
        completed=completed,
        out_of_scope_raw=out_of_scope_raw,
    )
