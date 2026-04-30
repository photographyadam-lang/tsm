# tsm — Phase Task List

> Tasks are ordered by dependency. Do not start a task until all hard deps are met.
> This file is managed by tsm once the tool is built. Until then, update Status lines manually.
> Spec: SPECIFICATION-task-session-manager-v1.3.md

---

## Phase structure

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1 — Foundation** | Package scaffold, all dataclasses/enums, project discovery, test fixtures | Pending |
| **Phase 2 — Parsers** | TASKS.md state machine (core + edge cases), SESSIONSTATE.md, TASKS-COMPLETED.md | Pending |
| **Phase 3 — Shadow & Writers** | Shadow/backup/undo, tasks writer (task+phase level), session writer, completed writer | Pending |
| **Phase 4 — Commands** | All 8 command modules with full test suites | Pending |
| **Phase 5 — CLI Entry Point** | __main__.py, load_project() bootstrap, end-to-end CLI verification | Pending |
| **Phase 6 — TUI** | Textual UI: task tree, detail panel, overlays, app wiring | Pending |

---

# Phase 1 — Foundation

**Status:** Pending

Establish the package skeleton, canonical data model (including LoadedProject and slugify_phase_name), project discovery, and all test fixtures. Nothing in later phases can start until this phase is complete. No logic, no I/O in models.py — pure data definitions only.

---

## Phase 1 tasks

### P1-T01 · Package scaffold and pyproject.toml

**Status:** ✅ Complete
**Complexity:** low
**What:** Create the full package directory structure as specified in §11.1: tsm/, tsm/commands/, tsm/parsers/, tsm/writers/, tsm/ui/, tests/, tests/fixtures/, tests/parsers/, tests/writers/, tests/commands/. Create stub __init__.py files in every package directory. Create pyproject.toml with name="tsm", requires-python=">=3.11", dependencies=["textual>=0.60.0"], and entry point tsm = "tsm.__main__:main" per §11.2. Create stub tsm/__main__.py with a main() function that prints "tsm: not yet implemented" and exits. Implements §11.1 and §11.2.
**Prerequisite:** None.
**Hard deps:** None
**Files:** pyproject.toml, tsm/__init__.py, tsm/__main__.py, tsm/app.py, tsm/models.py, tsm/project.py, tsm/shadow.py, tsm/commands/__init__.py, tsm/parsers/__init__.py, tsm/writers/__init__.py, tsm/ui/__init__.py, tests/__init__.py, tests/parsers/__init__.py, tests/writers/__init__.py, tests/commands/__init__.py
**Reviewer:** Skip
**Done when:**
- `pip install -e .` completes without errors
- `python -m tsm` executes and prints output without ImportError
- All package directories exist with __init__.py files
- `tsm` entry point resolves to `tsm.__main__:main`

### P1-T02 · models.py — dataclasses, enums, LoadedProject, slugify_phase_name

**Status:** ✅ Complete
**Complexity:** medium
**What:** Implement tsm/models.py with all dataclasses, enums, and helper functions defined in §5. Exactly in this order: TaskStatus enum (6 values), TaskComplexity enum (4 values), Task dataclass (14 fields in the exact field order from §5), Phase dataclass, PhaseOverviewRow dataclass, SessionState dataclass, PendingWrite dataclass, ProjectContext dataclass. Then §5.5: slugify_phase_name(name: str, existing_slugs: list[str] | None = None) -> str module-level function using the exact algorithm: lowercase → replace whitespace with hyphens → strip non-alphanumeric-non-hyphen → strip leading/trailing hyphens → collision suffix -2/-3 etc. Then §5.6: LoadedProject dataclass with fields project_context: ProjectContext, phases: list[Phase], phase_overview: list[PhaseOverviewRow], session: SessionState. Implements §5, §5.5, §5.6.
**Prerequisite:** P1-T01 complete.
**Hard deps:** P1-T01
**Files:** tsm/models.py
**Reviewer:** Skip
**Key constraints:**
- Field order in all dataclasses must match §5 exactly — do not add, reorder, or rename fields
- slugify_phase_name() must be a module-level function, not a method on Phase
- Complexity enum is informational only — no conditional logic anywhere in models.py may branch on TaskComplexity values
- LoadedProject fields must be project_context, phases, phase_overview, session — exactly these four, in this order
**Done when:**
- `from tsm.models import Task, Phase, SessionState, LoadedProject, slugify_phase_name, TaskStatus, TaskComplexity` resolves without error
- slugify_phase_name("Assessment Unification", []) == "assessment-unification"
- slugify_phase_name("Phase 1A", []) == "phase-1a"
- slugify_phase_name("Phase 1A", ["phase-1a"]) == "phase-1a-2"
- slugify_phase_name("Phase 1A", ["phase-1a", "phase-1a-2"]) == "phase-1a-3"
- All dataclasses instantiate correctly with keyword arguments matching §5 field names
- TaskStatus has exactly 6 members; TaskComplexity has exactly 4 members

### P1-T03 · project.py — discovery and .gitignore enforcement

**Status:** ✅ Complete
**Complexity:** medium
**What:** Implement tsm/project.py with two public functions. (1) find_project_root(start: Path) -> Path | None: walk up the directory tree from start, checking each directory for the presence of both TASKS.md and SESSIONSTATE.md; stop after checking 3 parent levels (start, start.parent, start.parent.parent, start.parent.parent.parent); return the first matching path or None. (2) ensure_tsm_dir(root: Path) -> ProjectContext: create .tsm/shadow/ and .tsm/backups/ if they do not exist; check .gitignore for .tsm/ entry and append if absent (create .gitignore if missing); print the one-time notice from §3.3 if .gitignore was modified; return a ProjectContext dataclass populated with absolute paths for all fields. Implements §3.2 and §3.3.
**Prerequisite:** P1-T02 complete.
**Hard deps:** P1-T02
**Files:** tsm/project.py, tests/test_project_discovery.py
**Reviewer:** Skip
**Key constraints:**
- Walk up exactly 3 parent levels maximum — do not exceed or parameterize this limit
- .gitignore enforcement must be idempotent — running ensure_tsm_dir twice on the same directory must not duplicate the .tsm/ entry
- find_project_root requires BOTH TASKS.md AND SESSIONSTATE.md to be present — either alone is not sufficient
**Done when:**
- find_project_root returns correct path when called from a subdirectory 1, 2, or 3 levels below a valid project root
- find_project_root returns None when no valid project root exists within 3 levels
- ensure_tsm_dir creates .tsm/shadow/ and .tsm/backups/ when they do not exist
- ensure_tsm_dir running twice on the same directory produces exactly one .tsm/ line in .gitignore
- ensure_tsm_dir on a directory with no .gitignore creates .gitignore containing .tsm/
- ensure_tsm_dir on a directory whose .gitignore already contains .tsm/ makes no changes

### P1-T04 · Test fixtures

**Status:** ✅ Complete
**Complexity:** low
**What:** Create all five test fixture files in tests/fixtures/. Each must cover the specific format variants that the parser tests depend on. TASKS.md: representative file with at least 2 phases, 6 tasks total with mixed statuses (complete, active, pending, blocked), 1 task with multi-line What field, 1 task with multi-line Done when field, 1 task with Key constraints field, 1 task without Key constraints field, 1 task with backtick-wrapped Files paths including a "(new)" suffix, 1 task with em-dash Hard deps, 1 task with "None" Hard deps, 1 task with "See spec §8" in Files, 1 ### Dependency graph block per phase. TASKS_CLEAN.md: minimal valid file, 2 tasks both pending, no errors or warnings. TASKS_ERRORS.md: file with deliberate errors — at least one duplicate task ID and at least one dangling dep reference. SESSIONSTATE.md: canonical format with populated active task, 2 up-next rows (one with Complexity column, one without), 2 completed rows, non-empty out-of-scope section. TASKS-COMPLETED.md: log with one phase section and 2 task rows. Implements §11.1 test fixtures and §12.1 fixture requirements.
**Prerequisite:** None.
**Hard deps:** P1-T01
**Files:** tests/fixtures/TASKS.md, tests/fixtures/TASKS_CLEAN.md, tests/fixtures/TASKS_ERRORS.md, tests/fixtures/SESSIONSTATE.md, tests/fixtures/TASKS-COMPLETED.md
**Reviewer:** Skip
**Key constraints:**
- TASKS_ERRORS.md must contain a duplicate task ID (for VC-01) and a dep pointing to a nonexistent task ID (for VC-02) — document these deliberately in a comment at the top of that fixture
- tests/fixtures/SESSIONSTATE.md last_updated timestamp must use the full YYYY-MM-DDTHH:MM format (not the legacy date-only format) so it does not trigger VC-12 when used in clean-pass tests
**Done when:**
- All 5 fixture files exist and are valid UTF-8 text
- TASKS.md fixture contains all 12 format variants enumerated in What above
- TASKS_ERRORS.md contains at least 1 duplicate task ID and 1 dangling dep
- SESSIONSTATE.md fixture parses without error when manually inspected against the §4.2 format rules
- TASKS-COMPLETED.md fixture contains a ## phase section heading and at least 2 table rows

### Dependency graph

```
P1-T01
  └── P1-T02
        └── P1-T03
P1-T01
  └── P1-T04
```

---

# Phase 2 — Parsers

**Status:** Pending

Build all three parsers in dependency order. The TASKS.md parser is split across two tasks: core field parsing first, then the edge-case extensions. All §12.2 and §12.3 tests must be green before Phase 3 begins. No command logic is permitted until parsers are complete.

---

## Phase 2 tasks

### P2-T01 · tasks_parser.py — state machine skeleton and core field parsing

**Status:** ✅ Complete
**Complexity:** high
**What:** Implement tsm/parsers/tasks_parser.py with parse_tasks_file(path: Path) -> tuple[list[PhaseOverviewRow], list[Phase]]. Build the 7-state line iterator state machine from §9.2: PREAMBLE, PHASE_STRUCTURE_TABLE, BETWEEN_PHASES, PHASE_HEADER, SUBPHASE_HEADER, TASK_BLOCK, DEP_GRAPH. Core field parsing in this task: all 6 status token variants from §4.1.3 (including emoji variants and **Active** bold-wrapped), task ID and title extraction from ### heading using the · separator, hard_deps parsing for all variants in §4.1.5 (None/None./em-dash/blank → []; comma-split otherwise), files parsing for all variants in §4.1.6 (comma-split, strip backticks, strip "(new)" suffix, "See spec" passthrough, blank → []), multiline What and Done when accumulation until next ** field label or structural boundary, raw_block capture of the full original source text for each task, DEP_GRAPH state that recognises ### Dependency graph heading, stores fenced block in Phase.dependency_graph_raw, and does not emit a Task object. Phase.id is set by calling slugify_phase_name() imported from models.py — no inline slug logic. Implements §9.2 core path and §9.5 edge cases for status/deps/files/multiline.
**Prerequisite:** P1-T04 complete.
**Hard deps:** P1-T02, P1-T04
**Files:** tsm/parsers/tasks_parser.py, tests/parsers/test_tasks_parser.py
**Reviewer:** Skip
**Key constraints:**
- Do not use a general Markdown parser library — line iterator state machine only, per §9.1
- ### Dependency graph blocks must enter DEP_GRAPH state and must NOT produce a Task object — this is a named test requirement
- raw_block must capture the full original source text of the task block exactly as it appeared in the file
- Phase.id must be set by calling slugify_phase_name() from models — never reimplement slug logic in the parser
**Done when:**
- test_parse_status_complete passes
- test_parse_status_active_bold passes
- test_parse_status_pending passes
- test_parse_status_blocked_lock passes
- test_parse_status_blocked_cross passes
- test_parse_hard_deps_multiple passes
- test_parse_hard_deps_em_dash passes
- test_parse_hard_deps_none_text passes
- test_parse_hard_deps_none_dot passes
- test_parse_files_backtick_new passes
- test_parse_files_multiple passes
- test_parse_files_see_spec passes
- test_parse_files_blank passes
- test_parse_multiline_what passes
- test_parse_multiline_done_when passes
- test_parse_phase_structure_table passes
- test_parse_multi_phase_file passes
- test_parse_raw_block_preserved passes
- test_task_id_title_extraction passes
- test_dep_graph_not_parsed_as_task passes
- test_dep_graph_raw_preserved passes

### P2-T02 · tasks_parser.py — complexity, key_constraints, subphase tracking

**Status:** ✅ Complete
**Complexity:** medium
**What:** Extend tsm/parsers/tasks_parser.py with three additions to the TASK_BLOCK field collection logic. (1) Complexity parsing (§4.1.4a): match **Complexity:** field value against high/medium/low/unset; unknown values silently default to TaskComplexity.UNSET and log a warning (do not raise); absent field defaults to TaskComplexity.UNSET. (2) Key constraints parsing (§4.1.9): **Key constraints:** is an optional field; if absent, key_constraints = [] with no error; if present with no bullet lines, key_constraints = []; if present with bullet lines, strip leading "- " from each line and collect as list of strings. (3) Subphase tracking: when the parser is in SUBPHASE_HEADER state (triggered by a ## heading that is not "Phase structure"), record the current subphase heading text; assign it to Task.subphase for all tasks collected until the next ## or # heading. No state machine changes — all additions are within existing field collection logic. Implements §9.5 complexity/key_constraints/subphase edge cases and §4.1.4a.
**Prerequisite:** P2-T01 complete with all 21 tests passing.
**Hard deps:** P2-T01
**Files:** tsm/parsers/tasks_parser.py, tests/parsers/test_tasks_parser.py
**Reviewer:** Skip
**Key constraints:**
- Unknown Complexity value must log a warning and return UNSET — must not raise an exception or corrupt the task object
- test_vc11_does_not_fire_for_absent_key_constraints belongs in this task's test suite — verify parser returns key_constraints=[] without VC-11 signal
- All 21 tests from P2-T01 must continue to pass after these additions
**Done when:**
- test_parse_complexity_high passes
- test_parse_complexity_low passes
- test_parse_complexity_unset_explicit passes
- test_parse_complexity_absent passes
- test_parse_complexity_unknown_value passes
- test_parse_key_constraints_present passes
- test_parse_key_constraints_absent passes
- test_parse_key_constraints_empty_field passes
- test_vc11_does_not_fire_for_absent_key_constraints passes
- All 21 tests from P2-T01 continue to pass (pytest tests/parsers/test_tasks_parser.py — 30 tests total, 0 failures)

### P2-T03 · session_parser.py

**Status:** ✅ Complete
**Complexity:** medium
**What:** Implement tsm/parsers/session_parser.py with parse_session_file(path: Path) -> SessionState. Section-based approach per §9.3: split file content on --- horizontal rule lines to identify section blocks; identify each block by its ## heading text. Parse *Last updated:* from the first non-blank line using two format attempts: datetime.strptime(value, "%Y-%m-%dT%H:%M") first, then datetime.strptime(value, "%Y-%m-%d") with time set to 00:00 for legacy date-only format (§9.5). Parse ## Active phase into active_phase_name and active_phase_spec strings. Parse ## Active task: store full block content verbatim in active_task_raw; also extract task ID and title from the **<ID> — <title>** bold line for SessionState.active_task stub; parse the "- Complexity:" bullet for TaskComplexity value; if block contains only [none] or is empty, set active_task = None (§4.2.3). Parse ## Up next as 5-column pipe-delimited table; if Complexity column is absent, default all rows to TaskComplexity.UNSET (§9.5). Parse ## Completed tasks as 3-column table. Parse ## Out of scope: store verbatim in out_of_scope_raw. Implements §9.3 and all §9.5 SESSIONSTATE edge cases.
**Prerequisite:** P1-T04 complete.
**Hard deps:** P1-T02, P1-T04
**Files:** tsm/parsers/session_parser.py, tests/parsers/test_session_parser.py
**Reviewer:** Skip
**Done when:**
- test_parse_last_updated passes
- test_parse_last_updated_legacy_date passes
- test_parse_active_phase passes
- test_parse_active_task_id passes
- test_parse_active_task_complexity passes
- test_parse_up_next_table passes
- test_parse_up_next_complexity_column passes
- test_parse_up_next_no_complexity_column passes
- test_parse_completed_table passes
- test_parse_out_of_scope_verbatim passes
- test_parse_active_task_unset_none passes
- test_parse_active_task_unset_blank passes

### P2-T04 · completed_parser.py

**Status:** ✅ Complete
**Complexity:** low
**What:** Implement tsm/parsers/completed_parser.py with parse_completed_file(path: Path) -> list[tuple[str, list[dict]]]. Identify phase sections by ## headings. Collect rows from the pipe-delimited table under each heading into a list of dicts with keys: task, description, complexity, commit, notes. Return a list of (phase_name, rows) tuples in file order. Handle missing file gracefully — return [] instead of raising. Implements §9.4 parsing half.
**Prerequisite:** P1-T04 complete.
**Hard deps:** P1-T02, P1-T04
**Files:** tsm/parsers/completed_parser.py, tests/parsers/test_completed_parser.py
**Reviewer:** Skip
**Done when:**
- parse_completed_file on the TASKS-COMPLETED.md fixture returns a list with at least 1 (phase_name, rows) tuple
- parse_completed_file on a nonexistent path returns [] without raising
- Each row dict contains exactly 5 keys: task, description, complexity, commit, notes

### Dependency graph

```
P1-T02 ──┐
P1-T04 ──┼──► P2-T01 ──► P2-T02
          │
P1-T02 ──┼──► P2-T03
P1-T04 ──┘
P1-T02 ──► P2-T04
P1-T04 ──► P2-T04
```

---

# Phase 3 — Shadow & Writers

**Status:** Pending

Build the write infrastructure. Shadow/backup comes first so writers can stage to it. The tasks_writer covers both task-level and phase-level status updates — these are two distinct functions in the same module. The dual write-strategy constraint (targeted replacement for TASKS.md, full reconstruction for SESSIONSTATE.md) must be enforced by module boundaries: tasks_writer.py exposes only targeted-replacement functions; session_writer.py exposes only the full renderer.

---

## Phase 3 tasks

### P3-T01 · shadow.py — stage, apply, backup, prune, history log

**Status:** ✅ Complete
**Complexity:** high
**What:** Implement tsm/shadow.py with the core shadow write pipeline from §6. Functions needed: stage(pending_write: PendingWrite) -> None — write content to the shadow path; apply(pending_writes: list[PendingWrite]) -> None — for each PendingWrite in order: create timestamped .bak backup in backups/ using format <filename>.<YYYY-MM-DDTHH-MM>.bak (colons replaced with hyphens, seconds omitted), use os.replace() to atomically move shadow file to live path, prune backups for this filename keeping the 5 most recent by mtime (delete older ones), append entry to history.log in the pipe-delimited format from §6.4; confirm_prompt(pending_writes: list[PendingWrite], yes: bool = False) -> bool — if yes=True, print the summary block from §6.2 to stdout and return True immediately without reading stdin; if yes=False (default), print the summary block and read Y/n from stdin, returning True for Y/Enter and False for n. The yes parameter is the only way auto-confirm is triggered — never default it to True internally. Implements §6.1–§6.4 and §6.2 --yes flag behaviour.
**Prerequisite:** P1-T03 complete.
**Hard deps:** P1-T02, P1-T03
**Files:** tsm/shadow.py, tests/test_shadow.py
**Reviewer:** Skip
**Key constraints:**
- Use os.replace() for atomic live-file writes — never shutil.copy or open/write directly to the live path
- Backup filename format is <filename>.<YYYY-MM-DDTHH-MM>.bak with colons replaced by hyphens and seconds omitted
- Backup pruning must sort by mtime, not lexicographic order — the 5 most recently modified .bak files are kept
- confirm_prompt must never default yes=True — auto-confirm is only triggered when the caller explicitly passes yes=True
**Done when:**
- test_shadow_creates_backup_on_apply passes
- test_shadow_prunes_to_5_backups passes
- test_shadow_gitignore_created passes
- test_shadow_gitignore_appended passes
- test_shadow_gitignore_idempotent passes
- test_confirm_prompt_yes_flag passes: confirm_prompt(pending_writes, yes=True) prints summary to stdout and returns True without reading stdin (use monkeypatch to verify stdin is never touched)

### P3-T02 · shadow.py — undo

**Status:** ✅ Complete
**Complexity:** medium
**What:** Extend tsm/shadow.py with the undo() function from §6.5. Algorithm: read history.log and find the last line that does not contain [undone]; for each filename listed on that line, find the most recent .bak file in backups/ and copy it to the live path; append [undone] to the end of that log line (in-place edit of the log file). Edge cases: if history.log is empty or all entries are already marked [undone], print "Nothing to undo." and return. If undo() is called again immediately after a successful undo (i.e., there is no non-[undone] entry), print "Nothing to undo." — this is the double-undo case. Undo must not create a new backup, must not write to shadow files, and must not add a new history.log entry. Implements §6.5.
**Prerequisite:** P3-T01 complete with all 5 shadow tests passing.
**Hard deps:** P3-T01
**Files:** tsm/shadow.py, tests/test_shadow.py
**Reviewer:** Skip
**Key constraints:**
- Undo is single-level only — do not implement multi-level undo even if it seems straightforward
- Undo must not create a new backup — it restores from the backup created at apply time
- Undo must not add a new history.log entry — it only modifies the existing entry by appending [undone]
**Done when:**
- test_shadow_undo_restores_live_file passes
- test_shadow_undo_no_history passes
- test_shadow_double_undo passes
- All 5 tests from P3-T01 continue to pass

### P3-T03 · tasks_writer.py — targeted status replacement (task-level and phase-level)

**Status:** ✅ Complete
**Complexity:** medium
**What:** Implement tsm/writers/tasks_writer.py with two public functions. (1) update_task_status(content: str, task_id: str, new_status: str) -> str: scan the file content for the line matching ### <task_id> ·, then within that task block find the **Status:** line and replace only that line with the new value; return the full file content with only that one line changed. (2) update_phase_status(content: str, phase_heading_text: str, new_status: str) -> str: scan for the H1 line # <phase_heading_text>, then within the phase header block (lines between that H1 and the first --- or next #) find the **Status:** line and replace only that line; return the full file content with only that one line changed. Both functions operate on raw string content (not parsed data model) and must produce output where all bytes outside the replaced line are identical to the input. A helper write_tasks_file(content: str, shadow_path: str) -> None writes content to the shadow path. Implements §9.2 write-back strategy (both task-level and phase-level variants from the v1.3 spec update).
**Prerequisite:** P2-T01 and P2-T02 complete.
**Hard deps:** P2-T02
**Files:** tsm/writers/tasks_writer.py, tests/writers/test_tasks_writer.py
**Reviewer:** Skip
**Key constraints:**
- Never re-serialize TASKS.md from the data model — targeted line replacement only; this is the sole purpose of this module
- update_phase_status targets the **Status:** line inside the phase header block (between the # heading and the first ---), NOT a task-level **Status:** line
- Both functions must raise a ValueError with a clear message if the target task ID or phase heading is not found in the content
**Done when:**
- update_task_status on fixture content → re-parse with tasks_parser → task.status equals the new value; all other task raw_blocks are identical to the originals
- update_phase_status on fixture content → re-parse with tasks_parser → phase.status equals the new value; all task raw_blocks are identical to the originals
- Bytes outside the replaced **Status:** line are identical before and after for both functions (verified with a byte diff)
- Both functions raise ValueError when given a task_id or phase_heading_text not present in the content

### P3-T04 · session_writer.py — full reconstruction renderer

**Status:** ✅ Complete
**Complexity:** medium
**What:** Implement tsm/writers/session_writer.py with render_sessionstate(state: SessionState) -> str. Full reconstruction per §9.3 renderer invariants: emit *Last updated: YYYY-MM-DDTHH:MM* using datetime.now() at render time (not at command invocation time); emit --- between every section; emit ## Active phase section from state.active_phase_name and state.active_phase_spec; emit ## Completed tasks as 3-column pipe-delimited table; emit ## Active task section by re-emitting state.active_task_raw verbatim (caller has already updated this field if a new task was promoted); emit ## Up next as 5-column pipe-delimited table including the Complexity column; emit ## Out of scope by re-emitting state.out_of_scope_raw verbatim. Also implement write_session_file(content: str, shadow_path: str) -> None. Implements §9.3 SESSIONSTATE.md write-back strategy.
**Prerequisite:** P2-T03 complete.
**Hard deps:** P2-T03
**Files:** tsm/writers/session_writer.py, tests/writers/test_session_writer.py
**Reviewer:** Skip
**Key constraints:**
- Never use targeted line replacement for SESSIONSTATE.md — always full reconstruction; this is the sole purpose of this module
- out_of_scope_raw must be re-emitted exactly as stored — no normalization, stripping, or modification of any kind
- active_task_raw must be re-emitted verbatim unless the calling command has explicitly replaced it with a new Task.raw_block value
**Done when:**
- render_sessionstate(state) → write to temp file → parse_session_file → returned SessionState fields match original state for all fields
- out_of_scope_raw survives round-trip byte-for-byte
- *Last updated:* in rendered output reflects the time of the render call, not an earlier time
- ## Up next table in rendered output contains the Complexity column

### P3-T05 · completed_writer.py — append writer

**Status:** ✅ Complete
**Complexity:** low
**What:** Implement tsm/writers/completed_writer.py with two public functions. (1) append_task_row(path: Path, shadow_path: str, phase_name: str, task_id: str, title: str, complexity: str, commit: str, notes: str) -> str: load existing file content (or create header if file missing), find the ## <phase_name> section (last occurrence), append a new table row, return the full reconstructed content string and write it to shadow_path. If the phase section does not exist, append a new ## <phase_name> section with the 5-column header row before appending the data row. (2) append_phase_marker(path: Path, shadow_path: str, phase_name: str, date: str) -> str: find the phase section and append the line **Phase complete: YYYY-MM-DD** after the last row. Both functions write to shadow_path, not to the live file. Implements §9.4 writing half.
**Prerequisite:** P2-T04 complete.
**Hard deps:** P2-T04
**Files:** tsm/writers/completed_writer.py
**Reviewer:** Skip
**Done when:**
- append_task_row on a new path creates the file with # Completed Tasks Log header, ---, the ## phase section, and the row
- append_task_row on an existing file with a matching phase section appends the row to that section without creating a duplicate section header
- append_task_row on an existing file with no matching phase section creates a new phase section at the end of the file
- append_phase_marker appends **Phase complete: YYYY-MM-DD** after the last row in the correct phase section

### Dependency graph

```
P1-T02 ──► P3-T01
P1-T03 ──► P3-T01
P3-T01 ──► P3-T02
P2-T02 ──► P3-T03
P2-T03 ──► P3-T04
P2-T04 ──► P3-T05
```

---

# Phase 4 — Commands

**Status:** Active

Build all 8 command modules. Every command function signature is (ctx: LoadedProject) -> list[PendingWrite], except help (no ctx, returns None) and new_project (target_dir: Path, name: str). Commands must not re-parse files — they receive a LoadedProject and work from it. Commands return PendingWrite lists; they do not call shadow.apply directly.

---

## Phase 4 tasks

### P4-T01 · commands/advance.py

**Status:** ✅ Complete
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

### P4-T02 · commands/init_phase.py

**Status:** ✅ Complete
**Complexity:** medium
**What:** Implement tsm/commands/init_phase.py with init_phase(ctx: LoadedProject, phase_id: str) -> list[PendingWrite]. Match phase_id case-insensitively against Phase.id slugs in ctx.phases. Precondition checks per §7.2: phase exists (abort with error if not), phase has at least one non-complete task (abort if all complete). Active task selection: first task in file order whose hard_deps list is empty or all deps are complete in ctx.phases; if no such task, active_task = [none] and print the §7.2 warning. Build 1 PendingWrite: SESSIONSTATE.md — set active_phase_name, active_task_raw, up_next (all non-active pending tasks for the phase), clear completed table, update last_updated; render via session_writer. Add HELP_TEXT static string constant. Implements §7.2.
**Prerequisite:** P3-T04 complete.
**Hard deps:** P3-T04
**Files:** tsm/commands/init_phase.py, tests/commands/test_init_phase.py
**Reviewer:** Skip
**Done when:**
- test_init_phase_sets_active_task passes
- test_init_phase_no_ready_task passes
- test_init_phase_unknown_id passes

### P4-T03 · commands/complete_phase.py

**Status:** ✅ Complete
**Complexity:** medium
**What:** Implement tsm/commands/complete_phase.py with complete_phase(ctx: LoadedProject) -> list[PendingWrite]. Precondition: all tasks in the current phase (matched by phase_id from ctx.session.active_phase_name) have status complete in ctx.phases; if not, abort with the §7.4 error listing incomplete task IDs. Next phase detection: iterate ctx.phases in order, find the first phase after the current one with status != complete; if none, next phase is [none]. Build 3 PendingWrite objects: (1) SESSIONSTATE.md — rotate to next phase (or [none]), set new active task, populate up_next, clear completed; (2) TASKS.md — call update_phase_status on live content targeting the completed phase's heading text; (3) TASKS-COMPLETED.md — call append_phase_marker. Add HELP_TEXT static string constant. Implements §7.4.
**Prerequisite:** P4-T01 complete.
**Hard deps:** P3-T03, P3-T04, P3-T05
**Files:** tsm/commands/complete_phase.py, tests/commands/test_complete_phase.py
**Reviewer:** Skip
**Key constraints:**
- Phase status update in TASKS.md must use update_phase_status (not update_task_status) — it targets the **Status:** line under the # phase heading, per §9.2
**Done when:**
- test_complete_phase_all_done passes
- test_complete_phase_incomplete_tasks passes
- test_complete_phase_no_next_phase passes

### P4-T04 · commands/vibe_check.py

**Status:** ✅ Complete
**Complexity:** medium
**What:** Implement tsm/commands/vibe_check.py with vibe_check(ctx: LoadedProject) -> None (prints directly; read-only, no PendingWrite). Implement all 13 validation rules VC-01 through VC-13 from §7.5. Rule notes: VC-11 warning fires for missing required fields (Status, Complexity, What, Prerequisite, Hard deps, Files, Reviewer, Done when) but NOT for absent Key constraints (absence is valid); VC-13 warning fires only for tasks in Active or Up next, not for completed tasks; VC-12 comparison must use datetime arithmetic, not date subtraction (7 days threshold). Output format matches the §7.5 output block exactly: header with timestamp, error count, warning count, grouped ERRORS then WARNINGS sections. Add HELP_TEXT static string constant. Implements §7.5.
**Prerequisite:** All Phase 2 parsers complete.
**Hard deps:** P2-T02, P2-T03
**Files:** tsm/commands/vibe_check.py, tests/commands/test_vibe_check.py
**Reviewer:** Skip
**Done when:**
- test_vibe_check_clean passes
- test_vibe_check_vc01_duplicate_id passes
- test_vibe_check_vc02_dangling_dep passes
- test_vibe_check_vc03_active_is_complete passes
- test_vibe_check_vc05_unmet_dep_in_up_next passes
- test_vibe_check_vc11_missing_field passes
- test_vibe_check_vc13_unset_complexity_active passes
- test_vibe_check_vc13_unset_complexity_up_next passes
- test_vibe_check_vc13_suppressed_for_complete passes
- test_vibe_check_vc12_datetime_comparison passes
- test_vibe_check_vc12_same_day_no_warning passes

### P4-T05 · commands/status.py and commands/undo.py

**Status:** ✅ Complete
**Complexity:** low
**What:** Implement tsm/commands/status.py with status(ctx: LoadedProject) -> None — read-only, prints the §7.6 formatted output to stdout. Print Phase, Spec, Updated, Active task block (with Complexity and Hard dep status icons), Up next summary line, and Completed count. Implement tsm/commands/undo.py with undo(ctx: ProjectContext) -> None — delegates directly to shadow.undo(ctx.project_context). Add HELP_TEXT static string constant to both modules. Implements §7.6 and §7.7.
**Prerequisite:** All Phase 3 tasks complete.
**Hard deps:** P3-T02, P3-T04
**Files:** tsm/commands/status.py, tsm/commands/undo.py
**Reviewer:** Skip
**Done when:**
- tsm status prints all 5 sections (Phase, Spec, Updated, Active task, Up next, Completed) correctly when run against a project built from the test fixtures
- Active task block in status output shows Complexity value and Hard dep status icons per §7.6
- tsm undo against a fixture project with a history entry delegates to shadow.undo without error
- tsm undo against a project with no history prints "Nothing to undo."

### P4-T06 · commands/help.py

**Status:** ✅ Complete
**Complexity:** low
**What:** Implement tsm/commands/help.py with help_command(command: str | None = None) -> None — read-only, no project root required. Three variants per §7.8: (1) no arg → print the full command list in the §7.8 format; (2) specific command name → import and print that command module's HELP_TEXT constant; (3) unknown command name → print "Unknown command: <name>". The list of known commands is the hardcoded set of 8 names. HELP_TEXT in this module contains the overall tsm help header and command list. All per-command HELP_TEXT constants are defined in their respective command modules (advance.py, init_phase.py, complete_phase.py, vibe_check.py, status.py, undo.py, new_project.py) — help.py imports them at call time. Implements §7.8.
**Prerequisite:** All other command module stubs must exist with HELP_TEXT constants defined.
**Hard deps:** P4-T01, P4-T02, P4-T03, P4-T04, P4-T05
**Files:** tsm/commands/help.py, tests/commands/test_help.py
**Reviewer:** Skip
**Key constraints:**
- Help text must be implemented as static HELP_TEXT string constants in each command module — not generated from code, docstrings, or argparse
- help_command does not require a project root and must not call find_project_root
**Done when:**
- test_help_lists_all_commands passes
- test_help_specific_command passes (output for tsm help advance contains "Preconditions", "Writes", "Example")
- test_help_unknown_command passes
- test_help_no_project_root_required passes

### P4-T07 · commands/new_project.py

**Status:** ✅ Complete
**Complexity:** medium
**What:** Implement tsm/commands/new_project.py with new_project(target_dir: Path, name: str | None = None) -> None. Abort conditions (§7.9): if TASKS.md or SESSIONSTATE.md already exist in target_dir, print the §7.9 error and return without creating anything. If name is None, prompt the user; default to target_dir.name if Enter is pressed with no input. Create all 5 files in target_dir using the exact template content from §7.9, substituting <Project Name> with the resolved name. Create .tsm/ directory and update .gitignore identically to first-run behavior (§3.3). Print the §7.9 post-creation output. Add HELP_TEXT static string constant. The generated TASKS.md and SESSIONSTATE.md must parse without errors via tasks_parser and session_parser (round-trip parsability). Implements §7.9.
**Prerequisite:** P2-T02 and P2-T03 complete.
**Hard deps:** P2-T02, P2-T03
**Files:** tsm/commands/new_project.py, tests/commands/test_new_project.py
**Reviewer:** Skip
**Done when:**
- test_new_project_creates_all_files passes
- test_new_project_with_name_flag passes
- test_new_project_prompts_for_name passes
- test_new_project_aborts_if_tasks_exists passes
- test_new_project_aborts_if_sessionstate_exists passes
- test_new_project_creates_gitignore_entry passes
- test_new_project_tasks_md_parseable passes
- test_new_project_sessionstate_parseable passes

### Dependency graph

```
P3-T03 ──┐
P3-T04 ──┼──► P4-T01
P3-T05 ──┘
P3-T04 ──► P4-T02
P3-T03 ──┐
P3-T04 ──┼──► P4-T03
P3-T05 ──┘
P2-T02 ──► P4-T04
P2-T03 ──► P4-T04
P3-T02 ──► P4-T05
P3-T04 ──► P4-T05
P4-T01 ──┐
P4-T02 ──┤
P4-T03 ──┤──► P4-T06
P4-T04 ──┤
P4-T05 ──┘
P2-T02 ──► P4-T07
P2-T03 ──► P4-T07
```

---

# Phase 5 — CLI Entry Point

**Status:** Pending

Wire all command modules through __main__.py with the load_project() bootstrap. This is also where the LoadedProject construction contract from §5.6 is implemented. Every command must be verified working via tsm <command> from the CLI before Phase 6 begins.

---

## Phase 5 tasks

### P5-T01 · __main__.py — CLI wiring, load_project bootstrap, --yes flag, exit codes

**Status:** Active
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

### Dependency graph

```
P4-T07 ──► P5-T01
```

---

# Phase 6 — TUI

**Status:** Pending

Build the Textual TUI as a wrapper around the already-tested command layer. Build in sub-component order: left panel, right panel, overlays, then app wiring. No TUI-only code paths — all business logic stays in the command layer.

---

## Phase 6 tasks

### P6-T01 · ui/task_tree.py — left panel

**Status:** Pending
**Complexity:** medium
**What:** Implement tsm/ui/task_tree.py with TaskTree(Widget). Uses Textual Tree widget. Phases are top-level tree nodes collapsed by default; the phase containing the active task is auto-expanded on mount. Task rows display: status icon + Task ID + title truncated to 30 characters. Active task is rendered in the app accent color; complete tasks and phases are rendered in a muted style. Keyboard navigation: arrow keys move through nodes, Enter on a phase node expands or collapses it, Enter on a task node emits a TaskSelected message (or equivalent reactive) for the right panel to display. Accepts a LoadedProject as its data source. Implements §8.2.
**Prerequisite:** P5-T01 complete.
**Hard deps:** P5-T01
**Files:** tsm/ui/task_tree.py
**Reviewer:** Skip
**Done when:**
- TaskTree mounts without error when given a LoadedProject built from the test fixture
- The phase containing the active task is expanded; all other phases are collapsed
- Complete tasks and phases render visually distinct from pending/active ones
- Selecting a task node emits the expected message or updates the expected reactive

### P6-T02 · ui/task_detail.py — right panel

**Status:** Pending
**Complexity:** medium
**What:** Implement tsm/ui/task_detail.py with TaskDetail(Widget). Displays full task metadata per §8.3: Task ID, Title, Status, Phase, Complexity with color indicator (🔴 high / 🟡 medium / 🟢 low / ⚪ unset), Hard deps each shown as <ID> <status-icon> using live status from the LoadedProject phases, Reviewer, Files one per line, Key constraints as a bullet list (omitted entirely when task.key_constraints == []), Done when word-wrapped. Accepts a Task and the full phases list for dep status lookup. Implements §8.3.
**Prerequisite:** P6-T01 complete.
**Hard deps:** P6-T01
**Files:** tsm/ui/task_detail.py
**Reviewer:** Skip
**Done when:**
- TaskDetail renders all fields for a high-complexity task with key constraints present
- Key constraints section is absent entirely (no heading, no empty list) when task.key_constraints == []
- All 4 Complexity color indicators (🔴 🟡 🟢 ⚪) render correctly for the corresponding TaskComplexity values
- Hard dep entries show the live status icon from the passed phases list

### P6-T03 · ui/confirm_overlay.py — confirm-to-apply modal

**Status:** Pending
**Complexity:** medium
**What:** Implement tsm/ui/confirm_overlay.py with ConfirmOverlay(ModalScreen[bool]). Displays the PendingWrite summary — the target_file and summary_lines from each PendingWrite in the list — in the §6.2 format. Responds to y/Y keys and a rendered [Y] Apply button → dismisses with True. Responds to n/N/Escape keys and a rendered [N] Discard button → dismisses with False. The caller receives the bool result via Textual's push_screen_with_result pattern. Implements §8.5.
**Prerequisite:** P6-T01 complete.
**Hard deps:** P6-T01
**Files:** tsm/ui/confirm_overlay.py
**Reviewer:** Skip
**Done when:**
- ConfirmOverlay displays all summary_lines from a list of 3 PendingWrites
- y/Y keypress dismisses with True
- n/N/Escape keypress dismisses with False
- [Y] Apply and [N] Discard buttons trigger the same results as their key equivalents

### P6-T04 · ui/vibe_panel.py and ui/help_panel.py

**Status:** Pending
**Complexity:** low
**What:** Implement tsm/ui/vibe_panel.py with VibecheckPanel(Widget): scrollable list replacing the right panel when vibe check is active; errors rendered in red, warnings in yellow, in the §7.5 output format; Escape or q dismisses and signals the app to restore TaskDetail. Implement tsm/ui/help_panel.py with HelpPanel(Widget): read-only scrollable panel displaying the full tsm help output text (identical content to CLI tsm help); Escape or q dismisses and signals the app to restore TaskDetail. Both panels are rendered in the right panel slot, replacing TaskDetail while active. Implements §8.6 and §8.7.
**Prerequisite:** P6-T02 complete.
**Hard deps:** P6-T02
**Files:** tsm/ui/vibe_panel.py, tsm/ui/help_panel.py
**Reviewer:** Skip
**Done when:**
- VibecheckPanel renders errors before warnings; error rows are visually distinct (red) from warning rows (yellow)
- HelpPanel content is identical to the output of help_command() from commands/help.py
- Escape dismisses both panels and restores TaskDetail in the right panel slot

### P6-T05 · app.py — full TUI wiring

**Status:** Pending
**Complexity:** high
**What:** Implement tsm/app.py with TsmApp(App). Compose two-panel layout: left panel hosts TaskTree, right panel hosts TaskDetail (default), VibecheckPanel (when vibe-check active), or HelpPanel (when help active). Fixed command bar footer per §8.1. Keybindings per §8.4: a → advance (prompt for commit message inline or via Input widget, then show ConfirmOverlay), i → init-phase (prompt for phase ID, then show ConfirmOverlay), c → complete-phase (show ConfirmOverlay), v → vibe-check (swap right panel to VibecheckPanel), u → undo (call shadow.undo directly, refresh), s → status (print to CLI or show in a read-only panel), ? → swap right panel to HelpPanel, q → quit. Context-aware command bar greying (§8.4): init-phase button greyed when active_task is set; complete-phase button greyed when any phase tasks are not complete; undo button greyed when history log has no undoable entry. After any write command applies, reload LoadedProject from disk and refresh both panels. Implements §8.1–§8.5.
**Prerequisite:** All P6-T01 through P6-T04 complete.
**Hard deps:** P6-T04
**Files:** tsm/app.py
**Reviewer:** Skip
**Key constraints:**
- All commands must already work via CLI before being wired into the TUI — do not add TUI-only code paths or bypass the command layer
- Context-aware greying is display-only — command functions still perform their own precondition checks; a greyed button that is somehow triggered must still abort cleanly
- After any write command applies, call load_project() again and refresh both panels from the new LoadedProject — do not mutate in-place
**Done when:**
- TUI launches without error against a valid project directory (tsm with no subcommand)
- All 8 keybindings (a, i, c, v, u, s, ?, q) dispatch to the correct handler
- ConfirmOverlay appears for advance, init-phase, and complete-phase; applying updates both panels
- Command bar greys out init-phase when active task is set
- Command bar greys out complete-phase when any tasks in the current phase are not complete
- Command bar greys out undo when history log is empty or all entries are [undone]

### Dependency graph

```
P5-T01 ──► P6-T01 ──► P6-T02 ──► P6-T03
                              └──► P6-T04
P6-T03 ──┐
P6-T04 ──┴──► P6-T05
```

---
