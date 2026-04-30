# tsm/commands/undo.py — Undo the most recent apply (Phase 4, P4-T05)
#
# Implements §7.7 undo command — delegates to shadow.undo().
#
# Public API:
#   undo(ctx: ProjectContext) -> None
#   HELP_TEXT: str
#
# Constraints (§7.7):
#   - Delegates directly to shadow.undo(ctx.root)
#   - Read-only in the sense that it delegates to shadow's undo logic
#   - HELP_TEXT must be a module-level string constant

from pathlib import Path

from tsm.models import ProjectContext
from tsm.shadow import undo as shadow_undo


# ── Public API ──────────────────────────────────────────────────────────────


def undo(ctx: ProjectContext) -> None:
    """Undo the most recent ``shadow.apply()`` operation.

    Delegates directly to :func:`tsm.shadow.undo` with the project root
    path.  See §6.5 for full undo algorithm.

    Args:
        ctx: The project context providing the root path.
    """
    shadow_undo(Path(ctx.root))


# ── HELP_TEXT ──────────────────────────────────────────────────────────────

HELP_TEXT = """\
tsm undo — Revert the most recent apply operation.

Usage: tsm undo

Single-level undo. Restores the live files from the backups that were created
by the most recent ``tsm apply`` operation.  Does not create new backups or
new history entries.

If there is nothing to undo (no history or all entries already marked [undone]),
prints "Nothing to undo." and exits gracefully.

Preconditions:
  - A project root must exist (TASKS.md and SESSIONSTATE.md must be present).
  - At least one apply operation must have been performed previously.

No new files are written — existing backups are restored.

Example:
  tsm undo
"""
