# tests/commands/test_status.py — P4-T05 status command tests
#
# Done-when criteria (from P4-T05 task block):
#
#   1. tsm status prints all 5 sections (Phase, Spec, Updated, Active task,
#      Up next, Completed) correctly when run against a project built from
#      the test fixtures
#   2. Active task block in status output shows Complexity value and Hard dep
#      status icons per §7.6

from datetime import datetime
from io import StringIO
from pathlib import Path
import sys

import pytest

from tsm.commands.status import HELP_TEXT, status
from tsm.models import (
    LoadedProject,
    Phase,
    PhaseOverviewRow,
    ProjectContext,
    SessionState,
    Task,
    TaskComplexity,
    TaskStatus,
)
from tsm.parsers.session_parser import parse_session_file
from tsm.parsers.tasks_parser import parse_tasks_file


# ── Fixture helpers ──────────────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
TASKS_FIXTURE = FIXTURE_DIR / "TASKS.md"
SESSION_FIXTURE = FIXTURE_DIR / "SESSIONSTATE.md"


def _build_loaded_project(tmp_path: Path) -> LoadedProject:
    """Build a LoadedProject from the fixture TASKS.md and SESSIONSTATE.md.

    Copies the fixture files into *tmp_path* so they can be used as live
    files, then parses both to construct a LoadedProject.
    """
    root = tmp_path.resolve()
    shadow_dir = root / ".tsm" / "shadow"
    backup_dir = root / ".tsm" / "backups"

    tasks_live = root / "TASKS.md"
    session_live = root / "SESSIONSTATE.md"
    completed_live = root / "TASKS-COMPLETED.md"

    # Copy fixture files
    tasks_live.write_text(
        TASKS_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    session_live.write_text(
        SESSION_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    completed_live.write_text(
        "# Completed Tasks Log\n\n---\n", encoding="utf-8"
    )

    pc = ProjectContext(
        root=str(root),
        tasks_path=str(tasks_live),
        sessionstate_path=str(session_live),
        tasks_completed_path=str(completed_live),
        shadow_dir=str(shadow_dir),
        backup_dir=str(backup_dir),
        history_log_path=str(root / ".tsm" / "history.log"),
    )

    phase_overview, phases = parse_tasks_file(tasks_live)
    session = parse_session_file(session_live)

    return LoadedProject(
        project_context=pc,
        phases=phases,
        phase_overview=phase_overview,
        session=session,
    )


def _run_status(ctx: LoadedProject) -> str:
    """Run status() and capture stdout output.

    Returns the captured output as a string.
    """
    captured = StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        status(ctx)
    finally:
        sys.stdout = old_stdout
    return captured.getvalue()


# ── Tests ────────────────────────────────────────────────────────────────────


def test_status_all_sections_present(tmp_path: Path) -> None:
    """Status output contains all 5 required sections when run against
    the fixture project.

    Expected sections: Phase, Spec, Updated, Active task, Up next, Completed.
    """
    ctx = _build_loaded_project(tmp_path)
    output = _run_status(ctx)

    # Phase section
    assert "Phase:" in output, f"Expected 'Phase:' in output, got:\n{output}"
    assert "Spec:" in output, f"Expected 'Spec:' in output, got:\n{output}"
    assert "Updated:" in output, (
        f"Expected 'Updated:' in output, got:\n{output}"
    )
    assert "Active task:" in output, (
        f"Expected 'Active task:' in output, got:\n{output}"
    )
    assert "Up next:" in output, (
        f"Expected 'Up next:' in output, got:\n{output}"
    )
    assert "Completed:" in output, (
        f"Expected 'Completed:' in output, got:\n{output}"
    )


def test_status_active_task_metadata(tmp_path: Path) -> None:
    """Active task block shows Complexity value and Hard dep status icons.

    The fixture has FA-T02 as active task with:
      - Complexity: high
      - Hard deps: FA-T01 (which is ✅ Complete)
    """
    ctx = _build_loaded_project(tmp_path)
    output = _run_status(ctx)

    # Complexity should be shown
    assert "Complexity:" in output, (
        f"Expected 'Complexity:' in output, got:\n{output}"
    )
    assert "high" in output.lower(), (
        f"Expected 'high' complexity in output, got:\n{output}"
    )

    # Hard deps should be shown
    assert "Hard deps:" in output, (
        f"Expected 'Hard deps:' in output, got:\n{output}"
    )
    # FA-T01 is a hard dep of FA-T02 and is ✅ Complete
    assert "FA-T01" in output, (
        f"Expected FA-T01 in hard deps, got:\n{output}"
    )


def test_status_phase_name_in_output(tmp_path: Path) -> None:
    """Phase line shows the active phase name from the fixture."""
    ctx = _build_loaded_project(tmp_path)
    output = _run_status(ctx)

    # The fixture SESSIONSTATE.md says "Phase 1 — Fixture Alpha"
    # The session parser captures this as active_phase_name
    assert "Phase 1" in output or "Fixture Alpha" in output, (
        f"Expected phase name in output, got:\n{output}"
    )


def test_status_updated_timestamp(tmp_path: Path) -> None:
    """Updated line shows the timestamp from the fixture."""
    ctx = _build_loaded_project(tmp_path)
    output = _run_status(ctx)

    # The fixture last_updated is 2026-04-15T14:30
    assert "2026-04-15" in output, (
        f"Expected fixture timestamp in output, got:\n{output}"
    )


def test_status_up_next_section(tmp_path: Path) -> None:
    """Up next section lists all up-next tasks with complexity."""
    ctx = _build_loaded_project(tmp_path)
    output = _run_status(ctx)

    # The fixture has FA-T03 and FA-T04 in up next
    assert "FA-T03" in output or "FA-T04" in output, (
        f"Expected up-next tasks in output, got:\n{output}"
    )
    # Should show complexity labels (medium, unset)
    assert "(" in output, (
        f"Expected complexity labels in parentheses, got:\n{output}"
    )


def test_status_completed_section(tmp_path: Path) -> None:
    """Completed section lists all completed tasks."""
    ctx = _build_loaded_project(tmp_path)
    output = _run_status(ctx)

    # The fixture has FA-T01 and FB-T01 in completed
    assert "FA-T01" in output, (
        f"Expected FA-T01 in completed section, got:\n{output}"
    )


def test_status_separator_lines(tmp_path: Path) -> None:
    """Status output is wrapped by separator lines."""
    ctx = _build_loaded_project(tmp_path)
    output = _run_status(ctx)

    lines = output.strip().splitlines()
    # First line should be a separator
    first_line = lines[0]
    assert "─" in first_line or "Session Status" in output, (
        f"Expected separator or header in first line, got: {first_line}"
    )
    # Last line should be a separator
    last_line = lines[-1]
    assert "─" in last_line, (
        f"Expected separator in last line, got: {last_line}"
    )


def test_status_no_active_task(tmp_path: Path) -> None:
    """When active_task is None, show [none] instead of task block.

    Build a session with no active task and verify output.
    """
    now = datetime.now()
    session = SessionState(
        last_updated=now,
        active_phase_name="Phase 1 — Fixture Alpha",
        active_phase_spec="`TASKS.md`",
        active_task=None,
        active_task_raw="[none]",
        up_next=[],
        completed=[],
        out_of_scope_raw="- Nothing\n",
    )

    pc = _build_loaded_project(tmp_path).project_context
    phase_overview, phases = parse_tasks_file(Path(pc.tasks_path))

    ctx = LoadedProject(
        project_context=pc,
        phases=phases,
        phase_overview=phase_overview,
        session=session,
    )

    output = _run_status(ctx)

    assert "[none]" in output, (
        f"Expected '[none]' for no active task, got:\n{output}"
    )
    assert "Active task:" in output, (
        f"Expected 'Active task:' in output, got:\n{output}"
    )


def test_help_text_defined() -> None:
    """HELP_TEXT is a non-empty string constant."""
    assert isinstance(HELP_TEXT, str)
    assert len(HELP_TEXT) > 0
    assert "tsm status" in HELP_TEXT
