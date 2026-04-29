# tests/parsers/test_tasks_parser.py — 21 core tests for P2-T01
#
# All tests use either the shared fixture file (tests/fixtures/TASKS.md) or
# inline minimal content to keep each test self-contained.

from pathlib import Path
from textwrap import dedent

import pytest

from tsm.models import TaskStatus, TaskComplexity
from tsm.parsers.tasks_parser import parse_tasks_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "TASKS.md"


def _parse_inline(content: str):
    """Write inline content to a temp file, parse it, return (overview, phases)."""
    tmp = FIXTURE_DIR / ".tmp_test_tasks.md"
    tmp.write_text(dedent(content), encoding="utf-8")
    try:
        return parse_tasks_file(tmp)
    finally:
        if tmp.exists():
            tmp.unlink()


def _get_task(phases, task_id: str):
    """Find a task by ID across all phases."""
    for phase in phases:
        for task in phase.tasks:
            if task.id == task_id:
                return task
    return None


# ===================================================================
# 1. Status token: ✅ Complete
# ===================================================================

class TestParseStatusComplete:
    """✅ Complete token maps to TaskStatus.COMPLETE."""

    def test_parse_status_complete(self):
        """FA-T01 has status ✅ Complete."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T01")
        assert task is not None, "FA-T01 not found"
        assert task.status == TaskStatus.COMPLETE, (
            f"Expected COMPLETE, got {task.status}"
        )


# ===================================================================
# 2. Status token: **Active** (bold-wrapped)
# ===================================================================

class TestParseStatusActiveBold:
    """**Active** bold-wrapped token maps to TaskStatus.ACTIVE."""

    def test_parse_status_active_bold(self):
        """FA-T02 has status **Active**."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T02")
        assert task is not None, "FA-T02 not found"
        assert task.status == TaskStatus.ACTIVE, (
            f"Expected ACTIVE, got {task.status}"
        )


# ===================================================================
# 3. Status token: Pending
# ===================================================================

class TestParseStatusPending:
    """Pending token maps to TaskStatus.PENDING."""

    def test_parse_status_pending(self):
        """FA-T03 has status Pending."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T03")
        assert task is not None, "FA-T03 not found"
        assert task.status == TaskStatus.PENDING, (
            f"Expected PENDING, got {task.status}"
        )


# ===================================================================
# 4. Status token: 🔒 Blocked
# ===================================================================

class TestParseStatusBlockedLock:
    """🔒 Blocked token maps to TaskStatus.BLOCKED."""

    def test_parse_status_blocked_lock(self):
        """FA-T04 has status 🔒 Blocked."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T04")
        assert task is not None, "FA-T04 not found"
        assert task.status == TaskStatus.BLOCKED, (
            f"Expected BLOCKED, got {task.status}"
        )


# ===================================================================
# 5. Status token: ❌ Blocked (cross-mark variant)
# ===================================================================

class TestParseStatusBlockedCross:
    """❌ Blocked token maps to TaskStatus.BLOCKED."""

    def test_parse_status_blocked_cross(self):
        content = """\
        # Test Phase

        ---

        ## Phase structure

        | Phase | Description | Status |
        |-------|-------------|--------|
        | **Phase 1 — Test** | Testing | Pending |

        ---

        # Phase 1 — Test

        ---

        ## Tasks

        ### XT-01 · Cross blocked task

        **Status:** ❌ Blocked
        **Complexity:** low
        **What:** A task blocked with the cross-mark variant.
        **Prerequisite:** None.
        **Hard deps:** None
        **Files:** none
        **Reviewer:** Skip
        **Done when:** Cross variant recognised
        """
        _, phases = _parse_inline(content)
        task = _get_task(phases, "XT-01")
        assert task is not None, "XT-01 not found"
        assert task.status == TaskStatus.BLOCKED, (
            f"Expected BLOCKED, got {task.status}"
        )


# ===================================================================
# 6. Hard deps: multiple comma-separated
# ===================================================================

class TestParseHardDepsMultiple:
    """Multiple comma-separated dependency IDs."""

    def test_parse_hard_deps_multiple(self):
        """FB-T03 has hard_deps = [FB-T01, FA-T02]."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FB-T03")
        assert task is not None, "FB-T03 not found"
        assert task.hard_deps == ["FB-T01", "FA-T02"], (
            f"Expected [FB-T01, FA-T02], got {task.hard_deps}"
        )


# ===================================================================
# 7. Hard deps: em-dash (—) → []
# ===================================================================

class TestParseHardDepsEmDash:
    """Em-dash '—' yields an empty list."""

    def test_parse_hard_deps_em_dash(self):
        """FA-T03 has hard deps = —."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T03")
        assert task is not None, "FA-T03 not found"
        assert task.hard_deps == [], (
            f"Expected [], got {task.hard_deps}"
        )


# ===================================================================
# 8. Hard deps: "None" text → []
# ===================================================================

class TestParseHardDepsNoneText:
    """The literal text "None" yields an empty list."""

    def test_parse_hard_deps_none_text(self):
        """FA-T01 has hard deps = None."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T01")
        assert task is not None, "FA-T01 not found"
        assert task.hard_deps == [], (
            f"Expected [], got {task.hard_deps}"
        )


# ===================================================================
# 9. Hard deps: "None." → []
# ===================================================================

class TestParseHardDepsNoneDot:
    """The literal text "None." yields an empty list."""

    def test_parse_hard_deps_none_dot(self):
        """FA-T04 has hard deps = None."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T04")
        assert task is not None, "FA-T04 not found"
        assert task.hard_deps == [], (
            f"Expected [], got {task.hard_deps}"
        )


# ===================================================================
# 10. Files: backtick-wrapped with (new) suffix
# ===================================================================

class TestParseFilesBacktickNew:
    """Backtick-wrapped file paths with (new) suffix are cleaned."""

    def test_parse_files_backtick_new(self):
        """FB-T03 has backtick files with (new) suffix."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FB-T03")
        assert task is not None, "FB-T03 not found"
        assert task.files == [
            "src/adapters.py",
            "src/validators.py",
            "docs/guide.md",
        ], f"Got {task.files}"


# ===================================================================
# 11. Files: multiple comma-separated
# ===================================================================

class TestParseFilesMultiple:
    """Multiple file paths are split on comma."""

    def test_parse_files_multiple(self):
        """FA-T02 has files = `src/feature.py`(new), `src/utils.py`."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T02")
        assert task is not None, "FA-T02 not found"
        assert task.files == ["src/feature.py", "src/utils.py"], (
            f"Got {task.files}"
        )


# ===================================================================
# 12. Files: "See spec §8" passthrough
# ===================================================================

class TestParseFilesSeeSpec:
    """The literal 'See spec §8' is kept as-is."""

    def test_parse_files_see_spec(self):
        """FA-T03 has files = See spec §8, config/settings.json."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T03")
        assert task is not None, "FA-T03 not found"
        assert task.files == ["See spec §8", "config/settings.json"], (
            f"Got {task.files}"
        )


# ===================================================================
# 13. Files: blank → []
# ===================================================================

class TestParseFilesBlank:
    """Blank Files field yields an empty list."""

    def test_parse_files_blank(self):
        """FA-T04 has an empty Files field."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T04")
        assert task is not None, "FA-T04 not found"
        # FA-T04 has `**Files:**` with no value → blank → []
        assert task.files == [], f"Expected [], got {task.files}"


# ===================================================================
# 14. Multi-line What
# ===================================================================

class TestParseMultilineWhat:
    """What field spanning multiple lines is accumulated."""

    def test_parse_multiline_what(self):
        """FA-T02 has a multi-line What field."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T02")
        assert task is not None, "FA-T02 not found"
        assert "spans across three distinct lines" in task.what, (
            f"Multi-line What not preserved: {task.what!r}"
        )
        # Verify it's actually multi-line
        assert "\n" in task.what, (
            f"What should contain newlines: {task.what!r}"
        )


# ===================================================================
# 15. Multi-line Done when
# ===================================================================

class TestParseMultilineDoneWhen:
    """Done when field spanning multiple lines is accumulated."""

    def test_parse_multiline_done_when(self):
        """FA-T03 has a multi-line Done when field."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T03")
        assert task is not None, "FA-T03 not found"
        assert "First criterion line" in task.done_when, (
            f"Multi-line Done when not preserved: {task.done_when!r}"
        )
        assert "\n" in task.done_when, (
            f"Done when should contain newlines: {task.done_when!r}"
        )


# ===================================================================
# 16. Phase structure table
# ===================================================================

class TestParsePhaseStructureTable:
    """Phase overview rows are correctly extracted."""

    def test_parse_phase_structure_table(self):
        overview, _ = parse_tasks_file(FIXTURE_PATH)
        # The fixture has 2 phase overview rows
        assert len(overview) == 2, f"Expected 2 overview rows, got {len(overview)}"
        names = [row.phase_name for row in overview]
        assert "Phase 1 — Fixture Alpha" in names, f"Missing Phase 1: {names}"
        assert "Phase 2 — Fixture Beta" in names, f"Missing Phase 2: {names}"


# ===================================================================
# 17. Multi-phase file
# ===================================================================

class TestParseMultiPhaseFile:
    """A file with multiple phases produces one Phase per # heading."""

    def test_parse_multi_phase_file(self):
        _, phases = parse_tasks_file(FIXTURE_PATH)
        assert len(phases) == 2, f"Expected 2 phases, got {len(phases)}"
        phase_ids = [p.id for p in phases]
        assert "phase-1--fixture-alpha" in phase_ids, (
            f"Missing phase-1: {phase_ids}"
        )
        assert "phase-2--fixture-beta" in phase_ids, (
            f"Missing phase-2: {phase_ids}"
        )


# ===================================================================
# 18. raw_block preserved byte-for-byte
# ===================================================================

class TestParseRawBlockPreserved:
    """raw_block contains the exact source text from the original file."""

    def test_parse_raw_block_preserved(self):
        """FA-T01 raw_block should start with the ### heading and contain fields."""
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T01")
        assert task is not None, "FA-T01 not found"
        assert task.raw_block.startswith("### FA-T01 · Completed setup task"), (
            f"raw_block should start with heading: {task.raw_block[:80]!r}"
        )
        assert "**Status:** ✅ Complete" in task.raw_block, (
            "raw_block missing Status"
        )
        assert "**Done when:**" in task.raw_block, "raw_block missing Done when"


# ===================================================================
# 19. Task ID and title extraction from ### heading
# ===================================================================

class TestTaskIdTitleExtraction:
    """### ID · Title correctly splits into id and title."""

    def test_task_id_title_extraction(self):
        _, phases = parse_tasks_file(FIXTURE_PATH)
        task = _get_task(phases, "FA-T01")
        assert task is not None, "FA-T01 not found"
        assert task.id == "FA-T01", f"Wrong id: {task.id}"
        assert task.title == "Completed setup task", f"Wrong title: {task.title}"

        task2 = _get_task(phases, "FB-T03")
        assert task2 is not None, "FB-T03 not found"
        assert task2.id == "FB-T03", f"Wrong id: {task2.id}"
        assert task2.title == "Active beta task with backtick new files", (
            f"Wrong title: {task2.title}"
        )


# ===================================================================
# 20. ### Dependency graph blocks must NOT produce a Task object
# ===================================================================

class TestDepGraphNotParsedAsTask:
    """### Dependency graph headings must not emit a Task."""

    def test_dep_graph_not_parsed_as_task(self):
        _, phases = parse_tasks_file(FIXTURE_PATH)
        # Ensure the dep graph headings did not spawn tasks
        all_task_ids = []
        for p in phases:
            all_task_ids.extend(t.id for t in p.tasks)
        # None of the dep-graph heading identifiers should appear
        assert "Dependency graph" not in all_task_ids, (
            "Dep graph heading was parsed as a task!"
        )
        # Also check only the 7 expected tasks exist
        expected = {"FA-T01", "FA-T02", "FA-T03", "FA-T04",
                    "FB-T01", "FB-T02", "FB-T03"}
        actual = set(all_task_ids)
        assert actual == expected, (
            f"Expected tasks {expected}, got {actual}"
        )


# ===================================================================
# 21. Dependency graph raw content preserved in Phase
# ===================================================================

class TestDepGraphRawPreserved:
    """Phase.dependency_graph_raw contains the fenced dep-graph block."""

    def test_dep_graph_raw_preserved(self):
        _, phases = parse_tasks_file(FIXTURE_PATH)
        # Phase 1 should have a dep graph
        phase1 = next(p for p in phases if "fixture-alpha" in p.id)
        raw = phase1.dependency_graph_raw
        assert raw, "Phase 1 dep graph raw should not be empty"
        assert "FA-T01" in raw, f"Dep graph missing FA-T01: {raw!r}"
        assert "└── FA-T02" in raw or "FA-T02" in raw, (
            f"Dep graph missing FA-T02: {raw!r}"
        )
        # Phase 2 should also have a dep graph
        phase2 = next(p for p in phases if "fixture-beta" in p.id)
        raw2 = phase2.dependency_graph_raw
        assert raw2, "Phase 2 dep graph raw should not be empty"
        assert "FB-T01" in raw2, f"Dep graph missing FB-T01: {raw2!r}"
