*Last updated: 2026-05-03T14:11*

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

---

## Active task

### P7-T07 · commands/repair.py

**Status:** Pending
**Complexity:** medium
**What:** Implement tsm/commands/repair.py with repair(ctx: LoadedProject, tasks: bool, session: bool, completed: bool) -> list[PendingWrite]. If all three flags False, set all to True (repair everything). TASKS.md repairs per §15.4: fill missing required fields with defaults, normalize malformed status tokens, detect duplicate IDs and rename second occurrence to <id>-duplicate automatically (no interactive prompt — rename shown in confirm summary), skip unparseable blocks and report them. SESSIONSTATE.md repairs: validate active task ID against TASKS.md, rebuild up_next if mismatched, upgrade legacy timestamp. TASKS-COMPLETED.md repairs: remove rows with unknown task IDs, remove empty phase sections. Every change listed in PendingWrite.summary_lines with [defaulted]/[normalized]/[removed]/[skipped] label and before/after values. Running repair twice on a clean file produces zero changes. Add HELP_TEXT. Implements §15.4.
**Prerequisite:** P7-T01 complete.
**Hard deps:** P7-T01, P3-T03, P3-T04, P3-T05
**Files:** tsm/commands/repair.py, tests/commands/test_repair.py
**Reviewer:** Skip
**Key constraints:**
- repair must never silently delete content — every change appears in the confirm summary with before/after
- Duplicate ID rename is automatic (second occurrence → <id>-duplicate) — no interactive prompting during staging
- Running repair on an already-clean project must produce zero changes and exit 0 (idempotency)
**Done when:**
- test_repair_fills_missing_fields passes
- test_repair_removes_vc10_rows passes
- test_repair_normalizes_session_task_id passes
- test_repair_skips_unparseable_content passes
- Confirm summary groups changes by file and labels each change correctly
- Running repair twice on an already-clean file produces zero changes (idempotency test)

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|------|-------------|-----------|------------|----------|
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
