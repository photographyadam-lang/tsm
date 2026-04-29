# Test Project

> Minimal valid TASKS.md with no errors or warnings.

---

## Phase structure

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1 — Clean Alpha** | First phase | Pending |
| **Phase 2 — Clean Beta** | Second phase | Pending |

---

# Phase 1 — Clean Alpha

**Status:** Pending

---

## Phase 1 tasks

### CA-T01 · First clean task

**Status:** Pending
**Complexity:** low
**What:** The first task in a clean fixture file.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/alpha.py
**Reviewer:** Skip
**Done when:**
- Parser loads without warnings or errors

### CA-T02 · Second clean task

**Status:** Pending
**Complexity:** low
**What:** The second task in a clean fixture file.
**Prerequisite:** None.
**Hard deps:** None
**Files:** src/alpha/utils.py
**Reviewer:** Skip
**Done when:**
- Both tasks parse with status Pending

---

### Dependency graph

```
CA-T01
  └── CA-T02
```

---

# Phase 2 — Clean Beta

**Status:** Pending

---

## Phase 2 tasks

### CB-T01 · Beta clean task

**Status:** Pending
**Complexity:** medium
**What:** First task in the second clean phase.
**Prerequisite:** None.
**Hard deps:** CA-T02
**Files:** src/beta.py
**Reviewer:** Skip
**Done when:**
- Cross-phase dependency resolves without warning

---

### Dependency graph

```
CA-T02 ──► CB-T01
```

---
