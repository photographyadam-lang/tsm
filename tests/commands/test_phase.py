# tests/commands/test_phase.py — P7-T04 phase CRUD command tests
#
# Done-when criteria (from P7-T04 task block):
#
#   1. test_phase_add_appends_phase_block passes
#   2. test_phase_add_updates_phase_structure_table passes
#   3. test_phase_edit_name_updates_heading_and_table passes
#   4. test_phase_move_reorders_h1_blocks passes
#   5. test_phase_remove_blocked_by_deps passes
#   6. test_phase_remove_force_cascade passes

from pathlib import Path

import pytest

from tsm.commands.phase import (
    HELP_TEXT,
    phase_add,
    phase_edit,
    phase_move,
    phase_remove,
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


class TestPhaseAdd:
    """``phase_add()`` creates a new phase block and updates the table."""

    def test_phase_add_appends_phase_block(self, tmp_path: Path):
        """Adding a new phase appends an H1 block to TASKS.md."""
        ctx = _build_fixture_loaded_project(tmp_path)

        result = phase_add(ctx, "Phase 3 — New Phase")

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
        assert "Phase 3 — New Phase" in " ".join(pw.summary_lines)

        # ── Verify shadow content has the new phase block ────────────────
        content = shadow.read_text(encoding="utf-8")

        # The new phase H1 heading should be present
        assert "# Phase 3 — New Phase" in content, (
            "New phase H1 heading not found in shadow content"
        )

        # The new phase should appear after the last existing phase
        assert "Phase 3" in content

        # All original content should still be present
        assert "Phase 1 — Fixture Alpha" in content
        assert "Phase 2 — Fixture Beta" in content

    def test_phase_add_updates_phase_structure_table(self, tmp_path: Path):
        """Adding a new phase adds a row to the Phase structure table."""
        ctx = _build_fixture_loaded_project(tmp_path)

        result = phase_add(ctx, "Phase 3 — New Phase")

        pw = result[0]
        shadow = Path(pw.shadow_path)
        content = shadow.read_text(encoding="utf-8")

        # ── Find the Phase structure table ───────────────────────────────
        # Locate the ## Phase structure section and extract the table
        ps_section = content.split("## Phase structure")
        assert len(ps_section) > 1, (
            "## Phase structure section not found"
        )

        # Extract all pipe-delimited data rows (skip header and separator)
        lines = ps_section[1].split("\n")
        table_rows = [
            l.strip()
            for l in lines
            if l.strip().startswith("|") and "---" not in l
        ]

        # Should have 3 data rows (2 original + 1 new)
        # Header row is | Phase | Description | Status |
        data_rows = table_rows[1:]  # skip header
        assert len(data_rows) == 3, (
            f"Expected 3 phase rows in table, got {len(data_rows)}: "
            f"{data_rows}"
        )

        # The new row should be for Phase 3 — New Phase
        assert any("Phase 3 — New Phase" in row for row in data_rows), (
            f"New phase row not found in table: {data_rows}"
        )

        # The original rows should still be present
        assert any("Phase 1 — Fixture Alpha" in row for row in data_rows)
        assert any("Phase 2 — Fixture Beta" in row for row in data_rows)


class TestPhaseEdit:
    """``phase_edit()`` updates heading and/or Phase structure table row."""

    def test_phase_edit_name_updates_heading_and_table(self, tmp_path: Path):
        """Editing a phase name changes the H1 heading and the table row."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Phase 2 — Fixture Beta has slug "phase-2--fixture-beta"
        result = phase_edit(
            ctx, "phase-2--fixture-beta", name="Phase 2 — Updated"
        )

        # ── Assert 1 PendingWrite ────────────────────────────────────────
        assert len(result) == 1

        pw = result[0]
        assert pw.target_file == "TASKS.md"

        shadow = Path(pw.shadow_path)
        content = shadow.read_text(encoding="utf-8")

        # ── Verify H1 heading was updated ────────────────────────────────
        assert "# Phase 2 — Updated" in content, (
            "Updated H1 heading not found"
        )
        # The old heading should no longer be present as an H1
        # (it may appear in the Phase structure table reference if not updated,
        #  but we check both below)

        # ── Verify Phase structure table row was updated ─────────────────
        ps_section = content.split("## Phase structure")[1]
        ps_lines = ps_section.split("\n")
        data_rows = [
            l.strip()
            for l in ps_lines
            if l.strip().startswith("|") and "---" not in l
        ][1:]  # skip header

        # Check the updated name appears in a table row
        assert any("Phase 2 — Updated" in row for row in data_rows), (
            f"Updated phase name not in table rows: {data_rows}"
        )

        # The old name should not appear in the table
        old_name_rows = [r for r in data_rows if "Phase 2 — Fixture Beta" in r]
        assert len(old_name_rows) == 0, (
            f"Old phase name still present in table: {old_name_rows}"
        )


class TestPhaseMove:
    """``phase_move()`` reorders H1 blocks."""

    def test_phase_move_reorders_h1_blocks(self, tmp_path: Path):
        """Moving Phase 1 after Phase 2 reverses their order."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Move Phase 1 — Fixture Alpha after Phase 2 — Fixture Beta
        result = phase_move(
            ctx, "phase-1--fixture-alpha", "phase-2--fixture-beta"
        )

        # ── Assert 1 PendingWrite ────────────────────────────────────────
        assert len(result) == 1

        pw = result[0]
        shadow = Path(pw.shadow_path)
        content = shadow.read_text(encoding="utf-8")

        # ── Verify Phase 2 comes BEFORE Phase 1 in the file ──────────────
        pos_phase2 = content.index("# Phase 2 — Fixture Beta")
        pos_phase1 = content.index("# Phase 1 — Fixture Alpha")

        assert pos_phase2 < pos_phase1, (
            f"Phase 2 should appear before Phase 1 after move, "
            f"but Phase 2 at {pos_phase2} > Phase 1 at {pos_phase1}"
        )

        # ── Verify Phase structure table is in the new order ─────────────
        ps_section = content.split("## Phase structure")[1]
        ps_lines = ps_section.split("\n")
        data_rows = [
            l.strip()
            for l in ps_lines
            if l.strip().startswith("|") and "---" not in l
        ][1:]  # skip header

        # Phase 2 should be first in the table
        assert len(data_rows) >= 2, (
            f"Expected at least 2 rows, got {len(data_rows)}"
        )
        assert "Phase 2 — Fixture Beta" in data_rows[0], (
            f"Expected Phase 2 first in table, got: {data_rows[0]}"
        )
        assert "Phase 1 — Fixture Alpha" in data_rows[1], (
            f"Expected Phase 1 second in table, got: {data_rows[1]}"
        )


class TestPhaseRemove:
    """``phase_remove()`` removes a phase and its tasks."""

    def test_phase_remove_blocked_by_deps(self, tmp_path: Path):
        """Removing Phase 1 without --force raises ValueError because
        FB-T03 depends on FA-T02 which is in Phase 1."""
        ctx = _build_fixture_loaded_project(tmp_path)

        # Phase 1 has FA-T02 which FB-T03 depends on
        # Removing Phase 1 would orphan FA-T02 → dangling dep
        with pytest.raises(ValueError) as exc_info:
            phase_remove(ctx, "phase-1--fixture-alpha", force=False)

        msg = str(exc_info.value)
        assert "Cannot remove" in msg or "dependency" in msg.lower(), (
            f"Expected dependency error message, got: {msg}"
        )
        assert "force" in msg.lower(), (
            f"Expected --force suggestion in message: {msg}"
        )

    def test_phase_remove_force_cascade(self, tmp_path: Path):
        """Removing Phase 1 with --force proceeds despite dangling deps
        and lists them in the summary."""
        ctx = _build_fixture_loaded_project(tmp_path)

        result = phase_remove(
            ctx, "phase-1--fixture-alpha", force=True
        )

        # ── Assert 1 PendingWrite ────────────────────────────────────────
        assert len(result) == 1

        pw = result[0]
        assert pw.target_file == "TASKS.md"

        # ── Verify summary includes force-mode warning ───────────────────
        summary = " ".join(pw.summary_lines)
        assert "force" in summary.lower() or "Force" in summary, (
            f"Force mode not mentioned in summary: {pw.summary_lines}"
        )

        # ── Verify shadow file exists ────────────────────────────────────
        shadow = Path(pw.shadow_path)
        assert shadow.exists(), f"Shadow file not written: {shadow}"

        content = shadow.read_text(encoding="utf-8")

        # ── Verify Phase 1 block was removed ─────────────────────────────
        assert "# Phase 1 — Fixture Alpha" not in content, (
            "Phase 1 H1 heading should not be in shadow content after removal"
        )

        # ── Verify Phase 2 content is still intact ───────────────────────
        assert "# Phase 2 — Fixture Beta" in content, (
            "Phase 2 H1 heading should still be present"
        )

        # ── Verify Phase structure table has 1 row ───────────────────────
        ps_section = content.split("## Phase structure")[1]
        ps_lines = ps_section.split("\n")
        data_rows = [
            l.strip()
            for l in ps_lines
            if l.strip().startswith("|") and "---" not in l
        ][1:]  # skip header

        assert len(data_rows) == 1, (
            f"Expected 1 phase row in table after removal, "
            f"got {len(data_rows)}: {data_rows}"
        )
        assert "Phase 2 — Fixture Beta" in data_rows[0]


# ── HELP_TEXT tests ─────────────────────────────────────────────────────────


class TestHELP_TEXT:
    """``HELP_TEXT`` is a module-level string constant."""

    def test_help_text_exists(self):
        """HELP_TEXT is a non-empty string."""
        assert isinstance(HELP_TEXT, str)
        assert len(HELP_TEXT) > 0
        assert "Preconditions" in HELP_TEXT
        assert "Writes" in HELP_TEXT
