# tsm/commands/help.py — Help command (Phase 4, P4-T06)
#
# Implements §7.8 help system.
#
# Public API:
#   help_command(command: str | None = None) -> None
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
  init-phase <phase-id>    Initialise SESSIONSTATE.md for the start of a phase
  advance                  Complete active task, promote next task to active
  complete-phase           Mark current phase done, rotate to the next phase
  vibe-check               Validate integrity of TASKS.md and SESSIONSTATE.md
  status                   Print current session state (read-only)
  undo                     Revert the most recent apply operation
  new-project [--name]     Scaffold blank workflow files in the current directory
  help [command]           Show this help, or detail for a specific command

Run 'tsm help <command>' for full usage of any command.
"""


# ── Command mapping from CLI name to module path ──────────────────────────────

_COMMAND_NAMES: dict[str, str] = {
    "init-phase": "tsm.commands.init_phase",
    "advance": "tsm.commands.advance",
    "complete-phase": "tsm.commands.complete_phase",
    "vibe-check": "tsm.commands.vibe_check",
    "status": "tsm.commands.status",
    "undo": "tsm.commands.undo",
    "new-project": "tsm.commands.new_project",
    "help": "tsm.commands.help",
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
    if command is None:
        print(HELP_TEXT)
        return

    module_path = _COMMAND_NAMES.get(command)
    if module_path is None:
        print(f"Unknown command: {command}")
        return

    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        print(f"Unknown command: {command}")
        return

    help_text = getattr(mod, "HELP_TEXT", None)
    if help_text is None:
        print(f"Unknown command: {command}")
        return

    print(help_text)
