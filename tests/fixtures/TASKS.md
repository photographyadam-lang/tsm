# tsm — Fixture Phase Task List

> Tasks are ordered by dependency. Do not start a task until all hard deps are met.
> This fixture file covers all format variants required by the parser tests.

---

## Phase structure

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1 — Fixture Alpha** | Alpha-phase tasks covering core format variants | ✅ Complete |
| **Phase 2 — Fixture Beta** | Beta-phase tasks covering remaining variants | Pending |

---

# Phase 1 — Fixture Alpha

**Status:** ✅ Complete

Establish the core fixture tasks that exercise status tokens, hard-deps variants, multi-line fields, backtick files, key constraints, and the dependency graph block.

---

## Phase 1 tasks

### FA-T01 · Completed setup task

**Status:** ✅ Complete
**Complexity:** low
**What:** Single-line what field for the simplest possible task block.
**Prerequisite:** None.
**Hard deps:** None
**Files:** none
**Reviewer:** Skip
**Done when:**
- Parser extracts all fields correctly
- Status token ✅ Complete is recognised

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

### FA-T03 · Pending task with multi-line done-when

**Status:** Pending
**Complexity:** medium
**What:** Single-line what for a task exercising multi-line Done when and See spec in Files.
**Prerequisite:** FA-T02 complete.
**Hard deps:** —
**Files:** See spec §8, config/settings.json
**Reviewer:** Skip
**Key constraints:**
- This task has key constraints with exactly two bullet items
- The second bullet item validates bullet-stripping logic
**Done when:**
- First criterion line for the multi-line Done when field.
- Second criterion line validates accumulation stops at the next task boundary.

### FA-T04 · Blocked task with None dot hard deps

**Status:** 🔒 Blocked
**Complexity:** unset
**What:** Single-line description for a blocked task with no explicit complexity.
**Prerequisite:** None.
**Hard deps:** None.
**Files:**
**Reviewer:** Skip
**Done when:**
- Status token 🔒 Blocked is recognised
- Hard deps value "None." parses to empty list
- Empty Files field parses to empty list
- Absent Complexity field defaults to UNSET

---

### Dependency graph

```
FA-T01
  └── FA-T02
        └── FA-T03
FA-T01
  └── FA-T04
```

---

# Phase 2 — Fixture Beta

**Status:** Pending

Additional fixture tasks covering mixed statuses and an extra dependency graph block.

---

## Phase 2 tasks

### FB-T01 · Completed beta task

**Status:** ✅ Complete
**Complexity:** low
**What:** A complete task in the second phase fixture.
**Prerequisite:** None.
**Hard deps:** FA-T01
**Files:** src/beta.py
**Reviewer:** Bob
**Done when:**
- Phase 2 fixture parses independently of Phase 1

### FB-T02 · Pending beta task without key constraints

**Status:** Pending
**Complexity:** low
**What:** This task intentionally omits the Key constraints field entirely.
The parser must return an empty list without raising errors or emitting warnings.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/beta/utils.py
**Reviewer:** Skip
**Done when:**
- key_constraints is [] (absent field)
- No VC-11 warning fires for this task

### FB-T03 · Active beta task with backtick new files

**Status:** **Active**
**Complexity:** medium
**What:** Single-line what for an active task in the beta phase.
**Prerequisite:** FB-T01 complete.
**Hard deps:** FB-T01, FA-T02
**Files:** `src/adapters.py`(new), `src/validators.py`(new), docs/guide.md
**Reviewer:** Carol
**Done when:**
- Multiple backtick-wrapped files with (new) suffix are parsed
- Files list strips backticks and removes (new) suffix

---

### Dependency graph

```
FA-T01 ──► FB-T01 ──► FB-T03
FB-T01 ──► FB-T02
```

---
