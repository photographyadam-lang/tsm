# tests/writers/test_tasks_writer.py — P3-T03 tasks_writer tests
#
# Tests cover all four "Done when:" criteria from the P3-T03 task block.
#
#   1. update_task_status on fixture content → re-parse → task.status
#      equals the new value; all other task raw_blocks are identical.
#   2. update_phase_status on fixture content → re-parse → phase.status
#      equals the new value; all task raw_blocks are identical.
#   3. Bytes outside the replaced **Status:** line are identical before
#      and after for both functions (byte-diff verified).
#   4. Both functions raise ValueError for unknown task_id / phase heading.

from pathlib import Path

import pytest

from tsm.models import TaskStatus
from tsm.parsers.tasks_parser import parse_tasks_file
from tsm.writers.tasks_writer import (
    update_task_status,
    update_phase_status,
)


# ── Fixture helpers ─────────────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "TASKS.md"


def _load_fixture() -> str:
    """Return the full text of the shared TASKS.md fixture."""
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _parse_content(content: str):
    """Write *content* to a temp file, parse it, return (overview, phases)."""
    tmp = FIXTURE_DIR / ".tmp_test_writers.md"
    tmp.write_text(content, encoding="utf-8")
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


def _get_raw_blocks(phases) -> dict[str, str]:
    """Return a dict mapping task_id → raw_block for all tasks."""
    blocks = {}
    for phase in phases:
        for task in phase.tasks:
            blocks[task.id] = task.raw_block
    return blocks


def _find_phase(phases, phase_name: str):
    """Find a phase by its name."""
    for phase in phases:
        if phase.name == phase_name:
            return phase
    return None


# ===================================================================
# Criterion 1: Task-level status update → round-trip
# ===================================================================


class TestUpdateTaskStatus:
    """``update_task_status`` changes the correct task's ``**Status:**``
    line, and after re-parsing the modified content only that task's
    status has changed; all other ``raw_block`` s are untouched."""

    def test_updates_status_to_complete(self):
        """FA-T03 (Pending) → ✅ Complete → status is COMPLETE."""
        content = _load_fixture()
        modified = update_task_status(content, "FA-T03", "✅ Complete")
        _, phases = _parse_content(modified)
        task = _get_task(phases, "FA-T03")
        assert task is not None
        assert task.status == TaskStatus.COMPLETE

    def test_updates_status_to_pending(self):
        """FA-T01 (Complete) → Pending → status is PENDING."""
        content = _load_fixture()
        modified = update_task_status(content, "FA-T01", "Pending")
        _, phases = _parse_content(modified)
        task = _get_task(phases, "FA-T01")
        assert task is not None
        assert task.status == TaskStatus.PENDING

    def test_updates_status_to_blocked(self):
        """FA-T01 (Complete) → 🔒 Blocked → status is BLOCKED."""
        content = _load_fixture()
        modified = update_task_status(content, "FA-T01", "🔒 Blocked")
        _, phases = _parse_content(modified)
        task = _get_task(phases, "FA-T01")
        assert task is not None
        assert task.status == TaskStatus.BLOCKED

    def test_updates_status_to_active(self):
        """FA-T03 (Pending) → **Active** → status is ACTIVE."""
        content = _load_fixture()
        modified = update_task_status(content, "FA-T03", "**Active**")
        _, phases = _parse_content(modified)
        task = _get_task(phases, "FA-T03")
        assert task is not None
        assert task.status == TaskStatus.ACTIVE

    def test_other_task_raw_blocks_unchanged(self):
        """After updating FA-T01's status, every other task's
        ``raw_block`` is byte-identical to the original."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        original_blocks = _get_raw_blocks(original_phases)

        modified = update_task_status(content, "FA-T01", "Pending")
        _, new_phases = _parse_content(modified)
        new_blocks = _get_raw_blocks(new_phases)

        for tid, orig_raw in original_blocks.items():
            if tid == "FA-T01":
                continue  # this one changed
            assert new_blocks[tid] == orig_raw, (
                f"raw_block for {tid} changed after FA-T01 status update"
            )

    def test_other_task_raw_blocks_unchanged_second_phase(self):
        """Same check but updating a Phase 2 task instead."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        original_blocks = _get_raw_blocks(original_phases)

        modified = update_task_status(content, "FB-T02", "✅ Complete")
        _, new_phases = _parse_content(modified)
        new_blocks = _get_raw_blocks(new_phases)

        for tid, orig_raw in original_blocks.items():
            if tid == "FB-T02":
                continue
            assert new_blocks[tid] == orig_raw, (
                f"raw_block for {tid} changed after FB-T02 status update"
            )


# ===================================================================
# Criterion 2: Phase-level status update → round-trip
# ===================================================================


class TestUpdatePhaseStatus:
    """``update_phase_status`` changes the phase header ``**Status:**``
    line, and after re-parsing the modified content the phase status
    reflects the new value while all task ``raw_block`` s are unchanged."""

    def test_updates_phase_status_to_complete(self):
        """Phase 2 (Pending) → ✅ Complete."""
        content = _load_fixture()
        modified = update_phase_status(
            content, "Phase 2 — Fixture Beta", "✅ Complete"
        )
        _, phases = _parse_content(modified)
        phase = _find_phase(phases, "Phase 2 — Fixture Beta")
        assert phase is not None
        assert phase.status == "✅ Complete"

    def test_updates_phase_status_to_pending(self):
        """Phase 1 (Complete) → Pending."""
        content = _load_fixture()
        modified = update_phase_status(
            content, "Phase 1 — Fixture Alpha", "Pending"
        )
        _, phases = _parse_content(modified)
        phase = _find_phase(phases, "Phase 1 — Fixture Alpha")
        assert phase is not None
        assert phase.status == "Pending"

    def test_all_task_raw_blocks_unchanged_after_phase_update(self):
        """Phase-level update must not touch any task raw_block."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        original_blocks = _get_raw_blocks(original_phases)

        modified = update_phase_status(
            content, "Phase 1 — Fixture Alpha", "Pending"
        )
        _, new_phases = _parse_content(modified)
        new_blocks = _get_raw_blocks(new_phases)

        for tid, orig_raw in original_blocks.items():
            assert new_blocks[tid] == orig_raw, (
                f"raw_block for {tid} changed after phase status update"
            )


# ===================================================================
# Criterion 3: Byte-diff — only the **Status:** line changes
# ===================================================================


class TestByteDiffVerification:
    """Verify that bytes outside the replaced ``**Status:**`` line are
    identical before and after for *both* functions."""

    def _assert_only_status_line_changed(
        self, original: str, modified: str
    ):
        """Compare line-by-line and assert that at most one line differs,
        and that differing line contains ``**Status:**``."""
        orig_lines = original.splitlines(keepends=True)
        mod_lines = modified.splitlines(keepends=True)

        assert len(orig_lines) == len(mod_lines), (
            "Line count changed!"
        )

        diffs = []
        for i, (o, m) in enumerate(zip(orig_lines, mod_lines)):
            if o != m:
                diffs.append((i, o, m))

        assert len(diffs) >= 1, "Expected at least one line to differ"
        assert len(diffs) == 1, (
            f"Expected exactly 1 differing line, got {len(diffs)}: {diffs}"
        )
        idx, original_line, modified_line = diffs[0]
        assert "**Status:**" in original_line, (
            f"Changed line {idx} is not a **Status:** line: "
            f"{original_line!r}"
        )
        assert "**Status:**" in modified_line, (
            f"Result line {idx} is not a **Status:** line: "
            f"{modified_line!r}"
        )

    def test_task_update_byte_diff(self):
        """Only the ``**Status:**`` line changes in a task update."""
        content = _load_fixture()
        modified = update_task_status(content, "FA-T03", "✅ Complete")
        self._assert_only_status_line_changed(content, modified)

    def test_task_update_byte_diff_second_phase(self):
        """Same check for a Phase 2 task."""
        content = _load_fixture()
        modified = update_task_status(content, "FB-T03", "✅ Complete")
        self._assert_only_status_line_changed(content, modified)

    def test_phase_update_byte_diff(self):
        """Only the ``**Status:**`` line changes in a phase update."""
        content = _load_fixture()
        modified = update_phase_status(
            content, "Phase 1 — Fixture Alpha", "Pending"
        )
        self._assert_only_status_line_changed(content, modified)

    def test_phase_update_byte_diff_phase2(self):
        """Same check for Phase 2."""
        content = _load_fixture()
        modified = update_phase_status(
            content, "Phase 2 — Fixture Beta", "✅ Complete"
        )
        self._assert_only_status_line_changed(content, modified)


# ===================================================================
# Criterion 4: ValueError for unknown task_id / phase heading
# ===================================================================


class TestValueError:
    """Both functions must raise ``ValueError`` with a clear message
    when given a target that does not exist in the content."""

    def test_unknown_task_id_raises(self):
        content = _load_fixture()
        with pytest.raises(ValueError, match="not found"):
            update_task_status(content, "NONEXISTENT-TASK", "✅ Complete")

    def test_unknown_phase_heading_raises(self):
        content = _load_fixture()
        with pytest.raises(ValueError, match="not found"):
            update_phase_status(
                content, "Phase 99 — Imaginary", "✅ Complete"
            )
