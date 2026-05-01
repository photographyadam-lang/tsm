# tsm — Agent Rules

> Read this file at the start of every session before reading SESSIONSTATE.md.
> These rules apply to all AI coding agents working on this project.

---

## Project overview

`tsm` (Task and Session State Manager) is a locally-run Python CLI/TUI application that manages agentic coding workflow state across projects. It reads and writes three markdown files — TASKS.md, SESSIONSTATE.md, TASKS-COMPLETED.md — using a shadow-directory write model (stage → confirm → apply → backup → log) so all changes are reviewed before being applied. It also scaffolds new projects (`new-project`) and provides integrity validation (`vibe-check`). The TUI is built with Textual and is the last thing built — every command must work as a CLI subcommand first.

---

## Stack

- **Python 3.11+** — use `list[str]`, `str | None`, `match` syntax freely; no `from __future__ import annotations` needed
- **Textual >= 0.60.0** — only dependency beyond stdlib; pin this version
- **No other dependencies** — no LLM libraries, no network libraries, no Markdown parser libraries
- **pytest** — for all tests; no other test framework

---

## Architecture rules

These are hard constraints. Do not work around them.

**No network, no LLM, no telemetry — ever.**
No requests, httpx, openai, anthropic, or any network call of any kind. All logic is fully deterministic. Nothing leaves the machine.

**No general Markdown parser libraries.**
All three file parsers use a custom line-iterator state machine (§9.2). Do not import markdown, mistune, commonmark, or any Markdown parsing library. The formats are domain-specific and well-defined.

**TASKS.md write constraint — targeted replacement only.**
`tsm` only modifies `**Status:**` lines in TASKS.md. It never rewrites, reformats, or regenerates any other content. The dependency graph ASCII art and all task block text are preserved byte-for-byte.
- Task-level updates: `update_task_status(content, task_id, new_status)` in `tasks_writer.py`
- Phase-level updates: `update_phase_status(content, phase_heading_text, new_status)` in `tasks_writer.py`
- Never call `session_writer.render_sessionstate()` on TASKS.md content. These strategies must not be mixed.

**SESSIONSTATE.md write constraint — full reconstruction only.**
All writes to SESSIONSTATE.md use `session_writer.render_sessionstate(state)`. Never use targeted line replacement on SESSIONSTATE.md. The only preserved-verbatim sections are `active_task_raw` (re-emitted unchanged unless a command explicitly promotes a new task) and `out_of_scope_raw` (never modified).

**`raw_block` is the source of truth for `## Active task`.**
When a command promotes a new active task, it sets `session.active_task_raw = task.raw_block` (the exact text from TASKS.md). Never construct this block from scratch or re-serialize from the Task dataclass fields.

**`LoadedProject` is built once in `__main__.py`.**
The `load_project(root)` factory is defined in `tsm/__main__.py`. Commands receive a `LoadedProject` and must not re-parse files themselves. See §5.6 for the construction contract.

**Complexity is informational only.**
`tsm` never branches on `TaskComplexity` values. It is surfaced in display and session state only. No routing, no blocking, no model selection logic.

**CLI-first.**
Every command must work as `tsm <command>` without the TUI. The TUI (Phase 6) is a wrapper around the tested command layer. Do not add TUI-only code paths.

---

## File ownership

| File | tsm relationship | Notes |
|------|-----------------|-------|
| `TASKS.md` | Read + write (Status lines only) | Never reformat; targeted replacement only |
| `SESSIONSTATE.md` | Read + write (full reconstruction) | out_of_scope section never modified |
| `TASKS-COMPLETED.md` | Read + append only | Never modifies existing rows |
| `AGENTS.md` | **Read-only — never modified** | This file |
| `SPECIFICATION.md` | **Read-only — never modified** | |
| `.tsm/shadow/` | Write (staging) | Cleared on discard |
| `.tsm/backups/` | Write (backup on apply) | Last 5 per file kept |
| `.tsm/history.log` | Append | One line per apply; [undone] suffix on undo |
| `.gitignore` | Append only (idempotent) | Adds `.tsm/` entry once |

---

## Test discipline

**Parsers must have passing tests before any command is built.** This is not a guideline — it is a gate. The build order in §13 enforces this.

Test ID assignment by task:
- **P2-T01** owns §12.2 tests 1–21 (core parser: status tokens, deps, files, multiline, raw_block, dep_graph)
- **P2-T02** owns §12.2 tests 22–30 (edge cases: complexity, key_constraints, subphase)
- **P2-T03** owns all §12.3 tests (session parser)
- **P3-T01/T02** own all §12.5 tests (shadow/backup/undo)
- **P4-T01 through P4-T07** own the §12.4 and §12.6 tests for their respective commands

Each task's `Done when:` block in TASKS.md lists the exact test IDs that must pass. Do not mark a task complete if any of its named tests are failing.

---

## Build order

Follow §13 of the spec. Each step must have passing tests before the next begins.

1. `models.py` — dataclasses, enums, `slugify_phase_name()`, `LoadedProject`
2. `project.py` — discovery, `.gitignore` enforcement
3. `parsers/tasks_parser.py` — core (21 tests must pass)
4. `parsers/tasks_parser.py` — edge cases (9 more tests; 30 total must pass)
5. `parsers/session_parser.py` — 12 tests must pass
6. `parsers/completed_parser.py`
7. `shadow.py` — stage, apply, backup, prune, history (5 tests must pass)
8. `shadow.py` — undo (3 more tests; 8 total must pass)
9. `writers/tasks_writer.py` — both `update_task_status` and `update_phase_status`
10. `writers/session_writer.py` — full reconstruction renderer
11. `writers/completed_writer.py` — append writer
12. `commands/advance.py` — 5 tests
13. `commands/init_phase.py` + `commands/complete_phase.py`
14. `commands/vibe_check.py` — 11 tests
15. `commands/status.py` + `commands/undo.py`
16. `commands/help.py` — 4 tests
17. `commands/new_project.py` — 8 tests including round-trip parsability
18. `__main__.py` — CLI wiring + `load_project()` bootstrap; verify every command works via CLI
19. `ui/` — TUI last: task_tree → task_detail → confirm_overlay → vibe_panel → help_panel → app.py

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
