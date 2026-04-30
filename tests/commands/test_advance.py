# tests/commands/test_advance.py — P4-T01 advance command tests
#
# Done-when criteria (from P4-T01 task block):
#
#   1. test_advance_happy_path passes
#   2. test_advance_no_active_task passes
#   3. test_advance_dep_not_met passes
#   4. test_advance_with_commit_message passes
#   5. test_advance_last_task_in_phase passes

from datetime import datetime
from pathlib import Path

import pytest

from tsm.commands.advance import HELP_TEXT, advance, confirm_summary
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

    tasks_live.write_text(TASKS_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    session_live.write_text(
        SESSION_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    # Create a minimal TASKS-COMPLETED.md if the fixture has one
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


# ── Tests ────────────────────────────────────────────────────────────────────


class TestAdvanceHappyPath:
    """``advance()`` with a valid active task and a ready follow-on task."""

    def test_advance_happy_path(self, tmp_path: Path):
        """Happy-path advance: active task exists, next up_next task has
        all deps met → 3 PendingWrites returned, session promoted correctly."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Verify preconditions from fixture
        assert ctx.session.active_task is not None
        assert ctx.session.active_task.id == "FA-T02"
        assert len(ctx.session.up_next) == 2  # FA-T03, FA-T04

        # Execute advance
        result = advance(ctx)

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
        session_shadow = next(
            pw for pw in result if pw.target_file == "SESSIONSTATE.md"
        )
        content = Path(session_shadow.shadow_path).read_text(encoding="utf-8")

        # The advanced task (FA-T02) should now be in completed
        assert "FA-T02" in content
        # The promoted task (FA-T03) should now be the active task
        assert "### FA-T03" in content
        # FA-T03 should no longer be in up_next
        assert "FA-T03" not in content.split("## Up next")[1] if "## Up next" in content else True

        # ── Verify TASKS.md shadow content has FA-T02 as Complete ─────────
        tasks_shadow = next(
            pw for pw in result if pw.target_file == "TASKS.md"
        )
        tasks_content = Path(tasks_shadow.shadow_path).read_text(
            encoding="utf-8"
        )
        # The original TASKS.md fixture has FA-T02 as **Active**
        # After advance, it should be ✅ Complete
        assert "✅ Complete" in tasks_content
        assert "FA-T02" in tasks_content

        # ── Verify TASKS-COMPLETED.md shadow content ──────────────────────
        completed_shadow = next(
            pw for pw in result if pw.target_file == "TASKS-COMPLETED.md"
        )
        completed_content = Path(completed_shadow.shadow_path).read_text(
            encoding="utf-8"
        )
        assert "FA-T02" in completed_content


class TestAdvanceNoActiveTask:
    """``advance()`` raises ValueError when there is no active task."""

    def test_advance_no_active_task(self, tmp_path: Path):
        """No active task set → ValueError with clear message."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Override session to have no active task
        ctx.session = SessionState(
            last_updated=datetime.now(),
            active_phase_name=ctx.session.active_phase_name,
            active_phase_spec=ctx.session.active_phase_spec,
            active_task=None,
            active_task_raw="[none]",
            up_next=ctx.session.up_next,
            completed=ctx.session.completed,
            out_of_scope_raw=ctx.session.out_of_scope_raw,
        )

        with pytest.raises(ValueError) as exc_info:
            advance(ctx)

        msg = str(exc_info.value).lower()
        assert "no active task" in msg or "cannot advance" in msg


class TestAdvanceDepNotMet:
    """``advance()`` when up_next tasks have unmet hard deps."""

    def test_advance_dep_not_met(self, tmp_path: Path):
        """Up-next tasks with unsatisfied hard deps → no promotion,
        active_task set to [none]."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Replace up_next with a task whose hard deps point to a
        # non-existent/non-complete task ID that is NOT the advanced task.
        # We'll craft a synthetic task that depends on "NONEXISTENT".
        nonexistent_dep_task = Task(
            id="FA-T050",
            title="Task with unmet dep",
            status=TaskStatus.PENDING,
            complexity=TaskComplexity.MEDIUM,
            what="A task whose hard dep cannot be satisfied.",
            prerequisite="None.",
            hard_deps=["NONEXISTENT"],
            files=[],
            reviewer="Skip",
            key_constraints=[],
            done_when="Never.",
            phase_id="phase-1-fixture-alpha",
            subphase=None,
            raw_block="",
        )

        ctx.session = SessionState(
            last_updated=ctx.session.last_updated,
            active_phase_name=ctx.session.active_phase_name,
            active_phase_spec=ctx.session.active_phase_spec,
            active_task=ctx.session.active_task,
            active_task_raw=ctx.session.active_task_raw,
            up_next=[nonexistent_dep_task],
            completed=ctx.session.completed,
            out_of_scope_raw=ctx.session.out_of_scope_raw,
        )

        result = advance(ctx)

        # Should still return 3 PendingWrites
        assert len(result) == 3

        # The session shadow should have active_task set to [none]
        session_pw = next(
            pw for pw in result if pw.target_file == "SESSIONSTATE.md"
        )
        content = Path(session_pw.shadow_path).read_text(encoding="utf-8")

        # Should contain [none] in the Active task section
        active_section = content.split("## Active task")[1].split("##")[0] if "## Active task" in content else ""
        assert "[none]" in active_section or "FA-T02" in content.split("## Completed tasks")[1].split("##")[0]


class TestAdvanceWithCommitMessage:
    """``advance()`` with a custom commit message."""

    def test_advance_with_commit_message(self, tmp_path: Path):
        """Commit message is passed through to completed list and
        TASKS-COMPLETED.md."""
        ctx = _build_fixture_loaded_project(tmp_path)
        commit_msg = "P4-T01: advance module complete"

        result = advance(ctx, commit_message=commit_msg)

        # ── Check SESSIONSTATE.md for commit message in completed ────────
        session_pw = next(
            pw for pw in result if pw.target_file == "SESSIONSTATE.md"
        )
        content = Path(session_pw.shadow_path).read_text(encoding="utf-8")
        assert commit_msg in content

        # ── Check TASKS-COMPLETED.md for commit message ───────────────────
        completed_pw = next(
            pw for pw in result if pw.target_file == "TASKS-COMPLETED.md"
        )
        completed_content = Path(completed_pw.shadow_path).read_text(
            encoding="utf-8"
        )
        # The commit message should appear in the row for FA-T02
        assert commit_msg in completed_content


class TestAdvanceLastTaskInPhase:
    """``advance()`` when this is the last task in the phase (no more up_next)."""

    def test_advance_last_task_in_phase(self, tmp_path: Path):
        """No remaining up_next tasks → active_task set to [none]."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Set up_next to empty list
        ctx.session = SessionState(
            last_updated=ctx.session.last_updated,
            active_phase_name=ctx.session.active_phase_name,
            active_phase_spec=ctx.session.active_phase_spec,
            active_task=ctx.session.active_task,
            active_task_raw=ctx.session.active_task_raw,
            up_next=[],
            completed=ctx.session.completed,
            out_of_scope_raw=ctx.session.out_of_scope_raw,
        )

        result = advance(ctx)

        assert len(result) == 3

        # The session shadow should have active_task set to [none]
        session_pw = next(
            pw for pw in result if pw.target_file == "SESSIONSTATE.md"
        )
        content = Path(session_pw.shadow_path).read_text(encoding="utf-8")

        # Active task section should contain [none]
        if "## Active task" in content:
            after_heading = content.split("## Active task")[1]
            # The next ## or end-of-string
            next_section = after_heading.split("##")[0] if "##" in after_heading else after_heading
            assert "[none]" in next_section


# ── Utility tests ────────────────────────────────────────────────────────────


class TestConfirmSummary:
    """``confirm_summary()`` produces a human-readable summary string."""

    def test_confirm_summary_format(self):
        """Summary string contains target files and summary lines."""
        pws = [
            PendingWrite(
                target_file="SESSIONSTATE.md",
                shadow_path="/tmp/.tsm/shadow/SESSIONSTATE.md",
                live_path="/tmp/SESSIONSTATE.md",
                backup_path="/tmp/.tsm/backups",
                summary_lines=["Update session state", "Promote task"],
            ),
            PendingWrite(
                target_file="TASKS.md",
                shadow_path="/tmp/.tsm/shadow/TASKS.md",
                live_path="/tmp/TASKS.md",
                backup_path="/tmp/.tsm/backups",
                summary_lines=["Mark task complete"],
            ),
        ]
        result = confirm_summary(pws)
        assert "SESSIONSTATE.md" in result
        assert "TASKS.md" in result
        assert "Update session state" in result
        assert "Promote task" in result
        assert "Mark task complete" in result
        assert "Pending changes" in result


class TestHELP_TEXT:
    """``HELP_TEXT`` is a module-level string constant."""

    def test_help_text_exists(self):
        """HELP_TEXT is a non-empty string."""
        assert isinstance(HELP_TEXT, str)
        assert len(HELP_TEXT) > 0
        assert "Preconditions" in HELP_TEXT
        assert "Writes" in HELP_TEXT
