*Last updated: 2026-04-29T00:00*

---

## Active phase
Phase 4 — Commands — in progress.
Spec: `SPECIFICATION-task-session-manager-v1.4.md`

---

## Completed tasks

| Task | Description | Commit message |
|---|---|---|

---

## Active task

### P4-T01 · commands/advance.py

**Status:** Pending
**Complexity:** high
**What:** Implement tsm/commands/advance.py with advance(ctx: LoadedProject, commit_message: str = "") -> list[PendingWrite]. Precondition: ctx.session.active_task is not None; abort with clear error if not. Next task promotion logic (§7.3): from ctx.session.up_next, select the first Task whose hard_deps are all met — meaning each dep ID has status complete in ctx.phases, OR equals the task just being advanced. If no task is ready, set active_task to None and emit the warning from §7.3. Build 3 PendingWrite objects: (1) SESSIONSTATE.md — append advanced task to completed list, set new active_task_raw to promoted task's raw_block or [none], remove promoted task from up_next, update last_updated; render via session_writer; (2) TASKS.md — call update_task_status on live file content; (3) TASKS-COMPLETED.md — call append_task_row. Also implement confirm_summary(pending_writes) -> str for the §7.3 confirm output. Add HELP_TEXT static string constant with full advance help text matching the §7.8 format (Preconditions, Writes, Example sections). Implements §7.3.
**Prerequisite:** All Phase 3 tasks complete.
**Hard deps:** P3-T03, P3-T04, P3-T05
**Files:** tsm/commands/advance.py, tests/commands/test_advance.py
**Reviewer:** Skip
**Key constraints:**
- advance() must return PendingWrite objects — it must not call shadow.apply() itself; the caller (CLI or TUI) applies after confirmation
- The "just-advanced task counts as complete for dep resolution" logic lives exclusively in advance.py — not in the writer or parser
- HELP_TEXT must be a module-level string constant, not a function or docstring
**Done when:**
- test_advance_happy_path passes
- test_advance_no_active_task passes
- test_advance_dep_not_met passes
- test_advance_with_commit_message passes
- test_advance_last_task_in_phase passes

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|---|---|---|---|---|
| P4-T02 | commands/init_phase.py | P3-T04 | medium | Skip |
| P4-T03 | commands/complete_phase.py | P3-T03, P3-T04, P3-T05 | medium | Skip |
| P4-T04 | commands/vibe_check.py | P2-T02, P2-T03 | medium | Skip |
| P4-T05 | commands/status.py and commands/undo.py | P3-T02, P3-T04 | low | Skip |
| P4-T06 | commands/help.py | P4-T01, P4-T02, P4-T03, P4-T04, P4-T05 | low | Skip |
| P4-T07 | commands/new_project.py | P2-T02, P2-T03 | medium | Skip |

---

## Out of scope

- Phase 6 TUI until all CLI commands are verified working end-to-end (§14 CLI-first constraint)
- Network calls, LLM calls, telemetry of any kind (§14)
- General Markdown parser libraries — line iterator state machine only (§9.1)
- Multi-level undo — single-level only in v1.0 (§14)
- Dependency graph edge validation in vibe-check — display/preservation only in v1.0 (§14)
- --output json on read-only commands — deferred to v2 (§2.2)