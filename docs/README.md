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

## Exit Codes

| Code | Meaning | Raised by |
|------|---------|-----------|
| `0` | Success | All commands |
| `1` | Precondition failure or generic error | Missing project root, unknown command |
| `2` | Parse error | Invalid [`TASKS.md`](../TASKS.md) or [`SESSIONSTATE.md`](../SESSIONSTATE.md) |
| `3` | Write error | Failed file write operation |

---

> **tsm** is fully local, deterministic, and never makes network calls of any kind. All logic runs on your machine with no telemetry, no LLM calls, and no external dependencies beyond Python's standard library and Textual.
