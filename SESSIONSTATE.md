*Last updated: 2026-05-01T15:04*

---

## Active phase

Phase 3 — Advanced Features & Polish
Spec: `TASKS.md`

---

## Completed tasks

| Task | Description | Commit message |
|------|-------------|----------------|

---

## Active task

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

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|------|-------------|-----------|------------|----------|
| P3-T02 | Add CSV and Markdown export/import | P2-T03 | medium | Skip |
| P3-T03 | Add statistics dashboard and productivity report | P2-T03 | low | Skip |

---

## Out of scope

- [List anything explicitly out of scope]
