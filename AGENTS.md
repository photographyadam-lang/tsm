# tsm — Agent Rules

> Read this file at the start of every session before reading SESSIONSTATE.md.
> These rules apply to all AI coding agents working on this project.
> **Current spec:** SPECIFICATION-task-session-manager-v1.6.md

---

## Project overview

`tsm` (Task and Session State Manager) is a locally-run Python CLI/TUI application that manages agentic coding workflow state across projects. It reads and writes three markdown files — TASKS.md, SESSIONSTATE.md, TASKS-COMPLETED.md — using a shadow-directory write model (stage → confirm → apply → backup → log) so all changes are reviewed before being applied. It also scaffolds new projects, provides integrity validation, and (Phase 7) supports LLM-assisted import of existing files, phase/task CRUD, file repair, state sync, and a live dependency engine.

---

## Stack

- **Python 3.11+** — use `list[str]`, `str | None`, `match` syntax freely; no `from __future__ import annotations` needed
- **Textual >= 0.60.0** — only UI dependency; pin this version
- **tomllib** — stdlib (Python 3.11+); used in `import_cmd.py` only for reading `.tsm/config.toml`
- **anthropic** — used in `import_cmd.py` only; never imported anywhere else in the codebase
- **No other dependencies** — no other LLM libraries, no network libraries, no Markdown parser libraries
- **pytest** — for all tests; no other test framework

---

## Architecture rules

These are hard constraints. Do not work around them.

**LLM and network calls are permitted in `import_cmd.py` only.**
No other module may import `anthropic`, `requests`, `httpx`, or any network library. `import_cmd.py` reads the API key from `.tsm/config.toml` via `tomllib` only — never from environment variables or sys.argv. All other commands are fully deterministic. Nothing leaves the machine except through `import_cmd.py`.

**No general Markdown parser libraries.**
All three file parsers use a custom line-iterator state machine (§9.2). Do not import markdown, mistune, commonmark, or any Markdown parsing library.

**TASKS.md write constraint.**
`tsm` has two classes of TASKS.md write operation — never mix them:
- **Status-only updates** (`advance`, `complete-phase`): use `update_task_status()` and `update_phase_status()` — targeted single-line replacement; all other bytes unchanged
- **Structural operations** (Phase 7 CRUD): use `insert_phase_block()`, `remove_phase_block()`, `insert_task_block()`, `remove_task_block()`, `reorder_phase_blocks()`, `reorder_task_blocks()`, `update_task_field()` — operate on raw string content; never re-serialize from the data model
- Never call `session_writer.render_sessionstate()` on TASKS.md content
- The `### Dependency graph` fenced blocks are preserved verbatim — never regenerated

**SESSIONSTATE.md write constraint — full reconstruction only.**
All writes to SESSIONSTATE.md use `session_writer.render_sessionstate(state)`. Never use targeted line replacement on SESSIONSTATE.md. `active_task_raw` is re-emitted verbatim unless a command explicitly promotes a new task. `out_of_scope_raw` is never modified.

**`raw_block` is the source of truth for `## Active task`.**
The `## Active task` section in SESSIONSTATE.md is the verbatim `Task.raw_block` from TASKS.md — the full `### ID · title` block with `**Field:**` syntax. Never construct this from scratch or serialize from Task dataclass fields.

**Dependency pre-write gate (Phase 7 commands only).**
All Phase 7 write commands call `check_deps()` on the **proposed in-memory state** after applying the intended transformation, but before staging writes. For remove operations this means checking the state *after* the task/phase has been removed from memory. If `check_deps()` returns errors: abort with exit 1 unless `--force` is passed (remove commands only).

**`LoadedProject` is built once in `__main__.py`.**
Commands receive a `LoadedProject` and must not re-parse files themselves. See §5.6 for the construction contract.

**Complexity is informational only.**
Never branch on `TaskComplexity` values. Surfaced in display and session state only.

**CLI-first.**
Every command must work as `tsm <command>` without the TUI. Do not add TUI-only code paths.

---

## File ownership

| File | tsm relationship | Notes |
|------|-----------------|-------|
| `TASKS.md` | Read + write | Status-only for workflow commands; structural for Phase 7 CRUD |
| `SESSIONSTATE.md` | Read + write (full reconstruction) | out_of_scope section never modified |
| `TASKS-COMPLETED.md` | Read + append only | Never modifies existing rows |
| `AGENTS.md` | **Read-only — never modified** | This file |
| `SPECIFICATION.md` | **Read-only — never modified** | |
| `.tsm/shadow/` | Write (staging) | Cleared on discard |
| `.tsm/backups/` | Write (backup on apply) | Last 5 per file kept |
| `.tsm/history.log` | Append | One line per apply; [undone] suffix on undo |
| `.tsm/config.toml` | Read-only | API key for `tsm import`; never written by tsm |
| `.gitignore` | Append only (idempotent) | Adds `.tsm/` entry once |

---

## Test discipline

**Parsers must have passing tests before any command is built.** This is a gate, not a guideline.

**Phase 7 gate:** `deps.py` (P7-T01) must have passing tests before any Phase 7 command is built.

Test ID assignment by task:
- **P2-T01** — §12.2 tests 1–21 (core parser)
- **P2-T02** — §12.2 tests 22–30 (complexity, key_constraints, subphase)
- **P2-T03** — all §12.3 tests (session parser)
- **P3-T01/T02** — all §12.5 tests (shadow/backup/undo)
- **P4-T01–P4-T07** — §12.4 and §12.6 tests per command
- **P7-T01** — §12.7 deps tests
- **P7-T03a/T03b** — structural writer tests
- **P7-T04–P7-T09** — §12.7 command tests per module

Each task's `Done when:` block in TASKS.md lists exact test IDs. Do not mark a task complete if any named tests are failing.

---

## Build order

### Phases 1–6 (complete)
1. `models.py` — dataclasses, enums, `slugify_phase_name()`, `LoadedProject`
2. `project.py` — discovery, `.gitignore` enforcement
3. `parsers/tasks_parser.py` — core (21 tests)
4. `parsers/tasks_parser.py` — edge cases (30 total tests)
5. `parsers/session_parser.py` — 12 tests
6. `parsers/completed_parser.py`
7. `shadow.py` — stage/apply/backup/prune/history (6 tests inc. --yes flag)
8. `shadow.py` — undo (8 total tests)
9. `writers/tasks_writer.py` — `update_task_status` and `update_phase_status`
10. `writers/session_writer.py` — full reconstruction renderer
11. `writers/completed_writer.py` — append writer
12. `commands/advance.py`
13. `commands/init_phase.py` + `commands/complete_phase.py`
14. `commands/vibe_check.py`
15. `commands/status.py` + `commands/undo.py`
16. `commands/help.py`
17. `commands/new_project.py`
18. `__main__.py` — CLI wiring, `load_project()`, `--yes` flag, exit codes
19. `ui/` — TUI: task_tree → task_detail → confirm_overlay → vibe_panel → help_panel → app.py

### Phase 7 (pending)
20. `deps.py` — dependency engine (P7-T01); all dep tests must pass before P7-T02+
21. `commands/deps.py` — deps command (P7-T02)
22. `writers/tasks_writer.py` — structural insert/remove/field-replace (P7-T03a)
23. `writers/tasks_writer.py` — reorder operations (P7-T03b)
24. `commands/phase.py` — phase CRUD (P7-T04)
25. `commands/task.py` — task CRUD (P7-T05)
26. `commands/repair.py` — file repair (P7-T07)
27. `commands/sync.py` — state sync (P7-T08)
28. `ui/task_form.py` — TaskFormOverlay (P7-T06; deps P6-T05 not P7-T05)
29. `commands/import_cmd.py` — LLM normalization (P7-T09; deps P7-T03a)

---

## Key dataclass invariants

These fields must never be omitted, retyped, or reordered.

**`Task`** (14 fields, in order):
`id`, `title`, `status`, `complexity`, `what`, `prerequisite`, `hard_deps`, `files`, `reviewer`, `key_constraints`, `done_when`, `phase_id`, `subphase`, `raw_block`

**`LoadedProject`** (4 fields, in order):
`project_context`, `phases`, `phase_overview`, `session`

**`SessionState`** (8 fields, in order):
`last_updated`, `active_phase_name`, `active_phase_spec`, `active_task`, `active_task_raw`, `up_next`, `completed`, `out_of_scope_raw`

**`PendingWrite`** (5 fields, in order):
`target_file`, `shadow_path`, `live_path`, `backup_path`, `summary_lines`

---

## Session start checklist

Before writing a single line of code:

1. **Read `AGENTS.md`** — you are doing this now
2. **Read `SESSIONSTATE.md`** — confirm the active phase and active task
3. **Read `TASKS.md`** — find the active task block and verify all hard deps have status `✅ Complete`
4. **Confirm out loud** what you are about to build, which files you will create or modify, and which `Done when:` criteria you are targeting
5. **Do not begin work** if `## Active task` is `[none]` or blank — ask for clarification
6. **Do not skip ahead** to a task that is not the active task, even if it looks simple

After completing a task:
- All named test IDs in `Done when:` must be passing
- Update `**Status:**` in TASKS.md from `Pending` → `✅ Complete` for the completed task
- Do not modify any other content in TASKS.md
- Report completion clearly so SESSIONSTATE.md can be advanced
