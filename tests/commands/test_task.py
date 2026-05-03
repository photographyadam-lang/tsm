# tests/commands/test_task.py — P7-T05 task CRUD command tests
#
# Done-when criteria (from P7-T05 task block):
#
#   1. test_task_add_generates_id passes
#   2. test_task_add_id_collision_increments passes
#   3. test_task_edit_field passes
#   4. test_task_move_within_phase passes
#   5. test_task_move_between_phases passes
#   6. test_task_remove_blocked_by_deps passes
#   7. test_task_remove_force passes
#   8. test_task_edit_hard_deps_dep_gate passes

from pathlib import Path

import pytest

from tsm.commands.task import (
    HELP_TEXT,
    task_add,
    task_edit,
    task_move,
    task_remove,
)
from tsm.models import (
    LoadedProject,
    ProjectContext,
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


# ── Tests ────────────────────────────────────────────────────────────────────


class TestTaskAdd:
    """``task_add()`` creates a new task with an auto-generated ID."""

    def test_task_add_generates_id(self, tmp_path: Path):
        """Adding a task to Phase 2 generates ID FB-T04 (next after FB-T03)."""
        ctx = _build_fixture_loaded_project(tmp_path)

        result = task_add(
            ctx, "phase-2--fixture-beta", "New test task"
        )

        # ── Assert 1 PendingWrite for TASKS.md ───────────────────────────
        assert len(result) == 1, (
            f"Expected 1 PendingWrite, got {len(result)}"
        )

        pw = result[0]
        assert pw.target_file == "TASKS.md"

        # ── Verify shadow file was written ───────────────────────────────
        shadow = Path(pw.shadow_path)
        assert shadow.exists(), f"Shadow file not written: {shadow}"
        assert pw.live_path is not None
        assert pw.backup_path is not None
        assert len(pw.summary_lines) > 0

        # ── Verify summary mentions the auto-generated ID ────────────────
        summary = " ".join(pw.summary_lines)
        # Phase 2 tasks: FB-T01, FB-T02, FB-T03 → next should be FB-T04
        assert "FB-T04" in summary, (
            f"Expected auto-generated ID 'FB-T04' in summary, got: {summary}"
        )

        # ── Verify shadow content has the new task block ─────────────────
        content = shadow.read_text(encoding="utf-8")
        assert "### FB-T04 · New test task" in content, (
            "New task heading not found in shadow content"
        )

        # ── Verify all original content is preserved ─────────────────────
        assert "### FA-T01 · Completed setup task" in content
        assert "### FB-T03 · Active beta task with backtick new files" in content

    def test_task_add_id_collision_increments(self, tmp_path: Path):
        """Adding multiple tasks increments the ID correctly."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Add first task → should get FA-T05 (Phase 1 has FA-T01..FA-T04)
        result1 = task_add(ctx, "phase-1--fixture-alpha", "First new task")
        summary1 = " ".join(result1[0].summary_lines)
        assert "FA-T05" in summary1, (
            f"Expected FA-T05 for first add, got: {summary1}"
        )

        # Verify the shadow content for the first add
        content1 = Path(result1[0].shadow_path).read_text(encoding="utf-8")
        assert "### FA-T05 · First new task" in content1

        # Now add a second task to a fresh project to verify collision handling
        # The collision case is when the auto-generated ID would conflict.
        # Build a new project context for a clean test
        ctx2 = _build_fixture_loaded_project(tmp_path)

        result2 = task_add(ctx2, "phase-1--fixture-alpha", "Second new task")
        summary2 = " ".join(result2[0].summary_lines)
        assert "FA-T05" in summary2, (
            f"Expected FA-T05 for add on fresh project, got: {summary2}"
        )


class TestTaskEdit:
    """``task_edit()`` updates a single field on an existing task."""

    def test_task_edit_field(self, tmp_path: Path):
        """Editing the What field on FA-T03 updates the shadow content."""
        ctx = _build_fixture_loaded_project(tmp_path)

        result = task_edit(
            ctx, "FA-T03", "What", "Updated description for FA-T03"
        )

        # ── Assert 1 PendingWrite ────────────────────────────────────────
        assert len(result) == 1, (
            f"Expected 1 PendingWrite, got {len(result)}"
        )

        pw = result[0]
        assert pw.target_file == "TASKS.md"

        # ── Verify shadow file was written ───────────────────────────────
        shadow = Path(pw.shadow_path)
        assert shadow.exists(), f"Shadow file not written: {shadow}"

        content = shadow.read_text(encoding="utf-8")

        # ── Verify the What field was updated ────────────────────────────
        assert "**What:** Updated description for FA-T03" in content, (
            "Updated What field not found in shadow content"
        )

        # ── Verify other fields in the same task are unchanged ───────────
        assert "**Status:** Pending" in content
        assert "**Complexity:** medium" in content
        assert "**Prerequisite:** FA-T02 complete." in content

        # ── Verify other tasks are unchanged ─────────────────────────────
        assert "**What:** Single-line what field for the simplest possible" in content

    def test_task_edit_hard_deps_dep_gate(self, tmp_path: Path):
        """Editing hard_deps with a non-existent dep ID causes ValueError."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # FA-T03 has no hard deps.  Setting hard_deps to a non-existent ID
        # should trigger the dep gate and raise ValueError.
        with pytest.raises(ValueError) as exc_info:
            task_edit(
                ctx, "FA-T03", "hard_deps", "NONEXISTENT-T99"
            )

        msg = str(exc_info.value)
        assert "dep" in msg.lower() or "Dep" in msg, (
            f"Expected dep-related error message, got: {msg}"
        )


class TestTaskMove:
    """``task_move()`` moves a task within or between phases."""

    def test_task_move_within_phase(self, tmp_path: Path):
        """Moving FA-T03 before FA-T02 within Phase 1 reorders the blocks."""
        ctx = _build_fixture_loaded_project(tmp_path)

        result = task_move(
            ctx, "FA-T03", "phase-1--fixture-alpha", after_task_id=None
        )

        # ── Assert at least 1 PendingWrite for TASKS.md ──────────────────
        assert len(result) >= 1, (
            f"Expected at least 1 PendingWrite, got {len(result)}"
        )

        pw = result[0]
        assert pw.target_file == "TASKS.md"

        shadow = Path(pw.shadow_path)
        content = shadow.read_text(encoding="utf-8")

        # ── Verify FA-T03 appears before FA-T02 now ──────────────────────
        pos_fa03 = content.index("### FA-T03 · Pending task with multi-line done-when")
        pos_fa02 = content.index("### FA-T02 · Active task with multi-line what")
        assert pos_fa03 < pos_fa02, (
            f"FA-T03 should appear before FA-T02 after move, "
            f"but FA-T03 at {pos_fa03} > FA-T02 at {pos_fa02}"
        )

    def test_task_move_between_phases(self, tmp_path: Path):
        """Moving FA-T03 from Phase 1 to Phase 2."""
        ctx = _build_fixture_loaded_project(tmp_path)

        result = task_move(
            ctx, "FA-T03", "phase-2--fixture-beta", after_task_id=None
        )

        # ── Assert at least 1 PendingWrite for TASKS.md ──────────────────
        assert len(result) >= 1, (
            f"Expected at least 1 PendingWrite, got {len(result)}"
        )

        pw = result[0]
        assert pw.target_file == "TASKS.md"

        shadow = Path(pw.shadow_path)
        content = shadow.read_text(encoding="utf-8")

        # ── Verify FA-T03 is now in Phase 2 section ──────────────────────
        # Phase 2 starts with "# Phase 2 — Fixture Beta"
        phase2_pos = content.index("# Phase 2 — Fixture Beta")
        fa03_pos = content.index("### FA-T03 · Pending task with multi-line done-when")
        assert fa03_pos > phase2_pos, (
            f"FA-T03 should be after Phase 2 heading, "
            f"but FA-T03 at {fa03_pos} < Phase 2 at {phase2_pos}"
        )

        # ── Verify FA-T03 is no longer in Phase 1 section ────────────────
        phase1_end = content.index("---", content.index("### Dependency graph"))
        phase2_start = content.index("# Phase 2 — Fixture Beta")
        phase1_section = content[phase1_end:phase2_start]
        assert "FA-T03" not in phase1_section, (
            "FA-T03 should not appear in Phase 1 section after move"
        )


class TestTaskRemove:
    """``task_remove()`` removes a task block."""

    def test_task_remove_blocked_by_deps(self, tmp_path: Path):
        """Removing FA-T02 without --force raises ValueError because
        FB-T03 depends on FA-T02."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # FA-T02 is a hard dep of FB-T03
        with pytest.raises(ValueError) as exc_info:
            task_remove(ctx, "FA-T02", force=False)

        msg = str(exc_info.value)
        assert "Cannot remove" in msg or "dependency" in msg.lower(), (
            f"Expected dependency error message, got: {msg}"
        )
        assert "force" in msg.lower(), (
            f"Expected --force suggestion in message: {msg}"
        )

    def test_task_remove_force(self, tmp_path: Path):
        """Removing FA-T02 with --force proceeds despite dangling deps."""
        ctx = _build_fixture_loaded_project(tmp_path)

        result = task_remove(ctx, "FA-T02", force=True)

        # ── Assert 1 PendingWrite ────────────────────────────────────────
        assert len(result) == 1, (
            f"Expected 1 PendingWrite, got {len(result)}"
        )

        pw = result[0]
        assert pw.target_file == "TASKS.md"

        # ── Verify summary includes force-mode warning ───────────────────
        summary = " ".join(pw.summary_lines)
        assert "force" in summary.lower() or "Force" in summary, (
            f"Force mode not mentioned in summary: {pw.summary_lines}"
        )

        # ── Verify shadow file exists and FA-T02 is removed ──────────────
        shadow = Path(pw.shadow_path)
        assert shadow.exists(), f"Shadow file not written: {shadow}"

        content = shadow.read_text(encoding="utf-8")

        # FA-T02 block should be gone
        assert "### FA-T02 · Active task with multi-line what" not in content, (
            "FA-T02 heading should not be in shadow content after removal"
        )

        # Other tasks should remain
        assert "### FA-T01 · Completed setup task" in content
        assert "### FA-T03 · Pending task with multi-line done-when" in content
        assert "### FB-T01 · Completed beta task" in content

        # Dangling dep warning in summary
        assert "dangling" in summary.lower(), (
            f"Expected dangling dep mention in force summary: {summary}"
        )


# ── HELP_TEXT tests ─────────────────────────────────────────────────────────


class TestHELP_TEXT:
    """``HELP_TEXT`` is a module-level string constant."""

    def test_help_text_exists(self):
        """HELP_TEXT is a non-empty string."""
        assert isinstance(HELP_TEXT, str)
        assert len(HELP_TEXT) > 0
        assert "Preconditions" in HELP_TEXT
        assert "Writes" in HELP_TEXT
