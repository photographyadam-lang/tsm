# tsm — Session Prompts

Three prompts are in this file:

1. **SESSION OPENER** — paste this at the start of every Claude Code session
2. **BUILD PROMPTS** — paste the relevant one after the agent confirms orientation
3. **THREAD MANAGER PROMPT** — paste into a separate Claude.ai conversation to manage state between sessions

Tasks marked ✅ are complete. The current active task is **P6-T05**.

---

## PROMPT 1 — SESSION OPENER

> Paste this as the first message in every new Claude Code session.
> Wait for the agent to echo back the active task before sending anything else.

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

## PROMPT 2 — BUILD PROMPTS

> After the agent confirms orientation, paste the relevant build prompt.
> Each prompt is self-contained.

---

### ✅ P1-T01 — Package scaffold and pyproject.toml

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

### ✅ P1-T02 — models.py

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

### ✅ P1-T03 — project.py

```
Build P1-T03 as specified.

Implement tsm/project.py and tests/test_project_discovery.py.

Key constraints:
- Walk up exactly 3 parent levels — no more, no parameterization
- Both TASKS.md AND SESSIONSTATE.md must be present — either alone is not enough
- ensure_tsm_dir must be idempotent — running it twice must not duplicate .tsm/ in .gitignore

Use tmp_path fixtures for all directory walk tests.

Run pytest tests/test_project_discovery.py — all tests must pass.

Commit message when complete: "P1-T03: project.py — discovery and .gitignore enforcement"
```

---

### ✅ P1-T04 — Test fixtures

```
Build P1-T04 as specified.

Create the five fixture files in tests/fixtures/. Must cover all format variants:

tests/fixtures/TASKS.md must contain:
  ✓ At least 2 phases with ### Dependency graph block each
  ✓ Tasks with statuses: ✅ Complete, **Active**, Pending, 🔒 Blocked
  ✓ 1 task with multi-line **What:** (3+ lines)
  ✓ 1 task with multi-line **Done when:** (2+ lines)
  ✓ 1 task with **Key constraints:** field (2 bullet items)
  ✓ 1 task WITHOUT **Key constraints:** field (omitted entirely)
  ✓ 1 task with backtick-wrapped **Files:** including a "(new)" suffix
  ✓ 1 task with em-dash — in **Hard deps:**
  ✓ 1 task with None in **Hard deps:**
  ✓ 1 task with "See spec §8" in **Files:**
tests/fixtures/TASKS_ERRORS.md must have a comment at top explaining deliberate errors (VC-01 duplicate ID, VC-02 dangling dep)
tests/fixtures/SESSIONSTATE.md must use YYYY-MM-DDTHH:MM timestamp format

Commit message when complete: "P1-T04: test fixtures for all format variants"
```

---

### ✅ P2-T01 — tasks_parser.py (core)

```
Build P2-T01 as specified.

Implement tsm/parsers/tasks_parser.py and tests/parsers/test_tasks_parser.py covering 21 core tests.

7-state machine: PREAMBLE, PHASE_STRUCTURE_TABLE, BETWEEN_PHASES, PHASE_HEADER, SUBPHASE_HEADER, TASK_BLOCK, DEP_GRAPH.

Critical constraints:
1. No Markdown parser library imports anywhere
2. Phase.id set by calling slugify_phase_name() from models.py — no inline slug logic
3. ### Dependency graph blocks must NOT emit a Task object
4. raw_block must be byte-for-byte identical to the original source

Run pytest tests/parsers/test_tasks_parser.py — all 21 named tests must pass.

21 tests: test_parse_status_complete, test_parse_status_active_bold, test_parse_status_pending, test_parse_status_blocked_lock, test_parse_status_blocked_cross, test_parse_hard_deps_multiple, test_parse_hard_deps_em_dash, test_parse_hard_deps_none_text, test_parse_hard_deps_none_dot, test_parse_files_backtick_new, test_parse_files_multiple, test_parse_files_see_spec, test_parse_files_blank, test_parse_multiline_what, test_parse_multiline_done_when, test_parse_phase_structure_table, test_parse_multi_phase_file, test_parse_raw_block_preserved, test_task_id_title_extraction, test_dep_graph_not_parsed_as_task, test_dep_graph_raw_preserved.

Commit message when complete: "P2-T01: tasks_parser — state machine core, 21 tests passing"
```

---

### ✅ P2-T02 — tasks_parser.py (edge cases)

```
Build P2-T02 as specified.

Extend tasks_parser.py with complexity parsing, key_constraints parsing, and subphase tracking. Add 9 tests.

Rules:
- Unknown complexity → TaskComplexity.UNSET + log warning — never raise
- Key constraints absent → key_constraints = [] — not a VC-11 violation
- Key constraints present but empty → key_constraints = []
- Key constraints with bullets → strip "- " prefix from each line

Run pytest tests/parsers/test_tasks_parser.py — all 30 tests must pass.

9 new tests: test_parse_complexity_high, test_parse_complexity_low, test_parse_complexity_unset_explicit, test_parse_complexity_absent, test_parse_complexity_unknown_value, test_parse_key_constraints_present, test_parse_key_constraints_absent, test_parse_key_constraints_empty_field, test_vc11_does_not_fire_for_absent_key_constraints.

Commit message when complete: "P2-T02: tasks_parser — complexity, key_constraints, 30 tests passing"
```

---

### ✅ P2-T03 — session_parser.py

```
Build P2-T03 as specified.

Implement tsm/parsers/session_parser.py and tests/parsers/test_session_parser.py.

Key implementation notes:
- Parse *Last updated:* with two formats: "%Y-%m-%dT%H:%M" first, then "%Y-%m-%d" with time 00:00 for legacy
- ## Active task: store verbatim as active_task_raw; parse task ID from **<ID> — <title>** line; parse "- Complexity:" bullet
- [none] or empty ## Active task → active_task = None
- ## Up next: if Complexity column absent, default all rows to TaskComplexity.UNSET
- ## Out of scope: store verbatim as out_of_scope_raw — never parse or transform

Run pytest tests/parsers/test_session_parser.py — all 12 tests must pass.

Commit message when complete: "P2-T03: session_parser — 12 tests passing"
```

---

### ✅ P2-T04 — completed_parser.py

```
Build P2-T04 as specified.

Implement tsm/parsers/completed_parser.py. Returns list[tuple[str, list[dict]]].
Missing file → return [] (no exception).
Each row dict has exactly 5 keys: task, description, complexity, commit, notes.

Write at least 3 tests: fixture parse, missing file, row key verification.

Commit message when complete: "P2-T04: completed_parser"
```

---

### ✅ P3-T01 — shadow.py (stage/apply/backup/prune/history)

```
Build P3-T01 as specified.

Implement shadow.py core pipeline. confirm_prompt signature:
  confirm_prompt(pending_writes: list[PendingWrite], yes: bool = False) -> bool

When yes=True: print summary to stdout and return True without reading stdin.
When yes=False: print summary and wait for Y/n from stdin.
The yes parameter defaults to False — never default it to True internally.

Critical:
- Use os.replace() for atomic live-file writes
- Backup filenames: <filename>.<YYYY-MM-DDTHH-MM>.bak (colons → hyphens, seconds omitted)
- Pruning sorts by mtime, not lexicographic order

Run pytest tests/test_shadow.py — these 6 tests must pass:
test_shadow_creates_backup_on_apply, test_shadow_prunes_to_5_backups, test_shadow_gitignore_created, test_shadow_gitignore_appended, test_shadow_gitignore_idempotent, test_confirm_prompt_yes_flag.

Commit message when complete: "P3-T01: shadow.py — stage/apply/backup/prune, 6 tests passing"
```

---

### ✅ P3-T02 — shadow.py (undo)

```
Build P3-T02 as specified.

Extend shadow.py with undo(). Add 3 tests.

Hard constraints:
- Single-level only
- Does NOT create a new backup
- Does NOT add a new history.log entry — appends [undone] to the existing entry
- Empty history or all-[undone] → print "Nothing to undo." and return

All 9 tests must pass (6 from P3-T01 + 3 new):
test_shadow_undo_restores_live_file, test_shadow_undo_no_history, test_shadow_double_undo.

Commit message when complete: "P3-T02: shadow.py — undo, 9 tests passing"
```

---

### ✅ P3-T03 — tasks_writer.py (status replacement)

```
Build P3-T03 as specified.

Two public functions:
  update_task_status(content: str, task_id: str, new_status: str) -> str
  update_phase_status(content: str, phase_heading_text: str, new_status: str) -> str

Both operate on raw string content and raise ValueError if target not found.
Output must be byte-identical to input except for the replaced **Status:** line.

Write tests verifying:
- Task-level: replace → re-parse → status matches; all other raw_blocks unchanged
- Phase-level: replace → re-parse → phase.status matches; all task raw_blocks unchanged
- ValueError for unknown IDs
- Byte diff confirms no other changes for both functions

IMPORTANT: Never re-serialize TASKS.md from the data model.

Commit message when complete: "P3-T03: tasks_writer — task-level and phase-level targeted replacement"
```

---

### ✅ P3-T04 — session_writer.py

```
Build P3-T04 as specified.

Implement render_sessionstate(state: SessionState) -> str and write_session_file().

Renderer invariants:
- *Last updated:* uses datetime.now() at render time
- active_task_raw re-emitted verbatim unless command explicitly replaced it
- out_of_scope_raw re-emitted verbatim — no normalization
- ## Up next always has 5-column header including Complexity

Write tests verifying:
- Round-trip: render → write → parse → all fields match
- out_of_scope_raw survives byte-for-byte
- *Last updated:* in output reflects render time
- ## Up next has Complexity column

IMPORTANT: Full reconstruction only — never targeted replacement on SESSIONSTATE.md.

Commit message when complete: "P3-T04: session_writer — full reconstruction renderer"
```

---

### ✅ P3-T05 — completed_writer.py

```
Build P3-T05 as specified.

Two functions: append_task_row() and append_phase_marker().

- Missing file → create with "# Completed Tasks Log\n\n---\n" header
- Phase section missing → append new section, then append row
- Both functions write to shadow_path, not live path

Write at least 4 tests: new file creation, append to existing section, new section created, append_phase_marker placement.

Commit message when complete: "P3-T05: completed_writer — append writer"
```

---

### ✅ P4-T01 — commands/advance.py

```
Build P4-T01 as specified.

advance() returns list[PendingWrite] — does NOT call shadow.apply() itself.

Dep resolution rule: a dep is met if its ID has status COMPLETE in ctx.phases OR equals the task just being advanced. This logic lives in advance.py only.

Also implement:
- confirm_summary(pending_writes) -> str for the §7.3 formatted output
- HELP_TEXT module-level string constant

Run pytest tests/commands/test_advance.py — all 5 tests must pass:
test_advance_happy_path, test_advance_no_active_task, test_advance_dep_not_met, test_advance_with_commit_message, test_advance_last_task_in_phase.

Commit message when complete: "P4-T01: commands/advance — 5 tests passing"
```

---

### ✅ P4-T02 — commands/init_phase.py

```
Build P4-T02 as specified.

Implement tsm/commands/init_phase.py and tests/commands/test_init_phase.py. Add HELP_TEXT constant.

Run pytest tests/commands/test_init_phase.py — all 3 tests must pass:
test_init_phase_sets_active_task, test_init_phase_no_ready_task, test_init_phase_unknown_id.

Commit message when complete: "P4-T02: commands/init_phase — 3 tests passing"
```

---

### ✅ P4-T03 — commands/complete_phase.py

```
Build P4-T03 as specified.

Add HELP_TEXT constant. Critical: TASKS.md write for phase status MUST use update_phase_status() — not update_task_status().

Run pytest tests/commands/test_complete_phase.py — all 3 tests must pass:
test_complete_phase_all_done, test_complete_phase_incomplete_tasks, test_complete_phase_no_next_phase.

Commit message when complete: "P4-T03: commands/complete_phase — 3 tests passing"
```

---

### ✅ P4-T04 — commands/vibe_check.py

```
Build P4-T04 as specified.

Add HELP_TEXT constant.

Rule notes:
- VC-11: fires for missing required fields but NOT for absent Key constraints
- VC-13: fires only for active/up-next tasks — suppressed for completed
- VC-12: uses timedelta > 7 days — not date comparison

Run pytest tests/commands/test_vibe_check.py — all 11 tests must pass.

Commit message when complete: "P4-T04: commands/vibe_check — 11 tests passing"
```

---

### ✅ P4-T05 — commands/status.py and commands/undo.py

```
Build P4-T05 as specified.

status() → prints §7.6 formatted output to stdout. Read-only.
undo() → delegates to shadow.undo(ctx). No return value.
Add HELP_TEXT constants to both modules.

Write minimal tests verifying: status output contains expected sections; undo delegates correctly; undo against empty history prints "Nothing to undo."

Commit message when complete: "P4-T05: commands/status and undo"
```

---

### ✅ P4-T06 — commands/help.py

```
Build P4-T06 as specified.

Help text imported from each command module's HELP_TEXT constant. Does NOT require project root.

Run pytest tests/commands/test_help.py — all 4 tests must pass:
test_help_lists_all_commands, test_help_specific_command, test_help_unknown_command, test_help_no_project_root_required.

Commit message when complete: "P4-T06: commands/help — 4 tests passing"
```

---

### ✅ P4-T07 — commands/new_project.py

```
Build P4-T07 as specified.

Add HELP_TEXT constant. Generated TASKS.md and SESSIONSTATE.md must parse without errors — use real parsers in round-trip tests. Abort if either file already exists.

Run pytest tests/commands/test_new_project.py — all 8 tests must pass:
test_new_project_creates_all_files, test_new_project_with_name_flag, test_new_project_prompts_for_name, test_new_project_aborts_if_tasks_exists, test_new_project_aborts_if_sessionstate_exists, test_new_project_creates_gitignore_entry, test_new_project_tasks_md_parseable, test_new_project_sessionstate_parseable.

Commit message when complete: "P4-T07: commands/new_project — 8 tests passing"
```

---

### ✅ P5-T01 — __main__.py

```
Build P5-T01 as specified.

load_project() construction order (must be exactly this):
  ctx = build_project_context(root)
  phase_overview, phases = parse_tasks_file(ctx.tasks_path)
  session = parse_session_file(ctx.sessionstate_path)
  return LoadedProject(project_context=ctx, phases=phases, phase_overview=phase_overview, session=session)

Parse --yes flag before dispatch — pass yes=True to confirm_prompt() for write commands.
Implement exit code contract: PreconditionError → 1, ParseError → 2, WriteError → 3, success → 0.
No sys.exit() anywhere except __main__.py.

Write commands: call command → get PendingWrite list → confirm_prompt(pending_writes, yes=yes_flag) → if True, apply.
Read-only commands: call and print.
No-root commands (help, new-project): skip project discovery.

Manual verification after implementation:
- tsm help  (outside any project dir — must exit 0)
- tsm new-project --name "Test"  (in empty dir — must exit 0)
- tsm status  (inside project dir)
- tsm vibe-check  (inside project dir)
- tsm advance --yes  (no stdin prompt, exits 0)
- tsm <unknown>  (must print "Unknown command: <unknown>" and exit 1)
- tsm --help  (identical to tsm help)

Commit message when complete: "P5-T01: __main__.py — CLI wiring, load_project, --yes, exit codes"
```

---

### P6-T05 — app.py — full TUI wiring ← ACTIVE

```
Build P6-T05 as specified.

Implement tsm/app.py with TsmApp(App). Two-panel layout with fixed command bar footer.

Keybindings (§8.4):
  a → advance (prompt for commit message, then ConfirmOverlay)
  i → init-phase (prompt for phase ID, then ConfirmOverlay)
  c → complete-phase (ConfirmOverlay)
  v → vibe-check (swap right panel to VibecheckPanel)
  u → undo (call shadow.undo directly, refresh)
  s → status (show in read-only panel or print to CLI)
  ? → swap right panel to HelpPanel
  q → quit

Context-aware greying (§8.4):
  init-phase → greyed when active task is set
  complete-phase → greyed when any current phase tasks are not complete
  undo → greyed when history log is empty or all entries are [undone]

Critical constraints:
- All commands must already work via CLI — do not add TUI-only code paths
- Greying is display-only — command functions still check preconditions
- After any write command applies: call load_project() again and refresh both panels from the new LoadedProject

After implementation, do a full manual smoke test:
- Launch tsm with no subcommand — TUI must open
- Press all 8 keybindings and confirm correct dispatch
- Run advance from TUI — confirm ConfirmOverlay appears and applying updates both panels
- Confirm greying behaviour for all three context-aware buttons

Commit message when complete: "P6-T05: app.py — full TUI wiring"
```

---

### P7-T01 — deps.py — dependency engine

```
Build P7-T01 as specified.

Implement tsm/deps.py with six public functions (all accept list[Phase], no file I/O):

  build_dep_graph(phases) -> dict[str, set[str]]
  get_dependents(task_id, phases) -> list[str]
  get_dep_chain(task_id, phases) -> list[str]
  get_blocked_tasks(phases) -> list[tuple[str, list[str]]]
  check_deps(phases) -> list[str]
  detect_cycles(phases) -> list[list[str]]

detect_cycles() must use DFS with visited + recursion-stack. Must handle both direct cycles (A→B→A) and indirect (A→B→C→A).
check_deps() validates: no dangling refs, no cycles, no self-references. Returns list[str] errors — never raises.
deps.py has zero imports from any command module.

Write tests/test_deps.py covering:
- build_dep_graph() on fixture → correct adjacency dict
- detect_cycles() returns [] on acyclic graph
- detect_cycles() returns cycle path when cycle exists
- test_deps_check_clean passes
- test_deps_check_dangling passes
- test_deps_pre_write_gate_blocks_remove passes
- test_deps_cycle_detection passes

Commit message when complete: "P7-T01: deps.py — dependency engine"
```

---

### P7-T02 — commands/deps.py - done

```
Build P7-T02 as specified.

Implement tsm/commands/deps.py. Read-only — no PendingWrite, no shadow, no confirmation.

Four modes (§16.3):
  deps_command(ctx, task_id=None, tree=False, blocked=False, check=False) -> None

  No args / --tree → full ASCII tree (bare invocation defaults to tree)
  task_id given → single task detail: depends-on list with status icons, required-by list
  --blocked → only tasks with unmet deps
  --check → validation; exit 0 on clean, exit 1 with issues listed

Output formats must match §16.3 exactly (box drawing chars, status icons).
Add HELP_TEXT constant. Wire into __main__.py.

Run pytest tests/test_deps.py — all deps command tests must pass:
test_deps_single_task, test_deps_tree_output, test_deps_blocked_list, test_deps_check_clean, test_deps_check_dangling.

Commit message when complete: "P7-T02: commands/deps — deps command"
```

---

### P7-T03a — tasks_writer.py (block insert, remove, field replacement)

```
Build P7-T03a as specified.

Extend tsm/writers/tasks_writer.py with six new functions operating on raw string content:

  insert_phase_block(content, phase_block, after_phase_id) -> str
  remove_phase_block(content, phase_id) -> str
  insert_task_block(content, task_block, phase_id, after_task_id) -> str
  remove_task_block(content, task_id) -> str
  update_phase_structure_table(content, rows: list[PhaseOverviewRow]) -> str
  update_task_field(content, task_id, field_name, new_value) -> str  ← §9.4a algorithm

update_task_field multi-line algorithm (§9.4a):
1. Find ### <task_id> · heading
2. Find **<field_name>:** line within block
3. Determine extent: scan forward until next ** label or structural boundary
4. Replace label line + value lines with new content
5. Key constraints special case: empty new_value → remove field block; field absent + non-empty → insert before **Done when:**

All functions raise ValueError if target ID not found.
insert_task_block must insert BEFORE ### Dependency graph, never after.

Write tests verifying:
- insert/remove → re-parse → correct structure; all other content byte-identical
- update_task_field multi-line What → re-parse → task.what equals new value; all other fields unchanged
- update_task_field adding Key constraints to task with none → field appears before Done when

Commit message when complete: "P7-T03a: tasks_writer — structural insert/remove/field-replace"
```

---

### P7-T03b — tasks_writer.py (reorder operations)

```
Build P7-T03b as specified.

Extend tasks_writer.py with two reorder functions:

  reorder_phase_blocks(content, ordered_phase_ids: list[str]) -> str
  reorder_task_blocks(content, phase_id, ordered_task_ids: list[str]) -> str

reorder_phase_blocks: reorders H1 blocks to match ordered_phase_ids. Content within each block preserved byte-for-byte. ValueError if any ID is missing or list is shorter than actual phase count.

reorder_task_blocks: reorders ### blocks within a single phase. Content within each block preserved byte-for-byte. ### Dependency graph block always remains last regardless of its position in ordered_task_ids.

Critical: verify byte-for-byte content preservation within blocks using a before/after diff in tests.

Write tests verifying:
- reorder_phase_blocks → re-parse → phases in new order; byte diff confirms zero content changes within any block
- reorder_task_blocks → re-parse → tasks in new order; dep graph still last; raw_blocks byte-identical
- reorder_phase_blocks with missing ID → ValueError
- reorder_task_blocks with dep graph in the list → dep graph still ends up last

Commit message when complete: "P7-T03b: tasks_writer — reorder operations"
```

---

### P7-T04 — commands/phase.py

```
Build P7-T04 as specified.

Four functions: phase_add, phase_edit, phase_move, phase_remove (all return list[PendingWrite]).

For each function:
1. Apply transformation to in-memory copy of ctx.phases to get proposed state
2. Call check_deps() on the proposed state (NOT the current state)
3. For remove without --force: abort if check_deps returns errors
4. Build PendingWrite using P7-T03a/T03b writer functions

phase_move calls reorder_phase_blocks.
phase_remove with --force: proceeds despite dep errors; lists dangling deps in confirm summary.

Add HELP_TEXT. Wire into __main__.py.

Run pytest tests/commands/test_phase.py — all 6 tests must pass:
test_phase_add_appends_phase_block, test_phase_add_updates_phase_structure_table,
test_phase_edit_name_updates_heading_and_table, test_phase_move_reorders_h1_blocks,
test_phase_remove_blocked_by_deps, test_phase_remove_force_cascade.

Commit message when complete: "P7-T04: commands/phase — phase CRUD"
```

---

### P7-T05 — commands/task.py

```
Build P7-T05 as specified.

Four functions: task_add, task_edit, task_move, task_remove (all return list[PendingWrite]).

task_edit field routing:
  - status field → use update_task_status() (single-line)
  - all other fields → use update_task_field() (§9.4a multi-line)
  Never use update_task_field() for the status field.

task_edit hard_deps: if new deps value creates a cycle or refs nonexistent ID, abort before writing (dep gate on proposed state).

task_move: if task is active/up-next in SESSIONSTATE.md, include SESSIONSTATE.md PendingWrite in result.

All functions call check_deps() on proposed in-memory state before staging.

Add HELP_TEXT. Wire into __main__.py.

Run pytest tests/commands/test_task.py — all 8 tests must pass:
test_task_add_generates_id, test_task_add_id_collision_increments, test_task_edit_field,
test_task_move_within_phase, test_task_move_between_phases,
test_task_remove_blocked_by_deps, test_task_remove_force, test_task_edit_hard_deps_dep_gate.

Commit message when complete: "P7-T05: commands/task — task CRUD"
```

---

### P7-T06 — ui/task_form.py — TaskFormOverlay

```
Build P7-T06 as specified.

Implement TaskFormOverlay(ModalScreen[dict | None]).

Fields: title (required), complexity (select), what (multiline), prerequisite, hard_deps, files, reviewer (select), key_constraints (multiline), done_when (multiline).

Add mode (no task passed): all fields blank.
Edit mode (task passed): all fields pre-populated with current values.

On confirm: dismiss with dict of field_name → new_value for CHANGED fields only.
On cancel/Escape: dismiss with None.
Required field (title) empty on confirm → show validation error, do not dismiss.

Verify:
- Mounts without error in both add and edit mode
- Edit mode pre-populates all fields
- Confirm dict contains only changed fields
- Cancel dismisses with None
- Empty title shows validation error

Commit message when complete: "P7-T06: ui/task_form — TaskFormOverlay"
```

---

### P7-T07 — commands/repair.py

```
Build P7-T07 as specified.

repair(ctx, tasks=False, session=False, completed=False) -> list[PendingWrite]
If all three False → set all True (repair everything).

TASKS.md repairs:
- Missing required fields → fill with safe defaults (complexity: unset, hard_deps: None, reviewer: Skip)
- Malformed status tokens → normalize to canonical form
- Duplicate task IDs → rename second occurrence to <id>-duplicate automatically (no interactive prompt)
- Unparseable content → skip and report with [skipped] label

SESSIONSTATE.md repairs:
- Active task ID not in TASKS.md → clear active task; list in confirm summary
- Up next IDs not in TASKS.md → remove from table
- Legacy date-only timestamp → upgrade to YYYY-MM-DDTHH:MM with 00:00

TASKS-COMPLETED.md repairs:
- Rows with unknown task IDs → remove with [removed] label
- Empty phase sections → remove

Every change in PendingWrite.summary_lines with [defaulted]/[normalized]/[removed]/[skipped] label and before/after values. Running repair on a clean project produces zero changes.

Run pytest tests/commands/test_repair.py — all 4 named tests + idempotency test must pass:
test_repair_fills_missing_fields, test_repair_removes_vc10_rows,
test_repair_normalizes_session_task_id, test_repair_skips_unparseable_content.

Commit message when complete: "P7-T07: commands/repair"
```

---

### P7-T08 — commands/sync.py

```
Build P7-T08 as specified.

sync(ctx, from_task_id: str) -> list[PendingWrite]

Algorithm (§15.5 v1.6):
1. Locate from_task_id — exit 1 "Unknown task ID: <id>" if not found
2. In-memory only: tasks before from_task_id in its phase → COMPLETE; from_task_id → ACTIVE; tasks after → PENDING; all phases before current → COMPLETE (all tasks within); all phases after → PENDING
3. Detect parallel dep chains in the phase — emit §15.5 warning prompt if found (Y/n, not hard block)
4. Identify tasks NEWLY set to COMPLETE (were not already COMPLETE before sync)
5. Build PendingWrites:
   TASKS.md → update_task_status/update_phase_status (targeted replacement only)
   SESSIONSTATE.md → session_writer (clear completed table)
   TASKS-COMPLETED.md → completed_writer for newly-complete tasks only, blank commit

Do NOT re-append tasks already in TASKS-COMPLETED.md.
Do NOT re-serialize TASKS.md from data model.

Run pytest tests/commands/test_sync.py — all 5 tests must pass:
test_sync_sets_active_task, test_sync_rebuilds_sessionstate,
test_sync_appends_completed_to_log, test_sync_warns_parallel_deps, test_sync_unknown_task_id.

Commit message when complete: "P7-T08: commands/sync"
```

---

### P7-T09 — commands/import_cmd.py

```
Build P7-T09 as specified.

Named import_cmd.py to avoid shadowing Python's import keyword.

import_files(ctx, tasks_path, session_path) -> list[PendingWrite]

1. Read API key from .tsm/config.toml using tomllib (stdlib). Exit 1 with setup instructions if missing:
   ❌ tsm import requires an API key.
      Add it to .tsm/config.toml:
      [import]
      api_key = "sk-ant-..."

2. Use the EXACT system prompt template from §15.1.2 as a module-level string constant.
   Do not paraphrase, shorten, or modify it.

3. Send raw file content to Anthropic API. Parse JSON response per §15.1.2 schema.
   On invalid JSON: retry once; if still invalid, exit 1 and write raw response to .tsm/import-debug.txt.

4. Fill missing fields with safe defaults (complexity: unset, hard_deps: None, reviewer: Skip, key_constraints: []).

5. Serialize normalized output using existing writer functions (insert_phase_block, insert_task_block) — never ad-hoc string building.

6. Confirm summary lists every field that was defaulted.

API key must come from config.toml only — never from env vars or sys.argv.
anthropic must be imported in this module only — no other module may import it.
All tests must mock API calls — never make real API calls in tests.

Run pytest tests/commands/test_import.py — all 6 tests must pass:
test_import_normalizes_tasks, test_import_fills_missing_fields_with_defaults,
test_import_no_api_key, test_import_api_error,
test_import_tasks_md_round_trip (generated output parses via tasks_parser),
test_import_sessionstate_round_trip (generated output parses via session_parser).

Commit message when complete: "P7-T09: commands/import_cmd — LLM-assisted normalization"
```

---

## PROMPT 3 — THREAD MANAGER PROMPT

> Paste this into a separate Claude.ai conversation (not Claude Code).
> Use this thread to track progress, advance SESSIONSTATE.md, and plan next sessions.

```
You are the project manager for the tsm build — a Python CLI/TUI tool I am building using Claude Code as the coding agent.

Your job in this thread is to:
1. Track which tasks are complete and which are next
2. Draft the SESSIONSTATE.md changes needed after each completed task
3. Confirm that a task's Done when criteria were actually met before I advance it
4. Surface blockers or dep chain issues before I start a session
5. Draft git commit messages

You do not write code. Architecture decisions are fixed in SPECIFICATION-task-session-manager-v1.6.md.

I will paste you the current SESSIONSTATE.md and TASKS.md at the start of each conversation.

When I report a task complete, ask me:
- Which named Done when criteria did you verify? (list them)
- What is the exact commit message?
- Were there any deviations from the spec?

Only after I confirm the criteria will you draft the SESSIONSTATE.md advance.

When drafting a SESSIONSTATE.md advance, produce the exact text to paste:
- Updated *Last updated:* line
- Row to add to ## Completed tasks table
- New ## Active task block (verbatim from the TASKS.md task block)
- Updated ## Up next table (remove the promoted task)
Also produce the one-line TASKS.md edit: exact **Status:** line replacement for the completed task.
```

---

## Quick reference — which prompt to use when

| Situation | Use |
|-----------|-----|
| Starting a new Claude Code session | Prompt 1 (Session Opener) |
| Agent confirmed orientation, ready to build | Prompt 2 (Build Prompt for active task) |
| Task complete, need to advance state | Prompt 3 (Thread Manager) |
| Starting a new phase | Prompt 3 to prepare SESSIONSTATE.md, then Prompt 1 in Claude Code |
| Something went wrong | Prompt 3 with current file contents pasted in |
