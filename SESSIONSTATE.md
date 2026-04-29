*Last updated: 2026-04-29T00:00*

---

## Active phase
Phase 2 — Parsers — in progress.
Spec: `SPECIFICATION-task-session-manager-v1.4.md`

---

## Completed tasks

| Task | Description | Commit message |
|---|---|---|
| P2-T01 |
| P2-T02 | tasks_parser.py — complexity, key_constraints, subphase tracking | P2-T01 | medium | Skip |
| P2-T03 | session_parser.py | P1-T02, P1-T04 | medium | Skip |
---

## Active task

### P2-T04 · completed_parser.py

**Status:** Pending
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

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|---|---|---|---|---|
| P2-T04 | completed_parser.py | P1-T02, P1-T04 | low | Skip |

---

## Out of scope

- Phase 6 TUI until all CLI commands are verified working end-to-end (§14 CLI-first constraint)
- Network calls, LLM calls, telemetry of any kind (§14)
- General Markdown parser libraries — line iterator state machine only (§9.1)
- Multi-level undo — single-level only in v1.0 (§14)
- Dependency graph edge validation in vibe-check — display/preservation only in v1.0 (§14)
- --output json on read-only commands — deferred to v2 (§2.2)