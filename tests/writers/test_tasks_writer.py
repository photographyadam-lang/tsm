# tests/writers/test_tasks_writer.py — P3-T03 + P7-T03a tasks_writer tests
#
# Phase 3 tests (P3-T03) cover update_task_status and update_phase_status.
# Phase 7 tests (P7-T03a) cover the six structural writer functions:
#   insert_phase_block, remove_phase_block, insert_task_block,
#   remove_task_block, update_phase_structure_table, update_task_field
#
# Done-when criteria (P7-T03a):
#   1. insert_phase_block → re-parse → new phase at correct position;
#      all other phase content byte-identical
#   2. remove_phase_block → re-parse → phase gone;
#      all other phases byte-identical
#   3. insert_task_block → re-parse → task at correct position;
#      dep graph block is still last in its phase
#   4. remove_task_block → re-parse → task gone;
#      all other task raw_blocks byte-identical
#   5. update_phase_structure_table → re-parse → PhaseOverviewRows match input;
#      all task blocks unchanged
#   6. update_task_field for a multi-line What field → re-parse → task.what
#      equals new value; all other task fields unchanged
#   7. update_task_field adding Key constraints to a task that had none →
#      re-parse → key_constraints populated; field appears before Done when

from pathlib import Path

import pytest

from tsm.models import PhaseOverviewRow, TaskStatus, TaskComplexity
from tsm.parsers.tasks_parser import parse_tasks_file
from tsm.parsers.session_parser import parse_session_file
from tsm.writers.tasks_writer import (
    update_task_status,
    update_phase_status,
    insert_phase_block,
    remove_phase_block,
    insert_task_block,
    remove_task_block,
    update_phase_structure_table,
    update_task_field,
    reorder_phase_blocks,
    reorder_task_blocks,
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
    """Return a dict mapping task_id -> raw_block for all tasks."""
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
# Criterion 1: insert_phase_block
# ===================================================================


NEW_PHASE_BLOCK = """\
# Phase 3 — Fixture Gamma

**Status:** Pending

Gamma-phase fixture tasks for structural writer tests.

---

## Phase 3 tasks

### GA-T01 · Gamma alpha task

**Status:** Pending
**Complexity:** low
**What:** First task in the new gamma phase.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/gamma.py
**Reviewer:** Skip
**Done when:**
- Gamma phase fixture parses correctly

---

### Dependency graph

```
GA-T01
```

---

"""


class TestInsertPhaseBlock:
    """``insert_phase_block`` inserts a new H1 phase block at the correct
    position; after re-parsing the new phase exists there and all other
    phase content is byte-identical."""

    def test_inserts_after_first_phase(self):
        """Insert new phase after Phase 1 → appears between Phase 1 and Phase 2."""
        content = _load_fixture()
        modified = insert_phase_block(
            content, NEW_PHASE_BLOCK, after_phase_id="phase-1--fixture-alpha"
        )
        overview, phases = _parse_content(modified)

        # Should now have 3 phases
        assert len(phases) == 3, f"Expected 3 phases, got {len(phases)}"

        # Phase order: Phase 1, Phase 3 (new), Phase 2
        assert phases[0].name == "Phase 1 — Fixture Alpha"
        assert phases[1].name == "Phase 3 — Fixture Gamma"
        assert phases[2].name == "Phase 2 — Fixture Beta"

    def test_inserts_at_end_when_no_after_id(self):
        """Insert with after_phase_id=None → appended at end of file."""
        content = _load_fixture()
        modified = insert_phase_block(content, NEW_PHASE_BLOCK, after_phase_id=None)
        overview, phases = _parse_content(modified)

        assert len(phases) == 3
        # New phase is last
        assert phases[-1].name == "Phase 3 — Fixture Gamma"

    def test_inserts_at_end_after_last_phase(self):
        """Insert after the last phase → appended at end."""
        content = _load_fixture()
        modified = insert_phase_block(
            content, NEW_PHASE_BLOCK, after_phase_id="phase-2--fixture-beta"
        )
        overview, phases = _parse_content(modified)

        assert len(phases) == 3
        assert phases[-1].name == "Phase 3 — Fixture Gamma"

    def test_other_phases_byte_identical_after_insert(self):
        """After inserting a phase between Phase 1 and Phase 2, the content
        of Phase 1 and Phase 2 is byte-identical to the original."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        original_phase1 = _find_phase(original_phases, "Phase 1 — Fixture Alpha")
        original_phase2 = _find_phase(original_phases, "Phase 2 — Fixture Beta")
        orig_p1_tasks = [t.raw_block for t in original_phase1.tasks] if original_phase1 else []
        orig_p2_tasks = [t.raw_block for t in original_phase2.tasks] if original_phase2 else []

        modified = insert_phase_block(
            content, NEW_PHASE_BLOCK, after_phase_id="phase-1--fixture-alpha"
        )
        _, new_phases = _parse_content(modified)
        new_phase1 = _find_phase(new_phases, "Phase 1 — Fixture Alpha")
        new_phase2 = _find_phase(new_phases, "Phase 2 — Fixture Beta")

        if new_phase1:
            new_p1_tasks = [t.raw_block for t in new_phase1.tasks]
            assert new_p1_tasks == orig_p1_tasks, (
                "Phase 1 task raw_blocks changed after insert"
            )
        if new_phase2:
            new_p2_tasks = [t.raw_block for t in new_phase2.tasks]
            assert new_p2_tasks == orig_p2_tasks, (
                "Phase 2 task raw_blocks changed after insert"
            )

    def test_unknown_phase_id_raises(self):
        """Insert with nonexistent after_phase_id → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="not found"):
            insert_phase_block(content, NEW_PHASE_BLOCK, after_phase_id="nonexistent-phase")


# ===================================================================
# Criterion 2: remove_phase_block
# ===================================================================


class TestRemovePhaseBlock:
    """``remove_phase_block`` removes the H1 phase block; after re-parsing
    the phase is gone and all other phases are byte-identical."""

    def test_removes_first_phase(self):
        """Remove Phase 1 → only Phase 2 remains."""
        content = _load_fixture()
        modified = remove_phase_block(content, "phase-1--fixture-alpha")
        overview, phases = _parse_content(modified)

        assert len(phases) == 1, f"Expected 1 phase, got {len(phases)}"
        assert phases[0].name == "Phase 2 — Fixture Beta"

    def test_removes_second_phase(self):
        """Remove Phase 2 → only Phase 1 remains."""
        content = _load_fixture()
        modified = remove_phase_block(content, "phase-2--fixture-beta")
        overview, phases = _parse_content(modified)

        assert len(phases) == 1
        assert phases[0].name == "Phase 1 — Fixture Alpha"

    def test_other_phases_byte_identical_after_remove(self):
        """After removing Phase 2, Phase 1's task raw_blocks are untouched."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        original_phase1 = _find_phase(original_phases, "Phase 1 — Fixture Alpha")
        orig_p1_tasks = [t.raw_block for t in original_phase1.tasks] if original_phase1 else []

        modified = remove_phase_block(content, "phase-2--fixture-beta")
        _, new_phases = _parse_content(modified)
        new_phase1 = _find_phase(new_phases, "Phase 1 — Fixture Alpha")

        if new_phase1:
            new_p1_tasks = [t.raw_block for t in new_phase1.tasks]
            assert new_p1_tasks == orig_p1_tasks, (
                "Phase 1 task raw_blocks changed after Phase 2 removal"
            )

    def test_unknown_phase_id_raises(self):
        """Remove with nonexistent phase_id → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="not found"):
            remove_phase_block(content, "nonexistent-phase")


# ===================================================================
# Criterion 3: insert_task_block
# ===================================================================


NEW_TASK_BLOCK = """\
### FA-T05 · New inserted task

**Status:** Pending
**Complexity:** low
**What:** A task inserted by the structural writer.
**Prerequisite:** None.
**Hard deps:** FA-T01
**Files:** src/new_feature.py
**Reviewer:** Skip
**Done when:**
- Inserted task parses correctly
- Dep graph block is still last
"""


class TestInsertTaskBlock:
    """``insert_task_block`` inserts a new task ### block within the correct
    phase, before the ### Dependency graph block."""

    def test_inserts_task_before_dep_graph(self):
        """Insert FA-T05 into Phase 1 → dep graph is still last in Phase 1."""
        content = _load_fixture()
        modified = insert_task_block(
            content, NEW_TASK_BLOCK, phase_id="phase-1--fixture-alpha",
            after_task_id=None,
        )
        _, phases = _parse_content(modified)

        phase1 = _find_phase(phases, "Phase 1 — Fixture Alpha")
        assert phase1 is not None

        task_ids = [t.id for t in phase1.tasks]
        # Dep graph task (FA-T04) should still be last in Phase 1
        # FA-T05 should be before dep graph
        assert "FA-T05" in task_ids, "FA-T05 was not inserted"

        # The original Phase 1 has FA-T01, FA-T02, FA-T03, FA-T04.
        # After insert (no after_task_id), FA-T05 goes at the start.
        # So order should be: FA-T05, FA-T01, FA-T02, FA-T03, FA-T04
        # (since dep graph is not a task and appears last)
        assert task_ids[0] == "FA-T05"  # first since after_task_id=None
        assert task_ids[-1] == "FA-T04"  # dep graph block remains last

    def test_inserts_task_after_specific_task(self):
        """Insert FA-T05 after FA-T02 → FA-T05 appears between FA-T02 and FA-T03."""
        content = _load_fixture()
        modified = insert_task_block(
            content, NEW_TASK_BLOCK, phase_id="phase-1--fixture-alpha",
            after_task_id="FA-T02",
        )
        _, phases = _parse_content(modified)

        phase1 = _find_phase(phases, "Phase 1 — Fixture Alpha")
        assert phase1 is not None

        task_ids = [t.id for t in phase1.tasks]
        # Original order: FA-T01, FA-T02, FA-T03, FA-T04
        # After FA-T02: FA-T01, FA-T02, FA-T05, FA-T03, FA-T04
        fa02_idx = task_ids.index("FA-T02")
        fa05_idx = task_ids.index("FA-T05")
        assert fa05_idx == fa02_idx + 1, (
            f"FA-T05 should be immediately after FA-T02, "
            f"but FA-T02 is at {fa02_idx} and FA-T05 is at {fa05_idx}"
        )

    def test_insert_task_into_second_phase(self):
        """Insert FA-T05 into Phase 2 → Phase 1 is untouched."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        orig_phase1_tasks = [
            t.raw_block
            for t in (_find_phase(original_phases, "Phase 1 — Fixture Alpha") or []).tasks
        ]

        modified = insert_task_block(
            content, NEW_TASK_BLOCK, phase_id="phase-2--fixture-beta",
            after_task_id=None,
        )
        _, new_phases = _parse_content(modified)
        new_phase1 = _find_phase(new_phases, "Phase 1 — Fixture Alpha")
        new_phase2 = _find_phase(new_phases, "Phase 2 — Fixture Beta")

        # Phase 1 untouched
        if new_phase1:
            new_p1_tasks = [t.raw_block for t in new_phase1.tasks]
            assert new_p1_tasks == orig_phase1_tasks, (
                "Phase 1 task raw_blocks changed after inserting into Phase 2"
            )

        # Phase 2 has the new task
        if new_phase2:
            task_ids = [t.id for t in new_phase2.tasks]
            assert "FA-T05" in task_ids

    def test_dep_graph_still_last_after_insert(self):
        """After inserting a task, ### Dependency graph block is still the last
        block-like structure in its phase (no task appears after it)."""
        content = _load_fixture()
        modified = insert_task_block(
            content, NEW_TASK_BLOCK, phase_id="phase-1--fixture-alpha",
            after_task_id="FA-T03",
        )
        _, phases = _parse_content(modified)

        phase1 = _find_phase(phases, "Phase 1 — Fixture Alpha")
        assert phase1 is not None
        # The dep_graph_raw should still be present
        assert phase1.dependency_graph_raw != "", "Dep graph block missing"
        # FA-T04 (Blocked, last task) should still be the last task
        task_ids = [t.id for t in phase1.tasks]
        assert task_ids[-1] == "FA-T04", (
            f"Expected FA-T04 (blocked dep graph task) to be last, "
            f"got {task_ids[-1]}; full order: {task_ids}"
        )

    def test_unknown_phase_id_raises(self):
        """Insert into nonexistent phase → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="not found"):
            insert_task_block(
                content, NEW_TASK_BLOCK, phase_id="nonexistent-phase",
            )

    def test_unknown_after_task_id_raises(self):
        """Insert after nonexistent task → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="not found"):
            insert_task_block(
                content, NEW_TASK_BLOCK, phase_id="phase-1--fixture-alpha",
                after_task_id="NONEXISTENT",
            )


# ===================================================================
# Criterion 4: remove_task_block
# ===================================================================


class TestRemoveTaskBlock:
    """``remove_task_block`` removes the ### task block; after re-parsing
    the task is gone and all other task raw_blocks are byte-identical."""

    def test_removes_first_task(self):
        """Remove FA-T01 → Phase 1 has FA-T02, FA-T03, FA-T04."""
        content = _load_fixture()
        modified = remove_task_block(content, "FA-T01")
        _, phases = _parse_content(modified)

        phase1 = _find_phase(phases, "Phase 1 — Fixture Alpha")
        assert phase1 is not None
        task_ids = [t.id for t in phase1.tasks]
        assert "FA-T01" not in task_ids
        assert task_ids == ["FA-T02", "FA-T03", "FA-T04"]

    def test_removes_middle_task(self):
        """Remove FA-T02 → Phase 1 has FA-T01, FA-T03, FA-T04."""
        content = _load_fixture()
        modified = remove_task_block(content, "FA-T02")
        _, phases = _parse_content(modified)

        phase1 = _find_phase(phases, "Phase 1 — Fixture Alpha")
        assert phase1 is not None
        task_ids = [t.id for t in phase1.tasks]
        assert "FA-T02" not in task_ids
        assert task_ids == ["FA-T01", "FA-T03", "FA-T04"]

    def test_removes_last_task(self):
        """Remove FA-T04 → Phase 1 has FA-T01, FA-T02, FA-T03."""
        content = _load_fixture()
        modified = remove_task_block(content, "FA-T04")
        _, phases = _parse_content(modified)

        phase1 = _find_phase(phases, "Phase 1 — Fixture Alpha")
        assert phase1 is not None
        task_ids = [t.id for t in phase1.tasks]
        assert "FA-T04" not in task_ids
        assert task_ids == ["FA-T01", "FA-T02", "FA-T03"]

    def test_removes_from_second_phase(self):
        """Remove FB-T02 → Phase 2 has FB-T01, FB-T03."""
        content = _load_fixture()
        modified = remove_task_block(content, "FB-T02")
        _, phases = _parse_content(modified)

        phase2 = _find_phase(phases, "Phase 2 — Fixture Beta")
        assert phase2 is not None
        task_ids = [t.id for t in phase2.tasks]
        assert "FB-T02" not in task_ids
        assert task_ids == ["FB-T01", "FB-T03"]

    def test_other_tasks_byte_identical_after_remove(self):
        """After removing FA-T02, all other tasks' raw_blocks are untouched."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        original_blocks = _get_raw_blocks(original_phases)

        modified = remove_task_block(content, "FA-T02")
        _, new_phases = _parse_content(modified)
        new_blocks = _get_raw_blocks(new_phases)

        for tid, orig_raw in original_blocks.items():
            if tid == "FA-T02":
                continue  # this one was removed
            assert new_blocks[tid] == orig_raw, (
                f"raw_block for {tid} changed after FA-T02 removal"
            )

    def test_unknown_task_id_raises(self):
        """Remove nonexistent task → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="not found"):
            remove_task_block(content, "NONEXISTENT-TASK")


# ===================================================================
# Criterion 5: update_phase_structure_table
# ===================================================================


class TestUpdatePhaseStructureTable:
    """``update_phase_structure_table`` rewrites the ## Phase structure table;
    after re-parsing the PhaseOverviewRows match input and all task blocks
    are unchanged."""

    def test_updates_table_rows(self):
        """Rewriting the table with new rows → re-parse returns those rows."""
        content = _load_fixture()
        new_rows = [
            PhaseOverviewRow(
                phase_name="Phase 1 — Fixture Alpha",
                description="Alpha phase (updated)",
                status="✅ Complete",
            ),
            PhaseOverviewRow(
                phase_name="Phase 2 — Fixture Beta",
                description="Beta phase (updated)",
                status="✅ Complete",
            ),
        ]
        modified = update_phase_structure_table(content, new_rows)
        overview, _ = _parse_content(modified)

        assert len(overview) == 2
        assert overview[0].phase_name == "Phase 1 — Fixture Alpha"
        assert overview[0].description == "Alpha phase (updated)"
        assert overview[0].status == "✅ Complete"
        assert overview[1].phase_name == "Phase 2 — Fixture Beta"
        assert overview[1].description == "Beta phase (updated)"
        assert overview[1].status == "✅ Complete"

    def test_all_task_blocks_unchanged(self):
        """After updating the structure table, all task raw_blocks are
        byte-identical to the originals."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        original_blocks = _get_raw_blocks(original_phases)

        new_rows = [
            PhaseOverviewRow(
                phase_name="Phase 1 — Fixture Alpha",
                description="Updated desc",
                status="✅ Complete",
            ),
            PhaseOverviewRow(
                phase_name="Phase 2 — Fixture Beta",
                description="Updated desc 2",
                status="Pending",
            ),
        ]
        modified = update_phase_structure_table(content, new_rows)
        _, new_phases = _parse_content(modified)
        new_blocks = _get_raw_blocks(new_phases)

        for tid, orig_raw in original_blocks.items():
            assert new_blocks[tid] == orig_raw, (
                f"raw_block for {tid} changed after structure table update"
            )

    def test_missing_section_raises(self):
        """Calling without ## Phase structure in content → ValueError."""
        content = "# Only a title\n\nNo structure table here."
        with pytest.raises(ValueError, match="not found"):
            update_phase_structure_table(content, [])


# ===================================================================
# Criterion 6: update_task_field — multi-line What
# ===================================================================


class TestUpdateTaskFieldMultiLineWhat:
    """``update_task_field`` for a multi-line What field → after re-parsing,
    task.what equals the new value and all other task fields are unchanged."""

    def test_updates_multiline_what(self):
        """FA-T02 has a multi-line What → replace it."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        original_task = _get_task(original_phases, "FA-T02")
        assert original_task is not None
        # FA-T02 has a 3-line What field
        assert "\n" in original_task.what

        new_what = "Replacement multi-line what.\nSecond line of what.\nThird line."
        modified = update_task_field(content, "FA-T02", "What", new_what)
        _, new_phases = _parse_content(modified)
        new_task = _get_task(new_phases, "FA-T02")
        assert new_task is not None
        # The parser appends a trailing newline to multi-line What fields
        # (blank lines from later fields like **Done when:** accumulate into
        # what_lines). This matches existing parser behaviour — the original
        # FA-T02 What also has a trailing \n.
        assert new_task.what == new_what + "\n", (
            f"Expected what={new_what + chr(10)!r}, got {new_task.what!r}"
        )

    def test_other_fields_unchanged_after_what_update(self):
        """After updating FA-T02's What, all other fields and other tasks
        are unchanged."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        original_task = _get_task(original_phases, "FA-T02")
        original_blocks = _get_raw_blocks(original_phases)

        new_what = "Updated what field.\nMulti-line content."
        modified = update_task_field(content, "FA-T02", "What", new_what)
        _, new_phases = _parse_content(modified)
        new_task = _get_task(new_phases, "FA-T02")
        new_blocks = _get_raw_blocks(new_phases)

        # Other tasks untouched
        for tid, orig_raw in original_blocks.items():
            if tid == "FA-T02":
                continue
            assert new_blocks[tid] == orig_raw, (
                f"raw_block for {tid} changed after FA-T02 What update"
            )

        # FA-T02's other fields are unchanged
        assert new_task is not None and original_task is not None
        assert new_task.title == original_task.title
        assert new_task.status == original_task.status
        assert new_task.complexity == original_task.complexity
        assert new_task.prerequisite == original_task.prerequisite
        assert new_task.hard_deps == original_task.hard_deps
        assert new_task.files == original_task.files
        assert new_task.reviewer == original_task.reviewer
        assert new_task.key_constraints == original_task.key_constraints
        assert new_task.done_when == original_task.done_when


# ===================================================================
# Criterion 7: update_task_field — adding Key constraints to absent
# ===================================================================


class TestUpdateTaskFieldAddKeyConstraints:
    """``update_task_field`` adding Key constraints to a task that had none
    → after re-parsing, key_constraints is populated and the field appears
    before **Done when:**."""

    def test_adds_key_constraints_to_task_without(self):
        """FB-T02 has no Key constraints field → add it."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        original_task = _get_task(original_phases, "FB-T02")
        assert original_task is not None
        assert original_task.key_constraints == [], (
            "FB-T02 should start with empty key_constraints"
        )

        new_constraints = "Must handle edge cases.\nMust log all operations."
        modified = update_task_field(
            content, "FB-T02", "Key constraints", new_constraints
        )
        _, new_phases = _parse_content(modified)
        new_task = _get_task(new_phases, "FB-T02")
        assert new_task is not None
        assert new_task.key_constraints == [
            "Must handle edge cases.",
            "Must log all operations.",
        ], f"Expected 2 constraints, got {new_task.key_constraints}"

    def test_key_constraints_appears_before_done_when(self):
        """In the re-parsed task, Key constraints content precedes
        **Done when:** in the raw_block."""
        content = _load_fixture()
        modified = update_task_field(
            content, "FB-T02", "Key constraints",
            "First constraint.\nSecond constraint.",
        )
        _, phases = _parse_content(modified)
        task = _get_task(phases, "FB-T02")
        assert task is not None

        # raw_block should show Key constraints before Done when
        raw = task.raw_block
        kc_pos = raw.find("**Key constraints:**")
        dw_pos = raw.find("**Done when:**")
        assert kc_pos != -1, "**Key constraints:** missing from raw_block"
        assert dw_pos != -1, "**Done when:** missing from raw_block"
        assert kc_pos < dw_pos, (
            "**Key constraints:** should appear before **Done when:** "
            f"but kc_pos={kc_pos} > dw_pos={dw_pos}"
        )

    def test_other_fields_unchanged_when_adding_key_constraints(self):
        """After adding Key constraints to FB-T02, all other fields are
        unchanged and other tasks are untouched."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        original_task = _get_task(original_phases, "FB-T02")
        original_blocks = _get_raw_blocks(original_phases)

        modified = update_task_field(
            content, "FB-T02", "Key constraints",
            "New constraint one.\nNew constraint two.",
        )
        _, new_phases = _parse_content(modified)
        new_task = _get_task(new_phases, "FB-T02")
        new_blocks = _get_raw_blocks(new_phases)

        # Other tasks untouched
        for tid, orig_raw in original_blocks.items():
            if tid == "FB-T02":
                continue
            assert new_blocks[tid] == orig_raw, (
                f"raw_block for {tid} changed after FB-T02 Key constraints add"
            )

        # FB-T02's other fields unchanged
        assert new_task is not None and original_task is not None
        assert new_task.title == original_task.title
        assert new_task.status == original_task.status
        assert new_task.complexity == original_task.complexity
        assert new_task.what == original_task.what
        assert new_task.prerequisite == original_task.prerequisite
        assert new_task.hard_deps == original_task.hard_deps
        assert new_task.files == original_task.files
        assert new_task.reviewer == original_task.reviewer
        assert new_task.done_when == original_task.done_when


# ===================================================================
# Additional update_task_field edge cases
# ===================================================================


class TestUpdateTaskFieldEdgeCases:
    """Edge cases for ``update_task_field`` — removal of Key constraints,
    single-line field updates, and Done when multi-line updates."""

    def test_removes_key_constraints(self):
        """Empty new_value on existing Key constraints → field removed."""
        content = _load_fixture()
        # FA-T01 has no Key constraints, but FA-T02 has them
        original_task = _get_task(_parse_content(content)[1], "FA-T02")
        assert original_task is not None
        assert len(original_task.key_constraints) > 0

        modified = update_task_field(
            content, "FA-T02", "Key constraints", ""
        )
        _, phases = _parse_content(modified)
        task = _get_task(phases, "FA-T02")
        assert task is not None
        assert task.key_constraints == [], (
            f"Expected empty key_constraints after removal, "
            f"got {task.key_constraints}"
        )
        # raw_block should not contain **Key constraints:**
        assert "**Key constraints:**" not in task.raw_block

    def test_updates_single_line_field(self):
        """Update the Files field (single-line) → value changes correctly."""
        content = _load_fixture()
        modified = update_task_field(
            content, "FA-T01", "Files", "src/updated.py"
        )
        _, phases = _parse_content(modified)
        task = _get_task(phases, "FA-T01")
        assert task is not None
        assert task.files == ["src/updated.py"], (
            f"Expected ['src/updated.py'], got {task.files}"
        )

    def test_updates_multiline_done_when(self):
        """FA-T03 has a multi-line Done when → replace it."""
        content = _load_fixture()
        original_task = _get_task(_parse_content(content)[1], "FA-T03")
        assert original_task is not None
        assert "\n" in original_task.done_when

        new_done_when = "New done when line 1.\nNew done when line 2.\nNew done when line 3."
        modified = update_task_field(
            content, "FA-T03", "Done when", new_done_when
        )
        _, phases = _parse_content(modified)
        task = _get_task(phases, "FA-T03")
        assert task is not None
        assert task.done_when == new_done_when, (
            f"Expected done_when={new_done_when!r}, got {task.done_when!r}"
        )

    def test_unknown_task_id_raises(self):
        """Update field on nonexistent task → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="not found"):
            update_task_field(content, "NONEXISTENT", "What", "new value")

    def test_unknown_field_name_raises(self):
        """Update nonexistent field on existing task → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="not found"):
            update_task_field(content, "FA-T01", "NonexistentField", "value")


# ===================================================================
# P7-T03b: reorder_phase_blocks
# ===================================================================


class TestReorderPhaseBlocks:
    """``reorder_phase_blocks`` reorders H1 phase blocks; after re-parsing
    the phases are in the new order and all content within each block is
    byte-identical."""

    def test_swaps_phase_order(self):
        """Swap Phase 1 and Phase 2 → Phase 2 appears first, then Phase 1."""
        content = _load_fixture()
        modified = reorder_phase_blocks(
            content,
            ordered_phase_ids=["phase-2--fixture-beta", "phase-1--fixture-alpha"],
        )
        overview, phases = _parse_content(modified)

        assert len(phases) == 2
        assert phases[0].name == "Phase 2 — Fixture Beta"
        assert phases[1].name == "Phase 1 — Fixture Alpha"

    def test_byte_identical_content_within_blocks(self):
        """After reordering, each phase's task raw_blocks are unchanged."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        orig_blocks = _get_raw_blocks(original_phases)

        modified = reorder_phase_blocks(
            content,
            ordered_phase_ids=["phase-2--fixture-beta", "phase-1--fixture-alpha"],
        )
        _, new_phases = _parse_content(modified)
        new_blocks = _get_raw_blocks(new_phases)

        for tid, orig_raw in orig_blocks.items():
            assert new_blocks[tid] == orig_raw, (
                f"raw_block for {tid} changed after phase reorder"
            )

    def test_same_order_no_change(self):
        """Reorder with the same order → no effective change; all blocks
        byte-identical."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        orig_blocks = _get_raw_blocks(original_phases)

        modified = reorder_phase_blocks(
            content,
            ordered_phase_ids=["phase-1--fixture-alpha", "phase-2--fixture-beta"],
        )
        _, new_phases = _parse_content(modified)
        new_blocks = _get_raw_blocks(new_phases)

        assert modified == content, "Content changed when reordering to same order"
        for tid, orig_raw in orig_blocks.items():
            assert new_blocks[tid] == orig_raw

    def test_missing_id_raises(self):
        """ordered_phase_ids with an ID that doesn't exist → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="not found"):
            reorder_phase_blocks(
                content,
                ordered_phase_ids=["phase-1--fixture-alpha", "nonexistent-phase"],
            )

    def test_partial_list_raises(self):
        """ordered_phase_ids shorter than actual phase count → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="ordered_phase_ids has 1"):
            reorder_phase_blocks(
                content,
                ordered_phase_ids=["phase-1--fixture-alpha"],
            )

    def test_extra_id_raises(self):
        """ordered_phase_ids longer than actual phase count → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="ordered_phase_ids has 3"):
            reorder_phase_blocks(
                content,
                ordered_phase_ids=[
                    "phase-1--fixture-alpha",
                    "phase-2--fixture-beta",
                    "extra-phase",
                ],
            )


# ===================================================================
# P7-T03b: reorder_task_blocks
# ===================================================================


class TestReorderTaskBlocks:
    """``reorder_task_blocks`` reorders ### task blocks within a single phase;
    after re-parsing the tasks are in the new order, the dep graph is still
    last, and all task raw_blocks are byte-identical."""

    def test_reverses_task_order_in_phase1(self):
        """Reverse FA-T01→FA-T04 in Phase 1 → tasks appear in reverse order;
        dep graph (FA-T04) is still last."""
        content = _load_fixture()
        modified = reorder_task_blocks(
            content,
            phase_id="phase-1--fixture-alpha",
            ordered_task_ids=["FA-T04", "FA-T03", "FA-T02", "FA-T01"],
        )
        _, phases = _parse_content(modified)
        phase1 = _find_phase(phases, "Phase 1 — Fixture Alpha")
        assert phase1 is not None

        task_ids = [t.id for t in phase1.tasks]
        assert task_ids == ["FA-T04", "FA-T03", "FA-T02", "FA-T01"], (
            f"Expected reversed order, got {task_ids}"
        )

    def test_dep_graph_still_last_after_reorder(self):
        """After reordering tasks, dep graph block is still the last
        block in its phase (suffix is unchanged)."""
        content = _load_fixture()
        modified = reorder_task_blocks(
            content,
            phase_id="phase-1--fixture-alpha",
            ordered_task_ids=["FA-T03", "FA-T01", "FA-T04", "FA-T02"],
        )
        _, phases = _parse_content(modified)
        phase1 = _find_phase(phases, "Phase 1 — Fixture Alpha")
        assert phase1 is not None
        assert phase1.dependency_graph_raw != "", "Dep graph block missing"

        task_ids = [t.id for t in phase1.tasks]
        # The ordered_task_ids is respected exactly; the --- separator
        # is in the suffix (not absorbed into any task block), so any
        # task can be last without breaking the parser.
        assert task_ids == ["FA-T03", "FA-T01", "FA-T04", "FA-T02"], (
            f"Expected exact order, got {task_ids}"
        )

    def test_raw_blocks_byte_identical_after_reorder(self):
        """After reordering tasks, all task raw_blocks are unchanged."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        orig_blocks = _get_raw_blocks(original_phases)

        modified = reorder_task_blocks(
            content,
            phase_id="phase-1--fixture-alpha",
            ordered_task_ids=["FA-T04", "FA-T03", "FA-T02", "FA-T01"],
        )
        _, new_phases = _parse_content(modified)
        new_blocks = _get_raw_blocks(new_phases)

        for tid, orig_raw in orig_blocks.items():
            assert new_blocks[tid] == orig_raw, (
                f"raw_block for {tid} changed after task reorder"
            )

    def test_reorder_tasks_in_phase2(self):
        """Reorder tasks in Phase 2 → order changes; dep graph still last."""
        content = _load_fixture()
        modified = reorder_task_blocks(
            content,
            phase_id="phase-2--fixture-beta",
            ordered_task_ids=["FB-T03", "FB-T02", "FB-T01"],
        )
        _, phases = _parse_content(modified)
        phase2 = _find_phase(phases, "Phase 2 — Fixture Beta")
        assert phase2 is not None

        task_ids = [t.id for t in phase2.tasks]
        assert task_ids == ["FB-T03", "FB-T02", "FB-T01"], (
            f"Expected FB-T03, FB-T02, FB-T01, got {task_ids}"
        )
        # FB-T03 is dep graph task — still last
        assert task_ids[-1] == "FB-T01"

    def test_dep_graph_id_in_list_not_last(self):
        """When dep graph task ID (FA-T04) appears in ordered_task_ids at a
        non-last position, the task order still respects ordered_task_ids
        (the --- separator is in the suffix, not absorbed into FA-T04)."""
        content = _load_fixture()
        modified = reorder_task_blocks(
            content,
            phase_id="phase-1--fixture-alpha",
            ordered_task_ids=["FA-T01", "FA-T04", "FA-T02", "FA-T03"],
        )
        _, phases = _parse_content(modified)
        phase1 = _find_phase(phases, "Phase 1 — Fixture Alpha")
        assert phase1 is not None

        task_ids = [t.id for t in phase1.tasks]
        # ordered_task_ids is respected exactly; FA-T04 does not need
        # to be forced last because the --- separator lives in the
        # suffix, not in any individual task block.
        assert task_ids == ["FA-T01", "FA-T04", "FA-T02", "FA-T03"], (
            f"Expected exact order, got {task_ids}"
        )
        # Dep graph block still present
        _, phases2 = _parse_content(modified)
        phase1b = _find_phase(phases2, "Phase 1 — Fixture Alpha")
        assert phase1b is not None
        assert phase1b.dependency_graph_raw != "", "Dep graph block missing"

    def test_phase1_untouched_when_reordering_phase2(self):
        """Reordering tasks in Phase 2 leaves Phase 1 task blocks unchanged."""
        content = _load_fixture()
        _, original_phases = _parse_content(content)
        orig_blocks = _get_raw_blocks(original_phases)

        modified = reorder_task_blocks(
            content,
            phase_id="phase-2--fixture-beta",
            ordered_task_ids=["FB-T03", "FB-T02", "FB-T01"],
        )
        _, new_phases = _parse_content(modified)
        new_blocks = _get_raw_blocks(new_phases)

        for tid, orig_raw in orig_blocks.items():
            if tid.startswith("FB"):
                continue  # Phase 2 tasks changed order
            assert new_blocks[tid] == orig_raw, (
                f"raw_block for {tid} changed after Phase 2 task reorder"
            )

    def test_missing_task_id_raises(self):
        """ordered_task_ids with a nonexistent task ID → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="not found"):
            reorder_task_blocks(
                content,
                phase_id="phase-1--fixture-alpha",
                ordered_task_ids=["FA-T01", "FA-T02", "FA-T99", "FA-T04"],
            )

    def test_partial_task_list_raises(self):
        """ordered_task_ids shorter than actual task count → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="ordered_task_ids has 2"):
            reorder_task_blocks(
                content,
                phase_id="phase-1--fixture-alpha",
                ordered_task_ids=["FA-T01", "FA-T02"],
            )

    def test_unknown_phase_raises(self):
        """Reorder tasks in a nonexistent phase → ValueError."""
        content = _load_fixture()
        with pytest.raises(ValueError, match="not found"):
            reorder_task_blocks(
                content,
                phase_id="nonexistent-phase",
                ordered_task_ids=["FA-T01", "FA-T02"],
            )
