# tsm — Error Fixture

> Deliberately malformed TASKS.md for vibe-check error detection tests.
>
> Deliberate errors:
>   1. ER-T01 appears TWICE (duplicate task ID — triggers VC-01).
>   2. ER-T03 lists "ER-NONEXIST" in Hard deps, a task ID that does not exist
>      anywhere in this file (dangling dependency — triggers VC-02).
>
> Do not "fix" these errors — they are the test data.

---

## Phase structure

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1 — Error Alpha** | Phase with intentional errors | Pending |

---

# Phase 1 — Error Alpha

**Status:** Pending

---

## Phase 1 tasks

### ER-T01 · First occurrence of duplicate ID

**Status:** Pending
**Complexity:** low
**What:** This is the first occurrence of ER-T01.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/error_one.py
**Reviewer:** Skip
**Done when:**
- Parser reports VC-01 for duplicate ER-T01

### ER-T01 · Second occurrence of duplicate ID

**Status:** Pending
**Complexity:** low
**What:** This is the second occurrence of ER-T01 — deliberate duplicate.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/error_one_again.py
**Reviewer:** Skip
**Done when:**
- Parser reports VC-01 for this duplicate

### ER-T02 · Valid task in error fixture

**Status:** Pending
**Complexity:** low
**What:** A valid task placed between the two error tasks.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/valid.py
**Reviewer:** Skip
**Done when:**
- This task parses without error despite being in an error fixture

### ER-T03 · Task with dangling dependency

**Status:** Pending
**Complexity:** medium
**What:** This task references ER-NONEXIST in Hard deps, which does not exist.
**Prerequisite:** None.
**Hard deps:** ER-NONEXIST
**Files:** src/dangling.py
**Reviewer:** Skip
**Done when:**
- Parser reports VC-02 for dangling dep ER-NONEXIST

---

### Dependency graph

```
ER-T01
  └── ER-T02
  └── ER-T03 ──► ER-NONEXIST
```

---
