# TodoFlow — Phase Task List

> Tasks are ordered by dependency. Do not start a task until all prerequisites are met.

---

## Phase structure

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1 — Core Backend & Data Layer** | Data models, persistence, CRUD operations | ✅ Complete |
| **Phase 2 — CLI Interface & Interaction** | Command parser, Rich TUI, search/filter/sort | **Active** |
| **Phase 3 — Advanced Features & Polish** | Recurring tasks, export/import, stats dashboard | Pending |

---

# Phase 1 — Core Backend & Data Layer

**Status:** ✅ Complete

Establish the foundation: data model definitions, JSON file persistence, and all CRUD operations. Every subsequent phase depends on this layer.

---

## Phase 1 tasks

### P1-T01 · Set up project structure and data models

**Status:** ✅ Complete
**Complexity:** low
**What:** Scaffold the Poetry project, define core data classes (Task, Priority, Category, DueDate) with validation, and set up the test framework.
**Prerequisite:** None.
**Hard deps:** None
**Files:** `pyproject.toml`, `src/__init__.py`, `src/models.py`, `tests/`
**Reviewer:** Skip
**Done when:**
- `poetry install` runs without errors
- Task dataclass validates title (non-empty), priority (low/med/high), and status (pending/active/done)
- Unit tests pass for all model validations

### P1-T02 · Implement file-based JSON persistence

**Status:** ✅ Complete
**Complexity:** medium
**What:** Build a JSON file store with atomic writes, in-memory read cache, and graceful recovery from corrupted files. Supports load/save/backup operations.
**Prerequisite:** P1-T01 complete.
**Hard deps:** P1-T01
**Files:** `src/store.py`, `tests/test_store.py`
**Reviewer:** Skip
**Key constraints:**
- Writes must be atomic (write to temp file, then rename)
- Corrupt JSON on load must fall back to latest valid backup
- Must handle concurrent-write edge cases gracefully
**Done when:**
- Store round-trips data correctly through JSON
- Simulated crash during write does not lose committed data
- Backup file is created on every successful write

### P1-T03 · Implement CRUD operations

**Status:** ✅ Complete
**Complexity:** medium
**What:** Expose create, read, update, delete, list, and mark-done operations through a TaskManager service class. All operations validate input and persist changes atomically.
**Prerequisite:** P1-T02 complete.
**Hard deps:** P1-T02
**Files:** `src/manager.py`, `tests/test_manager.py`
**Reviewer:** Skip
**Key constraints:**
- Must reject tasks with empty titles
- Deleting a non-existent task must raise TaskNotFoundError
- Listing supports optional status/priority filters
**Done when:**
- All CRUD integration tests pass against a temp JSON store
- Error cases (missing task, bad data) produce typed exceptions
- Manager methods are fully documented

---

### Dependency graph

```
P1-T01
  └── P1-T02
        └── P1-T03
```

---

# Phase 2 — CLI Interface & Interaction

**Status:** **Active**

Build the user-facing interface: an argparse command parser for fast CLI workflows, a Rich-based TUI for interactive exploration, and search/filter/sort for task discovery.

---

## Phase 2 tasks

### P2-T01 · Build CLI command parser

**Status:** **Active**
**Complexity:** medium
**What:** Implement an argparse-based command dispatcher that handles all user-facing commands: add, list, done, delete, edit, search, stats. Each command maps to a service-layer method.
**Prerequisite:** Phase 1 complete.
**Hard deps:** P1-T03
**Files:** `src/cli/parser.py`(new), `src/cli/commands.py`(new), `src/cli/__init__.py`(new)
**Reviewer:** Skip
**Key constraints:**
- Must validate all argument types before invoking service layer
- Help text must be auto-generated from command definitions
**Done when:**
- `todoflow add "Buy milk" --priority high` creates a task
- `todoflow list` prints a formatted table of all tasks
- `todoflow done 3` marks task #3 as completed
- Unknown commands print a useful error and exit code 1

### P2-T02 · Implement interactive TUI with Rich menus

**Status:** Pending
**Complexity:** high
**What:** Build an interactive terminal UI using the Rich library. Displays a live task table with colour-coded priorities, keyboard shortcuts for common actions, and a detail panel for the selected task.
**Prerequisite:** P2-T01 complete.
**Hard deps:** P2-T01
**Files:** `src/tui/app.py`(new), `src/tui/panels.py`(new), `src/tui/widgets.py`(new)
**Reviewer:** Skip
**Key constraints:**
- All TUI actions must flow through the same TaskManager as CLI commands
- Keyboard shortcuts must be documented in a help overlay
- Must handle terminal resize events gracefully
**Done when:**
- TUI starts with `todoflow ui` and shows all tasks in a sortable table
- Arrow keys navigate, Enter opens details, `d` marks done, `q` quits
- Priority colouring works (red=high, yellow=med, green=low)

### P2-T03 · Add search, filter, and sort for tasks

**Status:** Pending
**Complexity:** medium
**What:** Extend both CLI and TUI with powerful filtering: by status (all/pending/active/done), priority, category, due-date range, and free-text search across titles. Results are sortable by any column.
**Prerequisite:** P2-T01 complete.
**Hard deps:** P2-T01
**Files:** `src/filters.py`(new), `tests/test_filters.py`
**Reviewer:** Skip
**Done when:**
- `todoflow list --status pending --priority high` returns only matching tasks
- `todoflow search "groceries"` finds tasks with "groceries" in title or notes
- TUI filter bar accepts typed queries and updates results in real time
- Sort order persists across TUI sessions

---

### Dependency graph

```
P1-T03 ──► P2-T01 ──► P2-T02
P2-T01 ──► P2-T03
```

---

# Phase 3 — Advanced Features & Polish

**Status:** Pending

Add power-user features: recurring tasks with smart scheduling, data portability via export/import, and a statistics dashboard for productivity insights.

---

## Phase 3 tasks

### P3-T01 · Add recurring tasks and reminders engine

**Status:** Pending
**Complexity:** high
**What:** Implement a recurring-task scheduler that supports cron-like frequency expressions (daily, weekly mon, monthly 15th). When a recurring task is marked done, the engine computes the next due date and recreates it automatically.
**Prerequisite:** Phase 2 complete.
**Hard deps:** P2-T03
**Files:** `src/scheduler.py`(new), `tests/test_scheduler.py`
**Reviewer:** Skip
**Key constraints:**
- Must handle edge cases: Feb 29 on non-leap years, monthly on 31st
- Reminders fire when the app starts and a task is past due
- Recurrence expression must be human-readable and validated on creation
**Done when:**
- A `daily` task re-creates itself 24 h after being completed
- A `weekly mon` task always schedules for the next Monday
- Past-due recurring tasks show ⏰ in the TUI

### P3-T02 · Add CSV and Markdown export/import

**Status:** Pending
**Complexity:** medium
**What:** Export all tasks to CSV or Markdown format for sharing or backup. Import from CSV to bulk-load tasks. Preserve all fields including priority, category, and due dates.
**Prerequisite:** Phase 2 complete.
**Hard deps:** P2-T03
**Files:** `src/export.py`(new), `tests/test_export.py`
**Reviewer:** Skip
**Done when:**
- `todoflow export --format csv` writes tasks.csv with correct headers
- `todoflow export --format markdown` writes tasks.md as a readable table
- `todoflow import tasks.csv` loads all rows as new tasks
- Import validates each row and skips malformed entries with a warning

### P3-T03 · Add statistics dashboard and productivity report

**Status:** Pending
**Complexity:** low
**What:** Build a statistics module that computes aggregate metrics: tasks completed this week/month, average completion time, busiest day, completion rate by category. Display via a formatted CLI report and a TUI dashboard panel.
**Prerequisite:** Phase 2 complete.
**Hard deps:** P2-T03
**Files:** `src/stats.py`(new), `tests/test_stats.py`
**Reviewer:** Skip
**Done when:**
- `todoflow stats` prints a formatted report with all metrics
- TUI has a `Stats` tab showing charts (sparklines) for weekly trends
- Metrics are computed from the full task history, not just active tasks

---

### Dependency graph

```
P2-T03 ──► P3-T01
P2-T03 ──► P3-T02
P2-T03 ──► P3-T03
```

---
