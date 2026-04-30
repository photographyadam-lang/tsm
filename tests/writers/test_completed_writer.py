# tests/writers/test_completed_writer.py — P3-T05 completed_writer tests
#
# Done-when criteria (from P3-T05 task block):
#
#   1. append_task_row on a new path creates the file with
#      # Completed Tasks Log header, ---, the ## phase section, and the row
#   2. append_task_row on an existing file with a matching phase section
#      appends the row to that section without creating a duplicate section
#      header
#   3. append_task_row on an existing file with no matching phase section
#      creates a new phase section at the end of the file
#   4. append_phase_marker appends **Phase complete: YYYY-MM-DD** after
#      the last row in the correct phase section

from pathlib import Path

import pytest

from tsm.writers.completed_writer import (
    append_phase_marker,
    append_task_row,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _fixture_content() -> str:
    """Return the canonical TASKS-COMPLETED.md fixture content as a string."""
    path = FIXTURE_DIR / "TASKS-COMPLETED.md"
    return path.read_text(encoding="utf-8")


# ── Tests ────────────────────────────────────────────────────────────────────


class TestAppendTaskRow:
    """Test suite for :func:`append_task_row`."""

    # ------------------------------------------------------------------
    # 1. New file: creates header, phase section, and row
    # ------------------------------------------------------------------

    def test_new_file_creates_header_and_section(self, tmp_path: Path):
        """``append_task_row`` on a nonexistent path creates the file with
        the ``# Completed Tasks Log`` header, ``---``, the ``##`` phase
        section (including column header and separator), and the data row."""
        live = tmp_path / "TASKS-COMPLETED.md"
        shadow = str(tmp_path / ".tsm" / "shadow" / "TASKS-COMPLETED.md")

        result = append_task_row(
            path=live,
            shadow_path=shadow,
            phase_name="Phase 3 \u2014 Shadow & Writers",
            task_id="P3-T05",
            title="completed_writer.py \u2014 append writer",
            complexity="low",
            commit="abc1234",
            notes="Append writer implemented",
        )

        # Verify header present
        assert result.startswith("# Completed Tasks Log")
        assert "---" in result

        # Verify phase section
        assert "## Phase 3 \u2014 Shadow & Writers" in result

        # Verify column header and separator present
        assert "| Task | Description | Complexity | Commit | Notes |" in result
        assert "|------|-------------|------------|--------|-------|" in result

        # Verify data row present
        assert "| P3-T05 | completed_writer.py \u2014 append writer | low | abc1234 | Append writer implemented |" in result

        # Verify shadow file was written
        assert Path(shadow).exists()

    # ------------------------------------------------------------------
    # 2. Existing file with matching phase section: appends row
    # ------------------------------------------------------------------

    def test_existing_file_appends_row(self, tmp_path: Path):
        """``append_task_row`` on an existing file that already has the
        target phase section appends the new row after the last existing
        row without duplicating the section header."""
        live = tmp_path / "TASKS-COMPLETED.md"
        # Copy the fixture into the temp directory
        live.write_text(_fixture_content(), encoding="utf-8")
        shadow = str(tmp_path / ".tsm" / "shadow" / "TASKS-COMPLETED.md")

        result = append_task_row(
            path=live,
            shadow_path=shadow,
            phase_name="Phase 1 \u2014 Fixture Alpha",
            task_id="FA-T03",
            title="New appended task",
            complexity="medium",
            commit="xyz9999",
            notes="Appended via writer",
        )

        # Should have exactly one phase section heading
        count_phase = result.count("## Phase 1 \u2014 Fixture Alpha")
        assert count_phase == 1, (
            f"Expected 1 phase section heading, found {count_phase}"
        )

        # Should have the new row
        assert "| FA-T03 | New appended task | medium | xyz9999 | Appended via writer |" in result

        # The new row should appear after FA-T02
        fa02_idx = result.index("FA-T02")
        fa03_idx = result.index("FA-T03")
        assert fa03_idx > fa02_idx, (
            "New row FA-T03 should appear after FA-T02"
        )

        # The original rows should still be present
        assert "FA-T01" in result
        assert "FA-T02" in result

    # ------------------------------------------------------------------
    # 3. Existing file, no matching phase section: creates new section
    # ------------------------------------------------------------------

    def test_existing_file_new_phase_section(self, tmp_path: Path):
        """``append_task_row`` on an existing file that does not have the
        target phase section creates a new ``##`` section at the end of
        the file with its own column header and the data row."""
        live = tmp_path / "TASKS-COMPLETED.md"
        live.write_text(_fixture_content(), encoding="utf-8")
        shadow = str(tmp_path / ".tsm" / "shadow" / "TASKS-COMPLETED.md")

        result = append_task_row(
            path=live,
            shadow_path=shadow,
            phase_name="Phase 2 \u2014 New Phase",
            task_id="NP-T01",
            title="New phase task",
            complexity="high",
            commit="new001",
            notes="New phase created",
        )

        # Original phase section must remain
        assert "## Phase 1 \u2014 Fixture Alpha" in result

        # New phase section must appear
        assert "## Phase 2 \u2014 New Phase" in result

        # New phase section must have column header and separator
        # Find the new phase section
        phase2_idx = result.index("## Phase 2 \u2014 New Phase")
        after_phase2 = result[phase2_idx:]
        assert "| Task | Description | Complexity | Commit | Notes |" in after_phase2
        assert "|------|-------------|------------|--------|-------|" in after_phase2

        # New phase section must contain the data row
        assert "| NP-T01 | New phase task | high | new001 | New phase created |" in after_phase2

        # The new section must be at the end of the file (after the original section)
        phase1_idx = result.index("## Phase 1 \u2014 Fixture Alpha")
        assert phase2_idx > phase1_idx, (
            "New phase section should appear after existing phase section"
        )

    # ------------------------------------------------------------------
    # 4. append_task_row: last-occurrence semantics
    # ------------------------------------------------------------------

    def test_existing_file_last_occurrence_used(self, tmp_path: Path):
        """When a phase section appears twice, ``append_task_row`` uses
        the last occurrence (not the first)."""
        live = tmp_path / "TASKS-COMPLETED.md"
        # Build content with two occurrences of the same phase heading
        content = (
            "# Completed Tasks Log\n"
            "\n"
            "---\n"
            "\n"
            "## Phase X\n"
            "\n"
            "| Task | Description | Complexity | Commit | Notes |\n"
            "|------|-------------|------------|--------|-------|\n"
            "| PX-T01 | First occurrence | low | aaa | first |\n"
            "\n"
            "## Phase X\n"
            "\n"
            "| Task | Description | Complexity | Commit | Notes |\n"
            "|------|-------------|------------|--------|-------|\n"
            "| PX-T02 | Second occurrence | high | bbb | second |\n"
        )
        live.write_text(content, encoding="utf-8")
        shadow = str(tmp_path / ".tsm" / "shadow" / "TASKS-COMPLETED.md")

        result = append_task_row(
            path=live,
            shadow_path=shadow,
            phase_name="Phase X",
            task_id="PX-T03",
            title="Appended to last",
            complexity="medium",
            commit="ccc",
            notes="last occurrence",
        )

        # New row should appear after PX-T02 (the second occurrence),
        # not after PX-T01 (the first occurrence)
        px01_idx = result.index("PX-T01")
        px02_idx = result.index("PX-T02")
        px03_idx = result.index("PX-T03")

        assert px03_idx > px02_idx, (
            "New row should appear after the last occurrence (PX-T02), "
            f"but PX-T03 at {px03_idx} is before PX-T02 at {px02_idx}"
        )
        assert px02_idx > px01_idx, (
            "Second occurrence PX-T02 should be after first PX-T01"
        )


class TestAppendPhaseMarker:
    """Test suite for :func:`append_phase_marker`."""

    # ------------------------------------------------------------------
    # 5. Phase marker appended after last row
    # ------------------------------------------------------------------

    def test_phase_marker_appended(self, tmp_path: Path):
        """``append_phase_marker`` appends ``**Phase complete:
        YYYY-MM-DD**`` after the last data row in the correct phase
        section."""
        live = tmp_path / "TASKS-COMPLETED.md"
        live.write_text(_fixture_content(), encoding="utf-8")
        shadow = str(tmp_path / ".tsm" / "shadow" / "TASKS-COMPLETED.md")

        result = append_phase_marker(
            path=live,
            shadow_path=shadow,
            phase_name="Phase 1 \u2014 Fixture Alpha",
            date="2026-04-30",
        )

        # Phase marker must be present
        assert "**Phase complete: 2026-04-30**" in result

        # Marker must appear after the last data row (FA-T02)
        fa02_idx = result.index("FA-T02")
        marker_idx = result.index("**Phase complete: 2026-04-30**")
        assert marker_idx > fa02_idx, (
            "Phase marker should appear after the last data row"
        )

        # Phase section heading must still be present
        assert "## Phase 1 \u2014 Fixture Alpha" in result

    def test_phase_marker_no_duplicate_section(self, tmp_path: Path):
        """``append_phase_marker`` does not create duplicate section
        headings."""
        live = tmp_path / "TASKS-COMPLETED.md"
        live.write_text(_fixture_content(), encoding="utf-8")
        shadow = str(tmp_path / ".tsm" / "shadow" / "TASKS-COMPLETED.md")

        result = append_phase_marker(
            path=live,
            shadow_path=shadow,
            phase_name="Phase 1 \u2014 Fixture Alpha",
            date="2026-04-30",
        )

        count = result.count("## Phase 1 \u2014 Fixture Alpha")
        assert count == 1, (
            f"Expected 1 phase section heading, found {count}"
        )

    # ------------------------------------------------------------------
    # 6. Phase marker on file with single row
    # ------------------------------------------------------------------

    def test_phase_marker_single_row_section(self, tmp_path: Path):
        """``append_phase_marker`` works correctly on a section with only
        one data row."""
        live = tmp_path / "TASKS-COMPLETED.md"
        content = (
            "# Completed Tasks Log\n"
            "\n"
            "---\n"
            "\n"
            "## Single Row Phase\n"
            "\n"
            "| Task | Description | Complexity | Commit | Notes |\n"
            "|------|-------------|------------|--------|-------|\n"
            "| SR-T01 | Only task | low | single | just one |\n"
        )
        live.write_text(content, encoding="utf-8")
        shadow = str(tmp_path / ".tsm" / "shadow" / "TASKS-COMPLETED.md")

        result = append_phase_marker(
            path=live,
            shadow_path=shadow,
            phase_name="Single Row Phase",
            date="2026-05-01",
        )

        assert "**Phase complete: 2026-05-01**" in result
        sr_idx = result.index("SR-T01")
        marker_idx = result.index("**Phase complete: 2026-05-01**")
        assert marker_idx > sr_idx

    # ------------------------------------------------------------------
    # 7. Phase marker: ValueError for missing phase
    # ------------------------------------------------------------------

    def test_phase_marker_missing_phase(self, tmp_path: Path):
        """``append_phase_marker`` raises ``ValueError`` when the phase
        section does not exist."""
        live = tmp_path / "TASKS-COMPLETED.md"
        live.write_text(_fixture_content(), encoding="utf-8")
        shadow = str(tmp_path / ".tsm" / "shadow" / "TASKS-COMPLETED.md")

        with pytest.raises(ValueError, match="Phase section 'Nonexistent' not found"):
            append_phase_marker(
                path=live,
                shadow_path=shadow,
                phase_name="Nonexistent",
                date="2026-04-30",
            )

    # ------------------------------------------------------------------
    # 8. Phase marker: FileNotFoundError for missing file
    # ------------------------------------------------------------------

    def test_phase_marker_missing_file(self, tmp_path: Path):
        """``append_phase_marker`` raises ``FileNotFoundError`` when the
        live file does not exist."""
        live = tmp_path / "NONEXISTENT.md"
        shadow = str(tmp_path / ".tsm" / "shadow" / "NONEXISTENT.md")

        with pytest.raises(FileNotFoundError, match="does not exist"):
            append_phase_marker(
                path=live,
                shadow_path=shadow,
                phase_name="Any Phase",
                date="2026-04-30",
            )

    # ------------------------------------------------------------------
    # 9. Phase marker: shadow file written
    # ------------------------------------------------------------------

    def test_phase_marker_writes_shadow(self, tmp_path: Path):
        """``append_phase_marker`` writes the content to the shadow
        path."""
        live = tmp_path / "TASKS-COMPLETED.md"
        live.write_text(_fixture_content(), encoding="utf-8")
        shadow = str(tmp_path / ".tsm" / "shadow" / "TASKS-COMPLETED.md")

        append_phase_marker(
            path=live,
            shadow_path=shadow,
            phase_name="Phase 1 \u2014 Fixture Alpha",
            date="2026-04-30",
        )

        assert Path(shadow).exists()
        shadow_content = Path(shadow).read_text(encoding="utf-8")
        assert "**Phase complete: 2026-04-30**" in shadow_content
