# tests/writers/test_session_writer.py — P3-T04 session_writer tests
#
# Done-when criteria (from P3-T04 task block):
#
#   1. render_sessionstate(state) → write to temp file → parse_session_file
#      → returned SessionState fields match original state for all fields
#   2. out_of_scope_raw survives round-trip byte-for-byte
#   3. *Last updated:* in rendered output reflects the time of the render
#      call, not an earlier time
#   4. ## Up next table in rendered output contains the Complexity column

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tsm.models import (
    SessionState,
    Task,
    TaskComplexity,
    TaskStatus,
)
from tsm.parsers.session_parser import parse_session_file
from tsm.writers.session_writer import (
    render_sessionstate,
    write_session_file,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture_state() -> SessionState:
    """Load and return the canonical fixture SESSIONSTATE.md as a
    ``SessionState``.  This gives us real raw blocks (with the leading
    ``\\n`` that ``_split_sections`` produces) for round-trip testing."""
    path = FIXTURE_DIR / "SESSIONSTATE.md"
    return parse_session_file(path)


def _build_test_state() -> SessionState:
    """Build a representative ``SessionState`` that exercises every section
    of the renderer.

    The completed / up-next ``Task`` objects are constructed to match the
    shape that ``parse_session_file`` would produce after a round-trip so
    that field-level equality holds.

    For raw-block fields (``active_task_raw``, ``out_of_scope_raw``) we
    start from the fixture state so their format matches exactly what the
    parser produces from a ``---`` split.
    """
    fixture = _load_fixture_state()

    # -- Completed tasks (the parser produces Task objects with
    #    status=COMPLETE and stores the commit message in ``what``).
    completed = [
        Task(
            id="P3-T01",
            title="shadow.py \u2014 stage/apply/backup/prune/history",
            status=TaskStatus.COMPLETE,
            complexity=TaskComplexity.UNSET,
            what="P3-T01: shadow module complete",
            prerequisite="",
            hard_deps=[],
            files=[],
            reviewer="",
            key_constraints=[],
            done_when="",
            phase_id="",
            subphase=None,
            raw_block="",
        ),
        Task(
            id="P3-T02",
            title="shadow.py \u2014 undo",
            status=TaskStatus.COMPLETE,
            complexity=TaskComplexity.UNSET,
            what="P3-T02: undo complete",
            prerequisite="",
            hard_deps=[],
            files=[],
            reviewer="",
            key_constraints=[],
            done_when="",
            phase_id="",
            subphase=None,
            raw_block="",
        ),
    ]

    # -- Up-next tasks (the parser populates id, title, hard_deps,
    #    complexity, reviewer fields from the table).
    up_next = [
        Task(
            id="P3-T04",
            title="session_writer.py \u2014 full reconstruction renderer",
            status=TaskStatus.PENDING,
            complexity=TaskComplexity.MEDIUM,
            what="",
            prerequisite="",
            hard_deps=["P2-T03"],
            files=[],
            reviewer="Skip",
            key_constraints=[],
            done_when="",
            phase_id="",
            subphase=None,
            raw_block="",
        ),
        Task(
            id="P3-T05",
            title="completed_writer.py \u2014 append writer",
            status=TaskStatus.PENDING,
            complexity=TaskComplexity.LOW,
            what="",
            prerequisite="",
            hard_deps=["P2-T04"],
            files=[],
            reviewer="Skip",
            key_constraints=[],
            done_when="",
            phase_id="",
            subphase=None,
            raw_block="",
        ),
    ]

    return SessionState(
        last_updated=datetime.now(),  # placeholder; render ignores this
        active_phase_name="Phase 3 \u2014 Shadow & Writers \u2014 in progress.",
        active_phase_spec="`SPECIFICATION-task-session-manager-v1.4.md`",
        active_task=None,
        active_task_raw=fixture.active_task_raw,
        up_next=up_next,
        completed=completed,
        out_of_scope_raw=fixture.out_of_scope_raw,
    )


def _round_trip(state: SessionState, tmp_path: Path) -> SessionState:
    """Render *state*, write to a temp file under *tmp_path*, parse, and
    return the parsed ``SessionState``."""
    rendered = render_sessionstate(state)
    shadow = tmp_path / ".tsm" / "shadow" / "SESSIONSTATE.md"
    write_session_file(rendered, str(shadow))
    return parse_session_file(shadow)


# ── Tests ────────────────────────────────────────────────────────────────────


class TestSessionWriter:
    """Full test suite for :mod:`tsm.writers.session_writer`."""

    # ------------------------------------------------------------------
    # 1. Round-trip: all fields match
    # ------------------------------------------------------------------

    def test_round_trip_phase_and_spec(self, tmp_path: Path):
        """Active-phase name and spec survive round-trip."""
        state = _build_test_state()
        parsed = _round_trip(state, tmp_path)
        assert parsed.active_phase_name == state.active_phase_name
        assert parsed.active_phase_spec == state.active_phase_spec

    def test_round_trip_active_task_raw(self, tmp_path: Path):
        """``active_task_raw`` survives round-trip byte-for-byte."""
        state = _build_test_state()
        parsed = _round_trip(state, tmp_path)
        assert parsed.active_task_raw == state.active_task_raw

    def test_round_trip_out_of_scope_raw(self, tmp_path: Path):
        """``out_of_scope_raw`` survives round-trip byte-for-byte."""
        state = _build_test_state()
        parsed = _round_trip(state, tmp_path)
        assert parsed.out_of_scope_raw == state.out_of_scope_raw

    def test_round_trip_up_next_ids(self, tmp_path: Path):
        """Up-next task IDs survive round-trip."""
        state = _build_test_state()
        parsed = _round_trip(state, tmp_path)
        original_ids = [t.id for t in state.up_next]
        parsed_ids = [t.id for t in parsed.up_next]
        assert parsed_ids == original_ids

    def test_round_trip_up_next_complexity(self, tmp_path: Path):
        """Up-next complexity values survive round-trip."""
        state = _build_test_state()
        parsed = _round_trip(state, tmp_path)
        original_cx = [t.complexity for t in state.up_next]
        parsed_cx = [t.complexity for t in parsed.up_next]
        assert parsed_cx == original_cx

    def test_round_trip_up_next_hard_deps(self, tmp_path: Path):
        """Up-next hard-deps lists survive round-trip."""
        state = _build_test_state()
        parsed = _round_trip(state, tmp_path)
        original_deps = [t.hard_deps for t in state.up_next]
        parsed_deps = [t.hard_deps for t in parsed.up_next]
        assert parsed_deps == original_deps

    def test_round_trip_up_next_reviewer(self, tmp_path: Path):
        """Up-next reviewer values survive round-trip."""
        state = _build_test_state()
        parsed = _round_trip(state, tmp_path)
        original_r = [t.reviewer for t in state.up_next]
        parsed_r = [t.reviewer for t in parsed.up_next]
        assert parsed_r == original_r

    def test_round_trip_completed_ids(self, tmp_path: Path):
        """Completed task IDs survive round-trip."""
        state = _build_test_state()
        parsed = _round_trip(state, tmp_path)
        original_ids = [t.id for t in state.completed]
        parsed_ids = [t.id for t in parsed.completed]
        assert parsed_ids == original_ids

    def test_round_trip_completed_titles(self, tmp_path: Path):
        """Completed task titles survive round-trip."""
        state = _build_test_state()
        parsed = _round_trip(state, tmp_path)
        original_titles = [t.title for t in state.completed]
        parsed_titles = [t.title for t in parsed.completed]
        assert parsed_titles == original_titles

    def test_round_trip_completed_commit_msgs(self, tmp_path: Path):
        """Completed commit messages (stored in ``what``) survive round-trip."""
        state = _build_test_state()
        parsed = _round_trip(state, tmp_path)
        original_msgs = [t.what for t in state.completed]
        parsed_msgs = [t.what for t in parsed.completed]
        assert parsed_msgs == original_msgs

    # ------------------------------------------------------------------
    # 2. out_of_scope_raw byte-for-byte
    # ------------------------------------------------------------------

    def test_out_of_scope_byte_for_byte(self, tmp_path: Path):
        """Verbatim ``out_of_scope_raw`` from fixture survives round-trip."""
        # Load the fixture, which gives us real raw blocks from the parser.
        fixture = _load_fixture_state()
        original_raw = fixture.out_of_scope_raw

        # Use the fixture's session as baseline, render it, and round-trip.
        state = fixture
        # Replace last_updated and up_next/completed with test data so
        # nothing depends on fixture table content, but keep the raw blocks.
        state.up_next = []
        state.completed = []
        parsed = _round_trip(state, tmp_path)
        assert parsed.out_of_scope_raw == original_raw

    def test_out_of_scope_custom_verbatim(self, tmp_path: Path):
        """A custom ``out_of_scope_raw`` with special chars survives."""
        fixture = _load_fixture_state()
        custom_raw = (
            "\n## Out of scope\n"
            "\n"
            "- Custom item with \u2014 em dash\n"
            "- Another with \u201cquotes\u201d\n"
        )
        state = fixture
        state.out_of_scope_raw = custom_raw
        state.up_next = []
        state.completed = []
        parsed = _round_trip(state, tmp_path)
        assert parsed.out_of_scope_raw == custom_raw

    # ------------------------------------------------------------------
    # 3. *Last updated:* reflects render call time
    # ------------------------------------------------------------------

    def test_last_updated_is_current(self):
        """``*Last updated:*`` timestamp is at the current minute
        (renderer emits ``HH:MM`` granularity)."""
        state = _build_test_state()
        rendered = render_sessionstate(state)

        for line in rendered.split("\n"):
            if "*Last updated:" in line:
                value = line.replace("*", "").strip()
                prefix = "Last updated:"
                assert value.startswith(prefix)
                value = value[len(prefix):].strip()
                parsed_dt = datetime.strptime(value, "%Y-%m-%dT%H:%M")

                now = datetime.now()
                # The rendered timestamp should be within the last 2 minutes
                # (accounting for minute-boundary crossing).
                assert (
                    now - timedelta(minutes=2)
                    <= parsed_dt
                    <= now + timedelta(minutes=1)
                ), (
                    f"Rendered time {parsed_dt} is too far from current "
                    f"time {now}"
                )
                return

        pytest.fail("No *Last updated:* line found in rendered output")

    # ------------------------------------------------------------------
    # 4. ## Up next table includes Complexity column
    # ------------------------------------------------------------------

    def test_up_next_has_complexity_column(self):
        """The ``## Up next`` table header contains the Complexity column."""
        state = _build_test_state()
        rendered = render_sessionstate(state)
        assert (
            "| Task | Description | Hard deps | Complexity | Reviewer |"
            in rendered
        )

    def test_up_next_complexity_values_present(self):
        """Each up-next row contains a non-empty complexity value."""
        state = _build_test_state()
        rendered = render_sessionstate(state)
        for task in state.up_next:
            lines = rendered.split("\n")
            for line in lines:
                if line.startswith(f"| {task.id} |"):
                    cells = [c.strip() for c in line.split("|")]
                    # After split on pipes: ['', 'ID', 'title', 'deps',
                    # 'complexity', 'reviewer', '']
                    assert len(cells) >= 6, f"Row missing cells: {cells}"
                    assert cells[4], f"Complexity cell empty in: {line}"
                    break
            else:
                pytest.fail(
                    f"Row for task {task.id} not found in rendered output"
                )
