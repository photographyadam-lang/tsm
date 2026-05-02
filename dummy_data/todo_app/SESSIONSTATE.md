*Last updated: 2026-05-01T14:00*

---

## Active phase

Phase 1 — Core Backend & Data Layer — in progress.
Spec: `TASKS.md`

---

## Completed tasks

| Task | Description | Commit message |
|------|-------------|----------------|
| T01-S01 | Initial project scaffold with Poetry | scaffold: init project structure |
| T01-S02 | Data model definitions (Task, Priority, Category) | feat: add data models |
| T01-S03 | JSON persistence layer (read/write/cache) | feat: implement JSON store |

---

## Active task

### P2-T01 · Build CLI command parser

**Status:** **Active**
**Complexity:** medium
**What:** Implement an argparse-based command dispatcher that handles all user-facing commands:
add, list, done, delete, edit, search, stats. Each command maps to a service-layer method.
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

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|------|-------------|-----------|------------|----------|
| P2-T02 | Implement interactive TUI with Rich menus | P1-T03 | high | Skip |
| P2-T03 | Add search, filter, and sort for tasks | P2-T01 | medium | Skip |
| P3-T01 | Add recurring tasks and reminders engine | P2-T03 | high | Skip |
| P3-T02 | Add CSV/Markdown export/import | P2-T03 | medium | Skip |
| P3-T03 | Add statistics dashboard and productivity report | P2-T03 | low | Skip |

---

## Out of scope

- GUI/web interface
- Cloud sync or multi-device support
- Natural-language task parsing
