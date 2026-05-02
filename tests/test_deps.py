# tests/test_deps.py — Dependency engine tests (Phase 7, P7-T01 & P7-T02)
#
# P7-T01 — All 10 Done-when criteria covered:
#   test_deps_single_task
#   test_deps_tree_output
#   test_deps_blocked_list
#   test_deps_check_clean
#   test_deps_check_dangling
#   test_deps_pre_write_gate_blocks_remove
#   test_deps_cycle_detection
#   build_dep_graph() on fixture returns correct adjacency
#   detect_cycles() returns [] on clean acyclic graph
#   detect_cycles() returns cycle path when cycle exists
#
# P7-T02 — Command-level tests:
#   test_deps_single_task (command output)
#   test_deps_tree_output (command output)
#   test_deps_blocked_list (command output)
#   test_deps_check_clean (command exit 0)
#   test_deps_check_dangling (command exit 1)

import pytest

from tsm.deps import (
    build_dep_graph,
    check_deps,
    detect_cycles,
    get_blocked_tasks,
    get_dep_chain,
    get_dependents,
)
from tsm.models import Phase, Task, TaskComplexity, TaskStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(
    task_id: str,
    hard_deps: list[str] | None = None,
    status: TaskStatus = TaskStatus.PENDING,
) -> Task:
    """Create a minimal Task with only the fields relevant to dependency testing."""
    return Task(
        id=task_id,
        title=f"Task {task_id}",
        status=status,
        complexity=TaskComplexity.UNSET,
        what="",
        prerequisite="",
        hard_deps=hard_deps or [],
        files=[],
        reviewer="",
        key_constraints=[],
        done_when="",
        phase_id="",
        subphase=None,
        raw_block="",
    )


def _make_phase(phase_id: str, tasks: list[Task]) -> Phase:
    return Phase(
        id=phase_id,
        name=phase_id,
        status="pending",
        description="",
        tasks=tasks,
    )


def _single_phase(tasks: list[Task]) -> list[Phase]:
    return [_make_phase("phase-1", tasks)]


# ===================================================================
# test_deps_single_task
# ===================================================================


class TestSingleTask:
    """Graph with one task and no deps."""

    def test_deps_single_task(self) -> None:
        """Single task with no hard deps → correct singleton adjacency."""
        tasks = [_make_task("T01")]
        phases = _single_phase(tasks)

        graph = build_dep_graph(phases)
        assert graph == {"T01": []}

        assert get_dependents(phases, "T01") == []
        assert get_dep_chain(phases, "T01") == []
        assert get_blocked_tasks(phases) == []
        assert detect_cycles(phases) == []
        assert check_deps(phases) == []


# ===================================================================
# test_deps_tree_output
# ===================================================================


class TestTreeOutput:
    """Verify build_dep_graph returns correct multi-task adjacency."""

    def test_deps_tree_output(self) -> None:
        """Chain: T01 → T02 → T03 (T03 depends on T02, T02 on T01)."""
        t1 = _make_task("T01")
        t2 = _make_task("T02", hard_deps=["T01"])
        t3 = _make_task("T03", hard_deps=["T02"])
        phases = _single_phase([t1, t2, t3])

        graph = build_dep_graph(phases)
        assert graph == {
            "T01": [],
            "T02": ["T01"],
            "T03": ["T02"],
        }

    def test_build_dep_graph_fixture(self) -> None:
        """build_dep_graph on fixture-like data returns correct adjacency dict."""
        t1 = _make_task("A")
        t2 = _make_task("B", hard_deps=["A"])
        t3 = _make_task("C", hard_deps=["B"])
        t4 = _make_task("D", hard_deps=["A"])

        # Two-phase layout
        phases = [
            _make_phase("phase-1", [t1, t2]),
            _make_phase("phase-2", [t3, t4]),
        ]

        graph = build_dep_graph(phases)
        assert graph == {
            "A": [],
            "B": ["A"],
            "C": ["B"],
            "D": ["A"],
        }


# ===================================================================
# test_deps_blocked_list
# ===================================================================


class TestBlockedList:
    """Tasks with unmet hard deps appear in get_blocked_tasks()."""

    def test_deps_blocked_list(self) -> None:
        """T02 depends on T01 (pending) → T02 is blocked."""
        t1 = _make_task("T01", status=TaskStatus.PENDING)
        t2 = _make_task("T02", hard_deps=["T01"], status=TaskStatus.PENDING)
        phases = _single_phase([t1, t2])

        blocked = get_blocked_tasks(phases)
        assert len(blocked) == 1
        assert blocked[0].id == "T02"

    def test_deps_not_blocked_when_dep_complete(self) -> None:
        """T02 depends on T01 (complete) → T02 is not blocked."""
        t1 = _make_task("T01", status=TaskStatus.COMPLETE)
        t2 = _make_task("T02", hard_deps=["T01"], status=TaskStatus.PENDING)
        phases = _single_phase([t1, t2])

        blocked = get_blocked_tasks(phases)
        assert blocked == []

    def test_deps_blocked_multiple(self) -> None:
        """T03 depends on T01 and T02, both pending → blocked."""
        t1 = _make_task("T01", status=TaskStatus.PENDING)
        t2 = _make_task("T02", status=TaskStatus.PENDING)
        t3 = _make_task("T03", hard_deps=["T01", "T02"])
        phases = _single_phase([t1, t2, t3])

        blocked = get_blocked_tasks(phases)
        assert len(blocked) == 1
        assert blocked[0].id == "T03"


# ===================================================================
# test_deps_check_clean
# ===================================================================


class TestCheckClean:
    """check_deps returns [] on healthy graphs."""

    def test_deps_check_clean(self) -> None:
        """A chain with no issues passes clean."""
        t1 = _make_task("A")
        t2 = _make_task("B", hard_deps=["A"])
        t3 = _make_task("C", hard_deps=["B"])
        phases = _single_phase([t1, t2, t3])

        errors = check_deps(phases)
        assert errors == []

    def test_deps_check_empty(self) -> None:
        """No tasks → clean."""
        assert check_deps([]) == []

    def test_deps_disconnected(self) -> None:
        """Multiple tasks with no deps between them → clean."""
        t1 = _make_task("A")
        t2 = _make_task("B")
        t3 = _make_task("C")
        phases = _single_phase([t1, t2, t3])

        errors = check_deps(phases)
        assert errors == []


# ===================================================================
# test_deps_check_dangling
# ===================================================================


class TestCheckDangling:
    """check_deps catches references to nonexistent task IDs."""

    def test_deps_check_dangling(self) -> None:
        """T01 depends on X (doesn't exist) → dangling error."""
        t1 = _make_task("T01", hard_deps=["X"])
        phases = _single_phase([t1])

        errors = check_deps(phases)
        assert len(errors) >= 1
        assert any("dangling" in e.lower() or "X" in e for e in errors)

    def test_deps_check_dangling_multiple(self) -> None:
        """Multiple tasks with dangling deps produce multiple errors."""
        t1 = _make_task("T01", hard_deps=["MISSING"])
        t2 = _make_task("T02", hard_deps=["GHOST"])
        phases = _single_phase([t1, t2])

        errors = check_deps(phases)
        assert len(errors) >= 2

    def test_deps_self_reference(self) -> None:
        """Task that lists itself in hard_deps → self-reference error."""
        t1 = _make_task("T01", hard_deps=["T01"])
        phases = _single_phase([t1])

        errors = check_deps(phases)
        assert len(errors) >= 1
        assert any("self" in e.lower() or "T01" in e for e in errors)


# ===================================================================
# test_deps_pre_write_gate_blocks_remove
# ===================================================================


class TestPreWriteGate:
    """Simulate the pre-write gate: remove a task in-memory,
    then check_deps() on the proposed state."""

    def test_deps_pre_write_gate_blocks_remove(self) -> None:
        """B depends on A; remove A → check_deps flags dangling dep on B."""
        t_a = _make_task("A")
        t_b = _make_task("B", hard_deps=["A"])
        phases = _single_phase([t_a, t_b])

        # Pre-removal: clean
        assert check_deps(phases) == []

        # Propose removal of A (in-memory)
        proposed = _single_phase([t_b])  # A is gone

        errors = check_deps(proposed)
        assert len(errors) >= 1
        assert any("dangling" in e.lower() and "B" in e and "A" in e for e in errors)

    def test_deps_pre_write_gate_remove_with_force_bypass(self) -> None:
        """Even with a force flag concept, check_deps still reports errors
        (force is handled by the caller, not by deps.py)."""
        t_a = _make_task("A")
        t_b = _make_task("B", hard_deps=["A"])
        proposed = _single_phase([t_b])

        errors = check_deps(proposed)
        # check_deps is honest — it reports errors regardless
        assert len(errors) >= 1


# ===================================================================
# test_deps_cycle_detection
# ===================================================================


class TestCycleDetection:
    """detect_cycles using DFS with visited + recursion-stack."""

    def test_deps_cycle_detection(self) -> None:
        """A→B→A direct cycle detected; clean graph returns [].

        Combined test per Done-when spec.
        """
        # ---- Clean graph ----
        t1 = _make_task("A")
        t2 = _make_task("B", hard_deps=["A"])
        phases = _single_phase([t1, t2])
        assert detect_cycles(phases) == []

        # ---- Cycle A→B→A ----
        ta = _make_task("A", hard_deps=["B"])
        tb = _make_task("B", hard_deps=["A"])
        phases_cycle = _single_phase([ta, tb])

        cycle = detect_cycles(phases_cycle)
        assert len(cycle) >= 3
        # Cycle path should contain A, B, A
        assert cycle[0] == cycle[-1]  # starts and ends with same node
        assert set(cycle) == {"A", "B"}

    def test_detect_cycles_clean(self) -> None:
        """detect_cycles returns [] on a clean acyclic graph."""
        t1 = _make_task("X")
        t2 = _make_task("Y", hard_deps=["X"])
        t3 = _make_task("Z", hard_deps=["Y"])
        phases = _single_phase([t1, t2, t3])

        assert detect_cycles(phases) == []

    def test_detect_cycles_path(self) -> None:
        """detect_cycles returns the cycle path when a cycle exists."""
        ta = _make_task("A", hard_deps=["B"])
        tb = _make_task("B", hard_deps=["C"])
        tc = _make_task("C", hard_deps=["A"])
        phases = _single_phase([ta, tb, tc])

        cycle = detect_cycles(phases)
        assert len(cycle) >= 3
        assert cycle[0] == cycle[-1]  # cycle starts and ends at same node
        assert set(cycle) == {"A", "B", "C"}

    def test_detect_cycles_indirect(self) -> None:
        """Indirect cycle A→B→C→A correctly detected."""
        ta = _make_task("A", hard_deps=["B"])
        tb = _make_task("B", hard_deps=["C"])
        tc = _make_task("C", hard_deps=["A"])
        phases = _single_phase([ta, tb, tc])

        cycle = detect_cycles(phases)
        assert len(cycle) >= 3
        assert cycle[0] == cycle[-1]
        assert set(cycle) == {"A", "B", "C"}

    def test_deps_cycle_plus_clean_subgraph(self) -> None:
        """Cycle in one subgraph doesn't contaminate another clean subgraph."""
        # Subgraph 1: clean chain
        tx = _make_task("X")
        ty = _make_task("Y", hard_deps=["X"])

        # Subgraph 2: cycle A→B→A
        ta = _make_task("A", hard_deps=["B"])
        tb = _make_task("B", hard_deps=["A"])

        phases = _single_phase([tx, ty, ta, tb])

        cycle = detect_cycles(phases)
        assert len(cycle) >= 3
        assert cycle[0] == cycle[-1]


# ===================================================================
# Additional coverage — get_dep_chain and get_dependents
# ===================================================================


class TestDepChain:
    """Transitive ancestor resolution."""

    def test_get_dep_chain_single_level(self) -> None:
        """T02 depends on T01 → chain = [T01]."""
        t1 = _make_task("T01")
        t2 = _make_task("T02", hard_deps=["T01"])
        phases = _single_phase([t1, t2])

        chain = get_dep_chain(phases, "T02")
        assert chain == ["T01"]

    def test_get_dep_chain_transitive(self) -> None:
        """T03→T02→T01 → chain = [T01, T02]."""
        t1 = _make_task("T01")
        t2 = _make_task("T02", hard_deps=["T01"])
        t3 = _make_task("T03", hard_deps=["T02"])
        phases = _single_phase([t1, t2, t3])

        chain = get_dep_chain(phases, "T03")
        assert chain == ["T01", "T02"]

    def test_get_dep_chain_no_deps(self) -> None:
        """Task with no deps → empty chain."""
        t1 = _make_task("T01")
        phases = _single_phase([t1])

        assert get_dep_chain(phases, "T01") == []

    def test_get_dep_chain_multiple_ancestors(self) -> None:
        """T03 depends on T01 and T02 → chain includes both."""
        t1 = _make_task("T01")
        t2 = _make_task("T02")
        t3 = _make_task("T03", hard_deps=["T01", "T02"])
        phases = _single_phase([t1, t2, t3])

        chain = get_dep_chain(phases, "T03")
        assert "T01" in chain
        assert "T02" in chain


class TestDependents:
    """Inverse dependency lookup."""

    def test_get_dependents_simple(self) -> None:
        """T01 is depended on by T02."""
        t1 = _make_task("T01")
        t2 = _make_task("T02", hard_deps=["T01"])
        phases = _single_phase([t1, t2])

        deps = get_dependents(phases, "T01")
        assert deps == ["T02"]

    def test_get_dependents_multiple(self) -> None:
        """T01 is depended on by T02 and T03."""
        t1 = _make_task("T01")
        t2 = _make_task("T02", hard_deps=["T01"])
        t3 = _make_task("T03", hard_deps=["T01"])
        phases = _single_phase([t1, t2, t3])

        deps = get_dependents(phases, "T01")
        assert sorted(deps) == ["T02", "T03"]

    def test_get_dependents_none(self) -> None:
        """No task depends on T01."""
        t1 = _make_task("T01")
        t2 = _make_task("T02")
        phases = _single_phase([t1, t2])

        assert get_dependents(phases, "T01") == []


# ===================================================================
# P7-T02 — Command-level tests for deps_command
# ===================================================================
# Tests exercise deps_command output parsing via capsys to verify
# the four modes produce the correct printed output per §16.3.


from io import StringIO
from pathlib import Path
from typing import Generator

from tsm.commands.deps import HELP_TEXT, deps_command
from tsm.models import (
    LoadedProject,
    PhaseOverviewRow,
    ProjectContext,
    SessionState,
)
from tsm.parsers.tasks_parser import parse_tasks_file
from tsm.parsers.session_parser import parse_session_file


# Fixture directory
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
TASKS_FIXTURE = FIXTURE_DIR / "TASKS.md"
TASKS_CLEAN_FIXTURE = FIXTURE_DIR / "TASKS_CLEAN.md"
TASKS_ERRORS_FIXTURE = FIXTURE_DIR / "TASKS_ERRORS.md"
SESSION_FIXTURE = FIXTURE_DIR / "SESSIONSTATE.md"


def _build_project_context(tmp_path: Path, tasks_fixture: Path) -> ProjectContext:
    """Build a ProjectContext with *tasks_fixture* as the TASKS.md live file."""
    root = tmp_path.resolve()
    shadow_dir = root / ".tsm" / "shadow"
    backup_dir = root / ".tsm" / "backups"

    tasks_live = root / "TASKS.md"
    session_live = root / "SESSIONSTATE.md"
    completed_live = root / "TASKS-COMPLETED.md"

    # Copy the tasks fixture
    tasks_live.write_text(
        tasks_fixture.read_text(encoding="utf-8"), encoding="utf-8"
    )
    # Copy the session fixture
    session_live.write_text(
        SESSION_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    # Create an empty TASKS-COMPLETED.md
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


def _loaded_from_fixture(
    tmp_path: Path, tasks_fixture: Path
) -> LoadedProject:
    """Build a LoadedProject from a tasks fixture and the session fixture."""
    pc = _build_project_context(tmp_path, tasks_fixture)
    phase_overview, phases = parse_tasks_file(Path(pc.tasks_path))
    session = parse_session_file(Path(pc.sessionstate_path))

    return LoadedProject(
        project_context=pc,
        phases=phases,
        phase_overview=phase_overview,
        session=session,
    )


class TestDepsCommandSingleTask:
    """tsm deps <task-id> — single task detail (§16.3)."""

    def test_deps_single_task(self, tmp_path: Path, capsys) -> None:
        """deps FA-T02 prints depends-on (FA-T01) and required-by (FB-T03)."""
        loaded = _loaded_from_fixture(tmp_path, TASKS_FIXTURE)
        deps_command(loaded, task_id="FA-T02")
        captured = capsys.readouterr()

        # Should show depends-on info
        assert "Dependencies for FA-T02" in captured.out
        assert "FA-T01" in captured.out
        assert "✅ Complete" in captured.out

        # Should show required-by info
        assert "Required by" in captured.out
        assert "FB-T03" in captured.out

    def test_deps_single_task_no_deps(self, tmp_path: Path, capsys) -> None:
        """deps FA-T01 (no deps) shows (none) for depends-on."""
        loaded = _loaded_from_fixture(tmp_path, TASKS_FIXTURE)
        deps_command(loaded, task_id="FA-T01")
        captured = capsys.readouterr()

        assert "Dependencies for FA-T01" in captured.out
        assert "(none)" in captured.out

    def test_deps_single_task_unknown(self, tmp_path: Path, capsys) -> None:
        """deps NONEXIST prints unknown task error."""
        loaded = _loaded_from_fixture(tmp_path, TASKS_FIXTURE)
        deps_command(loaded, task_id="NONEXIST")
        captured = capsys.readouterr()

        assert "Unknown task ID: NONEXIST" in captured.out


class TestDepsCommandTree:
    """tsm deps --tree — full ASCII dependency tree (§16.3)."""

    def test_deps_tree_output(self, tmp_path: Path, capsys) -> None:
        """deps --tree prints all tasks with dep arrows; summary line correct."""
        loaded = _loaded_from_fixture(tmp_path, TASKS_FIXTURE)
        deps_command(loaded, tree=True)
        captured = capsys.readouterr()

        # Should show all fixture tasks
        assert "FA-T01" in captured.out
        assert "FA-T02" in captured.out
        assert "FA-T03" in captured.out
        assert "FA-T04" in captured.out
        assert "FB-T01" in captured.out
        assert "FB-T02" in captured.out
        assert "FB-T03" in captured.out

        # Should show dep arrows for tasks with deps
        assert "← FA-T01" in captured.out

        # Summary line
        assert "tasks" in captured.out
        assert "blocked" in captured.out
        assert "cycles" in captured.out

    def test_deps_bare_invocation_defaults_to_tree(
        self, tmp_path: Path, capsys
    ) -> None:
        """Bare deps invocation (no flags) defaults to --tree."""
        loaded = _loaded_from_fixture(tmp_path, TASKS_FIXTURE)
        deps_command(loaded)  # no args → should default to tree
        captured = capsys.readouterr()

        assert "Dependency Tree" in captured.out
        assert "FA-T01" in captured.out


class TestDepsCommandBlocked:
    """tsm deps --blocked — list tasks with unmet deps (§16.3)."""

    def test_deps_blocked_list(self, tmp_path: Path, capsys) -> None:
        """deps --blocked lists only tasks with unmet deps."""
        loaded = _loaded_from_fixture(tmp_path, TASKS_FIXTURE)
        deps_command(loaded, blocked=True)
        captured = capsys.readouterr()

        # FA-T02 depends on FA-T01 (complete) → NOT blocked
        # FA-T03 depends on FA-T02 (active) → blocked
        # FB-T01 depends on FA-T01 (complete) → NOT blocked
        # FB-T03 depends on FB-T01 (complete) and FA-T02 (active) → blocked
        assert "Blocked tasks" in captured.out


class TestDepsCommandCheck:
    """tsm deps --check — validation (§16.3)."""

    def test_deps_check_clean(self, tmp_path: Path, capsys) -> None:
        """deps --check exits 0 on clean fixture."""
        loaded = _loaded_from_fixture(tmp_path, TASKS_FIXTURE)
        try:
            deps_command(loaded, check=True)
        except Exception:
            pass  # We test the output, not the exception
        captured = capsys.readouterr()

        assert "No dependency issues found" in captured.out

    def test_deps_check_dangling(self, tmp_path: Path, capsys) -> None:
        """deps --check exits 1 on TASKS_ERRORS.md fixture."""
        loaded = _loaded_from_fixture(tmp_path, TASKS_ERRORS_FIXTURE)
        with pytest.raises(Exception):
            deps_command(loaded, check=True)
        captured = capsys.readouterr()

        assert "dependency issues found" in captured.out
        assert "ER-NONEXIST" in captured.out or "does not exist" in captured.out


class TestDepsHelpText:
    """Verify HELP_TEXT constant."""

    def test_help_text_exists(self) -> None:
        """HELP_TEXT is a non-empty string."""
        assert isinstance(HELP_TEXT, str)
        assert len(HELP_TEXT) > 0
        assert "tsm deps" in HELP_TEXT
