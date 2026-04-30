# tests/test_shadow.py — Shadow write pipeline tests (Phase 3, P3-T01/P3-T02)

import os
from datetime import datetime
from pathlib import Path

import pytest

from tsm.models import PendingWrite
from tsm.shadow import apply, confirm_prompt, stage, undo


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_pending(
    tmp_path: Path,
    filename: str = "TASKS.md",
    summary: str | None = None,
) -> PendingWrite:
    """Create a PendingWrite pointing into *tmp_path*.

    Ensures the shadow and backup directories exist.
    """
    root = tmp_path.resolve()
    shadow_dir = root / ".tsm" / "shadow"
    backup_dir = root / ".tsm" / "backups"
    shadow_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    live_path = root / filename
    shadow_path = shadow_dir / filename

    return PendingWrite(
        target_file=filename,
        shadow_path=str(shadow_path),
        live_path=str(live_path),
        backup_path=str(backup_dir),
        summary_lines=[summary or f"Update {filename}"],
    )


def _count_backups(backup_dir: Path, filename: str) -> int:
    """Count ``.bak`` files in *backup_dir* that start with *filename*."""
    return len(
        [p for p in backup_dir.iterdir() if p.name.startswith(f"{filename}.") and p.suffix == ".bak"]
    )


def _touch(path: Path, content: str = "") -> None:
    """Write *content* to *path*, ensuring parent directories exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ── test_shadow_creates_backup_on_apply ───────────────────────────────────


class TestShadowCreatesBackupOnApply:
    """P3-T01: apply creates a timestamped .bak backup."""

    def test_shadow_creates_backup_on_apply(self, tmp_path: Path) -> None:
        pw = _make_pending(tmp_path, "TASKS.md")
        live_path = Path(pw.live_path)
        backup_dir = Path(pw.backup_path)

        # Set up: live file exists with original content
        _touch(live_path, "ORIGINAL CONTENT")

        # Stage new content
        stage("NEW CONTENT", pw)

        # Apply
        apply([pw])

        # Live file now has new content
        assert live_path.read_text() == "NEW CONTENT"

        # Exactly one backup was created
        assert _count_backups(backup_dir, "TASKS.md") == 1

        # Backup contains the original content
        backups = list(backup_dir.glob("TASKS.md.*.bak"))
        assert backups[0].read_text() == "ORIGINAL CONTENT"

        # Backup filename matches required format
        assert backups[0].suffix == ".bak"
        name_part = backups[0].name
        # Format: TASKS.md.YYYY-MM-DDTHH-MM.bak  (note: hyphens, not colons)
        date_part = name_part.replace("TASKS.md.", "").replace(".bak", "")
        # Verify colon-replaced format (hyphens instead of colons in time)
        assert ":" not in date_part, "Backup filename must use hyphens, not colons"
        # Verify it parses as datetime
        datetime.strptime(date_part, "%Y-%m-%dT%H-%M")


# ── test_shadow_prunes_to_5_backups ──────────────────────────────────────


class TestShadowPrunesTo5Backups:
    """P3-T01: apply prunes backups to 5 most recent by mtime."""

    def test_shadow_prunes_to_5_backups(self, tmp_path: Path) -> None:
        pw = _make_pending(tmp_path, "TASKS.md")
        live_path = Path(pw.live_path)
        backup_dir = Path(pw.backup_path)

        # Create 6 pre-existing backups with distinct mtimes
        for i in range(6):
            ts = f"2026-04-{10 + i:02d}T10-0{i}"  # Apr 10–15
            bak_file = backup_dir / f"TASKS.md.{ts}.bak"
            _touch(bak_file, f"backup-{i}")
            # Set mtime so sorting is deterministic
            mtime = datetime(2026, 4, 10 + i, 10, i).timestamp()
            os.utime(str(bak_file), (mtime, mtime))

        assert _count_backups(backup_dir, "TASKS.md") == 6

        # Stage and apply a new change → creates 7th backup → prunes to 5
        _touch(live_path, "CURRENT")
        stage("NEW", pw)
        apply([pw])

        # Only 5 backups remain (the 5 most recent by mtime)
        assert _count_backups(backup_dir, "TASKS.md") == 5

        # The remaining backups should be the 5 newest ones
        remaining = sorted(
            [p for p in backup_dir.iterdir() if p.name.startswith("TASKS.md.") and p.suffix == ".bak"],
            key=lambda p: p.stat().st_mtime,
        )
        # The newest should be the one just created (today)
        assert remaining[-1].stat().st_mtime >= datetime(2026, 4, 15, 10, 5).timestamp()


# ── test_shadow_gitignore_created ─────────────────────────────────────────


class TestShadowGitignoreCreated:
    """P3-T01: apply creates .gitignore if it doesn't exist."""

    def test_shadow_gitignore_created(self, tmp_path: Path, capsys) -> None:
        pw = _make_pending(tmp_path, "README.md")
        root = Path(pw.backup_path).parent.parent
        gitignore = root / ".gitignore"

        assert not gitignore.exists()

        _touch(Path(pw.live_path), "hello")
        stage("world", pw)
        apply([pw])

        # .gitignore was created
        assert gitignore.exists()
        content = gitignore.read_text(encoding="utf-8")
        assert ".tsm/" in content

        # One-time notice was printed
        captured = capsys.readouterr()
        assert ".tsm/" in captured.out
        assert ".gitignore" in captured.out


# ── test_shadow_gitignore_appended ───────────────────────────────────────


class TestShadowGitignoreAppended:
    """P3-T01: apply appends .tsm/ to existing .gitignore that lacks it."""

    def test_shadow_gitignore_appended(self, tmp_path: Path, capsys) -> None:
        pw = _make_pending(tmp_path, "README.md")
        root = Path(pw.backup_path).parent.parent
        gitignore = root / ".gitignore"

        # Pre-existing .gitignore without .tsm/
        _touch(gitignore, "*.pyc\n__pycache__/\n")

        _touch(Path(pw.live_path), "hello")
        stage("world", pw)
        apply([pw])

        content = gitignore.read_text(encoding="utf-8")
        assert ".tsm/" in content
        assert content.startswith("*.pyc\n__pycache__/\n")  # existing content preserved

        captured = capsys.readouterr()
        assert ".gitignore" in captured.out
        assert "Added" in captured.out


# ── test_shadow_gitignore_idempotent ─────────────────────────────────────


class TestShadowGitignoreIdempotent:
    """P3-T01: apply twice does not duplicate .tsm/ in .gitignore."""

    def test_shadow_gitignore_idempotent(self, tmp_path: Path) -> None:
        pw = _make_pending(tmp_path, "README.md")
        root = Path(pw.backup_path).parent.parent
        gitignore = root / ".gitignore"

        # First apply — creates .gitignore with .tsm/
        _touch(Path(pw.live_path), "v1")
        stage("v1-shadow", pw)
        apply([pw])

        assert gitignore.exists()
        lines_after_first = gitignore.read_text(encoding="utf-8").splitlines()
        count_first = lines_after_first.count(".tsm/")
        assert count_first == 1, f"Expected 1 .tsm/ entry after first apply, got {count_first}"

        # Second apply — must not duplicate
        _touch(Path(pw.live_path), "v2")
        stage("v2-shadow", pw)
        apply([pw])

        lines_after_second = gitignore.read_text(encoding="utf-8").splitlines()
        count_second = lines_after_second.count(".tsm/")
        assert count_second == 1, f"Expected 1 .tsm/ entry after second apply, got {count_second}"


# ── test_confirm_prompt_yes_flag ─────────────────────────────────────────


class TestConfirmPromptYesFlag:
    """P3-T01: confirm_prompt(…, yes=True) prints summary and returns True
    without ever reading stdin."""

    def test_confirm_prompt_yes_flag(self, tmp_path: Path, monkeypatch, capsys) -> None:
        # Ensure stdin is never read — fail if input() is called
        monkeypatch.setattr("builtins.input", lambda _="": (_ for _ in ()).throw(AssertionError("input was called but should not have been")))

        pw = _make_pending(tmp_path, "TASKS.md", summary="Set Status → Complete")

        result = confirm_prompt([pw], yes=True)

        # Returns True immediately
        assert result is True

        # Summary was printed to stdout
        captured = capsys.readouterr()
        assert "Pending changes" in captured.out
        assert "TASKS.md" in captured.out
        assert "Set Status → Complete" in captured.out
        assert "Apply changes" in captured.out or "─" * 3 in captured.out


# ── test_shadow_undo_restores_live_file ──────────────────────────────────


class TestShadowUndoRestoresLiveFile:
    """P3-T02: undo restores the live file from the most recent backup."""

    def test_shadow_undo_restores_live_file(self, tmp_path: Path, capsys) -> None:
        root = tmp_path.resolve()
        pw = _make_pending(root, "TASKS.md")
        live_path = Path(pw.live_path)

        # Set up: live file with original content
        _touch(live_path, "ORIGINAL CONTENT")

        # Stage and apply new content
        stage("NEW CONTENT", pw)
        apply([pw])

        # Verify live file has new content
        assert live_path.read_text() == "NEW CONTENT"

        # Undo — restores original content from backup
        undo(root)

        assert live_path.read_text() == "ORIGINAL CONTENT"

        # No new backup was created — only the one from apply remains
        backups = list((root / ".tsm" / "backups").glob("TASKS.md.*.bak"))
        assert len(backups) == 1

        # History log entry is marked [undone]
        history_log = root / ".tsm" / "history.log"
        content = history_log.read_text(encoding="utf-8")
        assert "[undone]" in content
        # Exactly one [undone] marker
        assert content.count("[undone]") == 1

        # No "Nothing to undo." was printed
        captured = capsys.readouterr()
        assert "Nothing to undo." not in captured.out


# ── test_shadow_undo_no_history ──────────────────────────────────────────


class TestShadowUndoNoHistory:
    """P3-T02: undo with no history.log prints 'Nothing to undo.' """

    def test_shadow_undo_no_history(self, tmp_path: Path, capsys) -> None:
        root = tmp_path.resolve()

        # No .tsm/ directory exists at all
        undo(root)

        captured = capsys.readouterr()
        assert "Nothing to undo." in captured.out


# ── test_shadow_double_undo ──────────────────────────────────────────────


class TestShadowDoubleUndo:
    """P3-T02: calling undo twice restores once, then prints
    'Nothing to undo.' on the second call (double-undo guard)."""

    def test_shadow_double_undo(self, tmp_path: Path, capsys) -> None:
        root = tmp_path.resolve()
        pw = _make_pending(root, "TASKS.md")
        live_path = Path(pw.live_path)

        # Set up: live file with original content
        _touch(live_path, "ORIGINAL CONTENT")

        # Stage and apply
        stage("NEW CONTENT", pw)
        apply([pw])

        # First undo — succeeds
        undo(root)
        assert live_path.read_text() == "ORIGINAL CONTENT"
        captured1 = capsys.readouterr()
        assert "Nothing to undo." not in captured1.out

        # Second undo — double-undo guard fires
        undo(root)
        captured2 = capsys.readouterr()
        assert "Nothing to undo." in captured2.out

        # File stays in the restored state (not further modified)
        assert live_path.read_text() == "ORIGINAL CONTENT"

        # No new backup was created on either undo
        backups = list((root / ".tsm" / "backups").glob("TASKS.md.*.bak"))
        assert len(backups) == 1

        # History log still has exactly one [undone] marker
        history_log = root / ".tsm" / "history.log"
        content = history_log.read_text(encoding="utf-8")
        assert content.count("[undone]") == 1
