# tsm/project.py — Project discovery and .gitignore enforcement (Phase 1, P1-T03)

import os
import sys
from pathlib import Path

from tsm.models import ProjectContext


# ── Public API ──────────────────────────────────────────────────────────────


def find_project_root(start: Path) -> Path | None:
    """Walk up the directory tree from *start* (max 3 parent levels) looking
    for a directory that contains *both* ``TASKS.md`` and ``SESSIONSTATE.md``.

    Returns the first matching :class:`Path`, or ``None`` if none is found
    within the allowed range.
    """
    candidates = [
        start,
        start.parent,
        start.parent.parent,
        start.parent.parent.parent,
    ]

    for candidate in candidates:
        if (candidate / "TASKS.md").is_file() and (
            candidate / "SESSIONSTATE.md"
        ).is_file():
            return candidate.resolve()

    return None


def ensure_tsm_dir(root: Path) -> ProjectContext:
    """Create the ``.tsm/`` shadow-directory structure inside *root* and
    ensure ``.gitignore`` contains a ``.tsm/`` entry.

    Returns a fully-populated :class:`ProjectContext` with absolute paths.
    """
    root = root.resolve()

    shadow_dir = root / ".tsm" / "shadow"
    backup_dir = root / ".tsm" / "backups"

    shadow_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    # ── .gitignore enforcement (idempotent) ─────────────────────────────
    gitignore_path = root / ".gitignore"
    modified = False

    if not gitignore_path.exists():
        gitignore_path.write_text(".tsm/\n", encoding="utf-8")
        modified = True
    else:
        lines = gitignore_path.read_text(encoding="utf-8").splitlines()
        if ".tsm/" not in lines:
            # Append .tsm/ entry, preserving trailing newline if present
            content = gitignore_path.read_bytes()
            if content and not content.endswith(b"\n"):
                gitignore_path.write_bytes(content + b"\n.tsm/\n")
            else:
                gitignore_path.write_bytes(content + b".tsm/\n")
            modified = True

    if modified:
        # §3.3 one-time notice
        print(
            "Added .tsm/ to .gitignore — shadow files and backups will not be committed."
        )

    # ── Build ProjectContext ────────────────────────────────────────────
    return ProjectContext(
        root=str(root),
        tasks_path=str(root / "TASKS.md"),
        sessionstate_path=str(root / "SESSIONSTATE.md"),
        tasks_completed_path=str(root / "TASKS-COMPLETED.md"),
        shadow_dir=str(shadow_dir),
        backup_dir=str(backup_dir),
        history_log_path=str(root / ".tsm" / "history.log"),
    )
