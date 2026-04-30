# tests/commands/test_help.py — P4-T06 help command tests
#
# Done-when criteria (from P4-T06 task block):
#
#   1. test_help_lists_all_commands passes
#   2. test_help_specific_command passes (output for tsm help advance
#      contains "Preconditions", "Writes", "Example")
#   3. test_help_unknown_command passes
#   4. test_help_no_project_root_required passes

from io import StringIO
import sys

import pytest

from tsm.commands.help import HELP_TEXT, help_command


# ── test_help_lists_all_commands ──────────────────────────────────────────────


def test_help_lists_all_commands() -> None:
    """'tsm help' (no arg) prints the full command list."""
    captured = StringIO()
    sys.stdout = captured
    try:
        help_command()
    finally:
        sys.stdout = sys.__stdout__

    output = captured.getvalue()

    # Must include the header
    assert "tsm — Task and Session State Manager" in output
    # Must list all 8 commands
    assert "init-phase" in output
    assert "advance" in output
    assert "complete-phase" in output
    assert "vibe-check" in output
    assert "status" in output
    assert "undo" in output
    assert "new-project" in output
    assert "help" in output
    # Must include the "Run 'tsm help <command>'" line
    assert "Run 'tsm help <command>' for full usage" in output


# ── test_help_specific_command ────────────────────────────────────────────────


def test_help_specific_command() -> None:
    """'tsm help advance' prints advance module's HELP_TEXT."""
    captured = StringIO()
    sys.stdout = captured
    try:
        help_command("advance")
    finally:
        sys.stdout = sys.__stdout__

    output = captured.getvalue()

    # advance HELP_TEXT must contain "Preconditions", "Writes", "Example"
    assert "Preconditions" in output
    assert "Writes" in output
    assert "Example" in output
    # Must mention the command name
    assert "tsm advance" in output


# ── test_help_unknown_command ─────────────────────────────────────────────────


def test_help_unknown_command() -> None:
    """'tsm help <unknown>' prints 'Unknown command: <name>'."""
    captured = StringIO()
    sys.stdout = captured
    try:
        help_command("nonexistent")
    finally:
        sys.stdout = sys.__stdout__

    output = captured.getvalue()
    assert "Unknown command: nonexistent" in output


# ── test_help_no_project_root_required ────────────────────────────────────────


def test_help_no_project_root_required() -> None:
    """help_command does not require a project root — calling it with no
    context (no project, no LoadedProject, no find_project_root) must
    succeed without error."""
    # No project setup of any kind — just call help_command directly
    captured = StringIO()
    sys.stdout = captured
    try:
        help_command()
    finally:
        sys.stdout = sys.__stdout__

    output = captured.getvalue()
    assert "tsm — Task and Session State Manager" in output
