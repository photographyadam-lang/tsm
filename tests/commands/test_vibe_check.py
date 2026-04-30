# tests/commands/test_vibe_check.py — P4-T04 vibe_check command tests
#
# Done-when criteria (from P4-T04 task block):
#
#   1. test_vibe_check_clean passes
#   2. test_vibe_check_vc01_duplicate_id passes
#   3. test_vibe_check_vc02_dangling_dep passes
#   4. test_vibe_check_vc03_active_is_complete passes
#   5. test_vibe_check_vc05_unmet_dep_in_up_next passes
#   6. test_vibe_check_vc11_missing_field passes
#   7. test_vibe_check_vc13_unset_complexity_active passes
#   8. test_vibe_check_vc13_unset_complexity_up_next passes
#   9. test_vibe_check_vc13_suppressed_for_complete passes
#  10. test_vibe_check_vc12_datetime_comparison passes
#  11. test_vibe_check_vc12_same_day_no_warning passes

from datetime import datetime, timedelta
from pathlib import Path
from io import StringIO
import sys

import pytest

from tsm.commands.vibe_check import HELP_TEXT, vibe_check
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
from tsm.parsers.tasks_parser import parse_tasks_file


# ── Fixture helpers ──────────────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
TASKS_FIXTURE = FIXTURE_DIR / "TASKS.md"
TASKS_CLEAN_FIXTURE = FIXTURE_DIR / "TASKS_CLEAN.md"
TASKS_ERRORS_FIXTURE = FIXTURE_DIR / "TASKS_ERRORS.md"
SESSION_FIXTURE = FIXTURE_DIR / "SESSIONSTATE.md"


def _build_project_context(
    tmp_path: Path, tasks_fixture: Path
) -> ProjectContext:
    """Build a ProjectContext with *tasks_fixture* as the TASKS.md live file."""
    root = tmp_path.resolve()
    shadow_dir = root / ".tsm" / "shadow"
    backup_dir = root / ".tsm" / "backups"

    tasks_live = root / "TASKS.md"
    session_live = root / "SESSIONSTATE.md"
    completed_live = root / "TASKS-COMPLETED.md"

    # Copy the tasks fixture
    tasks_live.write_text(
        tasks_fixture.read_text(encoding="utf-8"), encoding="utf-8"
    )
    # Create a minimal session state file (content may be overwritten by tests)
    session_live.write_text(
        "*Last updated: 2026-04-15T14:30\n\n---\n\n## Active phase\n\nTest\n\n---\n\n## Active task\n\n[none]\n\n---\n\n## Up next\n\n| Task | Description | Hard deps | Complexity | Reviewer |\n|------|-------------|-----------|------------|----------|\n\n---\n\n## Out of scope\n\n- Nothing\n",
        encoding="utf-8",
    )
    # Create an empty TASKS-COMPLETED.md
    completed_live.write_text(
        "# Completed Tasks Log\n\n---\n", encoding="utf-8"
    )

    return ProjectContext(
        root=str(root),
        tasks_path=str(tasks_live),
        sessionstate_path=str(session_live),
        tasks_completed_path=str(completed_live),
        shadow_dir=str(shadow_dir),
        backup_dir=str(backup_dir),
        history_log_path=str(root / ".tsm" / "history.log"),
    )


def _tasks_only_loaded_project(
    tmp_path: Path, tasks_fixture: Path, session: SessionState
) -> LoadedProject:
    """Build a LoadedProject from a tasks fixture file and a given SessionState.

    Parses the tasks fixture to populate phases and phase_overview.
    Uses :session: as the session state directly.
    """
    pc = _build_project_context(tmp_path, tasks_fixture)
    phase_overview, phases = parse_tasks_file(Path(pc.tasks_path))

    return LoadedProject(
        project_context=pc,
        phases=phases,
        phase_overview=phase_overview,
        session=session,
    )


def _run_vibe_check(ctx: LoadedProject) -> str:
    """Run vibe_check and capture stdout output.

    Returns the captured output as a string.
    """
    captured = StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        vibe_check(ctx)
    finally:
        sys.stdout = old_stdout
    return captured.getvalue()


def _task_by_id(phases, task_id: str) -> Task | None:
    """Find a task by ID across all phases."""
    for phase in phases:
        for task in phase.tasks:
            if task.id == task_id:
                return task
    return None


# ── Tests ────────────────────────────────────────────────────────────────────


def test_vibe_check_clean(tmp_path: Path) -> None:
    """Clean fixture → 0 errors, 0 warnings."""
    # Build a clean session matching TASKS_CLEAN.md
    # Active task: CA-T01 (Pending, complexity low, no deps)
    # Up next: CA-T02 (Pending, complexity low, no deps)
    # Last updated: now (same day, no VC-12)
    now = datetime.now()
    active_task = Task(
        id="CA-T01",
        title="First clean task",
        status=TaskStatus.PENDING,
        complexity=TaskComplexity.LOW,
        what="The first task in a clean fixture file.",
        prerequisite="None.",
        hard_deps=[],
        files=["src/alpha.py"],
        reviewer="Skip",
        key_constraints=[],
        done_when="- Parser loads without warnings or errors",
        phase_id="phase-1-clean-alpha",
        subphase=None,
        raw_block="",
    )
    up_next_task = Task(
        id="CA-T02",
        title="Second clean task",
        status=TaskStatus.PENDING,
        complexity=TaskComplexity.LOW,
        what="The second task in a clean fixture file.",
        prerequisite="None.",
        hard_deps=[],
        files=["src/alpha/utils.py"],
        reviewer="Skip",
        key_constraints=[],
        done_when="- Both tasks parse with status Pending",
        phase_id="phase-1-clean-alpha",
        subphase=None,
        raw_block="",
    )

    session = SessionState(
        last_updated=now,
        active_phase_name="Phase 1 — Clean Alpha",
        active_phase_spec="`TASKS.md`",
        active_task=active_task,
        active_task_raw="",
        up_next=[up_next_task],
        completed=[],
        out_of_scope_raw="- Nothing\n",
    )

    ctx = _tasks_only_loaded_project(tmp_path, TASKS_CLEAN_FIXTURE, session)
    output = _run_vibe_check(ctx)

    # Should contain "No errors" and "No warnings"
    assert "No errors" in output, f"Expected no errors, got:\n{output}"
    assert "No warnings" in output, f"Expected no warnings, got:\n{output}"


def test_vibe_check_vc01_duplicate_id(tmp_path: Path) -> None:
    """Two tasks with same ID → VC-01 error."""
    now = datetime.now()
    session = SessionState(
        last_updated=now,
        active_phase_name="Phase 1 — Error Alpha",
        active_phase_spec="`TASKS.md`",
        active_task=None,
        active_task_raw="[none]",
        up_next=[],
        completed=[],
        out_of_scope_raw="- Nothing\n",
    )

    ctx = _tasks_only_loaded_project(tmp_path, TASKS_ERRORS_FIXTURE, session)
    output = _run_vibe_check(ctx)

    assert "VC-01" in output, f"Expected VC-01, got:\n{output}"
    assert "Duplicate task ID" in output, f"Expected duplicate message, got:\n{output}"
    assert "ER-T01" in output, f"Expected ER-T01 in output, got:\n{output}"


def test_vibe_check_vc02_dangling_dep(tmp_path: Path) -> None:
    """Dep pointing to nonexistent ID → VC-02 error."""
    now = datetime.now()
    session = SessionState(
        last_updated=now,
        active_phase_name="Phase 1 — Error Alpha",
        active_phase_spec="`TASKS.md`",
        active_task=None,
        active_task_raw="[none]",
        up_next=[],
        completed=[],
        out_of_scope_raw="- Nothing\n",
    )

    ctx = _tasks_only_loaded_project(tmp_path, TASKS_ERRORS_FIXTURE, session)
    output = _run_vibe_check(ctx)

    assert "VC-02" in output, f"Expected VC-02, got:\n{output}"
    assert "ER-NONEXIST" in output, f"Expected ER-NONEXIST in output, got:\n{output}"


def test_vibe_check_vc03_active_is_complete(tmp_path: Path) -> None:
    """Active task already complete in TASKS.md → VC-03 error.

    Use the main TASKS.md fixture where FA-T01 has status ✅ Complete.
    Set FA-T01 as the active task in session.
    """
    now = datetime.now()
    active_task = Task(
        id="FA-T01",
        title="Completed setup task",
        status=TaskStatus.COMPLETE,
        complexity=TaskComplexity.LOW,
        what="Single-line what field",
        prerequisite="None.",
        hard_deps=[],
        files=[],
        reviewer="Skip",
        key_constraints=[],
        done_when="- Parser extracts all fields correctly",
        phase_id="phase-1-fixture-alpha",
        subphase=None,
        raw_block="",
    )

    session = SessionState(
        last_updated=now,
        active_phase_name="Phase 1 — Fixture Alpha",
        active_phase_spec="`TASKS.md`",
        active_task=active_task,
        active_task_raw="",
        up_next=[],
        completed=[],
        out_of_scope_raw="- Nothing\n",
    )

    ctx = _tasks_only_loaded_project(tmp_path, TASKS_FIXTURE, session)
    output = _run_vibe_check(ctx)

    assert "VC-03" in output, f"Expected VC-03, got:\n{output}"
    assert "FA-T01" in output, f"Expected FA-T01 in output, got:\n{output}"
    assert "Complete" in output, f"Expected Complete status reference, got:\n{output}"


def test_vibe_check_vc05_unmet_dep_in_up_next(tmp_path: Path) -> None:
    """Up next task with unmet dep → VC-05 warning.

    Use the main TASKS.md fixture.
    Set up_next to include FA-T02 which has hard dep FA-T01 (which is ✅ Complete,
    so that one is met). Instead, use a session with a custom up-next task that
    has a dep on a task that is NOT complete.
    """
    now = datetime.now()

    # FA-T04 (Blocked, complexity unset) has hard deps: None.
    # Let's create an Up next task with a dep on a non-complete task.
    # FA-T03 depends on FA-T02 (which is **Active** — not complete)
    up_next_task = Task(
        id="FA-T03",
        title="Pending task with multi-line done-when",
        status=TaskStatus.PENDING,
        complexity=TaskComplexity.MEDIUM,
        what="Single-line what",
        prerequisite="FA-T02 complete.",
        hard_deps=["FA-T02"],  # FA-T02 is **Active**, not Complete
        files=["See spec §8", "config/settings.json"],
        reviewer="Skip",
        key_constraints=[],
        done_when="- First criterion line",
        phase_id="phase-1-fixture-alpha",
        subphase=None,
        raw_block="",
    )

    session = SessionState(
        last_updated=now,
        active_phase_name="Phase 1 — Fixture Alpha",
        active_phase_spec="`TASKS.md`",
        active_task=None,
        active_task_raw="[none]",
        up_next=[up_next_task],
        completed=[],
        out_of_scope_raw="- Nothing\n",
    )

    ctx = _tasks_only_loaded_project(tmp_path, TASKS_FIXTURE, session)
    output = _run_vibe_check(ctx)

    assert "VC-05" in output, f"Expected VC-05, got:\n{output}"
    assert "FA-T03" in output, f"Expected FA-T03 in output, got:\n{output}"
    assert "FA-T02" in output, f"Expected FA-T02 ref in output, got:\n{output}"


def test_vibe_check_vc11_missing_field(tmp_path: Path) -> None:
    """Task missing required field → VC-11 warning.

    FB-T02 in the main fixture intentionally omits Key constraints,
    but that's valid.  We need a task that's genuinely missing a required
    field.  FA-T04 has an empty Files field (parsed as []).
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

    ctx = _tasks_only_loaded_project(tmp_path, TASKS_FIXTURE, session)
    output = _run_vibe_check(ctx)

    # FA-T04 has empty Files field (parsed as []) and potentially empty
    # prerequisite ("None." has content, so that's fine).
    # Actually FA-T04 has:
    #   **Files:**
    #   (blank line)
    # So files = []
    assert "VC-11" in output, f"Expected VC-11, got:\n{output}"


def test_vibe_check_vc13_unset_complexity_active(tmp_path: Path) -> None:
    """Active task has complexity unset → VC-13 warning.

    Use the main TASKS.md fixture. FA-T04 has complexity: unset.
    Set FA-T04 as active task.
    """
    now = datetime.now()
    active_task = Task(
        id="FA-T04",
        title="Blocked task with None dot hard deps",
        status=TaskStatus.BLOCKED,
        complexity=TaskComplexity.UNSET,
        what="Single-line description for a blocked task",
        prerequisite="None.",
        hard_deps=[],
        files=[],
        reviewer="Skip",
        key_constraints=[],
        done_when="- Status token 🔒 Blocked is recognised",
        phase_id="phase-1-fixture-alpha",
        subphase=None,
        raw_block="",
    )

    session = SessionState(
        last_updated=now,
        active_phase_name="Phase 1 — Fixture Alpha",
        active_phase_spec="`TASKS.md`",
        active_task=active_task,
        active_task_raw="",
        up_next=[],
        completed=[],
        out_of_scope_raw="- Nothing\n",
    )

    ctx = _tasks_only_loaded_project(tmp_path, TASKS_FIXTURE, session)
    output = _run_vibe_check(ctx)

    assert "VC-13" in output, f"Expected VC-13, got:\n{output}"
    assert "FA-T04" in output, f"Expected FA-T04 in output, got:\n{output}"
    assert "unset" in output, f"Expected 'unset' in output, got:\n{output}"


def test_vibe_check_vc13_unset_complexity_up_next(tmp_path: Path) -> None:
    """Up next task has complexity unset → VC-13 warning.

    Use the main TASKS.md fixture. FA-T04 has complexity: unset.
    Set FA-T04 as an up-next task.
    """
    now = datetime.now()
    up_next_task = Task(
        id="FA-T04",
        title="Blocked task with None dot hard deps",
        status=TaskStatus.BLOCKED,
        complexity=TaskComplexity.UNSET,
        what="Single-line description for a blocked task",
        prerequisite="None.",
        hard_deps=[],
        files=[],
        reviewer="Skip",
        key_constraints=[],
        done_when="- Status token 🔒 Blocked is recognised",
        phase_id="phase-1-fixture-alpha",
        subphase=None,
        raw_block="",
    )

    session = SessionState(
        last_updated=now,
        active_phase_name="Phase 1 — Fixture Alpha",
        active_phase_spec="`TASKS.md`",
        active_task=None,
        active_task_raw="[none]",
        up_next=[up_next_task],
        completed=[],
        out_of_scope_raw="- Nothing\n",
    )

    ctx = _tasks_only_loaded_project(tmp_path, TASKS_FIXTURE, session)
    output = _run_vibe_check(ctx)

    assert "VC-13" in output, f"Expected VC-13, got:\n{output}"
    assert "FA-T04" in output, f"Expected FA-T04 in output, got:\n{output}"
    assert "Up next" in output, f"Expected 'Up next' in output, got:\n{output}"


def test_vibe_check_vc13_suppressed_for_complete(tmp_path: Path) -> None:
    """Completed task with unset complexity → no VC-13 warning.

    Only active and up-next tasks trigger VC-13.  A completed task
    in the completed list with UNSET complexity should not warn.
    """
    now = datetime.now()

    # Active task with complexity set (no VC-13 on this one)
    active_task = Task(
        id="FA-T01",
        title="Completed setup task",
        status=TaskStatus.COMPLETE,
        complexity=TaskComplexity.LOW,
        what="Single-line what field",
        prerequisite="None.",
        hard_deps=[],
        files=[],
        reviewer="Skip",
        key_constraints=[],
        done_when="- Parser extracts all fields correctly",
        phase_id="phase-1-fixture-alpha",
        subphase=None,
        raw_block="",
    )

    # Completed list has a task with UNSET — should NOT trigger VC-13
    completed_with_unset = Task(
        id="XXX-T00",
        title="Past completed task with unset complexity",
        status=TaskStatus.COMPLETE,
        complexity=TaskComplexity.UNSET,
        what="Already done",
        prerequisite="None.",
        hard_deps=[],
        files=[],
        reviewer="Skip",
        key_constraints=[],
        done_when="- Done",
        phase_id="phase-1-fixture-alpha",
        subphase=None,
        raw_block="",
    )

    session = SessionState(
        last_updated=now,
        active_phase_name="Phase 1 — Fixture Alpha",
        active_phase_spec="`TASKS.md`",
        active_task=active_task,
        active_task_raw="",
        up_next=[],
        completed=[completed_with_unset],
        out_of_scope_raw="- Nothing\n",
    )

    ctx = _tasks_only_loaded_project(tmp_path, TASKS_FIXTURE, session)
    output = _run_vibe_check(ctx)

    # Should NOT contain VC-13
    assert "VC-13" not in output, (
        f"Expected NO VC-13 for completed task, got:\n{output}"
    )


def test_vibe_check_vc12_datetime_comparison(tmp_path: Path) -> None:
    """Last updated 8 days ago → VC-12 warning."""
    now = datetime.now()
    eight_days_ago = now - timedelta(days=8)

    session = SessionState(
        last_updated=eight_days_ago,
        active_phase_name="Phase 1 — Fixture Alpha",
        active_phase_spec="`TASKS.md`",
        active_task=None,
        active_task_raw="[none]",
        up_next=[],
        completed=[],
        out_of_scope_raw="- Nothing\n",
    )

    ctx = _tasks_only_loaded_project(tmp_path, TASKS_FIXTURE, session)
    output = _run_vibe_check(ctx)

    assert "VC-12" in output, f"Expected VC-12, got:\n{output}"
    assert "8 days" in output or "days ago" in output, (
        f"Expected days-ago message, got:\n{output}"
    )


def test_vibe_check_vc12_same_day_no_warning(tmp_path: Path) -> None:
    """Last updated earlier today → no VC-12 warning."""
    now = datetime.now()
    earlier_today = now - timedelta(hours=2)

    session = SessionState(
        last_updated=earlier_today,
        active_phase_name="Phase 1 — Fixture Alpha",
        active_phase_spec="`TASKS.md`",
        active_task=None,
        active_task_raw="[none]",
        up_next=[],
        completed=[],
        out_of_scope_raw="- Nothing\n",
    )

    ctx = _tasks_only_loaded_project(tmp_path, TASKS_FIXTURE, session)
    output = _run_vibe_check(ctx)

    assert "VC-12" not in output, (
        f"Expected NO VC-12 for same-day update, got:\n{output}"
    )
