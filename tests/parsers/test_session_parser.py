# tests/parsers/test_session_parser.py — 12 tests for P2-T03
#
# Tests for parse_session_file() covering all §9.3 section types and
# §9.5 edge cases. Tests use either the shared fixture file
# (tests/fixtures/SESSIONSTATE.md) or inline content.

from datetime import datetime
from pathlib import Path
from textwrap import dedent

import pytest

from tsm.models import TaskComplexity, TaskStatus
from tsm.parsers.session_parser import parse_session_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "SESSIONSTATE.md"


def _parse_inline(content: str):
    """Write inline content to a temp file, parse it, return SessionState."""
    tmp = FIXTURE_DIR / ".tmp_test_session.md"
    tmp.write_text(dedent(content), encoding="utf-8")
    try:
        return parse_session_file(tmp)
    finally:
        if tmp.exists():
            tmp.unlink()


# ===================================================================
# 1. *Last updated:* — full datetime format
# ===================================================================

class TestParseLastUpdated:
    """*Last updated:* in full YYYY-MM-DDTHH:MM format."""

    def test_parse_last_updated(self):
        """Fixture SESSIONSTATE.md has *Last updated: 2026-04-15T14:30*."""
        state = parse_session_file(FIXTURE_PATH)
        assert state.last_updated == datetime(2026, 4, 15, 14, 30), (
            f"Expected 2026-04-15 14:30, got {state.last_updated}"
        )


# ===================================================================
# 2. *Last updated:* — legacy date-only format
# ===================================================================

class TestParseLastUpdatedLegacyDate:
    """*Last updated:* in legacy date-only YYYY-MM-DD format."""

    def test_parse_last_updated_legacy_date(self):
        """Date-only format sets time to 00:00."""
        content = """\
        *Last updated: 2026-04-15*

        ---

        ## Active phase

        Phase 1 — Test — in progress.
        Spec: `spec.md`

        ---

        ## Active task

        [none]

        ---

        ## Out of scope

        Nothing.
        """
        state = _parse_inline(content)
        assert state.last_updated == datetime(2026, 4, 15, 0, 0), (
            f"Expected 2026-04-15 00:00, got {state.last_updated}"
        )


# ===================================================================
# 3. ## Active phase
# ===================================================================

class TestParseActivePhase:
    """## Active phase section parsing."""

    def test_parse_active_phase(self):
        """Fixture has 'Phase 1 — Fixture Alpha — in progress.' and spec."""
        state = parse_session_file(FIXTURE_PATH)
        assert state.active_phase_name == "Phase 1 — Fixture Alpha — in progress.", (
            f"Unexpected active_phase_name: {state.active_phase_name!r}"
        )
        assert state.active_phase_spec == "`tests/fixtures/TASKS.md`", (
            f"Unexpected active_phase_spec: {state.active_phase_spec!r}"
        )


# ===================================================================
# 4. ## Active task — task ID and title extraction
# ===================================================================

class TestParseActiveTaskId:
    """Extract task ID and title from ### heading inside Active task block."""

    def test_parse_active_task_id(self):
        """Fixture has FA-T02 · Active task with multi-line what."""
        state = parse_session_file(FIXTURE_PATH)
        assert state.active_task is not None, "Expected active_task to be non-None"
        assert state.active_task.id == "FA-T02", (
            f"Expected FA-T02, got {state.active_task.id}"
        )
        assert state.active_task.title == "Active task with multi-line what", (
            f"Unexpected title: {state.active_task.title!r}"
        )


# ===================================================================
# 5. ## Active task — Complexity parsing
# ===================================================================

class TestParseActiveTaskComplexity:
    """Parse **Complexity:** field inside Active task block."""

    def test_parse_active_task_complexity(self):
        """Fixture has **Complexity:** high."""
        state = parse_session_file(FIXTURE_PATH)
        assert state.active_task is not None, "Expected active_task to be non-None"
        assert state.active_task.complexity == TaskComplexity.HIGH, (
            f"Expected HIGH, got {state.active_task.complexity}"
        )


# ===================================================================
# 6. ## Up next — full table parsing
# ===================================================================

class TestParseUpNextTable:
    """Parse the ## Up next pipe-delimited table."""

    def test_parse_up_next_table(self):
        """Fixture has 2 up-next rows with correct fields."""
        state = parse_session_file(FIXTURE_PATH)
        assert len(state.up_next) == 2, (
            f"Expected 2 up-next rows, got {len(state.up_next)}"
        )

        # First row: FA-T03
        row0 = state.up_next[0]
        assert row0.id == "FA-T03", f"Expected FA-T03, got {row0.id}"
        assert row0.title == "Pending task with multi-line done-when", (
            f"Unexpected title: {row0.title!r}"
        )
        assert row0.hard_deps == [], (
            f"Expected empty hard_deps (em-dash), got {row0.hard_deps}"
        )
        assert row0.complexity == TaskComplexity.MEDIUM, (
            f"Expected MEDIUM, got {row0.complexity}"
        )
        assert row0.reviewer == "Skip", f"Expected Skip, got {row0.reviewer}"

        # Second row: FA-T04
        row1 = state.up_next[1]
        assert row1.id == "FA-T04", f"Expected FA-T04, got {row1.id}"
        assert row1.complexity == TaskComplexity.UNSET, (
            f"Expected UNSET, got {row1.complexity}"
        )
        assert row1.hard_deps == [], (
            f"Expected empty hard_deps (None.), got {row1.hard_deps}"
        )


# ===================================================================
# 7. ## Up next — with Complexity column
# ===================================================================

class TestParseUpNextComplexityColumn:
    """## Up next table includes a Complexity column."""

    def test_parse_up_next_complexity_column(self):
        """5-column table with Complexity column parses complexity correctly."""
        content = """\
        *Last updated: 2026-04-15T00:00*

        ---

        ## Active phase

        Phase 1 — Test — in progress.
        Spec: `spec.md`

        ---

        ## Active task

        [none]

        ---

        ## Up next

        | Task | Description | Hard deps | Complexity | Reviewer |
        |------|-------------|-----------|------------|----------|
        | T-01 | First task | P1-T01 | high | Alice |
        | T-02 | Second task | — | low | Bob |

        ---

        ## Out of scope

        Nothing.
        """
        state = _parse_inline(content)
        assert len(state.up_next) == 2
        assert state.up_next[0].complexity == TaskComplexity.HIGH, (
            f"Expected HIGH, got {state.up_next[0].complexity}"
        )
        assert state.up_next[1].complexity == TaskComplexity.LOW, (
            f"Expected LOW, got {state.up_next[1].complexity}"
        )


# ===================================================================
# 8. ## Up next — without Complexity column
# ===================================================================

class TestParseUpNextNoComplexityColumn:
    """## Up next table without Complexity column defaults to UNSET."""

    def test_parse_up_next_no_complexity_column(self):
        """4-column table (no Complexity) defaults all rows to UNSET."""
        content = """\
        *Last updated: 2026-04-15T00:00*

        ---

        ## Active phase

        Phase 1 — Test — in progress.
        Spec: `spec.md`

        ---

        ## Active task

        [none]

        ---

        ## Up next

        | Task | Description | Hard deps | Reviewer |
        |------|-------------|-----------|----------|
        | T-01 | First task | — | Alice |
        | T-02 | Second task | P1-T01 | Bob |

        ---

        ## Out of scope

        Nothing.
        """
        state = _parse_inline(content)
        assert len(state.up_next) == 2
        assert state.up_next[0].complexity == TaskComplexity.UNSET, (
            f"Expected UNSET (no Complexity column), got {state.up_next[0].complexity}"
        )
        assert state.up_next[1].complexity == TaskComplexity.UNSET, (
            f"Expected UNSET (no Complexity column), got {state.up_next[1].complexity}"
        )


# ===================================================================
# 9. ## Completed tasks
# ===================================================================

class TestParseCompletedTable:
    """Parse the ## Completed tasks 3-column pipe-delimited table."""

    def test_parse_completed_table(self):
        """Fixture has 2 completed rows with correct fields."""
        state = parse_session_file(FIXTURE_PATH)
        assert len(state.completed) == 2, (
            f"Expected 2 completed rows, got {len(state.completed)}"
        )

        row0 = state.completed[0]
        assert row0.id == "FA-T01", f"Expected FA-T01, got {row0.id}"
        assert row0.title == "Completed setup task", (
            f"Unexpected title: {row0.title!r}"
        )

        row1 = state.completed[1]
        assert row1.id == "FB-T01", f"Expected FB-T01, got {row1.id}"
        assert row1.title == "Completed beta task", (
            f"Unexpected title: {row1.title!r}"
        )


# ===================================================================
# 10. ## Out of scope — verbatim preservation
# ===================================================================

class TestParseOutOfScopeVerbatim:
    """## Out of scope block is stored verbatim."""

    def test_parse_out_of_scope_verbatim(self):
        """out_of_scope_raw preserves the full block including heading."""
        state = parse_session_file(FIXTURE_PATH)
        assert "## Out of scope" in state.out_of_scope_raw, (
            "out_of_scope_raw should contain the ## heading"
        )
        assert "Phase 6 TUI" in state.out_of_scope_raw, (
            "out_of_scope_raw should contain the first bullet"
        )
        assert "Multi-level undo" in state.out_of_scope_raw, (
            "out_of_scope_raw should contain all bullets"
        )


# ===================================================================
# 11. ## Active task — [none] → active_task = None
# ===================================================================

class TestParseActiveTaskUnsetNone:
    """[none] content in Active task section sets active_task to None."""

    def test_parse_active_task_unset_none(self):
        """Block containing [none] returns active_task=None."""
        content = """\
        *Last updated: 2026-04-15T00:00*

        ---

        ## Active phase

        Phase 1 — Test — in progress.
        Spec: `spec.md`

        ---

        ## Active task

        [none]

        ---

        ## Out of scope

        Nothing.
        """
        state = _parse_inline(content)
        assert state.active_task is None, (
            "Expected active_task to be None for [none] block"
        )
        assert "[none]" in state.active_task_raw, (
            "active_task_raw should contain [none] for later display"
        )


# ===================================================================
# 12. ## Active task — blank/empty → active_task = None
# ===================================================================

class TestParseActiveTaskUnsetBlank:
    """Blank/empty content in Active task section sets active_task to None."""

    def test_parse_active_task_unset_blank(self):
        """Empty block returns active_task=None."""
        content = """\
        *Last updated: 2026-04-15T00:00*

        ---

        ## Active phase

        Phase 1 — Test — in progress.
        Spec: `spec.md`

        ---

        ## Active task

        ---

        ## Out of scope

        Nothing.
        """
        state = _parse_inline(content)
        assert state.active_task is None, (
            "Expected active_task to be None for empty block"
        )
