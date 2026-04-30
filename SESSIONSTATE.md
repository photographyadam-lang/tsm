*Last updated: 2026-04-29T00:00*

---

## Active phase
Phase 5 — CLI Entry Point — in progress.
Spec: `SPECIFICATION-task-session-manager-v1.4.md`

---

## Completed tasks

| Task | Description | Commit message |
|---|---|---|

---

## Active task

### P5-T01 · __main__.py — CLI wiring, load_project bootstrap, --yes flag, exit codes

**Status:** Pending
**Complexity:** medium
**What:** Implement tsm/__main__.py with main() entry point and load_project(root: Path) -> LoadedProject factory function per §5.6. Parse --yes flag from argv before dispatch — pass yes=True to confirm_prompt() for write commands when present; emit "Warning: --yes has no effect on <command>." if passed to a read-only command. Implement the §10.1 exit code contract: wrap all dispatch logic in try/except; map PreconditionError → exit(1), ParseError → exit(2), WriteError → exit(3), success → exit(0); no sys.exit() call appears anywhere else in the codebase. Route all 8 subcommands. help and new-project execute without project root discovery. All other commands: call find_project_root(Path.cwd()), print the §3.2 error and exit(1) if None, call ensure_tsm_dir(root) to get ProjectContext, call load_project(root) to parse both files, dispatch to command module. Handle --help flag identically to tsm help. For write commands (advance, init_phase, complete_phase): call command function → get PendingWrite list → call shadow.confirm_prompt(pending_writes, yes=yes_flag) → if True, call shadow.apply. For read-only commands (status, vibe_check): call and print. Handle unknown subcommand: print "Unknown command: <x>" and exit(1). Implements §3.1, §5.6 construction contract, §6.2 --yes behaviour, §10.1 exit code contract, §14 CLI-first constraint.
**Prerequisite:** All Phase 4 tasks complete.
**Hard deps:** P4-T07
**Files:** tsm/__main__.py, tests/test_cli.py
**Reviewer:** Skip
**Key constraints:**
- load_project() must be implemented here and must not be reimplemented in any command module
- The confirm → apply flow and --yes flag must be implemented here, not inside command functions
- sys.exit() must only be called in __main__.py — no other module may call sys.exit()
- Exit codes must be exactly 0/1/2/3 as defined in §10.1 — no other codes used
**Done when:**
- tsm help works when run outside any project directory and exits 0
- tsm new-project --name "Test" works in an empty directory and exits 0
- tsm status, tsm vibe-check, tsm advance, tsm init-phase, tsm complete-phase, tsm undo all dispatch correctly inside a valid project directory
- tsm advance --yes against a fixture project applies without stdin prompt and exits 0
- tsm advance against a project with no active task exits with code 1
- tsm status against a project with a malformed TASKS.md exits with code 2
- tsm <unknown> prints "Unknown command: <unknown>" and exits with code 1
- tsm --help output is identical to tsm help output
- test_confirm_prompt_yes_flag passes (inherited from P3-T01)
- test_cli_exit_code_precondition_failure passes
- test_cli_exit_code_parse_error passes
- Every command works via tsm <command> without the TUI (CLI-first verification gate for Phase 6)

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|---|---|---|---|---|

---

## Out of scope

- Phase 6 TUI until all CLI commands are verified working end-to-end (§14 CLI-first constraint)
- Network calls, LLM calls, telemetry of any kind (§14)
- General Markdown parser libraries — line iterator state machine only (§9.1)
- Multi-level undo — single-level only in v1.0 (§14)
- Dependency graph edge validation in vibe-check — display/preservation only in v1.0 (§14)
- --output json on read-only commands — deferred to v2 (§2.2)