# tests/test_project_discovery.py — P1-T03: project discovery and .gitignore enforcement

from pathlib import Path

import pytest

from tsm.project import ensure_tsm_dir, find_project_root


# ── Helpers ─────────────────────────────────────────────────────────────────


def _touch(path: Path) -> None:
    """Create an empty file at *path*, including parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")


# ── find_project_root ───────────────────────────────────────────────────────


class TestFindProjectRoot:
    def _make_valid_root(self, tmp_path: Path) -> Path:
        """Create a minimal valid project root with both marker files."""
        root = tmp_path / "project"
        _touch(root / "TASKS.md")
        _touch(root / "SESSIONSTATE.md")
        return root

    # ── 1, 2, and 3 levels below root ──────────────────────────────────

    def test_returns_root_when_called_from_1_level_deep(self, tmp_path):
        root = self._make_valid_root(tmp_path)
        sub = root / "sub1"
        sub.mkdir(parents=True, exist_ok=True)
        assert find_project_root(sub) == root.resolve()

    def test_returns_root_when_called_from_2_levels_deep(self, tmp_path):
        root = self._make_valid_root(tmp_path)
        sub = root / "sub1" / "sub2"
        sub.mkdir(parents=True, exist_ok=True)
        assert find_project_root(sub) == root.resolve()

    def test_returns_root_when_called_from_3_levels_deep(self, tmp_path):
        root = self._make_valid_root(tmp_path)
        sub = root / "sub1" / "sub2" / "sub3"
        sub.mkdir(parents=True, exist_ok=True)
        assert find_project_root(sub) == root.resolve()

    # ── Beyond 3 levels → None ─────────────────────────────────────────

    def test_returns_none_when_called_from_4_levels_deep(self, tmp_path):
        root = self._make_valid_root(tmp_path)
        sub = root / "a" / "b" / "c" / "d"
        sub.mkdir(parents=True, exist_ok=True)
        assert find_project_root(sub) is None

    # ── No valid project root ───────────────────────────────────────────

    def test_returns_none_when_no_marker_files_exist(self, tmp_path):
        d = tmp_path / "some_dir"
        d.mkdir(parents=True, exist_ok=True)
        assert find_project_root(d) is None

    def test_returns_none_when_only_tasks_md_exists(self, tmp_path):
        d = tmp_path / "partial"
        _touch(d / "TASKS.md")
        assert find_project_root(d) is None

    def test_returns_none_when_only_sessionstate_md_exists(self, tmp_path):
        d = tmp_path / "partial"
        _touch(d / "SESSIONSTATE.md")
        assert find_project_root(d) is None


# ── ensure_tsm_dir ─────────────────────────────────────────────────────────


class TestEnsureTsmDir:
    # ── Creates .tsm/shadow/ and .tsm/backups/ ─────────────────────────

    def test_creates_shadow_and_backup_dirs(self, tmp_path):
        ctx = ensure_tsm_dir(tmp_path)
        assert Path(ctx.shadow_dir).is_dir()
        assert Path(ctx.backup_dir).is_dir()

    # ── Idempotent — calling twice → one .tsm/ line ────────────────────

    def test_running_twice_produces_exactly_one_tsm_line(self, tmp_path):
        ensure_tsm_dir(tmp_path)
        ensure_tsm_dir(tmp_path)
        gitignore = tmp_path / ".gitignore"
        lines = gitignore.read_text(encoding="utf-8").splitlines()
        tsm_lines = [ln for ln in lines if ln.strip() == ".tsm/"]
        assert len(tsm_lines) == 1

    # ── No .gitignore → creates one with .tsm/ ──────────────────────────

    def test_creates_gitignore_when_missing(self, tmp_path):
        assert not (tmp_path / ".gitignore").exists()
        ensure_tsm_dir(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text(encoding="utf-8")
        assert ".tsm/" in content

    # ── Existing .gitignore with .tsm/ → no changes ─────────────────────

    def test_no_changes_when_gitignore_already_has_tsm(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        original = "# some config\n.tsm/\n*.pyc\n"
        gitignore.write_text(original, encoding="utf-8")
        ensure_tsm_dir(tmp_path)
        assert gitignore.read_text(encoding="utf-8") == original

    # ── Returns a fully-populated ProjectContext ────────────────────────

    def test_returns_populated_project_context(self, tmp_path):
        ctx = ensure_tsm_dir(tmp_path)
        assert ctx.root == str(tmp_path.resolve())
        assert ctx.tasks_path == str(tmp_path.resolve() / "TASKS.md")
        assert ctx.sessionstate_path == str(tmp_path.resolve() / "SESSIONSTATE.md")
        assert ctx.tasks_completed_path == str(
            tmp_path.resolve() / "TASKS-COMPLETED.md"
        )
        assert ctx.shadow_dir == str(tmp_path.resolve() / ".tsm" / "shadow")
        assert ctx.backup_dir == str(tmp_path.resolve() / ".tsm" / "backups")
        assert ctx.history_log_path == str(
            tmp_path.resolve() / ".tsm" / "history.log"
        )

    # ── Works with nested subdirectory — root detection not confused ────

    def test_ensure_tsm_dir_inside_subdir_uses_same_root(self, tmp_path):
        """Calling ensure_tsm_dir from a nested path should use that path as root."""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True, exist_ok=True)
        ctx = ensure_tsm_dir(nested)
        assert Path(ctx.root) == nested.resolve()
        assert Path(ctx.shadow_dir).parent == nested.resolve() / ".tsm"
        assert Path(ctx.backup_dir).parent == nested.resolve() / ".tsm"
