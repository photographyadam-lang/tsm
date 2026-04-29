*Last updated: 2026-04-15T14:30*

---

## Active phase

Phase 1 — Fixture Alpha — in progress.
Spec: `tests/fixtures/TASKS.md`

---

## Completed tasks

| Task | Description | Commit message |
|------|-------------|----------------|
| FA-T01 | Completed setup task | P1-T01: initial scaffold |
| FB-T01 | Completed beta task | P1-T02: models complete |

---

## Active task

### FA-T02 · Active task with multi-line what

**Status:** **Active**
**Complexity:** high
**What:** This task demonstrates the multi-line What field format.
It spans across three distinct lines to validate that the parser
correctly accumulates content until the next field label is found.
**Prerequisite:** FA-T01 complete.
**Hard deps:** FA-T01
**Files:** `src/feature.py`(new), `src/utils.py`
**Reviewer:** Alice
**Key constraints:**
- Must not modify global state or system configuration
- Must handle empty input edge cases without crashing
**Done when:**
- Multi-line What accumulates correctly into a single string

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|------|-------------|-----------|------------|----------|
| FA-T03 | Pending task with multi-line done-when | — | medium | Skip |
| FA-T04 | Blocked task with None dot hard deps | None. | unset | Skip |

---

## Out of scope

- Phase 6 TUI until all CLI commands are verified working end-to-end
- Network calls, LLM calls, telemetry of any kind
- General Markdown parser libraries — line iterator state machine only
- Multi-level undo — single-level only in v1.0
