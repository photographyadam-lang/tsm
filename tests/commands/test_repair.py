# tests/commands/test_repair.py — P7-T07 repair command tests
#
# Done-when criteria (from P7-T07 task block):
#
#   1. test_repair_fills_missing_fields passes
#   2. test_repair_removes_vc10_rows passes
#   3. test_repair_normalizes_session_task_id passes
#   4. test_repair_skips_unparseable_content passes
#   5. Confirm summary groups changes by file and labels each change correctly
#   6. Running repair twice on an already-clean file produces zero changes
#      (idempotency test)

from pathlib import Path

import pytest

from tsm.commands.repair import HELP_TEXT, repair
from tsm.models import (
    LoadedProject,
    ProjectContext,
)
from tsm.parsers.session_parser import parse_session_file
from tsm.parsers.tasks_parser import parse_tasks_file


# ── Fixture helpers ──────────────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
TASKS_FIXTURE = FIXTURE_DIR / "TASKS.md"
SESSION_FIXTURE = FIXTURE_DIR / "SESSIONSTATE.md"
COMPLETED_FIXTURE = FIXTURE_DIR / "TASKS-COMPLETED.md"


def _build_project_context(tmp_path: Path) -> ProjectContext:
    """Build a ProjectContext pointing at *tmp_path* as the project root."""
    root = tmp_path.resolve()
    shadow_dir = root / ".tsm" / "shadow"
    backup_dir = root / ".tsm" / "backups"
    return ProjectContext(
        root=str(root),
        tasks_path=str(root / "TASKS.md"),
        sessionstate_path=str(root / "SESSIONSTATE.md"),
        tasks_completed_path=str(root / "TASKS-COMPLETED.md"),
        shadow_dir=str(shadow_dir),
        backup_dir=str(backup_dir),
        history_log_path=str(root / ".tsm" / "history.log"),
    )


def _build_loaded_project(
    tmp_path: Path,
    tasks_content: str,
    session_content: str,
    completed_content: str,
) -> LoadedProject:
    """Build a LoadedProject from the given content strings, writing them to
    temporary files under *tmp_path*."""
    pc = _build_project_context(tmp_path)

    tasks_path = Path(pc.tasks_path)
    session_path = Path(pc.sessionstate_path)
    completed_path = Path(pc.tasks_completed_path)

    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text(tasks_content, encoding="utf-8")
    session_path.write_text(session_content, encoding="utf-8")
    completed_path.write_text(completed_content, encoding="utf-8")

    phase_overview, phases = parse_tasks_file(tasks_path)
    session = parse_session_file(session_path)

    return LoadedProject(
        project_context=pc,
        phases=phases,
        phase_overview=phase_overview,
        session=session,
    )


def _build_clean_loaded_project(tmp_path: Path) -> LoadedProject:
    """Build a LoadedProject from the canonical fixture files."""
    pc = _build_project_context(tmp_path)

    tasks_path = Path(pc.tasks_path)
    session_path = Path(pc.sessionstate_path)
    completed_path = Path(pc.tasks_completed_path)

    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text(
        TASKS_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    session_path.write_text(
        SESSION_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    if COMPLETED_FIXTURE.exists():
        completed_path.write_text(
            COMPLETED_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
        )
    else:
        completed_path.write_text(
            "# Completed Tasks Log\n\n---\n", encoding="utf-8"
        )

    phase_overview, phases = parse_tasks_file(tasks_path)
    session = parse_session_file(session_path)

    return LoadedProject(
        project_context=pc,
        phases=phases,
        phase_overview=phase_overview,
        session=session,
    )


# ── Helper: minimal valid TASKS.md for testing ──────────────────────────────

CLEAN_TASKS = """\
# Test Project — Phase Task List

> Preamble.

---

## Phase structure

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1 — Alpha** | Alpha tasks | Pending |

---

# Phase 1 — Alpha

**Status:** Pending

---

## Phase 1 tasks

### FA-T01 · First task

**Status:** Pending
**Complexity:** low
**What:** A simple task.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/main.py
**Reviewer:** Skip
**Done when:** - Everything works.

### FA-T02 · Second task

**Status:** Pending
**Complexity:** low
**What:** Another task.
**Prerequisite:** None.
**Hard deps:** FA-T01
**Files:** src/utils.py
**Reviewer:** Skip
**Done when:** - All tests pass.

---

### Dependency graph

```
FA-T01
  └── FA-T02
```

---
"""

CLEAN_SESSION = """\
*Last updated: 2026-05-01T10:00*

---

## Active phase

Phase 1 — Alpha — in progress.
Spec: `TASKS.md`

---

## Completed tasks

| Task | Description | Commit message |
|------|-------------|----------------|
| FA-T01 | First task | initial commit |

---

## Active task

### FA-T02 · Second task

**Status:** Pending
**Complexity:** low
**What:** Another task.
**Prerequisite:** None.
**Hard deps:** FA-T01
**Files:** src/utils.py
**Reviewer:** Skip
**Done when:** - All tests pass.

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|------|-------------|-----------|------------|----------|
| FA-T01 | First task | — | low | Skip |

---

## Out of scope

- Nothing.
"""

CLEAN_COMPLETED = """\
# Completed Tasks Log

---

## Phase 1 — Alpha

| Task | Description | Complexity | Commit | Notes |
|------|-------------|------------|--------|-------|
| FA-T01 | First task | low | abc123 | Initial implementation |
"""


# ── TASKS.md missing-fields fixture ─────────────────────────────────────────

TASKS_WITH_MISSING_FIELDS = """\
# Test Project — Phase Task List

---

## Phase structure

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1 — Alpha** | Alpha tasks | Pending |

---

# Phase 1 — Alpha

**Status:** Pending

---

## Phase 1 tasks

### FA-T01 · Task with missing What

**Status:** Pending
**Complexity:** low
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/main.py
**Reviewer:** Skip
**Done when:** - Works.

### FA-T02 · Task with missing Prerequisite and Reviewer

**Status:** Pending
**Complexity:** low
**What:** Has a description.
**Hard deps:** None
**Files:** src/utils.py
**Done when:** - Works.

---

### Dependency graph

```
FA-T01
  └── FA-T02
```

---
"""


# ── TASKS-COMPLETED.md with VC-10 rows fixture ──────────────────────────────

COMPLETED_WITH_UNKNOWN_IDS = """\
# Completed Tasks Log

---

## Phase 1 — Alpha

| Task | Description | Complexity | Commit | Notes |
|------|-------------|------------|--------|-------|
| FA-T01 | First task | low | abc123 | Done |
| UNKNOWN-T99 | Unknown task | medium | def456 | Missing |
| FA-T02 | Second task | low | ghi789 | Done |
| GHOST-X00 | Ghost task | high | jkl012 | Non-existent |

## Phase 2 — Empty Beta

| Task | Description | Complexity | Commit | Notes |
|------|-------------|------------|--------|-------|

## Phase 3 — Gamma

| Task | Description | Complexity | Commit | Notes |
|------|-------------|------------|--------|-------|
| FA-T01 | Already in log | low | mno345 | Duplicate |
"""


# ── SESSIONSTATE.md with unknown active task fixture ────────────────────────

SESSION_WITH_UNKNOWN_ACTIVE = """\
*Last updated: 2026-04-15T14:30*

---

## Active phase

Phase 1 — Alpha — in progress.
Spec: `TASKS.md`

---

## Completed tasks

| Task | Description | Commit message |
|------|-------------|----------------|
| FA-T01 | First task | initial commit |

---

## Active task

### UNKNOWN-T99 · Nonexistent task

**Status:** Pending
**Complexity:** low
**What:** This task does not exist in TASKS.md.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/ghost.py
**Reviewer:** Skip
**Done when:** - Never.

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|------|-------------|-----------|------------|----------|
| FA-T01 | First task | — | low | Skip |

---

## Out of scope

- Nothing.
"""


# ── SESSIONSTATE.md with legacy timestamp fixture ───────────────────────────

SESSION_WITH_LEGACY_TIMESTAMP = """\
*Last updated: 2026-04-15*

---

## Active phase

Phase 1 — Alpha — in progress.
Spec: `TASKS.md`

---

## Completed tasks

| Task | Description | Commit message |
|------|-------------|----------------|
| FA-T01 | First task | initial commit |

---

## Active task

### FA-T02 · Second task

**Status:** Pending
**Complexity:** low
**What:** Another task.
**Prerequisite:** None.
**Hard deps:** FA-T01
**Files:** src/utils.py
**Reviewer:** Skip
**Done when:** - All tests pass.

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|------|-------------|-----------|------------|----------|
| FA-T01 | First task | — | low | Skip |

---

## Out of scope

- Nothing.
"""


# ── TASKS.md with duplicate IDs fixture ─────────────────────────────────────

TASKS_WITH_DUPLICATES = """\
# Test Project — Phase Task List

---

## Phase structure

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1 — Alpha** | Alpha tasks | Pending |

---

# Phase 1 — Alpha

**Status:** Pending

---

## Phase 1 tasks

### FA-T01 · First occurrence

**Status:** Pending
**Complexity:** low
**What:** The first FA-T01.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/a.py
**Reviewer:** Skip
**Done when:** - Done.

### FA-T01 · Second occurrence (duplicate)

**Status:** Pending
**Complexity:** low
**What:** The second FA-T01 — deliberate duplicate.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/b.py
**Reviewer:** Skip
**Done when:** - Done.

---

### Dependency graph

```
FA-T01
```

---
"""


# ── Tests ────────────────────────────────────────────────────────────────────


class TestRepairTasks:
    """``repair()`` with ``tasks=True`` repairs TASKS.md."""

    def test_repair_fills_missing_fields(self, tmp_path: Path):
        """Missing required fields are filled with safe defaults."""
        ctx = _build_loaded_project(
            tmp_path,
            tasks_content=TASKS_WITH_MISSING_FIELDS,
            session_content=CLEAN_SESSION,
            completed_content=CLEAN_COMPLETED,
        )

        result = repair(ctx, tasks=True, session=False, completed=False)

        # ── Assert PendingWrite exists for TASKS.md ─────────────────────
        assert len(result) == 1, (
            f"Expected 1 PendingWrite for TASKS.md repair, got {len(result)}"
        )

        pw = result[0]
        assert pw.target_file == "TASKS.md"

        # ── Verify shadow file was written ──────────────────────────────
        shadow = Path(pw.shadow_path)
        assert shadow.exists(), f"Shadow file not written: {shadow}"

        content = shadow.read_text(encoding="utf-8")

        # ── FA-T01 was missing **What:** — should be filled with "" ────
        assert "**What:** " in content, (
            "FA-T01 should have **What:** field filled"
        )

        # ── FA-T02 was missing **Prerequisite:** and **Reviewer:** ──────
        assert "**Prerequisite:** None." in content, (
            "FA-T02 should have **Prerequisite:** filled with 'None.'"
        )
        assert "**Reviewer:** Skip" in content, (
            "FA-T02 should have **Reviewer:** filled with 'Skip'"
        )

        # ── Summary lines contain [defaulted] labels ────────────────────
        summary = " ".join(pw.summary_lines)
        assert "[defaulted]" in summary, (
            f"Expected [defaulted] label in summary, got: {summary}"
        )

    def test_repair_duplicate_ids(self, tmp_path: Path):
        """Duplicate task IDs are auto-renamed to <id>-duplicate."""
        ctx = _build_loaded_project(
            tmp_path,
            tasks_content=TASKS_WITH_DUPLICATES,
            session_content=CLEAN_SESSION,
            completed_content=CLEAN_COMPLETED,
        )

        result = repair(ctx, tasks=True, session=False, completed=False)

        # ── Assert PendingWrite exists ──────────────────────────────────
        assert len(result) == 1, (
            f"Expected 1 PendingWrite, got {len(result)}"
        )

        pw = result[0]
        assert pw.target_file == "TASKS.md"

        shadow = Path(pw.shadow_path)
        content = shadow.read_text(encoding="utf-8")

        # ── First occurrence should keep original ID ────────────────────
        assert "### FA-T01 · First occurrence" in content, (
            "First FA-T01 should keep its original ID"
        )
        # Second occurrence should be renamed
        assert "### FA-T01-duplicate · Second occurrence" in content, (
            "Second FA-T01 should be renamed to FA-T01-duplicate"
        )

        # ── Summary contains [duplicate] label ──────────────────────────
        summary = " ".join(pw.summary_lines)
        assert "[duplicate]" in summary, (
            f"Expected [duplicate] label in summary, got: {summary}"
        )


class TestRepairSession:
    """``repair()`` with ``session=True`` repairs SESSIONSTATE.md."""

    def test_repair_normalizes_session_task_id(self, tmp_path: Path):
        """Active task ID not in TASKS.md is cleared to [none]."""
        ctx = _build_loaded_project(
            tmp_path,
            tasks_content=CLEAN_TASKS,
            session_content=SESSION_WITH_UNKNOWN_ACTIVE,
            completed_content=CLEAN_COMPLETED,
        )

        result = repair(ctx, tasks=False, session=True, completed=False)

        # ── Assert PendingWrite exists for SESSIONSTATE.md ──────────────
        assert len(result) == 1, (
            f"Expected 1 PendingWrite, got {len(result)}"
        )

        pw = result[0]
        assert pw.target_file == "SESSIONSTATE.md"

        shadow = Path(pw.shadow_path)
        assert shadow.exists(), f"Shadow file not written: {shadow}"

        content = shadow.read_text(encoding="utf-8")

        # ── Active task should be [none] ────────────────────────────────
        assert "[none]" in content, (
            "Active task should be set to [none] after repair"
        )
        assert "UNKNOWN-T99" not in content, (
            "UNKNOWN-T99 should not appear in repaired SESSIONSTATE.md"
        )

        # ── Summary contains [removed] label ────────────────────────────
        summary = " ".join(pw.summary_lines)
        assert "[removed]" in summary, (
            f"Expected [removed] label in summary, got: {summary}"
        )

    def test_repair_legacy_timestamp(self, tmp_path: Path):
        """Legacy date-only timestamp is upgraded to YYYY-MM-DDTHH:MM."""
        ctx = _build_loaded_project(
            tmp_path,
            tasks_content=CLEAN_TASKS,
            session_content=SESSION_WITH_LEGACY_TIMESTAMP,
            completed_content=CLEAN_COMPLETED,
        )

        result = repair(ctx, tasks=False, session=True, completed=False)

        assert len(result) == 1, (
            f"Expected 1 PendingWrite, got {len(result)}"
        )

        shadow = Path(result[0].shadow_path)
        content = shadow.read_text(encoding="utf-8")

        # ── Legacy timestamp upgraded ───────────────────────────────────
        assert "*Last updated: 2026-04-15T00:00*" in content, (
            "Legacy timestamp should be upgraded to include T00:00"
        )
        # The old date-only format should be gone
        assert "*Last updated: 2026-04-15*\n" not in content, (
            "Old date-only timestamp should not remain"
        )

        # ── Summary contains [normalized] label ─────────────────────────
        summary = " ".join(result[0].summary_lines)
        assert "[normalized]" in summary, (
            f"Expected [normalized] label in summary, got: {summary}"
        )


class TestRepairCompleted:
    """``repair()`` with ``completed=True`` repairs TASKS-COMPLETED.md."""

    def test_repair_removes_vc10_rows(self, tmp_path: Path):
        """Rows with unknown task IDs are removed; empty sections removed."""
        ctx = _build_loaded_project(
            tmp_path,
            tasks_content=CLEAN_TASKS,
            session_content=CLEAN_SESSION,
            completed_content=COMPLETED_WITH_UNKNOWN_IDS,
        )

        result = repair(ctx, tasks=False, session=False, completed=True)

        # ── Assert PendingWrite exists for TASKS-COMPLETED.md ───────────
        assert len(result) == 1, (
            f"Expected 1 PendingWrite, got {len(result)}"
        )

        pw = result[0]
        assert pw.target_file == "TASKS-COMPLETED.md"

        shadow = Path(pw.shadow_path)
        assert shadow.exists(), f"Shadow file not written: {shadow}"

        content = shadow.read_text(encoding="utf-8")

        # ── Unknown rows removed ────────────────────────────────────────
        assert "UNKNOWN-T99" not in content, (
            "UNKNOWN-T99 row should have been removed"
        )
        assert "GHOST-X00" not in content, (
            "GHOST-X00 row should have been removed"
        )

        # ── Known rows preserved ────────────────────────────────────────
        assert "FA-T01" in content, (
            "FA-T01 row should be preserved"
        )
        assert "FA-T02" in content, (
            "FA-T02 row should be preserved"
        )

        # ── Empty phase sections removed ────────────────────────────────
        assert "Phase 2 — Empty Beta" not in content, (
            "Empty phase section should have been removed"
        )

        # ── Non-empty phase sections preserved ──────────────────────────
        assert "Phase 1 — Alpha" in content, (
            "Non-empty Phase 1 section should be preserved"
        )
        assert "Phase 3 — Gamma" in content, (
            "Phase 3 section (with FA-T01 row) should be preserved"
        )

        # ── Summary contains [removed] labels ───────────────────────────
        summary = " ".join(pw.summary_lines)
        assert "[removed]" in summary, (
            f"Expected [removed] label in summary, got: {summary}"
        )


class TestRepairAll:
    """``repair()`` repairs all three files when no flags are set."""

    def test_repair_all_flags_false_defaults_to_all(self, tmp_path: Path):
        """All three files are repaired when no flags are set."""
        ctx = _build_loaded_project(
            tmp_path,
            tasks_content=TASKS_WITH_MISSING_FIELDS,
            session_content=SESSION_WITH_LEGACY_TIMESTAMP,
            completed_content=COMPLETED_WITH_UNKNOWN_IDS,
        )

        result = repair(ctx, tasks=False, session=False, completed=False)

        # ── Should get 3 PendingWrites ──────────────────────────────────
        assert len(result) == 3, (
            f"Expected 3 PendingWrites for full repair, got {len(result)}"
        )

        target_files = {pw.target_file for pw in result}
        assert target_files == {"TASKS.md", "SESSIONSTATE.md",
                                "TASKS-COMPLETED.md"}, (
            f"Expected all three target files, got: {target_files}"
        )

        # ── All summaries have labels ───────────────────────────────────
        for pw in result:
            summary = " ".join(pw.summary_lines)
            assert any(label in summary for label in
                       ("[defaulted]", "[duplicate]", "[normalized]",
                        "[removed]")), (
                f"Summary missing expected label: {summary}"
            )

    def test_repair_idempotent_clean(self, tmp_path: Path):
        """Running repair twice on a clean project produces zero changes."""
        ctx = _build_clean_loaded_project(tmp_path)

        result = repair(ctx, tasks=True, session=True, completed=True)

        # ── Clean project should have zero changes ──────────────────────
        assert len(result) == 0, (
            f"Expected 0 PendingWrites for clean project, got {len(result)}"
        )

        # ── Second run should also produce zero changes ─────────────────
        result2 = repair(ctx, tasks=True, session=True, completed=True)
        assert len(result2) == 0, (
            f"Expected 0 PendingWrites on second repair, got {len(result2)}"
        )

    def test_repair_status_normalization(self, tmp_path: Path):
        """Malformed status tokens are normalised to canonical form."""

        tasks_with_bad_status = """\
# Test Project — Phase Task List

---

## Phase structure

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1 — Alpha** | Alpha tasks | Pending |

---

# Phase 1 — Alpha

**Status:** Pending

---

## Phase 1 tasks

### FA-T01 · Task with complete status

**Status:** Complete
**Complexity:** low
**What:** Uses 'Complete' instead of '✅ Complete'.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/a.py
**Reviewer:** Skip
**Done when:** - Done.

### FA-T02 · Task with active status

**Status:** Active
**Complexity:** low
**What:** Uses 'Active' instead of '**Active**'.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/b.py
**Reviewer:** Skip
**Done when:** - Done.

---

### Dependency graph

```
FA-T01
  └── FA-T02
```

---
"""

        ctx = _build_loaded_project(
            tmp_path,
            tasks_content=tasks_with_bad_status,
            session_content=CLEAN_SESSION,
            completed_content=CLEAN_COMPLETED,
        )

        result = repair(ctx, tasks=True, session=False, completed=False)

        # ── Should have changes ─────────────────────────────────────────
        assert len(result) == 1, (
            f"Expected 1 PendingWrite for status normalisation, "
            f"got {len(result)}"
        )

        pw = result[0]
        shadow = Path(pw.shadow_path)
        content = shadow.read_text(encoding="utf-8")

        # ── Status tokens should be normalised ──────────────────────────
        assert "**Status:** ✅ Complete" in content, (
            "FA-T01 status should be normalised to '✅ Complete'"
        )
        assert "**Status:** **Active**" in content, (
            "FA-T02 status should be normalised to '**Active**'"
        )

        # ── Old malformed tokens should be gone ─────────────────────────
        assert "**Status:** Complete\n" not in content, (
            "Old 'Complete' status should not remain"
        )
        assert "**Status:** Active\n" not in content, (
            "Old 'Active' status should not remain"
        )


# ── HELP_TEXT tests ─────────────────────────────────────────────────────────


class TestHELP_TEXT:
    """``HELP_TEXT`` is a module-level string constant."""

    def test_help_text_exists(self):
        """HELP_TEXT is a non-empty string."""
        assert isinstance(HELP_TEXT, str)
        assert len(HELP_TEXT) > 0
        assert "repair" in HELP_TEXT.lower()
        assert "Preconditions" in HELP_TEXT
        assert "Examples" in HELP_TEXT
