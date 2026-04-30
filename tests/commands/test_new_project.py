# tests/commands/test_new_project.py — P4-T07 new_project command tests
#
# Done-when criteria (from P4-T07 task block):
#
#   1. test_new_project_creates_all_files passes
#   2. test_new_project_with_name_flag passes
#   3. test_new_project_prompts_for_name passes
#   4. test_new_project_aborts_if_tasks_exists passes
#   5. test_new_project_aborts_if_sessionstate_exists passes
#   6. test_new_project_creates_gitignore_entry passes
#   7. test_new_project_tasks_md_parseable passes
#   8. test_new_project_sessionstate_parseable passes

from pathlib import Path

import pytest

from tsm.commands.new_project import HELP_TEXT, new_project
from tsm.parsers.session_parser import parse_session_file
from tsm.parsers.tasks_parser import parse_tasks_file

# ── Helpers ───────────────────────────────────────────────────────────────────


def _assert_abort_output(capsys, tmp_path: Path, existing_file: str):
    """Verify that calling new_project() when *existing_file* already exists
    prints the §7.9 error and does NOT create any other project files."""
    # Create the file that should trigger the abort
    (tmp_path / existing_file).touch()

    # Capture output
    new_project(tmp_path, name="Test Project")
    captured = capsys.readouterr()

    # Assert error message was printed
    assert "already exists" in captured.out, (
        f"Expected abort message, got: {captured.out!r}"
    )

    # Verify no other workflow files were created
    all_files = [
        "TASKS.md",
        "SESSIONSTATE.md",
        "TASKS-COMPLETED.md",
        "AGENTS.md",
        "SPECIFICATION.md",
    ]
    for fname in all_files:
        if fname == existing_file:
            continue
        assert not (tmp_path / fname).exists(), (
            f"File {fname} was created despite abort"
        )

    # Verify .tsm/ was not created
    assert not (tmp_path / ".tsm").exists(), (
        ".tsm/ was created despite abort"
    )


def _assert_project_files_exist(tmp_path: Path):
    """Assert that all 5 workflow files exist under *tmp_path*."""
    assert (tmp_path / "TASKS.md").is_file()
    assert (tmp_path / "SESSIONSTATE.md").is_file()
    assert (tmp_path / "TASKS-COMPLETED.md").is_file()
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / "SPECIFICATION.md").is_file()


def _assert_tsm_directories_exist(tmp_path: Path):
    """Assert that .tsm/shadow/ and .tsm/backups/ exist."""
    assert (tmp_path / ".tsm" / "shadow").is_dir()
    assert (tmp_path / ".tsm" / "backups").is_dir()


def _assert_gitignore_has_tsm(tmp_path: Path):
    """Assert .gitignore exists and contains a .tsm/ entry."""
    gitignore = tmp_path / ".gitignore"
    assert gitignore.is_file()
    content = gitignore.read_text(encoding="utf-8")
    assert ".tsm/" in content


# ── Tests ────────────────────────────────────────────────────────────────────


class TestNewProjectCreatesAllFiles:
    """``new_project()`` creates all expected files and directories."""

    def test_new_project_creates_all_files(self, tmp_path: Path):
        """All 5 workflow files, .tsm/ structure, and .gitignore are created."""
        new_project(tmp_path, name="Test Project")

        _assert_project_files_exist(tmp_path)
        _assert_tsm_directories_exist(tmp_path)
        _assert_gitignore_has_tsm(tmp_path)


class TestNewProjectWithNameFlag:
    """``new_project()`` with an explicit ``name`` argument."""

    def test_new_project_with_name_flag(self, tmp_path: Path):
        """Project name appears in TASKS.md heading and SPECIFICATION.md heading."""
        new_project(tmp_path, name="My App")

        _assert_project_files_exist(tmp_path)

        tasks_content = (tmp_path / "TASKS.md").read_text(encoding="utf-8")
        assert "# My App — Phase Task List" in tasks_content, (
            "Project name not found in TASKS.md heading"
        )

        spec_content = (tmp_path / "SPECIFICATION.md").read_text(
            encoding="utf-8"
        )
        assert "# My App — Technical Specification" in spec_content, (
            "Project name not found in SPECIFICATION.md heading"
        )


class TestNewProjectPromptsForName:
    """``new_project()`` prompts when ``name`` is None."""

    def test_new_project_prompts_for_name(
        self, tmp_path: Path, monkeypatch
    ):
        """When name is None and user presses Enter, default to directory name."""
        # Simulate user pressing Enter with no input
        monkeypatch.setattr("builtins.input", lambda _: "")

        new_project(tmp_path, name=None)

        _assert_project_files_exist(tmp_path)

        # Default should be the directory name (tmp_path's folder name)
        expected_name = tmp_path.name
        tasks_content = (tmp_path / "TASKS.md").read_text(encoding="utf-8")
        assert expected_name in tasks_content, (
            f"Expected directory name {expected_name!r} in TASKS.md, "
            f"but content starts with: {tasks_content[:100]!r}"
        )

    def test_new_project_prompts_with_custom_input(
        self, tmp_path: Path, monkeypatch
    ):
        """When user provides input, that input is used as the project name."""
        monkeypatch.setattr("builtins.input", lambda _: "Custom Name")

        new_project(tmp_path, name=None)

        _assert_project_files_exist(tmp_path)

        tasks_content = (tmp_path / "TASKS.md").read_text(encoding="utf-8")
        assert "# Custom Name — Phase Task List" in tasks_content


class TestNewProjectAbortsIfTasksExists:
    """``new_project()`` aborts when TASKS.md already exists."""

    def test_new_project_aborts_if_tasks_exists(
        self, tmp_path: Path, capsys
    ):
        """TASKS.md exists → error printed, nothing created."""
        _assert_abort_output(capsys, tmp_path, "TASKS.md")


class TestNewProjectAbortsIfSessionstateExists:
    """``new_project()`` aborts when SESSIONSTATE.md already exists."""

    def test_new_project_aborts_if_sessionstate_exists(
        self, tmp_path: Path, capsys
    ):
        """SESSIONSTATE.md exists → error printed, nothing created."""
        _assert_abort_output(capsys, tmp_path, "SESSIONSTATE.md")


class TestNewProjectCreatesGitignoreEntry:
    """``new_project()`` creates .gitignore with .tsm/ entry."""

    def test_new_project_creates_gitignore_entry(self, tmp_path: Path):
        """New project gets a .gitignore with a single .tsm/ entry."""
        new_project(tmp_path, name="Test")

        _assert_gitignore_has_tsm(tmp_path)

        # Exactly one .tsm/ line
        lines = (tmp_path / ".gitignore").read_text(
            encoding="utf-8"
        ).splitlines()
        tsm_lines = [l for l in lines if l.strip() == ".tsm/"]
        assert len(tsm_lines) == 1, (
            f"Expected exactly 1 .tsm/ line, got {len(tsm_lines)}: {tsm_lines}"
        )

    def test_new_project_gitignore_already_exists(self, tmp_path: Path):
        """When .gitignore already has .tsm/, it is not duplicated."""
        # Pre-create .gitignore with .tsm/ already present
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n.tsm/\n", encoding="utf-8")

        new_project(tmp_path, name="Test")

        # Should still have exactly one .tsm/ line
        lines = gitignore.read_text(encoding="utf-8").splitlines()
        tsm_lines = [l for l in lines if l.strip() == ".tsm/"]
        assert len(tsm_lines) == 1, (
            f"Expected 1 .tsm/ line (idempotent), got {len(tsm_lines)}: "
            f"{tsm_lines}"
        )


class TestNewProjectTasksMdParseable:
    """Generated TASKS.md is parseable by tasks_parser."""

    def test_new_project_tasks_md_parseable(self, tmp_path: Path):
        """Round-trip: create project → parse TASKS.md → no errors."""
        new_project(tmp_path, name="Parseable Project")

        tasks_path = tmp_path / "TASKS.md"
        assert tasks_path.is_file()

        # Parse — expect no exceptions
        phase_overview, phases = parse_tasks_file(tasks_path)

        # Verify basic structure
        assert len(phase_overview) == 1, (
            f"Expected 1 phase overview row, got {len(phase_overview)}"
        )
        assert phase_overview[0].phase_name == "Phase 1"

        assert len(phases) == 1, (
            f"Expected 1 phase, got {len(phases)}"
        )
        assert len(phases[0].tasks) == 1, (
            f"Expected 1 task, got {len(phases[0].tasks)}"
        )
        task = phases[0].tasks[0]
        assert task.id == "P1-T01"
        assert task.status.name == "PENDING"


class TestNewProjectSessionstateParseable:
    """Generated SESSIONSTATE.md is parseable by session_parser."""

    def test_new_project_sessionstate_parseable(self, tmp_path: Path):
        """Round-trip: create project → parse SESSIONSTATE.md → no errors."""
        new_project(tmp_path, name="Parseable Project")

        session_path = tmp_path / "SESSIONSTATE.md"
        assert session_path.is_file()

        # Parse — expect no exceptions
        state = parse_session_file(session_path)

        # Verify basic structure
        assert state.active_phase_name == "[none]"
        assert state.active_task is None, (
            "Expected active_task to be None for a fresh project"
        )
        assert len(state.up_next) == 0, (
            f"Expected empty up_next, got {len(state.up_next)}"
        )
        assert len(state.completed) == 0, (
            f"Expected empty completed, got {len(state.completed)}"
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
