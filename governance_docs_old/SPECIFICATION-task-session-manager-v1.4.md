# Task and Session State Manager — Technical Specification

**Version:** 1.4
**Date:** 2026-04-26
**Purpose:** Personal tool. A terminal UI application for managing agentic coding workflow state across projects.
**Language:** Python 3.11+
**TUI Framework:** Textual

**Changelog from v1.3:**
- §2.1 — Added `--yes` flag (auto-confirm for agent/CI invocation) to in-scope list
- §2.2 — Added `--output json` on read-only commands to deferred v2 list
- §6.2 — Added `--yes` flag behaviour to confirm prompt specification
- §7.1 — Added global options table documenting `--yes`
- §10 — Replaced implicit exit codes with a defined 4-code exit code contract
- §12.5 — Added 2 new shadow/CLI tests for `--yes` and exit code behaviour
- §14 — Added `--yes` flag and exit code constraints

**Changelog from v1.2:**
- §5.5 — Added `slugify_phase_name()` specification (moved from §14; was implicit)
- §5.6 — Added `LoadedProject` dataclass (new; required by all command functions)
- §9.2 — Added explicit phase-level status write-back specification (was missing; required by `complete-phase`)
- §9.2 — Added dual write-strategy constraint callout box
- §14 — Slug generation now cross-references §5.5 instead of being defined inline

---

## 1. Overview

The Task and Session State Manager (hereafter **tsm**) is a locally-run Python CLI application that eliminates manual copy-paste overhead when advancing tasks and phases in a structured agentic coding workflow.

It reads and writes five markdown files that govern each project's AI coding sessions:

| File | Role |
|------|------|
| `TASKS.md` | Master list of all phases and atomic tasks |
| `SESSIONSTATE.md` | Current session context (active phase, active task, up next, completed) |
| `TASKS-COMPLETED.md` | Permanent log of completed tasks with notes |
| `AGENTS.md` | AI agent rules — **read-only to tsm, never modified** |
| `SPECIFICATION.md` | Full technical spec — **read-only to tsm, never modified** |

All file writes go to a **shadow directory** first. The user reviews a plain-language summary of the changes and confirms before they are applied to the live files. Every write operation takes a timestamped backup (last 5 per file, auto-pruned).

---

## 2. Scope

### 2.1 In Scope — v1.0

- TUI display: phases and tasks from `TASKS.md`, with status and key metadata
- Phase initialization: populate `SESSIONSTATE.md` for the start of a new phase
- Task advancement: move Active → Completed, promote next task from Up Next → Active
- Phase completion: rotate `SESSIONSTATE.md`, update `TASKS.md` and `TASKS-COMPLETED.md`
- Vibe check: integrity validation across all three writable files
- Shadow directory write model with confirm-to-apply prompt
- Timestamped backup system (last 5 per file, auto-pruned)
- Auto `.gitignore` enforcement for shadow and backup dirs
- `undo` command to revert most recent apply
- `help` command with per-command detail
- `new-project` command to scaffold blank workflow files in a new directory
- Task complexity field (`high | medium | low | unset`) on tasks and in session state
- `--yes` flag on all write commands: auto-confirms without interactive prompt, for agent/CI invocation

### 2.2 Out of Scope — v1.0 (deferred)

- Template generation for LLM file population
- Full side-by-side diff view (replaced by summary-with-prompt in v1.0)
- Multi-project switcher UI (rely on `cd` + invocation)
- Network calls, LLM calls, telemetry of any kind
- GUI / web interface
- `--output json` flag on read-only commands (`status`, `vibe-check`) — deferred to v2

---

## 3. Invocation and Project Discovery

### 3.1 Entry Point

```
python -m tsm
```

Or via installed entry point: `tsm`

### 3.2 Project Discovery

On launch, `tsm` looks for its required files starting from the **current working directory** and walking up the directory tree (max 3 levels) until it finds a directory containing `TASKS.md` **and** `SESSIONSTATE.md`. This is the **project root**.

If no project root is found, `tsm` exits with a clear error:

```
Error: Could not find TASKS.md and SESSIONSTATE.md in the current directory
or any parent directory (checked up to 3 levels).

Make sure you are inside a project that uses this workflow, or create the
required files using a template.
```

### 3.3 Shadow Directory

Shadow and backup paths are **project-local**:

```
<project-root>/
  .tsm/
    shadow/
      TASKS.md
      SESSIONSTATE.md
      TASKS-COMPLETED.md
    backups/
      TASKS.md.2026-04-23T14-32.bak
      SESSIONSTATE.md.2026-04-23T14-32.bak
      TASKS-COMPLETED.md.2026-04-23T14-32.bak
    history.log
```

On first run in a project, `tsm` creates `.tsm/` and **appends `.tsm/` to the project's `.gitignore`** (creates `.gitignore` if it does not exist). It prints a one-time notice:

```
Added .tsm/ to .gitignore — shadow files and backups will not be committed.
```

---

## 4. File Format Specification

This section defines the canonical formats that `tsm` reads and writes. The parser must handle all variants documented here.

---

### 4.1 TASKS.md

#### 4.1.1 File-level structure

TASKS.md uses **heading-block format** for individual tasks. The phase structure overview at the top of the file is the only markdown table in the file.

```
# <Project Name> — Phase Task List

> [optional preamble lines]

---

## Phase structure

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1A** | <description> | ✅ Complete |
| **Phase 1B** | <description> | 🔒 Blocked — <reason> |
| **Assessment Unification** | <description> | In progress |

---

# <PHASE HEADING> — <subtitle>

**Status: [status token]**

[optional narrative paragraph]

---

## <Sub-phase heading>

### <Task ID> · <Task title>
**Status:** [status token]
**Complexity:** <high | medium | low | unset>
**What:** <description, may span multiple lines>
**Prerequisite:** <human-readable dep description, or "None.">
**Hard deps:** <comma-separated task IDs, or "None">
**Files:** <comma-separated file paths, or blank>
**Reviewer:** <Gemini | Skip | Yes | Human review required>
**Key constraints:**
- <rule the AI must not violate — omit this field entirely if none>
**Done when:** <acceptance criteria, may span multiple lines>

### <Next Task ID> · <Next Task title>
...

### Dependency graph

```
<ASCII dependency graph — one per phase, placed after that phase's tasks>
```

---

# <NEXT PHASE HEADING>
...
```

#### 4.1.2 Heading level conventions

| Level | Use |
|-------|-----|
| `#` (H1) | Phase headings (e.g. `# PHASE 1A — Foundation`) |
| `##` (H2) | Sub-phase groupings within a phase (e.g. `## U-Phase A — Extractions`) — and the special `## Phase structure` table |
| `###` (H3) | Individual task blocks (e.g. `### U-A1 · Extract evaluateShowIf`) — and the special `### Dependency graph` block |

The `## Phase structure` H2 is identified by its exact heading text and parsed as a table, not a sub-phase grouping.

#### 4.1.3 Status tokens

The parser must recognise all of these (case-insensitive on text content; emoji must match exactly):

| Raw value | Canonical status | Display label |
|-----------|-----------------|---------------|
| `✅ Complete` | `complete` | ✅ Complete |
| `**Active**` or `Active` | `active` | ▶ Active |
| `Pending` | `pending` | · Pending |
| `🔒 Blocked` or `❌ Blocked` | `blocked` | 🔒 Blocked |
| `⚠️ Needs review` | `needs_review` | ⚠️ Needs review |
| `In progress` | `in_progress` | ▶ In progress |

#### 4.1.4 Task block field parsing rules

A task block begins with `### <ID> · <title>` and ends at the next `###`, `##`, `#`, or `---` line.

Fields are identified by their bold label prefix on a line:

| Field label | Required | Notes |
|-------------|----------|-------|
| `**Status:**` | Yes | See §4.1.3 |
| `**Complexity:**` | Yes | See §4.1.4a — `high`, `medium`, `low`, or `unset` |
| `**What:**` | Yes | Free text; may span multiple lines until next `**` label |
| `**Prerequisite:**` | Yes | Human-readable; `"None."` if no deps |
| `**Hard deps:**` | Yes | Comma-separated task IDs; `"None"` if no deps |
| `**Files:**` | Yes | Comma-separated file paths; blank line acceptable |
| `**Reviewer:**` | Yes | Raw text value |
| `**Key constraints:**` | No | Optional bullet list of task-scoped rules the AI must not violate; omit if none |
| `**Done when:**` | Yes | Free text acceptance criteria; may span multiple lines |

Multi-line field values: a field's value continues on subsequent lines until the next line that starts with `**` (a new field label) or a structural boundary (`#`, `---`).

#### 4.1.4a Complexity field values

| Raw value | Canonical value | Meaning |
|-----------|----------------|---------|
| `high` | `high` | Use a large/capable model (e.g. Sonnet, GPT-4) |
| `medium` | `medium` | Standard model appropriate |
| `low` | `low` | Small/cheap model sufficient |
| `unset` or blank | `unset` | Not yet assessed — vibe check will warn |

The complexity field is **informational only**. tsm never acts on it automatically. It is surfaced in the TUI task detail panel and in `## Active task` in SESSIONSTATE.md so you can see it at the start of each coding session.

#### 4.1.5 Hard deps field parsing

- `None` or `None.` → empty list
- `—` (em dash), `-`, or blank → empty list
- Otherwise: split on `,`, strip whitespace from each item → list of task ID strings

#### 4.1.6 Files field parsing

- Blank line → empty list
- Otherwise: split on `,`, strip whitespace, strip surrounding backticks, strip ` (new)` suffix → list of path strings
- Exception: if the entire cell contains no `/` or `.` characters (e.g. `See spec §8`), store as-is as a single opaque string

#### 4.1.7 Task ID format

Task IDs match the pattern `[A-Z0-9]+-[A-Z][0-9]+` (e.g. `U-A1`, `P1B-T03`, `S-T01`). Vibe check enforces uniqueness across the entire file.

#### 4.1.8 Dependency graph block

Each phase section ends with a `### Dependency graph` H3 block containing a fenced code block of ASCII art. The parser must:
- Recognise this block by the heading text `Dependency graph` exactly
- Store the full raw content (fenced block included) in `Phase.dependency_graph_raw`
- Never modify this block on write — preserve it verbatim

#### 4.1.9 Canonical task block example

```markdown
### S-T06 · P1B overall banner — engine (data layer)
**Status:** ✅ Complete
**Complexity:** low
**What:** Add overallRisk, overallLabel, overallHeading, and situationHTML fields
to the P1B results object. Logic only — no UI changes.
**Prerequisite:** S-T05 complete.
**Hard deps:** S-T05
**Files:** `lib/engine/calculateDomain.ts`, `lib/engine/types.ts`
**Reviewer:** Skip
**Key constraints:**
- situationHTML must be server-rendered only — never passed to client components
**Done when:** tsc --noEmit clean, unit tests updated and passing.
```

If a task has no key constraints, the `**Key constraints:**` field is omitted entirely. The parser treats its absence as an empty list — it must not flag this as a VC-11 missing-field error.

---

### 4.2 SESSIONSTATE.md

#### 4.2.1 Canonical format

```markdown
*Last updated: YYYY-MM-DDTHH:MM*

---

## Active phase
<phase name> — <status>.
Spec: `<spec file>`

---

## Completed tasks

| Task | Description | Commit message |
|---|---|---|
| <task-id> | <description> | <commit message> |

---

## Active task

**<task-id> — <task title>**

- Complexity: <high | medium | low | unset>
- Files: <file list>
- Hard deps: <dep list>
- Reviewer: <reviewer>
- Key constraints:
  - <constraint>
  - <constraint>

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|---|---|---|---|---|
| <task-id> | <description> | <deps> | <complexity> | <reviewer> |

---

## Out of scope

- <item>
```

The `## Active task` block is a verbatim copy of `Task.raw_block` from TASKS.md. The `- Key constraints:` bullet list appears only when the source task block contains a `**Key constraints:**` field. If the task has no key constraints, that field is absent in both TASKS.md and the `## Active task` block — there is no placeholder.

#### 4.2.2 Section parsing rules

- Sections are delimited by `---` horizontal rules
- `*Last updated: YYYY-MM-DDTHH:MM*`: parse from the first non-blank line of the file; format is ISO 8601 date + hour + minute, colons preserved (not filesystem-escaped in the file content itself)
- `## Active task` block: everything between the heading and the next `---` is the task body — stored verbatim and re-emitted unchanged unless the command explicitly replaces it; the `- Complexity:` bullet is parsed out for display and VC-13
- `## Completed tasks` and `## Up next`: standard `|`-delimited markdown tables; `## Up next` includes a `Complexity` column
- `## Out of scope`: **read-only** — stored verbatim, never modified by tsm

#### 4.2.3 Blank/unset states

If `## Active task` contains only the heading line and no further content, or contains the literal text `[none]`, the task is considered unset. Same rule applies to `## Active phase`.

---

### 4.3 TASKS-COMPLETED.md

#### 4.3.1 Append-only format

```markdown
# Completed Tasks Log

---

## <Phase name>

**Completed: YYYY-MM-DDTHH:MM**

| Task | Description | Complexity | Commit message | Notes |
|------|-------------|------------|----------------|-------|
| <id> | <description> | <complexity> | <commit> | <notes> |
```

`tsm` only **appends** to this file — it never modifies existing content. If the file does not exist, `tsm` creates it with the header `# Completed Tasks Log` followed by `---`.

---

## 5. Data Model

These are the canonical Python dataclasses. Claude Code must implement these exactly.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


class TaskStatus(Enum):
    COMPLETE = "complete"
    ACTIVE = "active"
    PENDING = "pending"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"
    IN_PROGRESS = "in_progress"


class TaskComplexity(Enum):
    HIGH = "high"       # Use a large/capable model
    MEDIUM = "medium"   # Standard model appropriate
    LOW = "low"         # Small/cheap model sufficient
    UNSET = "unset"     # Not yet assessed


@dataclass
class Task:
    id: str                          # e.g. "U-A1"
    title: str                       # text after the · in the ### heading
    status: TaskStatus
    complexity: TaskComplexity       # **Complexity:** value; defaults to UNSET if absent
    what: str                        # **What:** value (multi-line joined as single string)
    prerequisite: str                # **Prerequisite:** value (human-readable)
    hard_deps: list[str]             # parsed task IDs from **Hard deps:**
    files: list[str]                 # parsed paths from **Files:**
    reviewer: str                    # raw **Reviewer:** value
    key_constraints: list[str]       # **Key constraints:** bullet items; empty list if field absent
    done_when: str                   # **Done when:** value (multi-line joined as single string)
    phase_id: str                    # slug of parent phase
    subphase: Optional[str]          # sub-phase heading text, or None
    raw_block: str                   # original full task block text — used for write-back


@dataclass
class Phase:
    id: str                          # slugified heading — see slugify_phase_name() in §5.5
    name: str                        # full heading text, e.g. "PHASE 1A — Foundation"
    status: str                      # raw status token from **Status:** line
    description: str                 # optional narrative paragraph after the heading
    tasks: list[Task] = field(default_factory=list)
    dependency_graph_raw: str = ""   # raw ### Dependency graph block, preserved verbatim


@dataclass
class PhaseOverviewRow:
    """Row from the ## Phase structure table at the top of TASKS.md."""
    phase_name: str
    description: str
    status: str


@dataclass
class SessionState:
    last_updated: datetime           # parsed from *Last updated: YYYY-MM-DDTHH:MM*
    active_phase_name: str           # may be "[none]"
    active_phase_spec: str           # spec file reference
    active_task: Optional[Task]      # None if unset/[none]
    active_task_raw: str             # verbatim ## Active task block body
    up_next: list[Task]
    completed: list[Task]            # completed tasks in current phase window
    out_of_scope_raw: str            # verbatim ## Out of scope block body


@dataclass
class PendingWrite:
    """Represents a staged file change awaiting user confirmation."""
    target_file: str                 # filename only, e.g. "SESSIONSTATE.md"
    shadow_path: str                 # absolute path to shadow copy
    live_path: str                   # absolute path to live file
    backup_path: str                 # absolute path to backup (created at apply time)
    summary_lines: list[str]         # human-readable bullet points describing changes


@dataclass
class ProjectContext:
    root: str                        # absolute path to project root
    tasks_path: str
    sessionstate_path: str
    tasks_completed_path: str
    shadow_dir: str
    backup_dir: str
    history_log_path: str
```

### 5.5 Helper functions

```python
import re

def slugify_phase_name(name: str, existing_slugs: list[str] | None = None) -> str:
    """Derive a Phase.id slug from a phase heading text string.

    Algorithm:
      1. Lowercase the entire string.
      2. Replace all whitespace sequences with a single hyphen.
      3. Strip all characters that are not alphanumeric (a-z, 0-9) or hyphens.
      4. Strip leading and trailing hyphens.
      5. Collision detection: if the resulting slug already appears in
         existing_slugs, append "-2". If "-2" also exists, try "-3", and so
         on until a unique slug is found.

    Args:
        name:           The raw phase heading text, e.g. "PHASE 1A — Foundation".
        existing_slugs: List of slugs already in use. Pass [] or omit when
                        building the first phase. The parser accumulates this
                        list as it reads phases in file order.

    Returns:
        A unique slug string, e.g. "phase-1a--foundation" or "phase-1a--foundation-2".

    Examples:
        slugify_phase_name("Assessment Unification", [])
            → "assessment-unification"
        slugify_phase_name("Phase 1A", [])
            → "phase-1a"
        slugify_phase_name("Phase 1A", ["phase-1a"])
            → "phase-1a-2"
        slugify_phase_name("Phase 1A", ["phase-1a", "phase-1a-2"])
            → "phase-1a-3"
    """
    if existing_slugs is None:
        existing_slugs = []
    slug = name.lower()
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    slug = slug.strip('-')
    if slug not in existing_slugs:
        return slug
    counter = 2
    while f"{slug}-{counter}" in existing_slugs:
        counter += 1
    return f"{slug}-{counter}"
```

This function is defined in `models.py` as a module-level function. The `tasks_parser.py` imports and calls it while building each `Phase` object, passing the accumulated list of slugs already assigned earlier in the file. **No other module should reimplement slug logic.**

### 5.6 LoadedProject dataclass

`LoadedProject` is the bootstrapping object passed to every command function. It carries the fully parsed in-memory state of a project — project paths, parsed TASKS.md, and parsed SESSIONSTATE.md — so each command receives a single coherent input rather than independently loading and cross-referencing files.

```python
@dataclass
class LoadedProject:
    """In-memory loaded state of a project. Passed to every command function.

    Built by __main__.py immediately after project root discovery:
      1. find_project_root() → ProjectContext
      2. parse_tasks_file()  → (phase_overview, phases)
      3. parse_session_file() → SessionState
      4. Construct LoadedProject from all three.

    Commands receive this object and must not re-parse files themselves.
    Writers receive only the specific data they need (e.g. a Phase, a Task,
    a SessionState), extracted from this object by the command layer.
    """
    project_context: ProjectContext
    phases: list[Phase]                    # all phases parsed from TASKS.md, in file order
    phase_overview: list[PhaseOverviewRow] # rows from ## Phase structure table
    session: SessionState                  # parsed from SESSIONSTATE.md
```

**Construction contract** (implemented in `__main__.py`, not in any command module):

```python
def load_project(root: Path) -> LoadedProject:
    ctx = build_project_context(root)
    phase_overview, phases = parse_tasks_file(ctx.tasks_path)
    session = parse_session_file(ctx.sessionstate_path)
    return LoadedProject(
        project_context=ctx,
        phases=phases,
        phase_overview=phase_overview,
        session=session,
    )
```

Commands that do not require a project root (`help`, `new-project`) never receive a `LoadedProject`.

---

## 6. Shadow Write Model

Every operation that modifies files follows this exact sequence.

### 6.1 Stage

1. Load current live file content from disk
2. Parse into the data model
3. Apply the transformation in memory
4. Serialize the updated data model back to markdown via a dedicated renderer
5. Write rendered string to the shadow copy (`<shadow_dir>/<filename>`)
6. Build a `PendingWrite` with human-readable `summary_lines`

### 6.2 Confirm prompt

Displayed as a modal overlay in the TUI (or plain stdout in CLI mode):

```
─────────────────────────────────────────
  Pending changes — review before applying
─────────────────────────────────────────
  SESSIONSTATE.md
    • Move U-C2 → Completed tasks (commit: "U-C2: create page client")
    • Set Active task → U-D1
    • Remove U-D1 from Up next

  TASKS.md
    • Set U-C2 status → ✅ Complete

  TASKS-COMPLETED.md
    • Append U-C2 to Phase: Assessment Unification

─────────────────────────────────────────
  Apply changes? [Y/n]:
```

- `Y` or Enter → Apply
- `n` → discard shadow files, return to main view with: `Changes discarded.`

#### `--yes` flag (auto-confirm mode)

When any write command is invoked with `--yes` (e.g. `tsm advance --yes`), `confirm_prompt()` skips the interactive prompt entirely, prints the change summary to stdout, and returns `True` immediately. The full summary is always printed — `--yes` suppresses the prompt, not the output.

This flag exists exclusively for agent and CI invocation where no human is present to type `Y`. It must never be passed implicitly or defaulted to `True` — it must be an explicit CLI argument every time.

**`--yes` is parsed in `__main__.py` before dispatch.** It is passed as a boolean argument to `confirm_prompt()`. No command module is aware of this flag — command functions always return `list[PendingWrite]` regardless.

### 6.3 Apply

For each file in the `PendingWrite` set, in order:

1. Create timestamped backup of the current live file:
   `<backup_dir>/<filename>.<YYYY-MM-DDTHH-MM>.bak`
   (colons replaced with hyphens for filesystem compatibility; seconds omitted)
2. Copy shadow file to live path (write to temp file, then `os.replace` for atomicity)
3. Prune backups for this filename: keep the 5 most recent, delete older ones
4. Append entry to `.tsm/history.log`

### 6.4 History log format

File: `.tsm/history.log`
One line per operation:

```
2026-04-23T14:32 | advance    | U-C2 → complete        | SESSIONSTATE.md, TASKS.md, TASKS-COMPLETED.md
2026-04-23T15:10 | init-phase | Assessment Unification  | SESSIONSTATE.md
2026-04-23T15:10 | init-phase | Assessment Unification  | SESSIONSTATE.md [undone]
```

### 6.5 Undo

1. Read the last non-`[undone]` entry in `.tsm/history.log`
2. For each file listed, find the most recent `.bak` file in `<backup_dir>/` and copy it to the live path
3. Mark the history log entry `[undone]`
4. Print:
   ```
   Undo: restored SESSIONSTATE.md, TASKS.md from backups taken at 2026-04-23T14-32.
   ```

Single-level only. A second consecutive `undo` prints: `Nothing to undo.`
Undo does not create a new backup and does not touch shadow files.

---

## 7. Commands

### 7.1 Command reference

| Command | Description |
|---------|-------------|
| `init-phase <phase-id>` | Initialize SESSIONSTATE.md for the start of a new phase |
| `advance` | Move Active → Completed, promote first ready Up Next task → Active |
| `complete-phase` | Mark current phase complete, rotate to next phase |
| `vibe-check` | Integrity validation across all three writable files |
| `undo` | Revert the most recent apply operation |
| `status` | Print current session state (read-only) |
| `help [command]` | Show help for all commands, or detailed help for a specific command |
| `new-project [--name <n>]` | Scaffold blank workflow files in the current directory |

All commands work both from the TUI (keybinding) and as CLI subcommands (`tsm <command>`).

#### Global options

| Flag | Applies to | Behaviour |
|------|-----------|-----------|
| `--yes` | All write commands (`advance`, `init-phase`, `complete-phase`) | Auto-confirm: print change summary, skip interactive prompt, apply immediately. For agent/CI use. |
| `--help` | Top-level only | Identical to `tsm help` |

`--yes` is not valid on read-only commands (`status`, `vibe-check`, `undo`, `help`, `new-project`). Passing it to a read-only command prints: `Warning: --yes has no effect on <command>.` and proceeds normally.

---

### 7.2 Command: `init-phase`

**Input:** Phase ID string (matched case-insensitively against phase slugs in TASKS.md).

**Precondition checks (abort with error if any fail):**
- Phase exists in TASKS.md
- Phase has at least one task with status not `complete`

**Active task selection logic:**
The first task in the phase (in file order) whose `hard_deps` list is either empty or contains only task IDs with status `complete` in TASKS.md. If no such task exists, `## Active task` is set to `[none]` and the user is warned:
```
⚠️  No tasks in this phase have all hard deps met.
    Set Active task manually once dependencies are resolved.
```

**Writes to SESSIONSTATE.md:**
- Set `## Active phase` to phase name + `— in progress.` + spec file reference
- Set `## Active task` to the selected task's full block body (from `Task.raw_block`)
- Set `## Up next` table to all remaining pending tasks for the phase (excluding active)
- Clear `## Completed tasks` (empty table, header row only)
- Update `*Last updated:*` to current datetime (YYYY-MM-DDTHH:MM)

No writes to TASKS.md or TASKS-COMPLETED.md.

**Confirm summary:**
```
SESSIONSTATE.md
  • Set Active phase → "Assessment Unification — in progress."
  • Set Active task → U-A1 (no hard deps, ready to start)
  • Added 14 tasks to Up next (U-A2 … U-E4)
  • Cleared Completed tasks
```

---

### 7.3 Command: `advance`

**Precondition check:** `## Active task` is set (not blank, not `[none]`).

**Commit message prompt** (before staging):
```
Commit message for <task-id> (optional — press Enter to skip):
>
```

**Next task promotion logic:**
From the current `## Up next` list, select the first task whose `hard_deps` are all met — meaning each dep ID is either already `complete` in TASKS.md, or is the task just being advanced. If no task is immediately ready, set `## Active task` to `[none]` and warn:
```
⚠️  No tasks in Up next have all hard deps met.
    Set Active task manually once dependencies are resolved.
```

**Writes:**

`SESSIONSTATE.md`:
- Append just-completed task row to `## Completed tasks` (ID, title, commit message)
- Set `## Active task` to the promoted task's `raw_block` body
- Remove promoted task from `## Up next`
- Update `*Last updated:*` to current datetime (YYYY-MM-DDTHH:MM)

`TASKS.md`:
- Set just-completed task's `**Status:**` line to `✅ Complete`
- All other content preserved verbatim

`TASKS-COMPLETED.md`:
- Append row to current phase section (create section if it does not exist)

**Confirm summary:**
```
SESSIONSTATE.md
  • Move U-C2 → Completed tasks (commit: "U-C2: create page client")
  • Set Active task → U-D1
  • Remove U-D1 from Up next

TASKS.md
  • Set U-C2 status → ✅ Complete

TASKS-COMPLETED.md
  • Append U-C2 to section "Assessment Unification"
```

---

### 7.4 Command: `complete-phase`

**Precondition check:** All tasks in the current phase (identified by `phase_id` in TASKS.md) must have status `complete`. If not:
```
❌ Cannot complete phase — the following tasks are not complete:
   U-D1 (Pending)
   U-D2 (Pending)
```

**Next phase detection:** Phases appear in TASKS.md in file order. The next phase is the first phase after the current one with a status other than `complete`. If none exists, next phase is `[none]`.

**Writes:**

`SESSIONSTATE.md`:
- Update `## Active phase` to next phase (or `[none]`)
- Clear `## Completed tasks`
- Set `## Active task` to first dep-free task of next phase (or `[none]`)
- Set `## Up next` to remaining tasks of next phase (or empty)
- Update `*Last updated:*` to current datetime (YYYY-MM-DDTHH:MM)

`TASKS.md`:
- Set completed phase's `**Status:**` line to `✅ Complete`
  (This is a **phase-level** status update — see §9.2 for the exact write-back strategy)

`TASKS-COMPLETED.md`:
- Append phase completion marker line: `**Phase complete: YYYY-MM-DD**`

**Confirm summary:**
```
SESSIONSTATE.md
  • Phase "Assessment Unification" → complete
  • Set Active phase → "PHASE 1C — Product Risk Level 1"
  • Set Active task → P1C-T01
  • Added 5 tasks to Up next

TASKS.md
  • Set Assessment Unification status → ✅ Complete

TASKS-COMPLETED.md
  • Append phase completion marker for Assessment Unification
```

---

### 7.5 Command: `vibe-check`

**Read-only — no file writes.**

#### Validation rules

| Rule ID | Severity | Description |
|---------|----------|-------------|
| VC-01 | Error | Duplicate task IDs anywhere in TASKS.md |
| VC-02 | Error | A `**Hard deps:**` value references a task ID that does not exist in TASKS.md |
| VC-03 | Error | The task in SESSIONSTATE.md `## Active task` has status `complete` in TASKS.md |
| VC-04 | Error | A task in SESSIONSTATE.md `## Up next` has status `complete` in TASKS.md |
| VC-05 | Warning | A task in SESSIONSTATE.md `## Up next` has at least one hard dep not yet `complete` in TASKS.md |
| VC-06 | Warning | SESSIONSTATE.md `## Active task` is blank or `[none]` |
| VC-07 | Warning | SESSIONSTATE.md `## Active phase` is blank or `[none]` |
| VC-08 | Error | `## Phase structure` table references a phase name with no matching `#` section in TASKS.md |
| VC-09 | Warning | A task in TASKS.md has status `Active` or `In progress` but does not match the `## Active task` in SESSIONSTATE.md |
| VC-10 | Error | TASKS-COMPLETED.md contains a task ID not found in TASKS.md |
| VC-11 | Warning | A task block in TASKS.md is missing a required field (`**Key constraints:**` absence is not a VC-11 violation — see §4.1.9) |
| VC-12 | Warning | `*Last updated:*` datetime in SESSIONSTATE.md is more than 7 days ago (compare as datetime, not date) |
| VC-13 | Warning | A task in SESSIONSTATE.md `## Up next` or `## Active task` has `complexity: unset` — model selection not yet assessed |

#### Output format

```
─────────────────────────────
  Vibe Check — 2026-04-23T14:32
─────────────────────────────

  ✅ No errors found.
  ⚠️  3 warnings

  WARNINGS
  ─────────
  VC-05  SESSIONSTATE.md · Up next
         U-D1 has unmet hard dep: U-C2 (Pending)

  VC-12  SESSIONSTATE.md
         Last updated 2026-04-10T09:15 — 13 days ago

  VC-13  SESSIONSTATE.md · Up next
         U-D2 complexity is unset — model not yet assessed

─────────────────────────────
```

If errors exist, the header reads:
```
  ❌ 1 error   ⚠️  1 warning
```

---

### 7.6 Command: `status`

Read-only. Prints structured summary to stdout. Does not launch TUI when run as `tsm status`.

```
─────────────────────────────
  Session Status
─────────────────────────────
  Phase:       Assessment Unification (in progress)
  Spec:        TECHNICAL-SPEC-unification.md
  Updated:     2026-04-23T14:32

  Active task: U-C2 — Create UnifiedAssessmentPageClient.tsx
               Complexity: high  ← use large model
               Hard deps:  U-C1 ✅
               Reviewer:   Gemini

  Up next:     U-D1 (med), U-D2 (high), U-D3 (low), U-E1 (unset), U-E2 (unset), U-E3 (unset), U-E4 (unset)  (7 tasks)

  Completed:   U-D1, U-D2, U-D3, U-C1  (4 tasks this phase)
─────────────────────────────
```

---

### 7.7 Command: `undo`

See §6.5.

---

### 7.8 Command: `help`

**Read-only — no file writes. Does not require a project root to be found.**

Invocation variants:

| Invocation | Output |
|------------|--------|
| `tsm help` | Lists all commands with a one-line description each |
| `tsm --help` | Identical to `tsm help` |
| `tsm help <command>` | Full detail for a single command: usage, description, preconditions, examples |

**`tsm help` output format:**

```
tsm — Task and Session State Manager

Usage: tsm <command> [options]

Commands:
  init-phase <phase-id>    Initialise SESSIONSTATE.md for the start of a phase
  advance                  Complete active task, promote next task to active
  complete-phase           Mark current phase done, rotate to the next phase
  vibe-check               Validate integrity of TASKS.md and SESSIONSTATE.md
  status                   Print current session state (read-only)
  undo                     Revert the most recent apply operation
  new-project [--name]     Scaffold blank workflow files in the current directory
  help [command]           Show this help, or detail for a specific command

Run 'tsm help <command>' for full usage of any command.
```

**`tsm help <command>` output format (example):**

```
tsm advance

  Complete the active task and promote the next ready task to active.

  Preconditions:
    • SESSIONSTATE.md ## Active task must be set (not blank, not [none])

  Writes:
    • SESSIONSTATE.md  — moves active → completed, sets new active task
    • TASKS.md         — sets completed task status to ✅ Complete
    • TASKS-COMPLETED.md — appends completed task row

  All writes go to shadow first and require confirmation before applying.

  Options:
    (none — commit message is prompted interactively)

  Example:
    tsm advance
```

Per-command detail must be implemented for all eight commands. The help text must stay in sync with the spec — implement as static strings in each command module, not generated from code.

This command is also accessible in the TUI via the `[?]` keybinding, which opens the help panel for the currently highlighted command.

---

### 7.9 Command: `new-project`

**Does not require an existing project root. Creates workflow files in the current working directory.**

**Invocation:**
```
tsm new-project [--name "Project Name"]
```

If `--name` is not provided, `tsm` prompts:
```
Project name (used in file headers, press Enter to use directory name):
>
```
If the user presses Enter with no input, the current directory name is used.

**Abort conditions (print error, create nothing):**
- `TASKS.md` already exists in the current directory
- `SESSIONSTATE.md` already exists in the current directory
- Either check fails → print:
  ```
  ❌ TASKS.md already exists in this directory.
     Use 'tsm status' to check the current project state.
     Run 'tsm new-project' only in an empty project directory.
  ```

**Files created:**

Creates all five workflow files as blank templates. No shadow/confirm flow — these are new files, nothing to overwrite.

`TASKS.md`:
```markdown
# <Project Name> — Phase Task List

> Tasks are ordered by dependency. Do not start a task until all prerequisites are met.

---

## Phase structure

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | [describe phase] | Pending |

---

# Phase 1 — [Phase title]

**Status:** Pending

[Describe what this phase delivers]

---

## Phase 1 tasks

### P1-T01 · [Task title]
**Status:** Pending
**Complexity:** unset
**What:** [Describe what this task does]
**Prerequisite:** None.
**Hard deps:** None
**Files:** 
**Reviewer:** [Gemini | Skip | Yes]
**Done when:** [Describe acceptance criteria]

### Dependency graph

```
P1-T01
```

---
```

`SESSIONSTATE.md`:
```markdown
*Last updated: YYYY-MM-DDTHH:MM*

---

## Active phase
[none]

---

## Completed tasks

| Task | Description | Commit message |
|---|---|---|

---

## Active task

[none]

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|---|---|---|---|---|

---

## Out of scope

- [List anything explicitly out of scope]
```

`TASKS-COMPLETED.md`:
```markdown
# Completed Tasks Log

---
```

`AGENTS.md`:
```markdown
# Agent Rules

> Rules for AI coding agents working on this project.
> Read this file at the start of every session before reading SESSIONSTATE.md.

---

## General rules

- Rule 1: Read SESSIONSTATE.md before starting any task
- Rule 2: Do not begin work if ## Active task is blank or [none]
- Rule 3: Only work on the task in ## Active task — do not skip ahead
- Rule 4: Do not modify files listed in ## Out of scope

---

## Project-specific rules

[Add project-specific constraints here]
```

`SPECIFICATION.md`:
```markdown
# <Project Name> — Technical Specification

**Version:** 0.1
**Date:** YYYY-MM-DD

---

## Overview

[Describe what this project builds]

---

## Architecture

[Describe the technical architecture]

---

## Key decisions

[Record important technical decisions and their rationale]
```

**Post-creation output:**
```
✅ Created project files for "<Project Name>" in /path/to/directory

  TASKS.md              — master task list (edit this to plan your work)
  SESSIONSTATE.md       — session state (managed by tsm)
  TASKS-COMPLETED.md    — completion log (managed by tsm)
  AGENTS.md             — AI agent rules (edit to add project constraints)
  SPECIFICATION.md      — technical spec (fill in before starting work)

Next steps:
  1. Fill in SPECIFICATION.md with your project's technical design
  2. Fill in TASKS.md with your phases and atomic tasks
  3. Add project-specific rules to AGENTS.md
  4. Run 'tsm init-phase <phase-id>' to begin your first phase
  5. Run 'tsm vibe-check' to validate your TASKS.md structure
```

`.tsm/` is also created and `.gitignore` is updated, identical to first-run behaviour described in §3.3.

---

## 8. TUI Layout

### 8.1 Screen layout

```
┌─────────────────────────────────────────────────────────────┐
│ tsm — Task & Session Manager                  [project name] │
├──────────────────────┬──────────────────────────────────────┤
│ PHASES & TASKS       │ TASK DETAIL                          │
│                      │                                      │
│ ▶ Phase 1A ✅        │ Task:       U-C2                     │
│   Phase 1B ✅        │ Title:      Create Unified...        │
│ ▶ Assessment Unif…   │ Status:     ▶ Active                 │
│   U-A1 ▶ Active     │ Complexity: 🔴 high                  │
│   U-A2 · Pending    │ Phase:      Assessment Unification   │
│   U-A3 · Pending    │                                      │
│   U-A4 · Pending    │ Hard deps:  U-C1 ✅                  │
│   U-B1 · Pending    │ Reviewer:   Gemini                   │
│                      │                                      │
│                      │ Files:                              │
│                      │   components/assessment/...         │
│                      │   components/assessment/...         │
│                      │                                      │
│                      │ Done when:                          │
│                      │   Grep acceptance criterion         │
│                      │   verifies Rule 24. Level 1 upsell  │
│                      │   hardcoded with inline comment.    │
├──────────────────────┴──────────────────────────────────────┤
│ [a]dvance  [i]nit-phase  [c]omplete-phase  [v]ibe-check     │
│ [u]ndo     [s]tatus      [?]help           [q]uit           │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Left panel — Phases & Tasks

- Textual `Tree` widget
- Phases are top-level nodes, **collapsed by default** unless they contain the active task
- Active phase auto-expanded on launch
- Task rows: status icon + Task ID + title truncated to 30 chars
- Active task highlighted in accent color; complete tasks and phases in muted color
- Keyboard: arrow keys to navigate, Enter to expand/collapse phase, Enter on task to load detail

### 8.3 Right panel — Task Detail

Shows full detail for the selected task:
- Task ID, Title, Status, Phase
- Complexity: displayed with color indicator — 🔴 high, 🟡 medium, 🟢 low, ⚪ unset
- Hard deps: each shown as `<ID> <status-icon>` (live status from parsed TASKS.md)
- Reviewer
- Files: one per line
- Key constraints: bullet list, shown only if the field is present; omitted entirely if the task has no constraints
- Done when: full text, word-wrapped

### 8.4 Command bar

Fixed footer. Context-aware greying:
- `[i]nit-phase` greyed out if a phase is already active with an active task set
- `[c]omplete-phase` greyed out if any tasks in current phase are not `complete`
- `[u]ndo` greyed out if no undoable entry exists in history log

### 8.5 Confirm-to-apply overlay

Modal overlay (not a separate screen). Displays the `PendingWrite` summary. Responds to `y`/`n` keys and rendered `[Y] Apply` / `[N] Discard` buttons.

### 8.6 Vibe Check panel

Replaces the right panel when vibe check is active. Scrollable list: errors first (red), then warnings (yellow). Press `Escape` or `q` to dismiss and return to task detail view.

### 8.7 Help panel

Replaces the right panel when `[?]` is pressed. Displays the full `tsm help` output as a scrollable read-only panel. Press `Escape` or `q` to dismiss. The content is the same as `tsm help` in CLI mode.

---

## 9. Parser Implementation

### 9.1 Overall strategy

All three writable files use a **structured line iterator with a state machine**. Do not use a general Markdown parser library. The formats are domain-specific and well-defined enough to parse with line-by-line state tracking.

### 9.2 TASKS.md parser

#### State machine states

| State | Description |
|-------|-------------|
| `PREAMBLE` | Before the first `---` |
| `PHASE_STRUCTURE_TABLE` | Inside the `## Phase structure` table block |
| `BETWEEN_PHASES` | Between `#` phase sections |
| `PHASE_HEADER` | Just read a `#` heading; reading phase-level metadata |
| `SUBPHASE_HEADER` | Inside a `##` sub-phase grouping |
| `TASK_BLOCK` | Inside a `###` task block; collecting field lines |
| `DEP_GRAPH` | Inside a `### Dependency graph` fenced code block |

#### Task block field collection

On entering `TASK_BLOCK` (triggered by a `### ` line that is not `### Dependency graph`):

1. Extract task ID and title from heading: `### <ID> · <title>`
2. Collect lines until next structural boundary (`###`, `##`, `#`, `---`)
3. Identify field lines by `**<FieldName>:**` prefix
4. Multi-line values: accumulate subsequent non-field, non-structural lines into the current field's value
5. Store full raw block in `Task.raw_block`

#### TASKS.md write-back strategy — task-level status update

When updating a **task's** status (the `advance` command):

1. Scan for the line `### <task-id> ·` to locate the task block
2. Within that block, find the `**Status:**` line
3. Replace **only that line** with the updated status value
4. Write full reconstructed file content (all other bytes identical) to shadow path

#### TASKS.md write-back strategy — phase-level status update

When updating a **phase's** status (the `complete-phase` command):

1. Scan for the line `# <phase-heading-text>` (exact H1 heading match) to locate the phase block
2. Within that phase header — the lines between the `#` heading and the first `---` or next `#` — find the `**Status:**` line
3. Replace **only that line** with the updated status value (e.g. `**Status:** ✅ Complete`)
4. Write full reconstructed file content (all other bytes identical) to shadow path

**Example:** Given this phase header block:

```markdown
# Assessment Unification — Phase 2

**Status:** In progress

This phase unifies the assessment flow.

---
```

After `complete-phase`, only the `**Status:**` line changes:

```markdown
# Assessment Unification — Phase 2

**Status:** ✅ Complete

This phase unifies the assessment flow.

---
```

All task blocks, dependency graph ASCII art, and all other content remain byte-for-byte identical.

> ⚠️ **Dual write-strategy constraint — do not mix these up:**
>
> | File | Strategy | Used by |
> |------|----------|---------|
> | `TASKS.md` | **Targeted line replacement only** — never full re-serialization | `advance` (task status), `complete-phase` (phase status) |
> | `SESSIONSTATE.md` | **Full reconstruction** via `render_sessionstate()` | All commands that write session state |
>
> Applying the wrong strategy to a file is a silent data-corruption bug:
> re-serializing TASKS.md will destroy dependency graph ASCII art and alter
> whitespace; targeted-replacing SESSIONSTATE.md will produce structurally
> inconsistent output. The writer modules enforce this — `tasks_writer.py`
> exposes only targeted-replacement functions; `session_writer.py` exposes only
> the full renderer. Neither module exposes the other's strategy.

Do **not** re-serialize the full file from the data model — this risks altering formatting, whitespace, or the dependency graph ASCII art. Use targeted line replacement only.

### 9.3 SESSIONSTATE.md parser

Section-based:
1. Split on `---` (horizontal rule lines) to identify section blocks
2. Identify each block by its `##` heading
3. `## Active task`: store full content as `active_task_raw`; also parse task ID and title from the `**<ID> — <title>**` line for display
4. `## Completed tasks` and `## Up next`: parse as standard `|`-delimited markdown tables
5. `*Last updated: YYYY-MM-DDTHH:MM*`: parse from first non-blank line using `datetime.strptime(value, "%Y-%m-%dT%H:%M")`
6. `## Out of scope`: store full content as `out_of_scope_raw`

#### SESSIONSTATE.md write-back strategy

Use **full reconstruction** via `render_sessionstate(state: SessionState) -> str`. Safe because tsm fully owns this file (the only freeform section is `## Out of scope`, stored verbatim and re-emitted unchanged).

Renderer invariants:
- Emit `*Last updated: YYYY-MM-DDTHH:MM*` with the current datetime on every write
- Emit `---` between every section
- Re-emit `active_task_raw` verbatim if not changed by the current command; replace with new task's `raw_block` only when the command explicitly promotes a new active task
- Re-emit `out_of_scope_raw` exactly as stored

### 9.4 TASKS-COMPLETED.md parser/writer

Parsing: identify phase sections by `## <phase name>` headings. Store as a list of `(phase_name: str, rows: list[dict])` tuples.

Writing: append-only.
1. Find the section for the current phase name (last occurrence)
2. If not found, append a new `## <phase name>` section with header row
3. Append the new data row
4. Write full reconstructed file content to shadow path

### 9.5 Edge cases that must be handled

| Variant | File | Handling |
|---------|------|----------|
| Backtick-wrapped paths | TASKS.md Files field | Strip `` ` `` wrappers |
| ` (new)` suffix | TASKS.md Files field | Strip suffix, retain path |
| Em dash `—` in Hard deps | TASKS.md | Empty list |
| `None` or `None.` in Hard deps | TASKS.md | Empty list |
| Multi-line `**What:**` or `**Done when:**` | TASKS.md | Accumulate lines until next `**` or structural boundary |
| `**Active**` bold-wrapped status | TASKS.md | Strip `**` wrappers before status matching |
| Status emoji prefix | TASKS.md | Match by emoji token, text token, or both |
| Blank `**Files:**` line | TASKS.md | Empty list |
| `See spec §N` in Files field | TASKS.md | Store as-is; do not attempt path splitting |
| `## Phase structure` H2 without tasks | TASKS.md | Parse as overview table, not a sub-phase |
| `### Dependency graph` H3 | TASKS.md | Enter `DEP_GRAPH` state; store raw content; do not parse as task |
| `**Key constraints:**` field absent from task block | TASKS.md | `key_constraints = []`; not a VC-11 error |
| `**Key constraints:**` field present with bullet items | TASKS.md | Each `- <item>` line parsed to list of strings, leading `- ` stripped |
| `**Key constraints:**` field present but empty (no bullet lines) | TASKS.md | `key_constraints = []` |
| `**Complexity:**` value not in known set | TASKS.md | Default to `TaskComplexity.UNSET`, log warning |
| Complexity column absent from `## Up next` table | SESSIONSTATE.md | Default all rows to `TaskComplexity.UNSET` |
| `*Last updated:*` in old date-only format `YYYY-MM-DD` | SESSIONSTATE.md | Parse as `datetime` with time `00:00`; rewrite as full datetime on next write |
| Active task block with no hard deps | SESSIONSTATE.md | `hard_deps = []` |
| TASKS-COMPLETED.md does not exist | TASKS-COMPLETED.md | Create with header on first write |

---

## 10. Error Handling

### 10.1 Exit code contract

Every invocation of `tsm` exits with one of these four codes. This contract is enforced in `__main__.py` — command modules raise exceptions; `__main__.py` catches and maps them to codes.

| Code | Meaning | When |
|------|---------|------|
| `0` | Success | Command completed normally (including `--yes` auto-apply, clean vibe-check, clean status print) |
| `1` | Precondition failure | Command precondition not met (no active task, incomplete phase, unknown phase ID, no project root found); also used for user-initiated abort (`n` at confirm prompt) |
| `2` | Parse error | TASKS.md or SESSIONSTATE.md could not be parsed; printed with file path and line number |
| `3` | Write failure | Shadow write or live apply failed; live files guaranteed untouched |

No other exit codes are used. An agent calling `tsm` via subprocess must branch on exit code, not parse stderr.

### 10.2 Startup errors

| Condition | Exit code | Behaviour |
|-----------|-----------|-----------|
| No project root found | 1 | Print §3.2 error message |
| TASKS.md parse failure | 2 | Print error with file path and line number |
| SESSIONSTATE.md parse failure | 2 | Print error with file path and line number |
| TASKS-COMPLETED.md missing | 0 | Create with header, continue |
| `.tsm/` not writable | 3 | Print error with path |

### 10.3 Command precondition failures

All precondition failures print a clear error to stdout, exit with code 1, and leave all files unmodified.

### 10.4 Write failures

If a shadow write or live apply fails:
1. Print error with file path and OS error message
2. Leave live files untouched
3. Print: `Live files were not modified. tsm undo is not needed.`
4. Exit with code 3

---

## 11. Packaging

### 11.1 Project structure

```
tsm/
  __init__.py
  __main__.py              # entry point + load_project() bootstrap
  app.py                   # Textual App class
  models.py                # all dataclasses, enums, and slugify_phase_name()
  project.py               # project discovery, .gitignore enforcement
  shadow.py                # shadow dir, backup, apply, undo, history log
  commands/
    __init__.py
    init_phase.py
    advance.py
    complete_phase.py
    vibe_check.py
    undo.py
    status.py
    help.py                # help command — static strings per command
    new_project.py         # new-project scaffolding command
  parsers/
    __init__.py
    tasks_parser.py        # TASKS.md state machine parser
    session_parser.py      # SESSIONSTATE.md section parser
    completed_parser.py    # TASKS-COMPLETED.md append parser
  writers/
    __init__.py
    tasks_writer.py        # targeted status-line replacement (task + phase level)
    session_writer.py      # full reconstruction renderer
    completed_writer.py    # append writer
  ui/
    __init__.py
    task_tree.py           # left panel (Textual Tree)
    task_detail.py         # right panel
    confirm_overlay.py     # confirm-to-apply modal
    vibe_panel.py          # vibe check results panel
    help_panel.py          # help panel (read-only, replaces right panel)
pyproject.toml
README.md
tests/
  fixtures/
    TASKS.md               # representative fixture — all status/format variants
    TASKS_CLEAN.md         # fixture for vibe-check clean-pass tests
    TASKS_ERRORS.md        # fixture for vibe-check error-detection tests
    SESSIONSTATE.md
    TASKS-COMPLETED.md
  parsers/
    test_tasks_parser.py
    test_session_parser.py
    test_completed_parser.py
  writers/
    test_tasks_writer.py
    test_session_writer.py
  commands/
    test_advance.py
    test_init_phase.py
    test_complete_phase.py
    test_vibe_check.py
    test_help.py
    test_new_project.py
  test_shadow.py
  test_project_discovery.py
```

### 11.2 Dependencies

```toml
[project]
name = "tsm"
requires-python = ">=3.11"
dependencies = [
    "textual>=0.60.0",
]

[project.scripts]
tsm = "tsm.__main__:main"
```

No LLM libraries. No network libraries. No markdown parsing libraries. Standard library only beyond Textual.

### 11.3 Installation

```bash
pip install -e .    # development (recommended)
pip install .       # standard
```

---

## 12. Test Requirements

### 12.1 Build constraint

**Parsers must have passing unit tests before any command logic is built.** Test fixtures must cover all format variants listed in §9.5.

### 12.2 TASKS.md parser tests

| Test ID | Description |
|---------|-------------|
| `test_parse_status_complete` | `✅ Complete` → `TaskStatus.COMPLETE` |
| `test_parse_status_active_bold` | `**Active**` → `TaskStatus.ACTIVE` |
| `test_parse_status_pending` | `Pending` → `TaskStatus.PENDING` |
| `test_parse_status_blocked_lock` | `🔒 Blocked` → `TaskStatus.BLOCKED` |
| `test_parse_status_blocked_cross` | `❌ Blocked` → `TaskStatus.BLOCKED` |
| `test_parse_hard_deps_multiple` | `U-A3, U-A4` → `["U-A3", "U-A4"]` |
| `test_parse_hard_deps_em_dash` | `—` → `[]` |
| `test_parse_hard_deps_none_text` | `None` → `[]` |
| `test_parse_hard_deps_none_dot` | `None.` → `[]` |
| `test_parse_files_backtick_new` | `` `file.ts` (new) `` → `["file.ts"]` |
| `test_parse_files_multiple` | Two comma-separated backtick paths → list of 2 strings |
| `test_parse_files_see_spec` | `See spec §8` → `["See spec §8"]` (stored as-is) |
| `test_parse_files_blank` | Blank `**Files:**` line → `[]` |
| `test_parse_multiline_what` | `**What:**` spanning 3 lines → single joined string |
| `test_parse_multiline_done_when` | `**Done when:**` spanning 2 lines → single joined string |
| `test_parse_phase_structure_table` | Overview table → list of `PhaseOverviewRow` objects |
| `test_parse_multi_phase_file` | File with 3 phases → 3 `Phase` objects, correct task counts |
| `test_parse_raw_block_preserved` | `Task.raw_block` exactly equals original source text |
| `test_task_id_title_extraction` | `### U-A1 · Extract evaluateShowIf` → `id="U-A1"`, `title="Extract evaluateShowIf"` |
| `test_dep_graph_not_parsed_as_task` | `### Dependency graph` block not emitted as a `Task` object |
| `test_dep_graph_raw_preserved` | `Phase.dependency_graph_raw` contains full fenced block verbatim |
| `test_parse_complexity_high` | `**Complexity:** high` → `TaskComplexity.HIGH` |
| `test_parse_complexity_low` | `**Complexity:** low` → `TaskComplexity.LOW` |
| `test_parse_complexity_unset_explicit` | `**Complexity:** unset` → `TaskComplexity.UNSET` |
| `test_parse_complexity_absent` | Task block with no `**Complexity:**` line → `TaskComplexity.UNSET` |
| `test_parse_complexity_unknown_value` | `**Complexity:** extreme` → `TaskComplexity.UNSET` (no exception) |
| `test_parse_key_constraints_present` | `**Key constraints:**` with 2 bullet items → `key_constraints` list of 2 strings |
| `test_parse_key_constraints_absent` | Task block with no `**Key constraints:**` field → `key_constraints = []` |
| `test_parse_key_constraints_empty_field` | `**Key constraints:**` field with no bullet lines → `key_constraints = []` |
| `test_vc11_does_not_fire_for_absent_key_constraints` | Task block missing `**Key constraints:**` → no VC-11 warning |

### 12.3 SESSIONSTATE.md parser tests

| Test ID | Description |
|---------|-------------|
| `test_parse_last_updated` | `2026-04-23T14:32` parsed to `datetime(2026, 4, 23, 14, 32)` |
| `test_parse_last_updated_legacy_date` | `2026-04-23` (date-only) parsed to `datetime(2026, 4, 23, 0, 0)` |
| `test_parse_active_phase` | Phase name and spec file parsed |
| `test_parse_active_task_id` | Task ID extracted from `**U-C2 — ...` |
| `test_parse_active_task_complexity` | `- Complexity: high` in active task block → `TaskComplexity.HIGH` on parsed task |
| `test_parse_up_next_table` | Up next table → list of task stubs |
| `test_parse_up_next_complexity_column` | Complexity column in Up next table parsed correctly |
| `test_parse_up_next_no_complexity_column` | Up next table without Complexity column → all tasks get `UNSET` |
| `test_parse_completed_table` | Completed table → list of task stubs |
| `test_parse_out_of_scope_verbatim` | Out of scope block stored exactly |
| `test_parse_active_task_unset_none` | `[none]` → `active_task = None` |
| `test_parse_active_task_unset_blank` | Empty section → `active_task = None` |

### 12.4 Command tests

| Test ID | Description |
|---------|-------------|
| `test_advance_happy_path` | Active → Completed, Up next[0] → Active, TASKS.md status updated |
| `test_advance_no_active_task` | Aborts cleanly, no files modified |
| `test_advance_dep_not_met` | First up-next task has unmet dep — skipped, active = `[none]`, warning emitted |
| `test_advance_with_commit_message` | Commit message appears in TASKS-COMPLETED.md row |
| `test_advance_last_task_in_phase` | Up next empty after advance; active = `[none]` |
| `test_init_phase_sets_active_task` | First dep-free task becomes active |
| `test_init_phase_no_ready_task` | Active = `[none]`, warning emitted |
| `test_init_phase_unknown_id` | Unknown phase ID → error, no writes |
| `test_complete_phase_all_done` | Phase status updated, SESSIONSTATE rotated to next phase |
| `test_complete_phase_incomplete_tasks` | Aborts with list of incomplete IDs |
| `test_complete_phase_no_next_phase` | Next phase = `[none]`, SESSIONSTATE cleared gracefully |
| `test_vibe_check_clean` | Clean fixtures → 0 errors, 0 warnings |
| `test_vibe_check_vc01_duplicate_id` | Two tasks with same ID → VC-01 error |
| `test_vibe_check_vc02_dangling_dep` | Dep pointing to nonexistent ID → VC-02 error |
| `test_vibe_check_vc03_active_is_complete` | Active task already `complete` in TASKS.md → VC-03 error |
| `test_vibe_check_vc05_unmet_dep_in_up_next` | Up next task with unmet dep → VC-05 warning |
| `test_vibe_check_vc11_missing_field` | Task block missing `**Done when:**` → VC-11 warning |
| `test_vibe_check_vc13_unset_complexity_active` | Active task has `complexity: unset` → VC-13 warning |
| `test_vibe_check_vc13_unset_complexity_up_next` | Up next task has `complexity: unset` → VC-13 warning |
| `test_vibe_check_vc13_suppressed_for_complete` | Completed task with `unset` → no VC-13 warning |
| `test_vibe_check_vc12_datetime_comparison` | `last_updated` 8 days ago → VC-12 warning |
| `test_vibe_check_vc12_same_day_no_warning` | `last_updated` earlier today → no VC-12 warning |

### 12.5 Shadow/backup tests

| Test ID | Description |
|---------|-------------|
| `test_shadow_creates_backup_on_apply` | Apply creates `.bak` file in backup dir |
| `test_shadow_prunes_to_5_backups` | Applying 6 times leaves exactly 5 backups for that file |
| `test_shadow_undo_restores_live_file` | Advance + undo → live file byte-identical to pre-advance state |
| `test_shadow_undo_no_history` | Empty history log → "Nothing to undo" |
| `test_shadow_double_undo` | Two consecutive undos → second returns "Nothing to undo" |
| `test_shadow_gitignore_created` | First run creates `.gitignore` with `.tsm/` entry |
| `test_shadow_gitignore_appended` | Existing `.gitignore` without `.tsm/` → entry appended |
| `test_shadow_gitignore_idempotent` | Existing `.gitignore` already has `.tsm/` → not added again |
| `test_confirm_prompt_yes_flag` | `confirm_prompt(pending_writes, yes=True)` prints summary and returns `True` without reading stdin |
| `test_cli_exit_code_precondition_failure` | `tsm advance` with no active task → exit code 1 |
| `test_cli_exit_code_parse_error` | `tsm status` with malformed TASKS.md → exit code 2 |

### 12.6 Help and new-project tests

| Test ID | Description |
|---------|-------------|
| `test_help_lists_all_commands` | `tsm help` output contains all 8 command names |
| `test_help_specific_command` | `tsm help advance` output contains "Preconditions", "Writes", "Example" sections |
| `test_help_unknown_command` | `tsm help foobar` prints error: "Unknown command: foobar" |
| `test_help_no_project_root_required` | `tsm help` succeeds when run outside any project directory |
| `test_new_project_creates_all_files` | All 5 files created in an empty directory |
| `test_new_project_with_name_flag` | `--name "My Project"` → project name appears in file headers |
| `test_new_project_prompts_for_name` | No `--name` flag → prompts; Enter uses directory name |
| `test_new_project_aborts_if_tasks_exists` | `TASKS.md` already present → error, no files created or modified |
| `test_new_project_aborts_if_sessionstate_exists` | `SESSIONSTATE.md` already present → error, no files created or modified |
| `test_new_project_creates_gitignore_entry` | `.tsm/` added to `.gitignore` after scaffolding |
| `test_new_project_tasks_md_parseable` | Generated `TASKS.md` parses without errors via `tasks_parser` |
| `test_new_project_sessionstate_parseable` | Generated `SESSIONSTATE.md` parses without errors via `session_parser` |

---

## 13. Recommended Build Order

Build in this exact order. Each step must have passing tests before the next begins.

1. **`models.py`** — Dataclasses, enums, and `slugify_phase_name()`. No logic, no I/O, no dependencies.

2. **`project.py`** — Project discovery (walk up from cwd, max 3 levels) and `.gitignore` enforcement. Tests: `test_project_discovery.py`.

3. **`parsers/tasks_parser.py` — core** — TASKS.md state machine (all 7 states) with core field parsing. Tests: `test_parse_status_*`, `test_parse_hard_deps_*`, `test_parse_files_*`, `test_parse_multiline_*`, `test_parse_phase_structure_table`, `test_parse_multi_phase_file`, `test_parse_raw_block_preserved`, `test_task_id_title_extraction`, `test_dep_graph_*` (21 tests) must all pass before step 4.

4. **`parsers/tasks_parser.py` — edge cases** — Add complexity, key_constraints, and subphase tracking. Tests: all `test_parse_complexity_*`, `test_parse_key_constraints_*`, `test_vc11_does_not_fire_for_absent_key_constraints` (9 tests) must all pass before step 5.

5. **`parsers/session_parser.py`** — SESSIONSTATE.md section parser with all §12.3 tests passing before proceeding.

6. **`parsers/completed_parser.py`** — TASKS-COMPLETED.md append parser.

7. **`shadow.py`** — Shadow dir, backup manager, apply, undo, history log. All §12.5 tests passing before proceeding.

8. **`writers/tasks_writer.py`** — Targeted status-line replacement for both task-level and phase-level updates. Tests: write → re-parse → correct status; all other bytes identical. Both `update_task_status` and `update_phase_status` must pass before proceeding.

9. **`writers/session_writer.py`** — Full reconstruction renderer. Test: render → parse → same data model round-trips cleanly.

10. **`writers/completed_writer.py`** — Append writer.

11. **`commands/advance.py`** — Core workflow command. All `test_advance_*` tests passing.

12. **`commands/init_phase.py`** and **`commands/complete_phase.py`** — Remaining workflow commands.

13. **`commands/vibe_check.py`** — All `test_vibe_check_*` tests passing.

14. **`commands/status.py`** and **`commands/undo.py`** — Utility commands.

15. **`commands/help.py`** — Static help strings for all commands. All `test_help_*` tests passing.

16. **`commands/new_project.py`** — Scaffolding command. All `test_new_project_*` tests passing, including round-trip parsability.

17. **`__main__.py`** — CLI entry point and `load_project()` bootstrap. Verify every command works via `tsm <command>` without TUI before proceeding.

18. **`ui/`** — Textual TUI, built last. Sub-order: `task_tree.py` → `task_detail.py` → `confirm_overlay.py` → `vibe_panel.py` → `help_panel.py` → `app.py`.

---

## 14. Known Constraints and Explicit Non-Requirements

- **No telemetry or network calls.** No data leaves the machine under any circumstance.
- **No LLM calls.** All logic is fully deterministic.
- **CLI-first.** Every command must work without the TUI. The TUI is a convenience wrapper.
- **Single-level undo only.** Multi-level undo deferred to v2.
- **Dependency graph is display/preservation only in v1.0.** Vibe check does not validate graph edges against `**Hard deps:**` field values (v2 enhancement).
- **Complexity is informational only.** tsm never acts on it automatically (no routing, no blocking, no model calls). It is surfaced in the TUI, `status` output, and `## Active task` block so you see it at session start.
- **Timestamp format is `YYYY-MM-DDTHH:MM`.** Seconds are omitted. Files written by older versions of tsm using date-only format (`YYYY-MM-DD`) are accepted and silently upgraded on next write.
- **`help` and `new-project` do not require a project root.** All other commands do.
- **Textual version pinning.** Pin `textual>=0.60.0`. Test against the pinned version.
- **Phase ID slugification.** Implemented as `slugify_phase_name()` in `models.py` — see §5.5. The parser calls this function for every phase; do not reimplement the logic inline.
- **TASKS.md write constraint.** tsm only modifies `**Status:**` lines in TASKS.md — at both the task level (via `update_task_status`) and the phase level (via `update_phase_status`). It never rewrites, reformats, or regenerates any other part of the file. The dependency graph ASCII art and all task block content are preserved byte-for-byte. See §9.2 for the dual write-strategy constraint.
- **LoadedProject construction.** Built once in `__main__.py` via `load_project()`. Commands must not re-parse files. See §5.6.
- **`--yes` flag is parsed in `__main__.py` only.** No command module receives or is aware of this flag. `confirm_prompt(pending_writes, yes: bool)` is the single call site. Defaulting `yes=True` anywhere other than an explicit `--yes` CLI argument is a bug.
- **Exit code contract is enforced in `__main__.py` only.** Command modules raise exceptions; `__main__.py` catches and maps to codes 0–3. See §10.1. No `sys.exit()` calls anywhere else in the codebase.
- **`--output json` on read-only commands is deferred to v2.** Do not implement or stub it in v1.0.
