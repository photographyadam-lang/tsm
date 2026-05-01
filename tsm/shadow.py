# tsm/shadow.py — Shadow write pipeline (Phase 3, P3-T01/P3-T02)

import os
from datetime import datetime
from pathlib import Path

from tsm.models import PendingWrite


# ── Public API ──────────────────────────────────────────────────────────────


def undo(root: Path) -> None:
    """Undo the most recent ``apply()`` operation (single-level).

    Algorithm (§6.5):

    1. Read ``.tsm/history.log``.
    2. Find the **last** line that does *not* contain ``[undone]``.
    3. For each filename listed on that line, find the most recent ``.bak``
       in ``.tsm/backups/`` and restore it to the live path.
    4. Append ``[undone]`` to that log line (in-place edit of the log file).

    Edge cases:

    * If ``history.log`` does not exist, is empty, or all entries are already
      marked ``[undone]``, print ``"Nothing to undo."`` and return.
    * If an undo is attempted immediately after a successful undo (double-undo),
      there will be no non-``[undone]`` entry → prints ``"Nothing to undo."``.

    Constraints:

    * Single-level only — no multi-level undo.
    * Does **not** create a new backup.
    * Does **not** write to shadow files.
    * Does **not** add a new entry to ``history.log``.
    """
    history_log_path = root / ".tsm" / "history.log"
    backup_dir = root / ".tsm" / "backups"

    if not history_log_path.exists():
        print("Nothing to undo.")
        return

    lines = history_log_path.read_text(encoding="utf-8").splitlines(keepends=True)

    # Find the last line that does NOT contain [undone]
    target_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if "[undone]" not in lines[i]:
            target_idx = i
            break

    if target_idx == -1:
        print("Nothing to undo.")
        return

    target_line = lines[target_idx].rstrip("\n\r")

    # Parse filenames from the log line format:
    #   {timestamp} | apply | staged changes | file1, file2
    parts = target_line.split(" | ")
    if len(parts) < 4:
        print("Nothing to undo.")
        return

    files_str = parts[-1]
    filenames = [f.strip() for f in files_str.split(",") if f.strip()]

    # Restore each file from its most recent .bak
    for filename in filenames:
        backups = sorted(
            [
                p
                for p in backup_dir.iterdir()
                if p.name.startswith(f"{filename}.") and p.suffix == ".bak"
            ],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not backups:
            print(f"Warning: no backup found for {filename}, skipping")
            continue

        latest_backup = backups[0]
        live_path = root / filename

        # Restore backup content to live path (no new backup created)
        live_bytes = latest_backup.read_bytes()
        live_path.write_bytes(live_bytes)

    # Mark the entry as undone (in-place edit of the log file)
    lines[target_idx] = target_line + " [undone]\n"
    history_log_path.write_text("".join(lines), encoding="utf-8")


def stage(content: str, pending_write: PendingWrite) -> None:
    """Write *content* to the shadow path of the given pending write.

    Creates the shadow parent directory if it does not exist.
    """
    shadow_path = Path(pending_write.shadow_path)
    shadow_path.parent.mkdir(parents=True, exist_ok=True)
    shadow_path.write_text(content, encoding="utf-8")


def apply(pending_writes: list[PendingWrite]) -> None:
    """Apply all pending writes in order.

    For each PendingWrite:

    1. Create a timestamped ``.bak`` backup in the backup directory using
       format ``<filename>.<YYYY-MM-DDTHH-MM>.bak`` (colons replaced with
       hyphens, seconds omitted).
    2. Use :func:`os.replace` to atomically move the shadow file to the live
       path.
    3. Prune backups for this filename — keep the 5 most recent by mtime,
       delete older ones.
    4. Append a pipe-delimited entry to ``.tsm/history.log``.

    Also ensures ``.gitignore`` contains a ``.tsm/`` entry (idempotent).
    """
    if not pending_writes:
        return

    _ensure_gitignore(pending_writes)
    _ensure_dirs(pending_writes)

    now = datetime.now()
    timestamp_backup = now.strftime("%Y-%m-%dT%H-%M")  # hyphens replace colons
    timestamp_log = now.strftime("%Y-%m-%dT%H:%M")

    history_log_path = _resolve_history_log_path(pending_writes[0])
    filenames_applied: list[str] = []

    for pw in pending_writes:
        live_path = Path(pw.live_path)
        shadow_path = Path(pw.shadow_path)
        backup_dir = Path(pw.backup_path)
        filename = live_path.name

        # 1. Create timestamped backup of the current live file
        backup_filename = f"{filename}.{timestamp_backup}.bak"
        backup_file = backup_dir / backup_filename
        if live_path.exists():
            live_bytes = live_path.read_bytes()
            backup_file.write_bytes(live_bytes)

        # 2. Atomic move: shadow → live
        if shadow_path.exists():
            os.replace(str(shadow_path), str(live_path))

        # 3. Prune backups for this filename — keep 5 most recent by mtime
        _prune_backups(backup_dir, filename)

        filenames_applied.append(filename)

    # 4. Append entry to history.log
    history_log_path.parent.mkdir(parents=True, exist_ok=True)
    files_str = ", ".join(filenames_applied)
    log_line = f"{timestamp_log} | apply | staged changes | {files_str}\n"
    with open(str(history_log_path), "a", encoding="utf-8") as f:
        f.write(log_line)


def confirm_prompt(
    pending_writes: list[PendingWrite], yes: bool = False
) -> bool:
    """Display pending changes summary and prompt for confirmation.

    If *yes* is ``True`` (``--yes`` flag), print the summary block and return
    ``True`` immediately without reading stdin.  Never defaults to ``True``
    internally — auto-confirm must be requested explicitly by the caller.

    Returns ``True`` if the user (or ``--yes`` flag) confirmed, ``False`` if
    they declined.
    """
    _print_summary(pending_writes)

    if yes:
        return True

    # NOTE: On Windows (PowerShell/CMD), Python's input("prompt") may not
    # reliably flush the prompt string to stdout before blocking on stdin,
    # causing a hang.  We work around this by printing the prompt explicitly
    # with flush=True, then calling input() with no argument.  This ensures
    # the prompt is visible before Python attempts to read from stdin.
    # See TSM #stdin-hang-on-windows.
    try:
        print("  Apply changes? [Y/n]: ", end="", flush=True)
        response = input()
    except (EOFError, KeyboardInterrupt):
        return False

    return response.strip().lower() in ("", "y", "yes")


# ── Internal helpers ────────────────────────────────────────────────────────


def _print_summary(pending_writes: list[PendingWrite]) -> None:
    """Print the §6.2 change summary block to stdout."""
    print("─" * 43)
    print("  Pending changes — review before applying")
    print("─" * 43)

    for pw in pending_writes:
        print(f"  {pw.target_file}")
        for line in pw.summary_lines:
            print(f"    • {line}")

    print("─" * 43)


def _ensure_gitignore(pending_writes: list[PendingWrite]) -> None:
    """Ensure ``.gitignore`` contains a ``.tsm/`` entry (idempotent).

    Derives the project root from the first pending write's backup path
    (``<root>/.tsm/backups/``).
    """
    root = _resolve_root(pending_writes[0])
    gitignore_path = root / ".gitignore"

    modified = False

    if not gitignore_path.exists():
        gitignore_path.write_text(".tsm/\n", encoding="utf-8")
        modified = True
    else:
        lines = gitignore_path.read_text(encoding="utf-8").splitlines()
        if ".tsm/" not in lines:
            content = gitignore_path.read_bytes()
            if content and not content.endswith(b"\n"):
                gitignore_path.write_bytes(content + b"\n.tsm/\n")
            else:
                gitignore_path.write_bytes(content + b".tsm/\n")
            modified = True

    if modified:
        print(
            "Added .tsm/ to .gitignore — shadow files and backups "
            "will not be committed."
        )


def _ensure_dirs(pending_writes: list[PendingWrite]) -> None:
    """Ensure backup directories exist for all pending writes."""
    for pw in pending_writes:
        Path(pw.backup_path).mkdir(parents=True, exist_ok=True)


def _prune_backups(backup_dir: Path, filename: str) -> None:
    """Remove all but the 5 most recently modified ``.bak`` files for
    *filename* in *backup_dir*.

    Sorting is by **mtime**, not lexicographic order.
    """
    backups = sorted(
        [
            p
            for p in backup_dir.iterdir()
            if p.name.startswith(f"{filename}.") and p.suffix == ".bak"
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for stale in backups[5:]:
        stale.unlink()


def _resolve_root(pw: PendingWrite) -> Path:
    """Derive the project root from a PendingWrite's backup path.

    Expects backup_path to be ``<root>/.tsm/backups/``.
    """
    return Path(pw.backup_path).parent.parent


def _resolve_history_log_path(pw: PendingWrite) -> Path:
    """Derive the history log path from a PendingWrite's backup path.

    Expects backup_path to be ``<root>/.tsm/backups/``; history log is
    ``<root>/.tsm/history.log``.
    """
    root = _resolve_root(pw)
    return root / ".tsm" / "history.log"
