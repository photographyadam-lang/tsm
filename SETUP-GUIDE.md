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

Copy these files into the root of the `tsm/` directory:

| File | Source |
|------|--------|
| `TASKS.md` | From this output package |
| `SESSIONSTATE.md` | From this output package |
| `TASKS-COMPLETED.md` | From this output package |
| `AGENTS.md` | From this output package |
| `SPECIFICATION-task-session-manager-v1.6.md` | From this output package |

Your directory should look like:

```
tsm/
  AGENTS.md
  SESSIONSTATE.md
  SPECIFICATION-task-session-manager-v1.6.md
  TASKS-COMPLETED.md
  TASKS.md
```

---

## Step 3 — Create a .gitattributes and .gitignore

**.gitattributes** (normalizes line endings across Windows/Linux/Mac):
```
* text=auto eol=lf
```

**.gitignore:**
```
.tsm/
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.pytest_cache/
```

The `.tsm/` entry is what tsm itself will check for on first run.

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
- `## Active phase` matches the phase you are starting
- `## Active task` shows the first task for that phase
- `## Completed tasks` table is empty
- `## Up next` contains the remaining tasks for the phase

If anything looks wrong, fix the state file before starting a session.

---

## Step 6 — Open a Claude Code session

Use the session opener prompt from `SESSION-PROMPTS.md`. Paste it as the first message in a new Claude Code session.

Wait for the agent to confirm orientation before sending the build prompt.

---

## How the workflow runs

Each coding session follows this cycle:

```
1. Open Claude Code
2. Paste SESSION OPENER PROMPT
3. Agent reads AGENTS.md → SESSIONSTATE.md → confirms active task
4. You paste BUILD PROMPT for that task
5. Agent builds + tests
6. Agent reports completion
7. Advance state (manually until Phase 5, then via tsm advance):
   - Move active task to ## Completed tasks table
   - Set next task as ## Active task
   - Remove it from ## Up next
   - Update *Last updated:* timestamp
   - Update **Status:** in TASKS.md: Pending → ✅ Complete
   - Append row to TASKS-COMPLETED.md
8. git commit -m "P1-T01: package scaffold complete"
9. Repeat
```

Once Phase 5 is complete and `tsm` is installed, use `tsm advance` instead of step 7.

---

## Manually advancing SESSIONSTATE.md

**What to change in SESSIONSTATE.md:**

1. Add the completed task to `## Completed tasks`:
   ```
   | P1-T01 | Package scaffold and pyproject.toml | chore: scaffold |
   ```

2. Update `## Active task` to the next task's full block (copy verbatim from TASKS.md)

3. Remove that task from `## Up next`

4. Update `*Last updated:*` to current datetime in `YYYY-MM-DDTHH:MM` format

**What to change in TASKS.md:**

Find the completed task's `**Status:**` line and change it to `✅ Complete`. Only this line — nothing else.

**What to append to TASKS-COMPLETED.md:**

```markdown
## Phase 1 — Foundation

| Task | Description | Complexity | Commit message | Notes |
|------|-------------|------------|----------------|-------|
| P1-T01 | Package scaffold and pyproject.toml | low | chore: scaffold | |
```

If the phase section already exists, append only the new row — never duplicate the section header.

---

## Dependency order quick reference

### Phases 1–6

**Phase 1:**
- P1-T01 → start immediately
- P1-T02 → after P1-T01
- P1-T03 → after P1-T02
- P1-T04 → after P1-T01 (parallel with P1-T02)

**Phase 2:** All tasks need P1-T02 + P1-T04. P2-T01 must finish before P2-T02. P2-T03 and P2-T04 can run parallel to P2-T01/T02.

**Phase 3:** Each writer depends on its corresponding parser. P3-T01 and P3-T03 can run in parallel.

**Phase 4:** All command tasks need all of Phase 3. P4-T06 (help) needs all other command stubs to exist first.

**Phase 5:** Needs all of Phase 4.

**Phase 6:** Needs Phase 5. Build strictly in order: T01 → T02 → T03/T04 (parallel) → T05.

### Phase 7

**Gate:** P7-T01 (deps.py) must pass all tests before any other Phase 7 task starts.

```
P7-T01 ──► P7-T02 (deps command)
P7-T01 ──► P7-T03a (writer: insert/remove/field-replace)
P7-T03a ──► P7-T03b (writer: reorder)
P7-T03b ──► P7-T04 (phase CRUD)
P7-T03b ──► P7-T05 (task CRUD)
P6-T05 ──► P7-T06 (TaskFormOverlay — needs TUI infrastructure)
P7-T01 ──► P7-T07 (repair)
P7-T01 ──► P7-T08 (sync)
P7-T03a ──► P7-T09 (import — needs writer functions for serialization)
```

P7-T07, P7-T08, and P7-T09 can run in parallel once their deps are met.

---

## When something goes wrong

**Agent produces code that doesn't work:** Run the named tests from `Done when:` before marking anything complete. The tests are the gate, not the agent's report.

**Task is larger than expected:** Stop mid-task, commit what's done, and continue in a new session. Update `*Last updated:*` in SESSIONSTATE.md but do not mark the task complete until all `Done when:` criteria pass.

**Need to restart a session:** `git stash` or `git checkout` to the last clean commit, then open a new Claude Code session.

**Phase 7 dep gate blocks a remove operation:** This is by design. Either resolve the dependency first, or use `--force` if you accept the dangling dep warning.

**`tsm import` fails with no API key:** Create `.tsm/config.toml` with:
```toml
[import]
api_key = "sk-ant-..."
```
This file is gitignored automatically.
