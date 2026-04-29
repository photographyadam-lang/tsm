# tsm — Session Prompts

Three prompts are in this file:

1. **SESSION OPENER** — paste this at the start of every Claude Code session
2. **BUILD PROMPT** — paste this after the agent confirms orientation; one per task
3. **THREAD MANAGER PROMPT** — paste this into a separate Claude.ai conversation to manage project state between sessions

---

---

## PROMPT 1 — SESSION OPENER

> Paste this as the first message in every new Claude Code session.
> Wait for the agent to echo back the active task before sending anything else.

---

```
Read AGENTS.md in full, then read SESSIONSTATE.md in full, then read the active task block in TASKS.md.

When you have read all three, reply with:
- The active task ID and title
- The files you will create or modify
- The Done when criteria you are targeting
- Any hard deps and whether they are all marked ✅ Complete in TASKS.md

Do not write any code or create any files until you have confirmed this and I have replied.
```

---

---

## PROMPT 2 — BUILD PROMPTS (one per task)

> After the agent confirms orientation, paste the relevant build prompt below.
> Each prompt is self-contained — you do not need to add anything to it.

---

### P1-T01 — Package scaffold and pyproject.toml - done

```
Build P1-T01 as specified.

Create the full package directory structure and all stub files. Exact structure:

tsm/
  __init__.py
  __main__.py       ← stub: main() prints "tsm: not yet implemented" and exits
  app.py            ← empty stub
  models.py         ← empty stub
  project.py        ← empty stub
  shadow.py         ← empty stub
  commands/__init__.py
  parsers/__init__.py
  writers/__init__.py
  ui/__init__.py
tests/
  __init__.py
  fixtures/         ← empty directory (add .gitkeep)
  parsers/__init__.py
  writers/__init__.py
  commands/__init__.py
pyproject.toml      ← see Done when criteria for exact content

Done when all four criteria in TASKS.md pass:
- pip install -e . completes without errors
- python -m tsm executes without ImportError
- All __init__.py files exist
- tsm entry point resolves to tsm.__main__:main

Commit message when complete: "P1-T01: package scaffold and pyproject.toml"
```

---

### P1-T02 — models.py - done 

```
Build P1-T02 as specified.

Implement tsm/models.py exactly. Field order and types must match §5 of the spec exactly.

Key items to verify before finishing:
1. slugify_phase_name() is a module-level function (not a class method)
2. LoadedProject has exactly 4 fields: project_context, phases, phase_overview, session
3. No conditional logic anywhere that branches on TaskComplexity values
4. All five slugify examples in Done when produce the correct output

Run these import checks before reporting done:
  from tsm.models import Task, Phase, SessionState, LoadedProject, slugify_phase_name, TaskStatus, TaskComplexity
  assert slugify_phase_name("Assessment Unification", []) == "assessment-unification"
  assert slugify_phase_name("Phase 1A", []) == "phase-1a"
  assert slugify_phase_name("Phase 1A", ["phase-1a"]) == "phase-1a-2"
  assert slugify_phase_name("Phase 1A", ["phase-1a", "phase-1a-2"]) == "phase-1a-3"

Commit message when complete: "P1-T02: models.py — all dataclasses, enums, LoadedProject, slugify_phase_name"
```

---

### P1-T03 — project.py - done 

```
Build P1-T03 as specified.

Implement tsm/project.py and tests/test_project_discovery.py.

The two public functions are find_project_root() and ensure_tsm_dir(). Key constraints:
- Walk up exactly 3 parent levels — no more, no parameterization
- Both TASKS.md AND SESSIONSTATE.md must be present — either alone is not enough
- ensure_tsm_dir must be idempotent — running it twice must not duplicate .tsm/ in .gitignore

Write test_project_discovery.py to cover all six Done when criteria. Use tmp_path fixtures
to create real directory structures for the walk tests.

Run pytest tests/test_project_discovery.py — all tests must pass.

Commit message when complete: "P1-T03: project.py — discovery and .gitignore enforcement"
```

---

### P1-T04 — Test fixtures - done

```
Build P1-T04 as specified.

Create the five fixture files in tests/fixtures/. These files are the test data that
all parser tests will load. They must be hand-crafted to cover specific format variants.

Required coverage (check each one before finishing):
- tests/fixtures/TASKS.md must contain ALL of these:
    ✓ At least 2 phases with ### Dependency graph block each
    ✓ Tasks with statuses: ✅ Complete, **Active**, Pending, 🔒 Blocked
    ✓ At least 1 task with multi-line **What:** (spans 3 lines)
    ✓ At least 1 task with multi-line **Done when:** (spans 2 lines)
    ✓ At least 1 task with **Key constraints:** field (2 bullet items)
    ✓ At least 1 task without **Key constraints:** field (omitted entirely)
    ✓ At least 1 task with backtick-wrapped **Files:** including a "(new)" suffix
    ✓ At least 1 task with em-dash (—) in **Hard deps:**
    ✓ At least 1 task with None in **Hard deps:**
    ✓ At least 1 task with "See spec §8" in **Files:**
- tests/fixtures/TASKS_ERRORS.md must have a comment at the top explaining deliberate errors, plus at least 1 duplicate task ID and 1 dangling dep
- tests/fixtures/SESSIONSTATE.md must use YYYY-MM-DDTHH:MM timestamp format

Do not create placeholder files. These must be real, parseable markdown.

Commit message when complete: "P1-T04: test fixtures for all format variants"
```

---

### P2-T01 — tasks_parser.py (core)

```
Build P2-T01 as specified.

Implement tsm/parsers/tasks_parser.py and tests/parsers/test_tasks_parser.py covering the 21 core tests.

The parser is a 7-state line iterator. States: PREAMBLE, PHASE_STRUCTURE_TABLE, BETWEEN_PHASES, PHASE_HEADER, SUBPHASE_HEADER, TASK_BLOCK, DEP_GRAPH.

Critical constraints — verify each before reporting done:
1. No Markdown parser library imports anywhere
2. Phase.id is set by calling slugify_phase_name() from models.py — no inline slug logic in the parser
3. ### Dependency graph blocks must NOT emit a Task object (test_dep_graph_not_parsed_as_task)
4. raw_block must be byte-for-byte identical to the original source (test_parse_raw_block_preserved)
5. All 6 status token variants from §4.1.3 must parse correctly

Run pytest tests/parsers/test_tasks_parser.py — all 21 named tests must pass before reporting done.

The 21 tests to target: test_parse_status_complete, test_parse_status_active_bold, test_parse_status_pending, test_parse_status_blocked_lock, test_parse_status_blocked_cross, test_parse_hard_deps_multiple, test_parse_hard_deps_em_dash, test_parse_hard_deps_none_text, test_parse_hard_deps_none_dot, test_parse_files_backtick_new, test_parse_files_multiple, test_parse_files_see_spec, test_parse_files_blank, test_parse_multiline_what, test_parse_multiline_done_when, test_parse_phase_structure_table, test_parse_multi_phase_file, test_parse_raw_block_preserved, test_task_id_title_extraction, test_dep_graph_not_parsed_as_task, test_dep_graph_raw_preserved.

Commit message when complete: "P2-T01: tasks_parser — state machine core, 21 tests passing"
```

---

### P2-T02 — tasks_parser.py (edge cases)

```
Build P2-T02 as specified.

Extend tsm/parsers/tasks_parser.py with complexity parsing, key_constraints parsing, and subphase tracking. Add 9 tests to tests/parsers/test_tasks_parser.py.

Rules:
- Unknown complexity value → TaskComplexity.UNSET + log warning — never raise
- Key constraints absent → key_constraints = [] — not a VC-11 violation
- Key constraints present but empty → key_constraints = []
- Key constraints with bullet items → strip "- " prefix from each line

After changes, run the full test file:
pytest tests/parsers/test_tasks_parser.py

All 30 tests (21 original + 9 new) must pass. If any of the original 21 regress, fix before reporting done.

The 9 new tests: test_parse_complexity_high, test_parse_complexity_low, test_parse_complexity_unset_explicit, test_parse_complexity_absent, test_parse_complexity_unknown_value, test_parse_key_constraints_present, test_parse_key_constraints_absent, test_parse_key_constraints_empty_field, test_vc11_does_not_fire_for_absent_key_constraints.

Commit message when complete: "P2-T02: tasks_parser — complexity, key_constraints, 30 tests passing"
```

---

### P2-T03 — session_parser.py

```
Build P2-T03 as specified.

Implement tsm/parsers/session_parser.py and tests/parsers/test_session_parser.py.

Key implementation notes:
- Parse *Last updated:* with two format attempts: "%Y-%m-%dT%H:%M" first, then "%Y-%m-%d" with time 00:00 for legacy format
- ## Active task: store verbatim as active_task_raw; also parse task ID from **<ID> — <title>** line; parse "- Complexity:" bullet
- [none] or empty ## Active task block → active_task = None (not an error)
- ## Up next: if Complexity column absent from table header, default all rows to TaskComplexity.UNSET
- ## Out of scope: store verbatim as out_of_scope_raw — never parse or transform

Run pytest tests/parsers/test_session_parser.py — all 12 tests must pass.

Commit message when complete: "P2-T03: session_parser — 12 tests passing"
```

---

### P2-T04 — completed_parser.py

```
Build P2-T04 as specified.

Implement tsm/parsers/completed_parser.py and tests/parsers/test_completed_parser.py.

parse_completed_file(path) returns list[tuple[str, list[dict]]].
Missing file → return [] (no exception).
Each row dict has exactly 5 keys: task, description, complexity, commit, notes.

Write at least 3 tests covering: fixture parse, missing file, row key verification.

Commit message when complete: "P2-T04: completed_parser"
```

---

### P3-T01 — shadow.py (stage/apply/backup/prune/history)

```
Build P3-T01 as specified.

Implement the core shadow pipeline in tsm/shadow.py and tests/test_shadow.py.

Functions needed: stage(), apply(), confirm_prompt().

Critical implementation requirements:
- apply() must use os.replace() for atomic live-file writes — never shutil.copy or open/write directly to live path
- Backup filenames: <filename>.<YYYY-MM-DDTHH-MM>.bak — colons become hyphens, seconds omitted
- Pruning must sort by mtime, not lexicographic — keep 5 most recently MODIFIED .bak files

Run pytest tests/test_shadow.py — these 5 tests must pass:
test_shadow_creates_backup_on_apply, test_shadow_prunes_to_5_backups, test_shadow_gitignore_created, test_shadow_gitignore_appended, test_shadow_gitignore_idempotent.

Commit message when complete: "P3-T01: shadow.py — stage/apply/backup/prune, 5 tests passing"
```

---

### P3-T02 — shadow.py (undo)

```
Build P3-T02 as specified.

Extend tsm/shadow.py with undo(). Add 3 tests to tests/test_shadow.py.

Undo rules (hard constraints):
- Single-level only
- Does NOT create a new backup
- Does NOT add a new history.log entry
- Marks the existing entry [undone] by appending to that line
- Empty history or all-[undone] → print "Nothing to undo." and return

All 8 tests must pass after changes (5 from P3-T01 + 3 new):
test_shadow_undo_restores_live_file, test_shadow_undo_no_history, test_shadow_double_undo.

Commit message when complete: "P3-T02: shadow.py — undo, 8 tests passing"
```

---

### P3-T03 — tasks_writer.py

```
Build P3-T03 as specified.

Implement tsm/writers/tasks_writer.py with TWO public functions and tests/writers/test_tasks_writer.py.

Function 1 — update_task_status(content: str, task_id: str, new_status: str) -> str
  Scan for "### <task_id> ·" line → find **Status:** line within that block → replace only that line.

Function 2 — update_phase_status(content: str, phase_heading_text: str, new_status: str) -> str
  Scan for "# <phase_heading_text>" H1 line → find **Status:** line within the phase header (before first --- or next #) → replace only that line.

Both functions:
- Operate on raw string content, not parsed data model
- Must raise ValueError if the target is not found
- Must produce output where all bytes outside the replaced line are identical to input

Write tests verifying:
- Task-level update: replace → re-parse → status matches; raw_blocks of other tasks unchanged
- Phase-level update: replace → re-parse → phase.status matches; all task raw_blocks unchanged
- ValueError raised for unknown task_id
- ValueError raised for unknown phase_heading_text
- Byte diff confirms no other changes for both functions

IMPORTANT: This module must never re-serialize TASKS.md from a data model. Targeted line replacement only.

Commit message when complete: "P3-T03: tasks_writer — task-level and phase-level targeted replacement"
```

---

### P3-T04 — session_writer.py

```
Build P3-T04 as specified.

Implement tsm/writers/session_writer.py with render_sessionstate(state: SessionState) -> str and write_session_file(), plus tests/writers/test_session_writer.py.

Renderer invariants (all must hold):
- *Last updated:* uses datetime.now() at render time — not passed in as a parameter
- active_task_raw is re-emitted verbatim — never reconstructed from Task fields
- out_of_scope_raw is re-emitted verbatim — never normalized or stripped
- ## Up next table always has the 5-column header including Complexity

Write tests verifying:
- Round-trip: render → write → parse → all SessionState fields match original
- out_of_scope_raw survives byte-for-byte
- *Last updated:* in output is current time (within a few seconds of the render call)
- ## Up next table in output has the Complexity column

IMPORTANT: This module uses full reconstruction only. Never use targeted line replacement on SESSIONSTATE.md.

Commit message when complete: "P3-T04: session_writer — full reconstruction renderer"
```

---

### P3-T05 — completed_writer.py

```
Build P3-T05 as specified.

Implement tsm/writers/completed_writer.py. Two functions: append_task_row() and append_phase_marker().

Key behavior:
- If file is missing, create it with "# Completed Tasks Log\n\n---\n" header
- If phase section is missing, append it (do not duplicate existing sections)
- Both functions write to shadow_path, not live_path

Write at least 4 tests covering: new file creation, append to existing section, new section created when phase missing, append_phase_marker placement.

Commit message when complete: "P3-T05: completed_writer — append writer"
```

---

### P4-T01 — commands/advance.py

```
Build P4-T01 as specified.

Implement tsm/commands/advance.py and tests/commands/test_advance.py.

The advance() function returns list[PendingWrite] — it does NOT call shadow.apply().

Dep resolution rule (critical): a dep is considered met if its task ID has status COMPLETE in ctx.phases OR if it equals the task just being advanced. This "self-counts-as-complete" logic lives in advance.py only.

Also implement:
- confirm_summary(pending_writes) -> str for the §7.3 formatted output
- HELP_TEXT static string constant at module level

Run pytest tests/commands/test_advance.py — all 5 tests must pass:
test_advance_happy_path, test_advance_no_active_task, test_advance_dep_not_met, test_advance_with_commit_message, test_advance_last_task_in_phase.

Commit message when complete: "P4-T01: commands/advance — 5 tests passing"
```

---

### P4-T02 — commands/init_phase.py

```
Build P4-T02 as specified.

Implement tsm/commands/init_phase.py and tests/commands/test_init_phase.py.
Add HELP_TEXT constant.

Run pytest tests/commands/test_init_phase.py — all 3 tests must pass:
test_init_phase_sets_active_task, test_init_phase_no_ready_task, test_init_phase_unknown_id.

Commit message when complete: "P4-T02: commands/init_phase — 3 tests passing"
```

---

### P4-T03 — commands/complete_phase.py

```
Build P4-T03 as specified.

Implement tsm/commands/complete_phase.py and tests/commands/test_complete_phase.py.
Add HELP_TEXT constant.

Critical: the TASKS.md write for phase status MUST use update_phase_status() — not update_task_status(). These are different functions targeting different block levels.

Run pytest tests/commands/test_complete_phase.py — all 3 tests must pass:
test_complete_phase_all_done, test_complete_phase_incomplete_tasks, test_complete_phase_no_next_phase.

Commit message when complete: "P4-T03: commands/complete_phase — 3 tests passing"
```

---

### P4-T04 — commands/vibe_check.py

```
Build P4-T04 as specified.

Implement tsm/commands/vibe_check.py and tests/commands/test_vibe_check.py.
Add HELP_TEXT constant.

Notes on specific rules:
- VC-11: fires for missing required fields (Status, What, Prerequisite, Hard deps, Files, Reviewer, Done when) but NOT for absent Key constraints — absence of Key constraints is valid
- VC-13: fires only for active task and up-next tasks — suppressed for completed tasks
- VC-12: uses datetime subtraction (timedelta > 7 days) — not date comparison

Run pytest tests/commands/test_vibe_check.py — all 11 tests must pass.

Commit message when complete: "P4-T04: commands/vibe_check — 11 tests passing"
```

---

### P4-T05 — commands/status.py and commands/undo.py

```
Build P4-T05 as specified.

Implement both commands and add HELP_TEXT constants to each.

status(ctx: LoadedProject) → prints §7.6 formatted output to stdout. Read-only.
undo(ctx: ProjectContext) → delegates to shadow.undo(ctx). No return value.

Write minimal tests verifying: status output contains expected sections; undo delegates correctly; undo against empty history prints "Nothing to undo."

Commit message when complete: "P4-T05: commands/status and undo"
```

---

### P4-T06 — commands/help.py

```
Build P4-T06 as specified.

Implement tsm/commands/help.py and tests/commands/test_help.py.

Help text for each command is imported from that command module's HELP_TEXT constant.
This module does NOT require a project root.

Run pytest tests/commands/test_help.py — all 4 tests must pass:
test_help_lists_all_commands, test_help_specific_command, test_help_unknown_command, test_help_no_project_root_required.

Commit message when complete: "P4-T06: commands/help — 4 tests passing"
```

---

### P4-T07 — commands/new_project.py

```
Build P4-T07 as specified.

Implement tsm/commands/new_project.py and tests/commands/test_new_project.py.
Add HELP_TEXT constant.

The generated TASKS.md and SESSIONSTATE.md must parse without errors — use the real parsers in the round-trip tests.

Abort if TASKS.md or SESSIONSTATE.md already exist — create nothing.

Run pytest tests/commands/test_new_project.py — all 8 tests must pass:
test_new_project_creates_all_files, test_new_project_with_name_flag, test_new_project_prompts_for_name, test_new_project_aborts_if_tasks_exists, test_new_project_aborts_if_sessionstate_exists, test_new_project_creates_gitignore_entry, test_new_project_tasks_md_parseable, test_new_project_sessionstate_parseable.

Commit message when complete: "P4-T07: commands/new_project — 8 tests passing"
```

---

### P5-T01 — __main__.py

```
Build P5-T01 as specified.

Implement tsm/__main__.py with main() entry point and load_project(root: Path) -> LoadedProject.

load_project() construction order (must be exactly this):
  ctx = build_project_context(root)  # from project.py
  phase_overview, phases = parse_tasks_file(ctx.tasks_path)
  session = parse_session_file(ctx.sessionstate_path)
  return LoadedProject(project_context=ctx, phases=phases, phase_overview=phase_overview, session=session)

Write commands: advance, init_phase, complete_phase → get PendingWrite list → confirm_prompt → if confirmed, apply.
Read-only commands: status, vibe_check → call and print.
No-root commands: help, new_project → skip project discovery entirely.

After implementation, run the full manual verification:
- tsm help  (outside any project dir — must work)
- tsm new-project --name "Test"  (in empty dir — must work)
- tsm status  (inside project dir — must print session state)
- tsm vibe-check  (inside project dir — must print check results)
- tsm <unknown>  (must print "Unknown command: <unknown>" and exit 1)
- tsm --help  (must be identical to tsm help)

Commit message when complete: "P5-T01: __main__.py — CLI wiring and load_project bootstrap"
```

---

### P6-T01 through P6-T05 — TUI

> Use the TASKS.md Done when criteria directly for these tasks.
> The TUI tasks are intentionally left without individual build prompts here —
> by Phase 6 you have enough momentum to derive them yourself.
> The pattern is: read the task block, implement the Textual widget, verify the Done when criteria.

---

---

## PROMPT 3 — THREAD MANAGER PROMPT

> Paste this into a separate Claude.ai conversation (not Claude Code).
> Use this thread to track progress, advance SESSIONSTATE.md, and plan next sessions.
> This is your "project manager" conversation — it is not for writing code.

---

```
You are the project manager for the tsm build — a Python CLI/TUI tool I am building using Claude Code as the coding agent.

Your job in this thread is to help me:
1. Track which tasks are complete and which are next
2. Draft the SESSIONSTATE.md changes needed after each completed task
3. Confirm that a task's Done when criteria were actually met before I advance it
4. Surface any blockers or dep chain issues before I start a session
5. Draft git commit messages

You do not write code. You do not make architecture decisions. Those are fixed in the spec.

I will paste you the current SESSIONSTATE.md and TASKS.md at the start of this conversation, and update you after each completed task session.

Here is the current project state:

--- SESSIONSTATE.md ---
[paste current SESSIONSTATE.md here]

--- TASKS.md (Phase structure table and current phase only) ---
[paste Phase structure table + current phase tasks here]
---

When I report a task complete, ask me:
- Which named Done when criteria did you verify? (list them)
- What is the exact commit message?
- Were there any deviations from the spec?

Only after I confirm the criteria will you draft the SESSIONSTATE.md advance.

When drafting a SESSIONSTATE.md advance, produce the exact text to paste, in this format:
- Updated *Last updated:* line
- Updated ## Completed tasks table row to add
- New ## Active task block (copy from the TASKS.md task block I provide)
- Updated ## Up next table (remove the task just promoted)
Also produce the one-line TASKS.md edit: the exact **Status:** line replacement for the completed task.
```

---

---

## Quick reference — which prompt to use when

| Situation | Use |
|-----------|-----|
| Starting a new Claude Code session | Prompt 1 (Session Opener) |
| Agent has confirmed orientation, ready to build | Prompt 2 (Build Prompt for active task) |
| Task complete, need to advance state | Prompt 3 (Thread Manager) |
| Starting a new phase | Prompt 3 to prepare SESSIONSTATE.md, then Prompt 1 in Claude Code |
| Something went wrong, need to understand current state | Prompt 3 with current file contents pasted in |
