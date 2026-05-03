*Last updated: 2026-05-03T14:53*

---

## Active phase

Phase 7 — Management & Integrity — in progress.
Spec: `SPECIFICATION-task-session-manager-v1.6.md`

---

## Completed tasks

| Task | Description | Commit message |
|------|-------------|----------------|
| P7-T01 | deps.py — dependency engine | advanced |
| P7-T02 | commands/deps.py — deps command | advanced |
| P7-T03a | tasks_writer.py — block insert, remove, and field replacement | advanced |
| P7-T03b | tasks_writer.py — block reorder operations | advanced |
| P7-T04 | commands/phase.py — phase CRUD commands | advanced |
| P7-T05 | commands/task.py — task CRUD commands | advanced |
| P7-T06 | ui/task_form.py — TaskFormOverlay widget | advanced |
| P7-T07 | commands/repair.py | advanced |
| P7-T08 | commands/sync.py | advanced |

---

## Active task

[none]

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|------|-------------|-----------|------------|----------|

---

## Out of scope

- Network calls outside import_cmd.py — no other module may make network calls (§14)
- General Markdown parser libraries — line iterator state machine only (§9.1)
- Multi-level undo — single-level only in v1.0 (§14)
- Dependency graph ASCII art regeneration — preserved verbatim, never rewritten (§14)
- --output json on read-only commands — deferred to v2 (§2.2)
- TUI-only code paths — all business logic stays in the command layer (§14)
- Graphical dependency visualisation (SVG/HTML) — ASCII only in v1 (§14)
