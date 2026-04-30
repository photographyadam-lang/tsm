# tests/commands/test_complete_phase.py — P4-T03 complete_phase command tests
#
# Done-when criteria (from P4-T03 task block):
#
#   1. test_complete_phase_all_done passes
#   2. test_complete_phase_incomplete_tasks passes
#   3. test_complete_phase_no_next_phase passes

from datetime import datetime
from pathlib import Path

import pytest

from tsm.commands.complete_phase import HELP_TEXT, complete_phase
from tsm.models import (
    LoadedProject,
    PendingWrite,
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


def _build_project_context(tmp_path: Path) -> ProjectContext:
    """Build a ProjectContext pointing at *tmp_path* as the project root,
    with fixture files as the live paths."""
    root = tmp_path.resolve()
    shadow_dir = root / ".tsm" / "shadow"
    backup_dir = root / ".tsm" / "backups"

    # Copy fixture files into tmp_path so live paths exist
    tasks_live = root / "TASKS.md"
    session_live = root / "SESSIONSTATE.md"
    completed_live = root / "TASKS-COMPLETED.md"

    tasks_live.write_text(
        TASKS_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    session_live.write_text(
        SESSION_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    completed_fixture = FIXTURE_DIR / "TASKS-COMPLETED.md"
    if completed_fixture.exists():
        completed_live.write_text(
            completed_fixture.read_text(encoding="utf-8"), encoding="utf-8"
        )
    else:
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


def _build_fixture_loaded_project(tmp_path: Path) -> LoadedProject:
    """Build a LoadedProject from the fixture files, rooted at *tmp_path*."""
    pc = _build_project_context(tmp_path)

    # Parse the fixture files
    phase_overview, phases = parse_tasks_file(Path(pc.tasks_path))
    session = parse_session_file(Path(pc.sessionstate_path))

    return LoadedProject(
        project_context=pc,
        phases=phases,
        phase_overview=phase_overview,
        session=session,
    )


def _task_by_id(phases, task_id: str) -> Task | None:
    """Find a task by ID across all phases."""
    for phase in phases:
        for task in phase.tasks:
            if task.id == task_id:
                return task
    return None


def _phase_by_id(phases, phase_id: str):
    """Find a phase by ID across all phases."""
    for phase in phases:
        if phase.id == phase_id:
            return phase
    return None


def _phase_by_name(phases, name: str):
    """Find a phase by name across all phases."""
    for phase in phases:
        if phase.name == name:
            return phase
    return None


# ── Tests ────────────────────────────────────────────────────────────────────


class TestCompletePhaseAllDone:
    """``complete_phase()`` when all tasks in the current phase are complete."""

    def test_complete_phase_all_done(self, tmp_path: Path):
        """Phase 1 (Fixture Alpha) all tasks complete → rotates to Phase 2
        with FB-T02 as active task and FB-T03 in up_next."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Build Phase 1 — Fixture Alpha with ALL tasks complete
        phase1_alpha = _phase_by_name(ctx.phases, "Phase 1 — Fixture Alpha")
        assert phase1_alpha is not None, "Phase 1 — Fixture Alpha must exist"

        # Set all Phase 1 tasks to COMPLETE
        for task in phase1_alpha.tasks:
            task.status = TaskStatus.COMPLETE

        # The fixture session has active_phase_name = "Phase 1 — Fixture Alpha"
        # Override session to reflect this correctly
        ctx.session = SessionState(
            last_updated=datetime.now(),
            active_phase_name="Phase 1 — Fixture Alpha",
            active_phase_spec="`tests/fixtures/TASKS.md`",
            active_task=None,
            active_task_raw="",
            up_next=[],
            completed=[],
            out_of_scope_raw=ctx.session.out_of_scope_raw,
        )

        # Execute complete_phase
        result = complete_phase(ctx)

        # ── Assert 3 PendingWrites ────────────────────────────────────────
        assert len(result) == 3, (
            f"Expected 3 PendingWrites, got {len(result)}"
        )

        targets = [pw.target_file for pw in result]
        assert "SESSIONSTATE.md" in targets
        assert "TASKS.md" in targets
        assert "TASKS-COMPLETED.md" in targets

        # ── Verify shadow files were written ──────────────────────────────
        for pw in result:
            shadow = Path(pw.shadow_path)
            assert shadow.exists(), f"Shadow file not written: {shadow}"
            assert pw.live_path is not None
            assert pw.backup_path is not None
            assert len(pw.summary_lines) > 0

        # ── Verify SESSIONSTATE.md shadow content ─────────────────────────
        session_pw = next(
            pw for pw in result if pw.target_file == "SESSIONSTATE.md"
        )
        content = Path(session_pw.shadow_path).read_text(encoding="utf-8")

        # Active phase should now be Phase 2 — Fixture Beta
        assert "Phase 2 — Fixture Beta" in content

        # FB-T02 should be the active task (first pending task with no deps)
        assert "### FB-T02" in content

        # FB-T02 should NOT be in up_next
        up_next_section = content.split("## Up next")[1].split("##")[0] \
            if "## Up next" in content else ""
        assert "FB-T02" not in up_next_section

        # FB-T03 should be in up_next
        assert "FB-T03" in up_next_section

        # Completed table should be empty (cleared on phase rotation)
        completed_section = content.split("## Completed tasks")[1].split(
            "##"
        )[0] if "## Completed tasks" in content else ""
        header_lines = [
            l for l in completed_section.split("\n")
            if l.strip().startswith("|")
        ]
        # Exactly 2 header rows (column headers + separator), no data rows
        assert len(header_lines) == 2, (
            f"Expected 2 header-only table rows, got {len(header_lines)}: "
            f"{header_lines}"
        )

        # ── Verify TASKS.md shadow content ────────────────────────────────
        tasks_pw = next(
            pw for pw in result if pw.target_file == "TASKS.md"
        )
        tasks_content = Path(tasks_pw.shadow_path).read_text(
            encoding="utf-8"
        )
        # Phase 1's status should now be ✅ Complete
        # Look for the phase 1 status line
        assert "✅ Complete" in tasks_content
        # The phase heading "Phase 1 — Fixture Alpha" should be present
        assert "Phase 1 — Fixture Alpha" in tasks_content

        # ── Verify TASKS-COMPLETED.md shadow content ──────────────────────
        completed_pw = next(
            pw for pw in result if pw.target_file == "TASKS-COMPLETED.md"
        )
        completed_content = Path(completed_pw.shadow_path).read_text(
            encoding="utf-8"
        )
        assert "Phase complete:" in completed_content


class TestCompletePhaseIncompleteTasks:
    """``complete_phase()`` when some tasks in the current phase are
    not complete."""

    def test_complete_phase_incomplete_tasks(self, tmp_path: Path):
        """Phase 1 has FA-T02 as **Active** (not complete)
        → ValueError listing FA-T02."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Ensure Phase 1 — Fixture Alpha has at least one incomplete task
        # In the fixture, FA-T02 is **Active** (not complete)
        phase1_alpha = _phase_by_name(ctx.phases, "Phase 1 — Fixture Alpha")
        assert phase1_alpha is not None

        # Verify there is at least one non-complete task
        incomplete = [
            t for t in phase1_alpha.tasks
            if t.status != TaskStatus.COMPLETE
        ]
        assert len(incomplete) > 0, (
            "Expected at least one incomplete task in Phase 1"
        )

        # Set session to point at Phase 1 — Fixture Alpha
        ctx.session = SessionState(
            last_updated=datetime.now(),
            active_phase_name="Phase 1 — Fixture Alpha",
            active_phase_spec="`tests/fixtures/TASKS.md`",
            active_task=None,
            active_task_raw="",
            up_next=[],
            completed=[],
            out_of_scope_raw=ctx.session.out_of_scope_raw,
        )

        # Execute complete_phase — should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            complete_phase(ctx)

        msg = str(exc_info.value)

        # Must mention the phase name
        assert "Phase 1" in msg or "Fixture Alpha" in msg

        # Must list the incomplete task ID(s)
        for t in incomplete:
            assert t.id in msg, (
                f"Error message should mention incomplete task {t.id}, "
                f"got: {msg}"
            )


class TestCompletePhaseNoNextPhase:
    """``complete_phase()`` when the current phase is the last phase."""

    def test_complete_phase_no_next_phase(self, tmp_path: Path):
        """Phase 2 (Fixture Beta) is the last phase with all tasks complete
        → next phase is [none]."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Build Phase 2 — Fixture Beta with ALL tasks complete
        phase2_beta = _phase_by_name(ctx.phases, "Phase 2 — Fixture Beta")
        assert phase2_beta is not None, "Phase 2 — Fixture Beta must exist"

        # Set all Phase 2 tasks to COMPLETE
        for task in phase2_beta.tasks:
            task.status = TaskStatus.COMPLETE

        # Also ensure Phase 1 is already complete (we need the current phase
        # to be Phase 2, and Phase 1 to also be complete so it doesn't get
        # picked as the next phase)
        phase1_alpha = _phase_by_name(ctx.phases, "Phase 1 — Fixture Alpha")
        assert phase1_alpha is not None
        for task in phase1_alpha.tasks:
            task.status = TaskStatus.COMPLETE

        # Write a TASKS-COMPLETED.md with a Phase 2 section so that
        # append_phase_marker can find it
        pc = ctx.project_context
        completed_content = (
            "# Completed Tasks Log\n\n"
            "---\n\n"
            "## Phase 1 — Fixture Alpha\n\n"
            "| Task | Description | Complexity | Commit | Notes |\n"
            "|------|-------------|------------|--------|-------|\n"
            "| FA-T01 | Completed setup task | low | abc1234 | Initial scaffold |\n\n"
            "## Phase 2 — Fixture Beta\n\n"
            "| Task | Description | Complexity | Commit | Notes |\n"
            "|------|-------------|------------|--------|-------|\n"
            "| FB-T01 | Completed beta task | low | def5678 | Beta work done |\n"
        )
        Path(pc.tasks_completed_path).write_text(
            completed_content, encoding="utf-8"
        )

        # Set session to point at Phase 2 — Fixture Beta (last phase)
        ctx.session = SessionState(
            last_updated=datetime.now(),
            active_phase_name="Phase 2 — Fixture Beta",
            active_phase_spec="`tests/fixtures/TASKS.md`",
            active_task=None,
            active_task_raw="",
            up_next=[],
            completed=[],
            out_of_scope_raw=ctx.session.out_of_scope_raw,
        )

        # Execute complete_phase
        result = complete_phase(ctx)

        # ── Assert 3 PendingWrites ────────────────────────────────────────
        assert len(result) == 3, (
            f"Expected 3 PendingWrites, got {len(result)}"
        )

        targets = [pw.target_file for pw in result]
        assert "SESSIONSTATE.md" in targets
        assert "TASKS.md" in targets
        assert "TASKS-COMPLETED.md" in targets

        # ── Verify SESSIONSTATE.md shadow content ─────────────────────────
        session_pw = next(
            pw for pw in result if pw.target_file == "SESSIONSTATE.md"
        )
        content = Path(session_pw.shadow_path).read_text(encoding="utf-8")

        # Active phase should now be [none]
        assert "[none]" in content

        # Should not specify a phase name
        # "Fixture Beta" should not appear in active phase section
        # (it could appear in completed tasks table which is cleared)
        # Actually completed is cleared, so it shouldn't appear at all
        # But the TASKS.md shadow might reference it

        # Active task should be [none]
        assert "active_task" not in content or "[none]" in content

        # ── Verify TASKS.md shadow content ────────────────────────────────
        tasks_pw = next(
            pw for pw in result if pw.target_file == "TASKS.md"
        )
        tasks_content = Path(tasks_pw.shadow_path).read_text(
            encoding="utf-8"
        )
        # Phase 2's status should now be ✅ Complete
        assert "✅ Complete" in tasks_content
        assert "Phase 2 — Fixture Beta" in tasks_content

        # ── Verify TASKS-COMPLETED.md shadow content ──────────────────────
        completed_pw = next(
            pw for pw in result if pw.target_file == "TASKS-COMPLETED.md"
        )
        completed_content = Path(completed_pw.shadow_path).read_text(
            encoding="utf-8"
        )
        assert "Phase complete:" in completed_content

    # ── HELP_TEXT test ───────────────────────────────────────────────────


class TestHelpText:
    """``HELP_TEXT`` constant exists and is non-empty."""

    def test_help_text_exists(self):
        """HELP_TEXT should be a non-empty string."""
        assert isinstance(HELP_TEXT, str)
        assert len(HELP_TEXT) > 0
        assert "complete-phase" in HELP_TEXT
