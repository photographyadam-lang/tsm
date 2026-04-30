# tests/commands/test_init_phase.py — P4-T02 init_phase command tests
#
# Done-when criteria (from P4-T02 task block):
#
#   1. test_init_phase_sets_active_task passes
#   2. test_init_phase_no_ready_task passes
#   3. test_init_phase_unknown_id passes

from datetime import datetime
from pathlib import Path

import pytest

from tsm.commands.init_phase import HELP_TEXT, init_phase
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


# ── Tests ────────────────────────────────────────────────────────────────────


class TestInitPhaseSetsActiveTask:
    """``init_phase()`` with a valid phase and a ready task."""

    def test_init_phase_sets_active_task(self, tmp_path: Path):
        """Phase 2 (fixture beta) has FB-T02 as first pending task with
        no hard deps → FB-T02 becomes active, FB-T03 goes to up_next,
        completed list is cleared."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Phase 2 — Fixture Beta (id: "phase-2-fixture-beta")
        # Tasks in file order:
        #   FB-T01: ✅ Complete (skip)
        #   FB-T02: Pending, deps: None → empty list → select!
        #   FB-T03: **Active** → non-complete → goes to up_next
        # The slugify function produces double hyphens where em-dashes are
        # stripped: "Phase 2 — Fixture Beta" → "phase-2--fixture-beta"
        result = init_phase(ctx, "phase-2--fixture-beta")

        # ── Assert 1 PendingWrite for SESSIONSTATE.md ─────────────────────
        assert len(result) == 1, (
            f"Expected 1 PendingWrite, got {len(result)}"
        )

        pw = result[0]
        assert pw.target_file == "SESSIONSTATE.md"

        # ── Verify shadow file was written ────────────────────────────────
        shadow = Path(pw.shadow_path)
        assert shadow.exists(), f"Shadow file not written: {shadow}"
        assert pw.live_path is not None
        assert pw.backup_path is not None
        assert len(pw.summary_lines) > 0
        assert "FB-T02" in " ".join(pw.summary_lines)

        # ── Verify SESSIONSTATE.md shadow content ─────────────────────────
        content = shadow.read_text(encoding="utf-8")

        # Active phase should now be Phase 2 — Fixture Beta
        assert "Fixture Beta" in content

        # Active task should be FB-T02
        assert "### FB-T02" in content

        # FB-T02 should NOT be in up_next
        up_next_section = content.split("## Up next")[1].split("##")[0] \
            if "## Up next" in content else ""
        assert "FB-T02" not in up_next_section

        # FB-T03 should be in up_next
        assert "FB-T03" in up_next_section

        # Completed table should be empty (cleared on phase init)
        completed_section = content.split("## Completed tasks")[1].split(
            "##"
        )[0] if "## Completed tasks" in content else ""
        # Only the header rows (| Task |...| and |------|...) should exist
        header_lines = [
            l for l in completed_section.split("\n")
            if l.strip().startswith("|")
        ]
        # Exactly 2 header rows (column headers + separator), no data rows
        assert len(header_lines) == 2, (
            f"Expected 2 header-only table rows, got {len(header_lines)}: "
            f"{header_lines}"
        )


class TestInitPhaseNoReadyTask:
    """``init_phase()`` when no task in the phase has all deps met."""

    def test_init_phase_no_ready_task(self, tmp_path: Path):
        """A phase where the first non-complete task has unmet hard deps
        → active_task set to [none], warning printed."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Construct a synthetic phase with one task that has an unmet dep
        unmet_dep_task = Task(
            id="FA-T099",
            title="Task with unmet dep",
            status=TaskStatus.PENDING,
            complexity=TaskComplexity.LOW,
            what="A task whose hard dep cannot be satisfied.",
            prerequisite="None.",
            hard_deps=["NONEXISTENT-DEP"],
            files=[],
            reviewer="Skip",
            key_constraints=[],
            done_when="Never.",
            phase_id="synthetic-phase",
            subphase=None,
            raw_block=(
                "### FA-T099 · Task with unmet dep\n\n"
                "**Status:** Pending\n"
                "**Complexity:** low\n"
                "**What:** A task whose hard dep cannot be satisfied.\n"
                "**Prerequisite:** None.\n"
                "**Hard deps:** NONEXISTENT-DEP\n"
                "**Files:**\n"
                "**Reviewer:** Skip\n"
                "**Done when:**\n"
                "- Never.\n"
            ),
        )

        # We need to add this task to a phase object. We'll create a
        # minimal phase and inject it into ctx.phases.
        from tsm.models import Phase

        synthetic_phase = Phase(
            id="synthetic-phase",
            name="Synthetic Phase",
            status="Pending",
            description="A phase with no ready task.",
            tasks=[unmet_dep_task],
            dependency_graph_raw="",
        )

        # Replace ctx.phases with just the synthetic phase
        ctx.phases = [synthetic_phase]

        # Also need a valid active_phase_spec in the session
        ctx.session = SessionState(
            last_updated=ctx.session.last_updated,
            active_phase_name=ctx.session.active_phase_name,
            active_phase_spec=ctx.session.active_phase_spec,
            active_task=ctx.session.active_task,
            active_task_raw=ctx.session.active_task_raw,
            up_next=ctx.session.up_next,
            completed=ctx.session.completed,
            out_of_scope_raw=ctx.session.out_of_scope_raw,
        )

        # Execute init_phase on the synthetic phase
        result = init_phase(ctx, "synthetic-phase")

        # ── Assert 1 PendingWrite ─────────────────────────────────────────
        assert len(result) == 1

        pw = result[0]
        assert pw.target_file == "SESSIONSTATE.md"

        # Verify shadow content shows [none]
        shadow = Path(pw.shadow_path)
        content = shadow.read_text(encoding="utf-8")

        # When active_task_raw is "[none]", the renderer emits it verbatim
        # (without a "## Active task" heading) as a bare [none] block.
        assert "[none]" in content, (
            "Expected active_task to be [none] when no task is ready"
        )

        # Up next should contain FA-T099 (the only non-complete task)
        up_next_section = content.split("## Up next")[1].split("##")[0] \
            if "## Up next" in content else ""
        assert "FA-T099" in up_next_section


class TestInitPhaseUnknownId:
    """``init_phase()`` with a phase ID that does not match any phase."""

    def test_init_phase_unknown_id(self, tmp_path: Path):
        """Non-matching phase_id → ValueError with clear message."""
        ctx = _build_fixture_loaded_project(tmp_path)

        with pytest.raises(ValueError) as exc_info:
            init_phase(ctx, "nonexistent-phase")

        msg = str(exc_info.value).lower()
        assert "not found" in msg or "nonexistent-phase" in msg


# ── HELP_TEXT tests ─────────────────────────────────────────────────────────


class TestHELP_TEXT:
    """``HELP_TEXT`` is a module-level string constant."""

    def test_help_text_exists(self):
        """HELP_TEXT is a non-empty string."""
        assert isinstance(HELP_TEXT, str)
        assert len(HELP_TEXT) > 0
        assert "Preconditions" in HELP_TEXT
        assert "Writes" in HELP_TEXT
