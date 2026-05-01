# tsm — Project Setup Guide

This guide gets you from zero to a running Claude Code session on the first task.

---

## Prerequisites

- Python 3.11 or later (`python --version`)
- Git
- A Claude Code installation (or your preferred AI coding agent)

---

## Step 1 — Create the project directory

```bash
mkdir tsm
cd tsm
git init
```

---

## Step 2 — Place the project files

Copy these five files into the root of the `tsm/` directory:

| File | Source |
|------|--------|
| `TASKS.md` | From this output package |
| `SESSIONSTATE.md` | From this output package |
| `TASKS-COMPLETED.md` | From this output package |
| `AGENTS.md` | From this output package |
| `SPECIFICATION-task-session-manager-v1.3.md` | From this output package |

Your directory should look like:

```
tsm/
  AGENTS.md
  SESSIONSTATE.md
  SPECIFICATION-task-session-manager-v1.3.md
  TASKS-COMPLETED.md
  TASKS.md
```

---

## Step 3 — Create a .gitignore

Create `tsm/.gitignore` with this content:

```
.tsm/
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.pytest_cache/
```

The `.tsm/` entry is what tsm itself will check for on first run. Including it now means the first-run notice won't fire.

---

## Step 4 — Make your first git commit

```bash
git add .
git commit -m "chore: project scaffold — spec, tasks, agent rules"
```

This is your clean starting checkpoint. You can always return here.

---

## Step 5 — Verify SESSIONSTATE.md is correct

Open `SESSIONSTATE.md` and confirm:
- `## Active phase` is `Phase 1 — Foundation — in progress.`
- `## Active task` shows `P1-T01 · Package scaffold and pyproject.toml`
- `## Up next` has P1-T02, P1-T03, P1-T04
- `## Completed tasks` table is empty

If anything looks wrong, do not start a session — fix the state file first.

---

## Step 6 — Open a Claude Code session

Use the session opener prompt from `SESSION-PROMPTS.md`. Paste it as the first message in a new Claude Code session.

Wait for the agent to confirm orientation before sending the build prompt.

---

## How the workflow runs from here

Each coding session follows this cycle:

```
1. Open Claude Code
2. Paste SESSION OPENER PROMPT
3. Agent reads AGENTS.md → SESSIONSTATE.md → confirms active task
4. You paste BUILD PROMPT for that task
5. Agent builds + tests
6. Agent reports completion
7. You manually advance SESSIONSTATE.md (until tsm itself is built):
   - Move active task to ## Completed tasks table
   - Set next task as ## Active task
   - Remove it from ## Up next
   - Update *Last updated:* timestamp
   - Update **Status:** in TASKS.md: Pending → ✅ Complete
   - Append row to TASKS-COMPLETED.md
8. New git commit: "P1-T01: package scaffold complete"
9. Repeat
```

Once Phase 5 is complete and `tsm` itself is working, you switch to using `tsm advance` instead of step 7.

---

## Manually advancing SESSIONSTATE.md (Phase 1–5)

Until `tsm advance` exists, advance the state by hand after each completed task.

**What to change in SESSIONSTATE.md:**

1. Move the active task row to `## Completed tasks`:
   ```
   | P1-T01 | Package scaffold and pyproject.toml | chore: scaffold |
   ```

2. Update `## Active task` to the next task's full block (copy from TASKS.md)

3. Remove that task from `## Up next`

4. Update `*Last updated:*` to current datetime

**What to change in TASKS.md:**

Find the completed task's `**Status:**` line and change it:
```
**Status:** ✅ Complete
```
Only this line. Nothing else.

**What to append to TASKS-COMPLETED.md:**

```markdown
## Phase 1 — Foundation

**Completed: 2026-04-23T10:00**

| Task | Description | Complexity | Commit message | Notes |
|------|-------------|------------|----------------|-------|
| P1-T01 | Package scaffold and pyproject.toml | low | chore: scaffold | |
```

If the phase section already exists, just append the row — don't duplicate the section header.

---

## Dependency order quick reference

Tasks within a phase can sometimes run in parallel. Here's what can start as soon as what:

**Phase 1:**
- P1-T01 → start immediately
- P1-T02 → after P1-T01
- P1-T03 → after P1-T02
- P1-T04 → after P1-T01 (can run parallel to P1-T02)

**Phase 2:** All four tasks need P1-T02 + P1-T04. P2-T01 must complete before P2-T02.

**Phase 3:** Each writer depends on its corresponding parser completing first.

**Phase 4:** All command tasks need all of Phase 3. P4-T06 (help) needs all other command stubs.

**Phase 5:** Needs all of Phase 4.

**Phase 6:** Needs Phase 5. Build strictly in sub-order: T01 → T02 → T03, T04 → T05.

---

## When something goes wrong

**Agent produces plausible-looking code that doesn't work:** Treat all agent output as requiring verification. Run the named tests from `Done when:` before marking anything complete.

**Task is larger than expected:** It is fine to stop mid-task, commit what's done, and continue in a new session. Update `SESSIONSTATE.md` `*Last updated:*` but do not mark the task complete until all `Done when:` criteria pass.

**You need to re-run a session from scratch:** The git history is your checkpoint. `git stash` or `git checkout` to the last clean commit, then start a new Claude Code session.

**Parser tests fail after adding complexity/key_constraints (P2-T02):** All 21 P2-T01 tests must continue to pass. If any regress, fix before proceeding — the P2-T02 task explicitly requires this.
