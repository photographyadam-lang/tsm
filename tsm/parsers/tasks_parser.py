# tsm/parsers/tasks_parser.py — 7-state line iterator state machine (P2-T02)
#
# Implements the core parse_tasks_file() function using the §9.2 state
# machine.  States:
#   PREAMBLE, PHASE_STRUCTURE_TABLE, BETWEEN_PHASES, PHASE_HEADER,
#   SUBPHASE_HEADER, TASK_BLOCK, DEP_GRAPH

from __future__ import annotations

import warnings
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from tsm.models import (
    Phase,
    PhaseOverviewRow,
    Task,
    TaskComplexity,
    TaskStatus,
    slugify_phase_name,
)


# ---------------------------------------------------------------------------
# Internal helpers — status / deps / files
# ---------------------------------------------------------------------------

_EMOJI_COMPLETE = "\u2705"
_EMOJI_LOCK = "\U0001F512"
_EMOJI_CROSS = "\u274C"


def _parse_status(value: str) -> TaskStatus:
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
    v = value.strip()
    if not v or v == "None" or v == "None." or v == "\u2014":
        return []
    return [dep.strip() for dep in v.split(",") if dep.strip()]


def _parse_files(value: str) -> list[str]:
    v = value.strip()
    if not v or v.lower() == "none":
        return []
    parts = [p.strip() for p in v.split(",")]
    result: list[str] = []
    for part in parts:
        if not part:
            continue
        # Strip (new) suffix BEFORE checking backticks, so that
        # `src/adapters.py`(new) is handled correctly.
        if part.endswith("(new)"):
            part = part[:-5].rstrip()
        if part.startswith("`") and part.endswith("`"):
            part = part[1:-1]
        result.append(part)
    return result


def _parse_complexity(value: str) -> TaskComplexity:
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


def _parse_task_heading(raw: str) -> tuple[str, str]:
    """Extract (task_id, title) from a ### ID · Title heading line."""
    rest = raw[3:].strip()  # strip "###" prefix
    if " \u00b7 " in rest:
        parts = rest.split(" \u00b7 ", 1)
        return parts[0].strip(), parts[1].strip()
    # Fallback: split on the middle-dot character variant
    if " \u2022 " in rest:
        parts = rest.split(" \u2022 ", 1)
        return parts[0].strip(), parts[1].strip()
    return rest, rest


def _split_field_line(line: str):
    """Split a '**FieldName:** value' line into (field_name, value).

    Uses string operations instead of regex to avoid issues with the
    Python 3.14 re v2.2.1 module's backtracking behaviour.

    The format is: '**FieldName:** value' — colon BEFORE the closing
    asterisks, so we search for ':**' (colon + ``**``).
    """
    # Must start with **
    if not line.startswith("**"):
        return None, None
    # Find the closing pattern ':**' (colon + **)
    idx = line.find(":**", 2)
    if idx == -1:
        return None, None
    field_name = line[2:idx]
    value = line[idx + 3:]  # skip past ":**"
    if value.startswith(" "):
        value = value[1:]
    return field_name, value


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


class _State(Enum):
    PREAMBLE = auto()
    PHASE_STRUCTURE_TABLE = auto()
    BETWEEN_PHASES = auto()
    PHASE_HEADER = auto()
    SUBPHASE_HEADER = auto()
    TASK_BLOCK = auto()
    DEP_GRAPH = auto()


def _new_task(
    task_id: str,
    title: str,
    phase_id: str,
    subphase: str | None,
) -> Task:
    return Task(
        id=task_id,
        title=title,
        status=TaskStatus.PENDING,
        complexity=TaskComplexity.UNSET,
        what="",
        prerequisite="",
        hard_deps=[],
        files=[],
        reviewer="",
        key_constraints=[],
        done_when="",
        phase_id=phase_id,
        subphase=subphase,
        raw_block="",
    )


def parse_tasks_file(path: Path) -> tuple[list[PhaseOverviewRow], list[Phase]]:
    content = path.read_text(encoding="utf-8")
    if "\r\n" in content:
        content = content.replace("\r\n", "\n")
    lines = content.split("\n")

    state = _State.PREAMBLE

    phase_overview: list[PhaseOverviewRow] = []
    phases: list[Phase] = []

    current_phase: Optional[Phase] = None
    current_task: Optional[Task] = None
    current_subphase: Optional[str] = None
    task_block_start: int = -1

    in_fence: bool = False
    dep_graph_buffer: list[str] = []

    what_lines: list[str] = []
    done_when_lines: list[str] = []

    # Tracks whether we've seen the **Key constraints:** field label;
    # subsequent "- " bullet lines are collected into task.key_constraints.
    in_key_constraints: bool = False

    def _flush_task() -> None:
        nonlocal current_task, task_block_start, what_lines, done_when_lines, in_key_constraints
        if current_task is None:
            return
        if what_lines:
            current_task.what = "\n".join(what_lines)
        if done_when_lines:
            current_task.done_when = "\n".join(done_when_lines)

        if task_block_start >= 0:
            current_task.raw_block = "\n".join(lines[task_block_start:i])

        current_task.subphase = current_subphase
        if current_phase is not None:
            current_phase.tasks.append(current_task)

        current_task = None
        task_block_start = -1
        what_lines = []
        done_when_lines = []
        in_key_constraints = False

    def _start_new_phase(heading_text: str) -> None:
        nonlocal current_phase, current_subphase, dep_graph_buffer, in_fence
        _flush_task()
        _flush_dep_graph()
        if current_phase is not None:
            phases.append(current_phase)
        existing_slugs = [p.id for p in phases]
        phase_id = slugify_phase_name(heading_text, existing_slugs)
        current_phase = Phase(
            id=phase_id, name=heading_text, status="Pending", description=""
        )
        current_subphase = None
        dep_graph_buffer = []
        in_fence = False

    def _flush_dep_graph() -> None:
        nonlocal dep_graph_buffer, in_fence
        if current_phase is not None and dep_graph_buffer:
            current_phase.dependency_graph_raw = "\n".join(dep_graph_buffer)
        dep_graph_buffer = []
        in_fence = False

    def _finalise_phase() -> None:
        nonlocal current_phase
        _flush_task()
        _flush_dep_graph()
        if current_phase is not None:
            phases.append(current_phase)
            current_phase = None

    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # ── PREAMBLE ──────────────────────────────────────────────────────
        if state == _State.PREAMBLE:
            if stripped == "---":
                state = _State.PHASE_STRUCTURE_TABLE
            i += 1

        # ── PHASE_STRUCTURE_TABLE ─────────────────────────────────────────
        elif state == _State.PHASE_STRUCTURE_TABLE:
            if stripped == "---":
                state = _State.BETWEEN_PHASES
                i += 1
                continue

            if stripped.startswith("|") and not stripped.startswith("|---"):
                cells = [c.strip() for c in stripped.split("|")]
                # Skip header row ("| Phase | Description | Status |")
                # and separator
                if len(cells) >= 4 and cells[1] and cells[1].lower() != "phase":
                    phase_name = cells[1].strip("* ")
                    desc = cells[2]
                    status = cells[3]
                    phase_overview.append(
                        PhaseOverviewRow(
                            phase_name=phase_name,
                            description=desc,
                            status=status,
                        )
                    )
            i += 1

        # ── BETWEEN_PHASES ────────────────────────────────────────────────
        elif state == _State.BETWEEN_PHASES:
            if stripped == "---":
                i += 1
                continue

            # H3 heading: could be a dependency graph
            if stripped.startswith("### "):
                heading_text = stripped[4:].strip()
                if "dependency graph" in heading_text.lower():
                    state = _State.DEP_GRAPH
                    dep_graph_buffer = []
                    in_fence = False
                    i += 1
                    continue
                # Any other ### heading in BETWEEN_PHASES is skipped
                i += 1
                continue

            if stripped.startswith("# ") and not stripped.startswith("## "):
                heading_text = raw[2:].strip()
                _start_new_phase(heading_text)
                state = _State.PHASE_HEADER
                i += 1
                continue

            if stripped.startswith("## ") and "Phase structure" not in stripped:
                current_subphase = raw[3:].strip()
                state = _State.SUBPHASE_HEADER
                i += 1
                continue

            i += 1

        # ── PHASE_HEADER ──────────────────────────────────────────────────
        elif state == _State.PHASE_HEADER:
            if stripped == "---":
                state = _State.BETWEEN_PHASES
                i += 1
                continue

            field_name, value = _split_field_line(stripped)
            if field_name == "Status":
                current_phase.status = value
                i += 1
                continue

            if stripped.startswith("# ") and not stripped.startswith("## "):
                heading_text = raw[2:].strip()
                _start_new_phase(heading_text)
                state = _State.PHASE_HEADER
                i += 1
                continue

            if stripped.startswith("## ") and "Phase structure" not in stripped:
                current_subphase = raw[3:].strip()
                state = _State.SUBPHASE_HEADER
                i += 1
                continue

            # Description line (non-blank, non-field)
            if stripped and not stripped.startswith("**"):
                if current_phase.description:
                    current_phase.description += "\n" + raw
                else:
                    current_phase.description = raw
            i += 1

        # ── SUBPHASE_HEADER ───────────────────────────────────────────────
        elif state == _State.SUBPHASE_HEADER:
            if stripped == "---":
                state = _State.BETWEEN_PHASES
                i += 1
                continue

            if stripped.startswith("### "):
                _flush_task()
                task_id, title = _parse_task_heading(raw)
                current_task = _new_task(
                    task_id,
                    title,
                    current_phase.id if current_phase else "",
                    current_subphase,
                )
                task_block_start = i
                what_lines = []
                done_when_lines = []
                in_key_constraints = False
                state = _State.TASK_BLOCK
                i += 1
                continue

            if stripped.startswith("# ") and not stripped.startswith("## "):
                heading_text = raw[2:].strip()
                _start_new_phase(heading_text)
                state = _State.PHASE_HEADER
                i += 1
                continue

            i += 1

        # ── TASK_BLOCK ────────────────────────────────────────────────────
        elif state == _State.TASK_BLOCK:
            # Structural boundaries first

            # H1 = new phase
            if stripped.startswith("# ") and not stripped.startswith("## "):
                _flush_task()
                heading_text = raw[2:].strip()
                _start_new_phase(heading_text)
                state = _State.PHASE_HEADER
                i += 1
                continue

            # H2 = subphase boundary
            if stripped.startswith("## ") and "Phase structure" not in stripped:
                _flush_task()
                current_subphase = raw[3:].strip()
                state = _State.SUBPHASE_HEADER
                i += 1
                continue

            # H3 = next task or dependency graph
            if stripped.startswith("### "):
                heading_text = stripped[4:].strip()
                if heading_text.lower().startswith("dependency graph"):
                    _flush_task()
                    state = _State.DEP_GRAPH
                    dep_graph_buffer = []
                    in_fence = False
                    i += 1
                    continue
                else:
                    _flush_task()
                    task_id, title = _parse_task_heading(raw)
                    current_task = _new_task(
                        task_id,
                        title,
                        current_phase.id if current_phase else "",
                        current_subphase,
                    )
                    task_block_start = i
                    what_lines = []
                    done_when_lines = []
                    in_key_constraints = False
                    i += 1
                    continue

            # --- divider → back to BETWEEN_PHASES
            if stripped == "---":
                _flush_task()
                state = _State.BETWEEN_PHASES
                i += 1
                continue

            # ── Field parsing ────────────────────────────────────────────
            if current_task is not None:
                _process_task_field_line(
                    raw,
                    current_task,
                    what_lines,
                    done_when_lines,
                    in_key_constraints,
                )
                in_key_constraints = _check_in_key_constraints(
                    stripped, in_key_constraints
                )
            i += 1

        # ── DEP_GRAPH ─────────────────────────────────────────────────────
        elif state == _State.DEP_GRAPH:
            if stripped == "---":
                _flush_dep_graph()
                state = _State.BETWEEN_PHASES
                i += 1
                continue

            if stripped.startswith("```"):
                in_fence = not in_fence
                dep_graph_buffer.append(raw)
                i += 1
                continue

            if stripped.startswith("# ") and not stripped.startswith("## "):
                _flush_dep_graph()
                heading_text = raw[2:].strip()
                _start_new_phase(heading_text)
                state = _State.PHASE_HEADER
                i += 1
                continue

            dep_graph_buffer.append(raw)
            i += 1

        else:
            i += 1

    # ── End of file ──────────────────────────────────────────────────────
    _finalise_phase()

    return phase_overview, phases


# ---------------------------------------------------------------------------
# Field-line processing helpers
# ---------------------------------------------------------------------------


def _check_in_key_constraints(stripped: str, current: bool) -> bool:
    """Return True if we are still inside a Key constraints block.

    We enter when we see **Key constraints:** and stay until we hit a
    non-blank, non-bullet line that is also not a `#` heading.
    """
    if stripped.startswith("**Key constraints:**"):
        return True
    if current:
        if stripped == "" or stripped.startswith("- "):
            return True
        return False
    return False


def _process_task_field_line(
    raw: str,
    task: Task,
    what_lines: list[str],
    done_when_lines: list[str],
    in_key_constraints: bool,
) -> None:
    """Parse a single line inside a TASK_BLOCK and update `task` in-place."""
    stripped = raw.strip()

    # Blank line — preserve in multi-line accumulators
    if not stripped:
        if what_lines:
            what_lines.append("")
        if done_when_lines:
            done_when_lines.append("")
        return

    # Try to split as a field line
    field, value = _split_field_line(stripped)

    if field is None:
        # Not a field label
        # Check for bullet points (key constraints continuation)
        if stripped.startswith("- ") and in_key_constraints:
            task.key_constraints.append(stripped[2:])
            return
        # Not a bullet — could be continuation of What or Done when
        if what_lines and not done_when_lines:
            what_lines.append(raw)
        elif done_when_lines:
            done_when_lines.append(raw)
        elif not what_lines and not done_when_lines:
            what_lines.append(raw)
        return

    # ---- Field processing ----

    if field == "Status":
        task.status = _parse_status(value)

    elif field == "Complexity":
        task.complexity = _parse_complexity(value)

    elif field == "What":
        # If we were accumulating done_when, flush it first
        if done_when_lines:
            task.done_when = "\n".join(done_when_lines)
            done_when_lines.clear()
        what_lines.append(value)

    elif field == "Prerequisite":
        task.prerequisite = value.strip()

    elif field == "Hard deps":
        task.hard_deps = _parse_hard_deps(value)

    elif field == "Files":
        task.files = _parse_files(value)

    elif field == "Reviewer":
        task.reviewer = value.strip()

    elif field == "Key constraints":
        val = value.strip()
        if val:
            if val.startswith("- "):
                task.key_constraints.append(val[2:])
            else:
                task.key_constraints.append(val)

    elif field == "Done when":
        done_when_lines.append(value)
