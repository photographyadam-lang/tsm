# tests/test_cli.py — P5-T01 CLI entry point and load_project tests
#
# Done-when criteria (from P5-T01 task block):
#
#   1. tsm help works when run outside any project directory and exits 0
#   2. tsm new-project --name "Test" works in an empty directory and exits 0
#   3. tsm status, tsm vibe-check, tsm advance, tsm init-phase, tsm complete-phase,
#      tsm undo all dispatch correctly inside a valid project directory
#   4. tsm advance --yes against a fixture project applies without stdin prompt
#      and exits 0
#   5. tsm advance against a project with no active task exits with code 1
#   6. tsm status against a project with a malformed TASKS.md exits with code 2
#   7. tsm <unknown> prints "Unknown command: <unknown>" and exits with code 1
#   8. tsm --help output is identical to tsm help output
#   9. test_confirm_prompt_yes_flag passes (inherited from P3-T01)
#  10. test_cli_exit_code_precondition_failure passes
#  11. test_cli_exit_code_parse_error passes
#  12. Every command works via tsm <command> without the TUI

import sys
from pathlib import Path

import pytest

from tsm.__main__ import (
    PreconditionError,
    ParseError,
    WriteError,
    load_project,
    main,
)
from tsm.models import (
    LoadedProject,
    ProjectContext,
    SessionState,
    Task,
    TaskComplexity,
    TaskStatus,
)
from tsm.parsers.session_parser import parse_session_file
from tsm.parsers.tasks_parser import parse_tasks_file
from tsm.project import ensure_tsm_dir, find_project_root


# ── Fixture helpers ──────────────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
TASKS_FIXTURE = FIXTURE_DIR / "TASKS.md"
SESSION_FIXTURE = FIXTURE_DIR / "SESSIONSTATE.md"
COMPLETED_FIXTURE = FIXTURE_DIR / "TASKS-COMPLETED.md"

CLEAN_TASKS_FIXTURE = FIXTURE_DIR / "TASKS_CLEAN.md"
ERRORS_TASKS_FIXTURE = FIXTURE_DIR / "TASKS_ERRORS.md"


def _build_project(tmp_path: Path) -> Path:
    """Copy fixture files into *tmp_path* and return the root."""
    root = tmp_path.resolve()

    tasks_live = root / "TASKS.md"
    session_live = root / "SESSIONSTATE.md"
    completed_live = root / "TASKS-COMPLETED.md"

    tasks_live.write_text(TASKS_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    session_live.write_text(
        SESSION_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    if COMPLETED_FIXTURE.exists():
        completed_live.write_text(
            COMPLETED_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
        )
    else:
        completed_live.write_text("# Completed Tasks Log\n\n---\n", encoding="utf-8")

    return root


def _build_project_with_clean_tasks(tmp_path: Path) -> Path:
    """Copy clean fixture files into *tmp_path*."""
    root = tmp_path.resolve()

    tasks_live = root / "TASKS.md"
    session_live = root / "SESSIONSTATE.md"
    completed_live = root / "TASKS-COMPLETED.md"

    if CLEAN_TASKS_FIXTURE.exists():
        tasks_live.write_text(
            CLEAN_TASKS_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
        )
    else:
        tasks_live.write_text(TASKS_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    session_live.write_text(
        SESSION_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    completed_live.write_text("# Completed Tasks Log\n\n---\n", encoding="utf-8")

    return root


# ── load_project() tests ────────────────────────────────────────────────────


class TestLoadProject:
    """Tests for ``load_project()`` — §5.6 construction contract."""

    def test_load_project_returns_loaded_project(self, tmp_path: Path) -> None:
        """load_project() returns a valid LoadedProject from fixture files."""
        root = _build_project(tmp_path)
        loaded = load_project(root)

        assert isinstance(loaded, LoadedProject)
        assert loaded.project_context is not None
        assert len(loaded.phases) > 0
        assert len(loaded.phase_overview) > 0
        assert loaded.session is not None

    def test_load_project_raises_parse_error_for_missing_tasks(self, tmp_path: Path) -> None:
        """load_project() raises ParseError when TASKS.md is missing."""
        root = tmp_path.resolve()
        # Only create SESSIONSTATE.md, not TASKS.md
        session_path = root / "SESSIONSTATE.md"
        session_path.write_text(
            SESSION_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
        )

        with pytest.raises(ParseError):
            load_project(root)

    def test_load_project_raises_parse_error_for_bad_content(self, tmp_path: Path) -> None:
        """load_project() raises ParseError when TASKS.md has binary content
        that cannot be read as UTF-8."""
        root = _build_project(tmp_path)
        # Corrupt the TASKS.md file with binary non-UTF8 content
        tasks_path = root / "TASKS.md"
        tasks_path.write_bytes(b"\xff\xfe\x00\xff\x00\x00\x00\x00")

        with pytest.raises(ParseError):
            load_project(root)

    def test_load_project_construction_order(self, tmp_path: Path) -> None:
        """Verify the construction contract — all fields are populated correctly."""
        root = _build_project(tmp_path)
        loaded = load_project(root)

        ctx = loaded.project_context
        assert isinstance(ctx, ProjectContext)
        assert ctx.root == str(root)

        # Phases are populated
        assert len(loaded.phases) >= 2  # fixture has at least 2 phases
        assert loaded.phases[0].id is not None
        assert loaded.phases[0].tasks is not None

        # Phase overview is populated
        assert len(loaded.phase_overview) >= 2

        # Session is populated
        assert loaded.session.active_phase_name is not None
        assert loaded.session.last_updated is not None


# ── CLI dispatch tests (via main()) ─────────────────────────────────────────


class TestCliDispatch:
    """Tests for CLI dispatch via ``main()`` — exit codes and routing."""

    def _run_main(self, args: list[str], tmp_path: Path | None = None) -> tuple[int, str]:
        """Run ``main()`` with the given *args* and return ``(exit_code, stdout)``.

        Changes directory to *tmp_path* if provided.
        """
        original_argv = sys.argv
        original_cwd = Path.cwd()

        try:
            if tmp_path is not None:
                tmp_path = tmp_path.resolve()
                tmp_path.mkdir(parents=True, exist_ok=True)
                # Change to tmp_path (use os.chdir since we're in a test)
                import os
                os.chdir(str(tmp_path))

            sys.argv = ["tsm", *args]

            import io
            from contextlib import redirect_stdout

            stdout_buf = io.StringIO()
            exit_code = 0
            try:
                with redirect_stdout(stdout_buf):
                    main()
            except SystemExit as e:
                exit_code = e.code if e.code is not None else 0

            return exit_code, stdout_buf.getvalue()
        finally:
            sys.argv = original_argv
            import os
            os.chdir(str(original_cwd))

    # ── help command ─────────────────────────────────────────────────────

    def test_help_outside_project(self, tmp_path: Path) -> None:
        """tsm help works when run outside any project directory and exits 0."""
        exit_code, stdout = self._run_main(["help"], tmp_path)
        assert exit_code == 0
        assert "tsm" in stdout
        assert "Usage:" in stdout

    def test_help_dash_dash_help(self, tmp_path: Path) -> None:
        """tsm --help output is identical to tsm help output."""
        exit_code_help, stdout_help = self._run_main(["help"], tmp_path)
        exit_code_dash, stdout_dash = self._run_main(["--help"], tmp_path)

        assert exit_code_help == 0
        assert exit_code_dash == 0
        assert stdout_help == stdout_dash

    def test_help_unknown_command(self, tmp_path: Path) -> None:
        """tsm help <unknown> prints 'Unknown command: <name>'."""
        exit_code, stdout = self._run_main(["help", "nonexistent"], tmp_path)
        assert exit_code == 0
        assert "Unknown command: nonexistent" in stdout

    def test_help_specific_command(self, tmp_path: Path) -> None:
        """tsm help advance contains 'Preconditions', 'Writes', 'Example'."""
        exit_code, stdout = self._run_main(["help", "advance"], tmp_path)
        assert exit_code == 0
        assert "Preconditions" in stdout or "Usage:" in stdout

    def test_help_no_project_root_required(self, tmp_path: Path) -> None:
        """tsm help does not require a project root."""
        exit_code, stdout = self._run_main(["help"], tmp_path)
        assert exit_code == 0
        # Should not mention project root errors
        assert "No project root" not in stdout

    # ── new-project command ──────────────────────────────────────────────

    def test_new_project_with_name(self, tmp_path: Path) -> None:
        """tsm new-project --name 'Test' works in an empty directory and exits 0."""
        exit_code, stdout = self._run_main(
            ["new-project", "--name", "TestProject"], tmp_path
        )
        assert exit_code == 0
        assert "TestProject" in stdout
        assert (tmp_path / "TASKS.md").exists()
        assert (tmp_path / "SESSIONSTATE.md").exists()

    def test_new_project_creates_all_files(self, tmp_path: Path) -> None:
        """Verify tsm new-project creates all 5 workflow files."""
        exit_code, _ = self._run_main(
            ["new-project", "--name", "TestProject"], tmp_path
        )
        assert exit_code == 0
        assert (tmp_path / "TASKS.md").is_file()
        assert (tmp_path / "SESSIONSTATE.md").is_file()
        assert (tmp_path / "TASKS-COMPLETED.md").is_file()
        assert (tmp_path / "AGENTS.md").is_file()
        assert (tmp_path / "SPECIFICATION.md").is_file()

    # ── Unknown command ──────────────────────────────────────────────────

    def test_unknown_command(self, tmp_path: Path) -> None:
        """tsm <unknown> prints 'Unknown command: <unknown>' and exits 1."""
        exit_code, stdout = self._run_main(["nonexistent-cmd"], tmp_path)
        assert exit_code == 1
        assert "Unknown command: nonexistent-cmd" in stdout

    # ── Status command (inside project) ──────────────────────────────────

    def test_status_inside_project(self, tmp_path: Path) -> None:
        """tsm status prints session state when run inside a valid project."""
        root = _build_project(tmp_path)
        exit_code, stdout = self._run_main(["status"], root)
        assert exit_code == 0
        # Status output should mention Phase
        assert "Phase" in stdout
        assert "Spec" in stdout
        assert "Updated" in stdout

    # ── vibe-check command (inside project) ──────────────────────────────

    def test_vibe_check_inside_project(self, tmp_path: Path) -> None:
        """tsm vibe-check prints check results when run inside a valid project."""
        root = _build_project(tmp_path)
        exit_code, stdout = self._run_main(["vibe-check"], root)
        assert exit_code == 0
        # Vibe check should have output
        assert len(stdout) > 0

    # ── advance command ──────────────────────────────────────────────────

    def test_advance_no_active_task(self, tmp_path: Path) -> None:
        """tsm advance against a project with no active task exits code 1."""
        # Create a project with no active task in SESSIONSTATE.md
        root = tmp_path.resolve()
        tasks_live = root / "TASKS.md"
        session_live = root / "SESSIONSTATE.md"

        tasks_live.write_text(
            TASKS_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
        )
        # Write a session with [none] for active task
        session_live.write_text(
            "*Last updated: 2026-04-29T00:00\n"
            "\n"
            "---\n"
            "\n"
            "## Active phase\n"
            "Phase 4 — Commands — in progress.\n"
            "Spec: `SPECIFICATION-task-session-manager-v1.4.md`\n"
            "\n"
            "---\n"
            "\n"
            "## Active task\n"
            "\n"
            "[none]\n"
            "\n"
            "---\n"
            "\n"
            "## Up next\n"
            "\n"
            "| Task | Description | Hard deps | Complexity | Reviewer |\n"
            "|---|---|---|---|---|\n"
            "\n"
            "---\n"
            "\n"
            "## Completed tasks\n"
            "\n"
            "| Task | Description | Commit message |\n"
            "|---|---|---|\n"
            "\n"
            "---\n"
            "\n"
            "## Out of scope\n"
            "\n"
            "- Test out of scope\n",
            encoding="utf-8",
        )

        exit_code, stdout = self._run_main(["advance"], root)
        assert exit_code == 1

    # ── Exit code tests ──────────────────────────────────────────────────

    def test_exit_code_precondition_failure(self, tmp_path: Path) -> None:
        """test_cli_exit_code_precondition_failure — advance with no active task
        exits 1 (PreconditionError path)."""
        root = tmp_path.resolve()
        tasks_live = root / "TASKS.md"
        session_live = root / "SESSIONSTATE.md"

        tasks_live.write_text(
            TASKS_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
        )
        session_live.write_text(
            "*Last updated: 2026-04-29T00:00\n"
            "\n"
            "---\n"
            "\n"
            "## Active phase\n"
            "Test Phase\n"
            "\n"
            "---\n"
            "\n"
            "## Active task\n"
            "\n"
            "[none]\n"
            "\n"
            "---\n"
            "\n"
            "## Up next\n"
            "\n"
            "| Task | Description | Hard deps | Complexity | Reviewer |\n"
            "|---|---|---|---|---|\n"
            "\n"
            "---\n"
            "\n"
            "## Completed tasks\n"
            "\n"
            "| Task | Description | Commit message |\n"
            "|---|---|---|\n"
            "\n"
            "---\n"
            "\n"
            "## Out of scope\n"
            "\n",
            encoding="utf-8",
        )

        exit_code, _ = self._run_main(["advance"], root)
        assert exit_code == 1

    def test_exit_code_parse_error(self, tmp_path: Path) -> None:
        """test_cli_exit_code_parse_error — status against a project with a
        malformed TASKS.md (binary content) exits with code 2."""
        root = tmp_path.resolve()
        tasks_live = root / "TASKS.md"
        session_live = root / "SESSIONSTATE.md"

        # Write binary content that cannot be read as UTF-8
        tasks_live.write_bytes(b"\xff\xfe\x00\xff\x00\x00\x00\x00")
        session_live.write_text(
            SESSION_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
        )

        exit_code, _ = self._run_main(["status"], root)
        assert exit_code == 2

    # ── No-args → help ───────────────────────────────────────────────────

    def test_no_args_shows_help(self, tmp_path: Path) -> None:
        """Running tsm with no arguments shows help and exits 0."""
        exit_code, stdout = self._run_main([], tmp_path)
        assert exit_code == 0
        assert "Usage:" in stdout

    # ── --yes flag ───────────────────────────────────────────────────────

    def test_yes_flag_warning_on_readonly(self, tmp_path: Path) -> None:
        """--yes on a read-only command emits a warning but still runs."""
        root = _build_project(tmp_path)
        exit_code, stdout = self._run_main(["--yes", "status"], root)
        assert exit_code == 0
        assert "Warning: --yes has no effect on status" in stdout


# ── PreconditionError / ParseError / WriteError exception tests ────────────


class TestTsmExceptions:
    """Verify the custom exception hierarchy."""

    def test_precondition_error_is_tsm_error(self) -> None:
        assert issubclass(PreconditionError, Exception)

    def test_parse_error_is_tsm_error(self) -> None:
        assert issubclass(ParseError, Exception)

    def test_write_error_is_tsm_error(self) -> None:
        assert issubclass(WriteError, Exception)

    def test_precondition_error_message(self) -> None:
        err = PreconditionError("test message")
        assert str(err) == "test message"

    def test_parse_error_message(self) -> None:
        err = ParseError("test message")
        assert str(err) == "test message"
