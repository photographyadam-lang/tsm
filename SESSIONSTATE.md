*Last updated: 2026-05-02T16:43*

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

---

## Active task

### P7-T04 · commands/phase.py — phase CRUD commands

**Status:** Pending
**Complexity:** medium
**What:** Implement tsm/commands/phase.py with four functions: phase_add(ctx, name, after_phase_id, status) -> list[PendingWrite]; phase_edit(ctx, phase_id, name, status) -> list[PendingWrite]; phase_move(ctx, phase_id, after_phase_id) -> list[PendingWrite]; phase_remove(ctx, phase_id, force) -> list[PendingWrite]. Each function: (1) applies the intended transformation to an in-memory copy of ctx.phases to produce the proposed state; (2) calls check_deps() on the proposed state; (3) for remove without force, aborts if check_deps returns errors; (4) builds PendingWrite for TASKS.md using structural writer functions from P7-T03a/T03b. phase_add creates a new phase block and updates the Phase structure table. phase_edit updates heading and/or Phase structure table row. phase_move calls reorder_phase_blocks. phase_remove calls remove_phase_block; with --force proceeds despite dep errors and lists dangling deps in confirm summary. Add HELP_TEXT. Wire into __main__.py. Implements §15.2.
**Prerequisite:** P7-T03b complete.
**Hard deps:** P7-T03b
**Files:** tsm/commands/phase.py, tests/commands/test_phase.py
**Reviewer:** Skip
**Done when:**
- test_phase_add_appends_phase_block passes
- test_phase_add_updates_phase_structure_table passes
- test_phase_edit_name_updates_heading_and_table passes
- test_phase_move_reorders_h1_blocks passes
- test_phase_remove_blocked_by_deps passes
- test_phase_remove_force_cascade passes

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|------|-------------|-----------|------------|----------|
| P7-T05 | commands/task.py — task CRUD commands | P7-T03 | unset |  |
| P7-T06 | ui/task_form.py — TaskFormOverlay widget | P6-T05 | unset |  |
| P7-T07 | commands/repair.py | P7-T01, P3-T03, P3-T04, P3-T05 | medium | Skip |
| P7-T08 | commands/sync.py | P7-T01, P3-T03, P3-T04, P3-T05 | medium | Skip |

---

## Out of scope

- Network calls outside import_cmd.py — no other module may make network calls (§14)
- General Markdown parser libraries — line iterator state machine only (§9.1)
- Multi-level undo — single-level only in v1.0 (§14)
- Dependency graph ASCII art regeneration — preserved verbatim, never rewritten (§14)
- --output json on read-only commands — deferred to v2 (§2.2)
- TUI-only code paths — all business logic stays in the command layer (§14)
- Graphical dependency visualisation (SVG/HTML) — ASCII only in v1 (§14)
