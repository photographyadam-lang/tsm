# tsm/commands/help.py — Help command (Phase 4, P4-T06)
#
# Implements §7.8 help system.
#
# Public API:
#   help_command(command: str | None = None) -> None
#   get_help_text(command: str | None = None) -> str
#   HELP_TEXT: str
#
# Constraints (§7.8):
#   - Read-only — no file writes of any kind
#   - Does not require a project root — must not call find_project_root
#   - Per-command HELP_TEXT is imported at call time from each command module

import importlib
from typing import Optional


# ── HELP_TEXT constant for this module ────────────────────────────────────────

HELP_TEXT = """\
tsm — Task and Session State Manager

Usage: tsm <command> [options]

Commands:
  advance                  Complete active task, promote next task to active
  complete-phase           Mark current phase done, rotate to the next phase
  deps [--tree|--blocked|--check]   Inspect and validate task dependencies
  help [command]           Show this help, or detail for a specific command
  init-phase <phase-id>    Initialise SESSIONSTATE.md for the start of a phase
  new-project [--name]     Scaffold blank workflow files in the current directory
  phase <add|edit|move|remove> [args...]  Phase CRUD commands
  repair [--tasks] [--session] [--completed]  Repair inconsistencies in workflow files
  status                   Print current session state (read-only)
  task <add|edit|move|remove> [args...]   Task CRUD commands
  undo                     Revert the most recent apply operation
  vibe-check               Validate integrity of TASKS.md and SESSIONSTATE.md

Run 'tsm help <command>' for full usage of any command.
"""


# ── Command mapping from CLI name to module path ──────────────────────────────

_COMMAND_NAMES: dict[str, str] = {
    "advance": "tsm.commands.advance",
    "complete-phase": "tsm.commands.complete_phase",
    "deps": "tsm.commands.deps",
    "help": "tsm.commands.help",
    "init-phase": "tsm.commands.init_phase",
    "new-project": "tsm.commands.new_project",
    "phase": "tsm.commands.phase",
    "repair": "tsm.commands.repair",
    "status": "tsm.commands.status",
    "task": "tsm.commands.task",
    "undo": "tsm.commands.undo",
    "vibe-check": "tsm.commands.vibe_check",
}


# ── Public API ────────────────────────────────────────────────────────────────


def help_command(command: Optional[str] = None) -> None:
    """Print help text.

    Three variants per §7.8:
      1. No argument → print the full command list (HELP_TEXT from this module).
      2. Specific command name → import and print that module's HELP_TEXT.
      3. Unknown command name → print "Unknown command: <name>".

    Args:
        command: Optional CLI command name (e.g. "advance", "init-phase").
    """
    text = get_help_text(command)
    print(text)


def get_help_text(command: Optional[str] = None) -> str:
    """Return help text as a string (no printing).

    Three variants per §7.8:
      1. No argument → return the full command list (HELP_TEXT from this module).
      2. Specific command name → import and return that module's HELP_TEXT.
      3. Unknown command name → return "Unknown command: <name>".

    Args:
        command: Optional CLI command name (e.g. "advance", "init-phase").

    Returns:
        The help text string (never ``None``).
    """
    if command is None:
        return HELP_TEXT

    module_path = _COMMAND_NAMES.get(command)
    if module_path is None:
        return f"Unknown command: {command}"

    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        return f"Unknown command: {command}"

    help_text = getattr(mod, "HELP_TEXT", None)
    if help_text is None:
        return f"Unknown command: {command}"

    return help_text
