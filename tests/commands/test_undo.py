# tests/commands/test_undo.py — P4-T05 undo command tests
#
# Done-when criteria (from P4-T05 task block):
#
#   1. tsm undo against a fixture project with a history entry delegates to
#      shadow.undo without error
#   2. tsm undo against a project with no history prints "Nothing to undo."

from io import StringIO
from pathlib import Path
import sys

import pytest

from tsm.commands.undo import HELP_TEXT, undo
from tsm.models import ProjectContext
from tsm.shadow import apply as shadow_apply, stage as shadow_stage
from tsm.models import PendingWrite


# ── Fixture helpers ──────────────────────────────────────────────────────────


def _build_project_context(tmp_path: Path) -> ProjectContext:
    """Build a ProjectContext in *tmp_path* with an empty project structure."""
    root = tmp_path.resolve()
    shadow_dir = root / ".tsm" / "shadow"
    backup_dir = root / ".tsm" / "backups"

    tasks_live = root / "TASKS.md"
    session_live = root / "SESSIONSTATE.md"
    completed_live = root / "TASKS-COMPLETED.md"

    # Create initial live files
    tasks_live.write_text(
        "# Test Project\n\n---\n\n## Phase 1\n\n**Status:** Pending\n",
        encoding="utf-8",
    )
    session_live.write_text(
        "*Last updated: 2026-04-15T14:30*\n\n---\n\n## Active phase\n\nTest\n\n---\n",
        encoding="utf-8",
    )
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


def _run_undo(ctx: ProjectContext) -> str:
    """Run undo() and capture stdout output.

    Returns the captured output as a string.
    """
    captured = StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        undo(ctx)
    finally:
        sys.stdout = old_stdout
    return captured.getvalue()


# ── Tests ────────────────────────────────────────────────────────────────────


def test_undo_with_history(tmp_path: Path) -> None:
    """Undo against a project with a history entry succeeds without error.

    Creates a pending write, stages content, applies it (which creates a
    history entry), then undoes it.  Verifies the live file is restored.
    """
    ctx = _build_project_context(tmp_path)

    # Capture original content before modification
    original_content = Path(ctx.tasks_path).read_text(encoding="utf-8")

    # Create a shadow write to stage and apply
    shadow_path = Path(ctx.shadow_dir) / "TASKS.md"
    modified_content = "# Modified Content\n\n---\n"

    pw = PendingWrite(
        target_file="TASKS.md",
        shadow_path=str(shadow_path),
        live_path=ctx.tasks_path,
        backup_path=ctx.backup_dir,
        summary_lines=["Test modification"],
    )

    # Stage and apply (creates backup + history entry)
    shadow_stage(modified_content, pw)
    shadow_apply([pw])

    # Verify the live file was modified
    assert (
        Path(ctx.tasks_path).read_text(encoding="utf-8") == modified_content
    ), "Live file should be modified after apply"

    # Now undo — should restore original content
    output = _run_undo(ctx)

    # Should not print "Nothing to undo."
    assert "Nothing to undo." not in output, (
        f"Expected successful undo, got: {output}"
    )

    # Live file should be restored to original
    restored = Path(ctx.tasks_path).read_text(encoding="utf-8")
    assert restored == original_content, (
        f"Expected original content after undo, got:\n{restored}"
    )


def test_undo_no_history(tmp_path: Path) -> None:
    """Undo against a project with no history prints 'Nothing to undo.'"""
    ctx = _build_project_context(tmp_path)

    # Ensure no history.log exists
    history_path = Path(ctx.history_log_path)
    if history_path.exists():
        history_path.unlink()

    output = _run_undo(ctx)

    assert "Nothing to undo." in output, (
        f"Expected 'Nothing to undo.' for no history, got:\n{output}"
    )


def test_undo_empty_history(tmp_path: Path) -> None:
    """Undo against a project with empty history prints 'Nothing to undo.'"""
    ctx = _build_project_context(tmp_path)

    # Create an empty history.log
    history_path = Path(ctx.history_log_path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text("", encoding="utf-8")

    output = _run_undo(ctx)

    assert "Nothing to undo." in output, (
        f"Expected 'Nothing to undo.' for empty history, got:\n{output}"
    )


def test_undo_all_already_undone(tmp_path: Path) -> None:
    """Undo when all entries are already [undone] prints 'Nothing to undo.'"""
    ctx = _build_project_context(tmp_path)

    # Create a history.log with only [undone] entries
    history_path = Path(ctx.history_log_path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        "2026-04-15T14:30 | apply | staged changes | TASKS.md [undone]\n",
        encoding="utf-8",
    )

    output = _run_undo(ctx)

    assert "Nothing to undo." in output, (
        f"Expected 'Nothing to undo.' for all-undone history, got:\n{output}"
    )


def test_help_text_defined() -> None:
    """HELP_TEXT is a non-empty string constant."""
    assert isinstance(HELP_TEXT, str)
    assert len(HELP_TEXT) > 0
    assert "tsm undo" in HELP_TEXT
