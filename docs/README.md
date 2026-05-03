# tsm — Task and Session State Manager

**tsm** is a local CLI/TUI application that manages agentic coding workflow state across projects. It reads and writes three Markdown files — [`TASKS.md`](../TASKS.md), [`SESSIONSTATE.md`](../SESSIONSTATE.md), and [`TASKS-COMPLETED.md`](../TASKS-COMPLETED.md) — using a **shadow-directory write model** so every change is reviewed before being applied.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Opening the Application](#opening-the-application)
- [CLI Commands](#cli-commands)
  - [`tsm help`](#tsm-help)
  - [`tsm new-project`](#tsm-new-project)
  - [`tsm init-phase`](#tsm-init-phase)
  - [`tsm advance`](#tsm-advance)
  - [`tsm complete-phase`](#tsm-complete-phase)
  - [`tsm status`](#tsm-status)
  - [`tsm vibe-check`](#tsm-vibe-check)
  - [`tsm undo`](#tsm-undo)
- [TUI (Terminal User Interface)](#tui-terminal-user-interface)
  - [Keybindings](#keybindings)
  - [Panels](#panels)
- [The Shadow Write Model](#the-shadow-write-model)
- [Typical Workflow](#typical-workflow)
- [File Reference](#file-reference)

---

## Installation

### Prerequisites

- **Python 3.11+**
- **Git**

### Steps

1. Clone or navigate to a project that contains [`TASKS.md`](../TASKS.md) and [`SESSIONSTATE.md`](../SESSIONSTATE.md).

2. (Optional but recommended) Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS / Linux:
   source .venv/bin/activate
   ```

3. Install the package:

   ```bash
   pip install -e .
   ```

   This installs the `tsm` console script and its only dependency — [`Textual`](https://textual.textualize.io/) `>= 0.60.0` — for the TUI.

4. Verify the installation:

   ```bash
   tsm help
   ```

---

## Quick Start

### Scaffold a new project

```bash
cd my-project
tsm new-project --name "My App"
```

This creates:
- [`TASKS.md`](../TASKS.md) — a starter task list with one placeholder phase and task
- [`SESSIONSTATE.md`](../SESSIONSTATE.md) — an empty session state file
- [`TASKS-COMPLETED.md`](../TASKS-COMPLETED.md) — an empty completion log
- [`AGENTS.md`](../AGENTS.md) — a copy of the agent rules file
- [`SPECIFICATION.md`](../SPECIFICATION.md) — a copy of the project specification
- `.tsm/` — the shadow-directory structure (`.gitignore` is updated automatically)

> **Note:** If [`TASKS.md`](../TASKS.md) or [`SESSIONSTATE.md`](../SESSIONSTATE.md) already exist, `tsm new-project` will refuse to overwrite them.

### Open the TUI

```bash
tsm
```

Running `tsm` with no subcommand inside a project root launches the **Textual TUI** (see [TUI section](#tui-terminal-user-interface) below).

If you are not inside a project root, `tsm` with no arguments prints the help text instead.

---

## Opening the Application

### TUI mode

```bash
# Navigate to a project directory
cd /path/to/project

# Launch the Textual TUI
tsm
```

The TUI detects the project automatically by walking up the directory tree (up to 3 parent levels) looking for both [`TASKS.md`](../TASKS.md) and [`SESSIONSTATE.md`](../SESSIONSTATE.md). If neither is found, the help text is printed instead.

### CLI mode

Run any command directly:

```bash
tsm <command> [options]
```

Every command that exists in the TUI also works as a standalone CLI call. The `--yes` flag can be appended to skip the confirmation prompt on write commands.

---

## CLI Commands

### `tsm help`

```bash
tsm help              # Print full command list
tsm help advance      # Print help for a specific command
tsm --help            # Same as 'tsm help'
```

Read-only. Does not require a project root.

### `tsm new-project`

```bash
tsm new-project --name "My App"
```

Scaffolds a complete set of blank workflow files in the current directory. Prevents overwriting existing [`TASKS.md`](../TASKS.md) or [`SESSIONSTATE.md`](../SESSIONSTATE.md).

**Writes:**
1. [`TASKS.md`](../TASKS.md) — a generated placeholder phase/task
2. [`SESSIONSTATE.md`](../SESSIONSTATE.md) — empty session state with `[none]` active task
3. [`TASKS-COMPLETED.md`](../TASKS-COMPLETED.md) — header-only log
4. [`AGENTS.md`](../AGENTS.md) — agent rules copy
5. [`SPECIFICATION.md`](../SPECIFICATION.md) — spec copy
6. `.tsm/` — shadow/ and backups/ subdirectories
7. `.gitignore` — `.tsm/` entry appended (idempotent)

### `tsm init-phase`

```bash
tsm init-phase phase-2-fixture-beta
tsm init-phase "Phase 2 — Fixture Beta"
tsm init-phase --yes phase-2-fixture-beta
```

Initialises [`SESSIONSTATE.md`](../SESSIONSTATE.md) for the start of a phase. The first task in file order whose hard dependencies are all met becomes the active task. All other non-complete tasks in the phase populate the **Up next** list.

**Preconditions:**
- A project root must exist
- The specified phase must exist and have at least one non-complete task

**Writes:** [`SESSIONSTATE.md`](../SESSIONSTATE.md) only.

### `tsm advance`

```bash
tsm advance                        # No commit message
tsm advance "P4-T01: advance module complete"
tsm advance --yes                   # Skip confirmation prompt
```

Marks the current active task as **Complete**, promotes the next ready task from **Up next** to **Active**, and appends a row to [`TASKS-COMPLETED.md`](../TASKS-COMPLETED.md). Also updates the completed task's `**Status:**` line in [`TASKS.md`](../TASKS.md) to `✅ Complete`.

**Preconditions:**
- A project root must exist
- An active task must be set

**Writes:**
1. [`SESSIONSTATE.md`](../SESSIONSTATE.md) — promotes next task
2. [`TASKS.md`](../TASKS.md) — targeted status line update only
3. [`TASKS-COMPLETED.md`](../TASKS-COMPLETED.md) — appends new row

### `tsm complete-phase`

```bash
tsm complete-phase
tsm complete-phase --yes
```

Rotates to the next phase (the first phase after the current one whose status is not already `✅ Complete`). Selects the first ready task in the new phase as active, populates **Up next**, and clears the completed list. Updates the completed phase's status line in [`TASKS.md`](../TASKS.md).

**Preconditions:**
- All tasks in the current phase must be marked **Complete**
- A phase must be active (run `tsm init-phase` first)

**Writes:**
1. [`SESSIONSTATE.md`](../SESSIONSTATE.md) — rotates to next phase
2. [`TASKS.md`](../TASKS.md) — targeted phase status line update
3. [`TASKS-COMPLETED.md`](../TASKS-COMPLETED.md) — appends phase-complete marker

### `tsm status`

```bash
tsm status
```

Prints a structured summary of the current session state to stdout:
- Active phase name and spec reference
- Last updated timestamp
- Active task details (with complexity and hard-dep status icons)
- Up-next task list
- Completed task count

**Read-only.** Does not modify any files.

### `tsm vibe-check`

```bash
tsm vibe-check
```

Validates the integrity of [`TASKS.md`](../TASKS.md), [`SESSIONSTATE.md`](../SESSIONSTATE.md), and [`TASKS-COMPLETED.md`](../TASKS-COMPLETED.md) against 13 rules (VC-01 through VC-13):

| Rule | Severity | Description |
|------|----------|-------------|
| VC-01 | Error | Duplicate task IDs in [`TASKS.md`](../TASKS.md) |
| VC-02 | Error | Hard dep references a nonexistent task ID |
| VC-03 | Error | Active task has status Complete in [`TASKS.md`](../TASKS.md) |
| VC-04 | Error | Up-next task has status Complete in [`TASKS.md`](../TASKS.md) |
| VC-05 | Warning | Up-next task has unmet hard deps |
| VC-06 | Warning | Active task is `[none]` or blank |
| VC-07 | Warning | Active phase is `[none]` or blank |
| VC-08 | Error | Phase structure table ref with no matching section |
| VC-09 | Warning | Task with Active/In-Progress status not matching session |
| VC-10 | Error | [`TASKS-COMPLETED.md`](../TASKS-COMPLETED.md) contains unknown task ID |
| VC-11 | Warning | Task block missing a required field |
| VC-12 | Warning | Last updated is more than 7 days ago |
| VC-13 | Warning | Active/up-next task has complexity: unset |

**Read-only.** Does not modify any files.

### `tsm undo`

```bash
tsm undo
```

Reverts the most recent `tsm apply` operation. Restores live files from the backups created during the last apply. Does not create new backups or history entries.

If there is nothing to undo (no history, or all entries already marked `[undone]`), prints `"Nothing to undo."` and exits gracefully.

**Single-level only** — no multi-level undo.

---

## TUI (Terminal User Interface)

The TUI is built with [Textual](https://textual.textualize.io/) and presents a two-panel layout with a context-aware command bar.

```
┌─────────────────────┬──────────────────────┐
│                     │                       │
│    TaskTree         │   TaskDetail /        │
│    (left panel)     │   VibecheckPanel /    │
│                     │   HelpPanel           │
├─────────────────────┴──────────────────────┤
│  [a]Advance [i]Init [c]Complete ...        │
└────────────────────────────────────────────┘
```

### Launching the TUI

```bash
cd /path/to/project
tsm
```

### Keybindings

| Key | Action | Description |
|-----|--------|-------------|
| `a` | **Advance** | Mark active task complete, promote next task. Prompts for an optional commit message, then shows a confirmation overlay before applying. |
| `i` | **Init Phase** | Initialise a new phase. Prompts for the phase ID (e.g. `phase-2`), then shows a confirmation overlay. Greyed out when an active task is already set. |
| `c` | **Complete Phase** | Mark the current phase complete and rotate to the next one. Shows a confirmation overlay. Greyed out when any tasks in the current phase are incomplete. |
| `v` | **Vibe Check** | Run integrity validation and display results in the right panel. |
| `u` | **Undo** | Revert the most recent apply operation. Greyed out when there is nothing to undo. |
| `s` | **Status** | Print the current session state to the terminal. |
| `?` | **Help** | Show the help panel in the right panel. |
| `q` | **Quit** | Exit the TUI. |

### Context-aware command bar

The command bar at the bottom of the TUI shows all available keybindings. Buttons are styled in **dim** (greyed out) when the action is not available:

- **Init** (i) — greyed when an active task is already set
- **Complete** (c) — greyed when any tasks in the current phase are not marked Complete
- **Undo** (u) — greyed when the history log is empty or all entries are marked `[undone]`

This greying is **display-only** — the underlying command functions still perform their own precondition checks, so triggering a greyed action still aborts cleanly.

### Panels

**Left panel — TaskTree:**
Shows all phases and their tasks in a collapsible tree. The active task is highlighted. Click on any task to view its details in the right panel.

**Right panel — TaskDetail (default):**
Displays the full detail of the selected or active task, including its status, complexity, description, hard dependencies, files, key constraints, and the "Done when" criteria.

**Right panel — VibecheckPanel (v key):**
Shows the results of the most recent vibe-check, listing any errors or warnings found.

**Right panel — HelpPanel (? key):**
Displays the full command reference.

---

## The Shadow Write Model

Every write command in `tsm` follows a **stage → confirm → apply → backup → log** pipeline:

1. **Stage** — The command computes the necessary file changes and writes them to `.tsm/shadow/` (staging directory) instead of modifying the live files directly.
2. **Confirm** — A confirmation overlay (in the TUI) or a prompt (in the CLI) shows you exactly what will change: which files will be modified, and a summary of each change.
3. **Apply** — If you confirm, the staged changes are copied from `.tsm/shadow/` to their live locations.
4. **Backup** — Before overwriting each live file, a `.bak` copy is saved in `.tsm/backups/`. The last 5 backups per file are retained.
5. **Log** — A single-line entry is appended to `.tsm/history.log` recording the timestamp, operation, and affected files.

The `--yes` flag skips the confirm step, equivalent to `--assume-yes`.

### Safety guarantees

- **No silent overwrites** — every write is previewed before being applied
- **Single-level undo** — the most recent apply can always be reverted via `tsm undo`
- **Backup retention** — the last 5 backups per file are kept in `.tsm/backups/`
- **`.gitignore` enforcement** — the `.tsm/` directory is automatically added to `.gitignore` so shadow files and backups are never committed

---

## Typical Workflow

```mermaid
graph LR
    A[Scaffold project<br/>tsm new-project] --> B[Init first phase<br/>tsm init-phase phase-1]
    B --> C[Work on active task]
    C --> D[Advance when done<br/>tsm advance "commit msg"]
    D --> E{More tasks<br/>in phase?}
    E -->|Yes| C
    E -->|No| F[Complete phase<br/>tsm complete-phase]
    F --> G{More phases?}
    G -->|Yes| B
    G -->|No| H[Done!]
```

1. **Scaffold** — `tsm new-project --name "My App"`
2. **Init** — `tsm init-phase phase-1` to set up the first phase's session state
3. **Build** — Work on the active task (the actual coding happens outside `tsm`)
4. **Advance** — `tsm advance "feat: implemented login"` to mark the task complete and promote the next one
5. **Complete phase** — `tsm complete-phase` once all tasks in a phase are done
6. **Repeat** — `tsm init-phase phase-2`, build, advance, complete...

### Validation checkpoints

Run `tsm vibe-check` at any point to validate the integrity of your workflow files. This is especially useful before advancing or completing a phase.

---

## File Reference

| File | `tsm` relationship | Notes |
|------|-------------------|-------|
| [`TASKS.md`](../TASKS.md) | Read + write (status lines only) | Never reformatted; targeted replacement only |
| [`SESSIONSTATE.md`](../SESSIONSTATE.md) | Read + write (full reconstruction) | Out-of-scope section never modified |
| [`TASKS-COMPLETED.md`](../TASKS-COMPLETED.md) | Read + append only | Never modifies existing rows |
| [`AGENTS.md`](../AGENTS.md) | Read-only — never modified | Agent rules file |
| [`SPECIFICATION.md`](../SPECIFICATION.md) | Read-only — never modified | Project specification |
| `.tsm/shadow/` | Write (staging) | Cleared on discard |
| `.tsm/backups/` | Write (backup on apply) | Last 5 per file kept |
| `.tsm/history.log` | Append | One line per apply; `[undone]` suffix on undo |

---

## LLM Prompts

> These prompts are designed for you to paste into a conversation with any LLM (Claude, GPT, etc.) to check, repair, or convert the three workflow files — [`TASKS.md`](../TASKS.md), [`SESSIONSTATE.md`](../SESSIONSTATE.md), and [`TASKS-COMPLETED.md`](../TASKS-COMPLETED.md) — **without** using the `tsm` tool itself.
>
> Each prompt is self-contained. Paste the entire prompt block, then paste the file content after it.

---

### Prompt: Check (Validate)

> Use this when you want an LLM to validate the integrity of your workflow files against the spec. Paste this prompt, then paste each file's content.

```
You are a validation assistant. I will give you the contents of three Markdown files that
follow a specific workflow format: TASKS.md, SESSIONSTATE.md, and TASKS-COMPLETED.md.

Your job is to check each file against the rules below and produce a numbered list of every
issue found, with the severity (Error or Warning), the file and line reference, and a
description of the problem. If no issues are found, say "All checks passed."

--- RULES ---

TASKS.md rules:

1. File must start with an H1 heading (#) as the project title.
2. After the preamble, there must be a ## Phase structure table with 3 columns:
   | Phase | Description | Status |
3. Every row in the Phase structure table must correspond to an actual H1 phase section
   later in the file. The status column must use a recognised status token.
4. Phase sections are H1 headings (#). Each has:
   - A **Status:** line immediately after the heading
   - An optional narrative paragraph
   - One or more H3 task blocks (### ID · Title)
   - A ### Dependency graph block at the end (fenced code block)
5. Task blocks begin with ### <ID> · <title> and end at the next ###, ##, #, or --- line.
6. Each task block must have ALL of these fields (exact **Label:** syntax):
   - **Status:** — one of: ✅ Complete, **Active**, Active, Pending, 🔒 Blocked, ❌ Blocked,
     ⚠️ Needs review, In progress
   - **Complexity:** — one of: high, medium, low, unset
   - **What:** — description (may span multiple lines)
   - **Prerequisite:** — human-readable, or "None."
   - **Hard deps:** — comma-separated task IDs, "None", "—", or blank
   - **Files:** — comma-separated paths, or blank
   - **Reviewer:** — any text
   - **Key constraints:** — OPTIONAL bullet list (omit if none)
   - **Done when:** — acceptance criteria (may span multiple lines)
7. Task IDs match the pattern [A-Z0-9]+-[A-Z][0-9]+ (e.g. P1-T01, U-A1). They must be
   unique across the entire file.
8. All task IDs in Hard deps must exist as task IDs elsewhere in the file.
9. Multi-line field values continue until the next **Label:** line or a structural boundary
   (#, ---).

SESSIONSTATE.md rules:

10. First non-blank line must be *Last updated: YYYY-MM-DDTHH:MM* (ISO 8601 date + hour +
    minute).
11. Sections are delimited by --- horizontal rules, in this order:
    - ## Active phase
    - ## Completed tasks (table with columns: Task | Description | Commit message)
    - ## Active task (verbatim copy of the task block from TASKS.md)
    - ## Up next (table with columns: Task | Description | Hard deps | Complexity | Reviewer)
    - ## Out of scope (bullet list)
12. ## Active task must contain either the literal [none] or a complete task block (### ID ·
    title with all **Field:** lines). If a task block is present, the task ID must exist in
    TASKS.md.
13. ## Active phase must contain the phase name, status, and spec reference. If set, the
    phase name must exist in TASKS.md.
14. Every task listed in ## Up next must exist in TASKS.md.
15. Every task listed in ## Completed tasks must exist in TASKS.md.
16. ## Out of scope content is informational — never modify it.

TASKS-COMPLETED.md rules:

17. File starts with "# Completed Tasks Log".
18. Each phase section is a ## heading. Within it, a table with columns:
    | Task | Description | Complexity | Commit message | Notes |
19. All task IDs in the table rows must exist in TASKS.md.
20. Existing rows are never modified — only appended.

Cross-file rules:

21. If a task is marked as **Active** or In progress in SESSIONSTATE.md, its status in
    TASKS.md must NOT be ✅ Complete.
22. If a task is listed in ## Up next and has Hard deps, those deps should ideally be met
    (status ✅ Complete in TASKS.md). Unmet deps are a warning.
23. *Last updated:* more than 7 days ago is a warning (stale session).

Produce output in this format for each issue:
  [Error|Warning] [File] — [description] (around line N)

For unset/none/blank fields or [none] active task, produce warnings, not errors.
```

---

### Prompt: Repair (Fix Issues)

> Use this when you've run a check and found issues, or when files are known to be corrupt/malformed. Paste this prompt, then paste the file content.

```
You are a file repair specialist. I will give you the content of one or more workflow
Markdown files (TASKS.md, SESSIONSTATE.md, TASKS-COMPLETED.md) that have structural
issues. Your job is to fix them according to the rules below.

Output the FULL repaired file content for each file. Do not abbreviate or use placeholders.

--- REPAIR RULES ---

General rules:
- Preserve all content that is valid. Only change what is broken.
- Maintain byte-for-byte fidelity for all content you do not touch.
- After repair, the file must parse correctly under the spec rules.

TASKS.md repairs:

1. **Missing required fields:** If a task block is missing **Status:**, **Complexity:**,
   **What:**, **Prerequisite:**, **Hard deps:**, **Files:**, **Reviewer:**, or
   **Done when:**, add the missing field with a safe default:
   - Status → "Pending"
   - Complexity → "unset"
   - Hard deps → "None"
   - Reviewer → "Skip"
   - Prerequisite → "None."
   - Files → "" (blank line)
   - If **Key constraints:** is absent, leave it absent — it's optional
   - Insert missing fields in the canonical field order (see below)
2. **Canonical field order within a task block:**
   Status → Complexity → What → Prerequisite → Hard deps → Files → Reviewer →
   Key constraints (optional) → Done when
3. **Malformed status tokens:** Normalise recognised tokens:
   - "Complete", "completed", "DONE" → "✅ Complete"
   - "Active" (not bold), "ACTIVE" → "**Active**"
   - "in-progress", "in_progress" → "In progress"
   - "BLOCKED", "blocked" → "🔒 Blocked"
   - "needs review", "needs_review" → "⚠️ Needs review"
   Unknown status tokens → leave as-is and flag in summary.
4. **Malformed complexity:** Normalise to lowercase: HIGH → high, Medium → medium,
   Unset → unset. Unknown values → "unset".
5. **Duplicate task IDs:** If two task blocks have the same ID, rename the second
   occurrence to <id>-duplicate (e.g. P1-T01-duplicate). Log both in a summary.
6. **Missing **:** on field labels:** If a field line has "Status:" instead of
   "**Status:**", add the bold markers.
7. **Dependency graph blocks:** Leave completely unchanged — never modify them.
8. **Phase structure table:** If a phase exists as an H1 section but is missing from
   the ## Phase structure table, add a row for it. If a table row has no matching
   H1 section, remove the row.
9. **Phase **Status:** lines:** If a phase heading (#) is missing its **Status:** line,
   add it with value "Pending".

SESSIONSTATE.md repairs:

10. **Active task ID not in TASKS.md:** If the ## Active task block contains a task
    ID that does not exist in TASKS.md, replace the entire ## Active task content
    with "[none]" and note the removed ID in a summary.
11. **Up next IDs not in TASKS.md:** Remove any rows from ## Up next table whose
    task ID does not exist in TASKS.md. Note each removal.
12. **Legacy date format:** If *Last updated:* has only a date (YYYY-MM-DD) without
    time, append T00:00 to make it YYYY-MM-DDTHH:MM.
13. **Active task format:** Ensure the ## Active task block (if not [none]) is a
    verbatim copy from TASKS.md — it must start with ### <ID> · <title> and contain
    all **Field:** lines exactly as in TASKS.md. If it differs, replace it with the
    correct content from TASKS.md.

TASKS-COMPLETED.md repairs:

14. **Unknown task IDs:** Remove any table rows whose task ID does not exist in
    TASKS.md. Note each removed row.
15. **Empty phase sections:** If a ## phase section has no table rows, remove the
    entire section (heading + table header + empty body).

After repairs, produce a summary like:
  Repairs applied:
  - [TASKS.md] Added missing **Status:** to P1-T05 (default: Pending)
  - [TASKS.md] Renamed duplicate P1-T01 → P1-T01-duplicate
  - [SESSIONSTATE.md] Removed unknown task X-T99 from ## Up next
  - [TASKS-COMPLETED.md] Removed row with unknown ID Y-T01
  - 0 errors remaining after repair
```

---

### Prompt: Convert (Transform to tsm Format)

> Use this when you have existing project notes, checklists, or unstructured Markdown that you want to convert into the tsm workflow format. Paste this prompt, then paste your source material.

```
You are a format converter. I will give you unstructured or semi-structured project notes
and I want you to convert them into the tsm (Task and Session State Manager) workflow
format. You will output three files: TASKS.md, SESSIONSTATE.md, and TASKS-COMPLETED.md.

If the source material has phases and tasks, group them accordingly. If the source is a
flat list of items, create a single phase "Phase 1 — Migration" with all items as tasks.

--- OUTPUT FORMAT ---

TASKS.md structure:

```
# <Project Name> — Phase Task List

> [optional: a short description of the project]

---

## Phase structure

| Phase | Description | Status |
|-------|-------------|--------|
| **<Phase Name>** | <brief description> | Pending |

---

# <PHASE NAME> — <Subtitle>

**Status:** Pending

[optional: paragraph describing the phase]

---

## <Sub-phase heading (optional)>

### <PREFIX-T01> · <Task title>
**Status:** Pending
**Complexity:** <high | medium | low | unset>
**What:** <description of what to build — 1-3 sentences>
**Prerequisite:** <what must be done first, or "None.">
**Hard deps:** <comma-separated task IDs, or "None">
**Files:** <comma-separated file paths, or blank>
**Reviewer:** <Skip | Human review required | etc.>
**Key constraints:**
- <rule the AI must not violate — omit if none>
**Done when:**
- <specific, verifiable acceptance criteria>
```

TASK ID GENERATION:
- Phase prefix: take the first letter of each major word in the phase name, uppercase.
  E.g. "Phase 1 — Foundation" → prefix "P1", "Assessment Unification" → prefix "A",
  "Phase 2 — Widget Engine" → prefix "P2".
- Task numbers: T01, T02, T03, etc.
- Combined: P1-T01, P1-T02, A-T01, P2-T01.

If a phase already has a task naming scheme (e.g. "U-A1", "S-T06"), preserve it.

FIELD RULES:
- Status: use "Pending" for all new tasks, "✅ Complete" for tasks already done
- Complexity: infer from context — "high" for complex multi-file work, "medium" for
  standard changes, "low" for simple/config edits, "unset" if unsure
- Prerequisite: "None." if no dependency
- Hard deps: comma-separated task IDs, or "None"
- Files: comma-separated paths, or blank
- Reviewer: "Skip" if not specified
- Key constraints: include only if there are important rules the AI must follow
- Done when: list specific, testable criteria — each on its own bullet line

SESSIONSTATE.md structure:

```
*Last updated: <current datetime in YYYY-MM-DDTHH:MM format>

---

## Active phase

<none>

---

## Completed tasks

| Task | Description | Commit message |
|------|-------------|----------------|
|      |             |                |

---

## Active task

[none]

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|------|-------------|-----------|------------|----------|
|      |             |           |            |          |

---

## Out of scope

(empty — add nothing)
```

TASKS-COMPLETED.md structure:

```
# Completed Tasks Log

---

## <Phase name>

| Task | Description | Complexity | Commit message | Notes |
|------|-------------|------------|----------------|-------|
```

- Populate TASKS-COMPLETED.md only with tasks you marked as ✅ Complete
- Leave commit message and notes columns blank

CONVERSION GUIDELINES:

1. Group related items into phases. A good phase has 3-10 tasks.
2. Order tasks by dependency — tasks that must come first get lower numbers.
3. Set Hard deps based on natural order: if task B needs task A's output, B's
   Hard deps includes A's ID.
4. Multi-line **What:** and **Done when:** values are fine — use clear line breaks.
5. If the source has an order, preserve it. If not, use logical grouping.
6. If the source is entirely unstructured (e.g. a brainstorm dump), create one
   phase "Phase 1 — Initial Build" with reasonable task groupings.
7. Output ALL THREE files in full, clearly labelled with "--- TASKS.md ---",
   "--- SESSIONSTATE.md ---", "--- TASKS-COMPLETED.md ---" markers.
8. After conversion, explain your phase/task grouping decisions in a brief summary.
```

---

### Quick reference

| Situation | Prompt to use |
|-----------|---------------|
| Files look OK but you want a second opinion | [Check](#prompt-check-validate) |
| Files have known issues or corruption | [Repair](#prompt-repair-fix-issues) |
| Starting a new project from scratch | Use `tsm new-project` instead |
| Adapting existing notes/checklists into tsm format | [Convert](#prompt-convert-transform-to-tsm-format) |
| One file needs a quick fix (e.g. bad status token) | [Repair](#prompt-repair-fix-issues) with just that file |
| Validate after making manual edits | [Check](#prompt-check-validate) |
| Existing project using a different format | [Convert](#prompt-convert-transform-to-tsm-format) |

---

## Exit Codes

| Code | Meaning | Raised by |
|------|---------|-----------|
| `0` | Success | All commands |
| `1` | Precondition failure or generic error | Missing project root, unknown command |
| `2` | Parse error | Invalid [`TASKS.md`](../TASKS.md) or [`SESSIONSTATE.md`](../SESSIONSTATE.md) |
| `3` | Write error | Failed file write operation |

---

> **tsm** is fully local, deterministic, and never makes network calls of any kind. All logic runs on your machine with no telemetry, no LLM calls, and no external dependencies beyond Python's standard library and Textual.
