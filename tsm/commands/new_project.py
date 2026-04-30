# tsm/commands/new_project.py — Scaffold a new project (Phase 4, P4-T07)
#
# Implements §7.9 project scaffolding logic.
#
# Public API:
#   new_project(target_dir: Path, name: str | None = None) -> None
#   HELP_TEXT: str

import sys
from datetime import datetime
from pathlib import Path

HELP_TEXT = """\
tsm new-project — Scaffold blank workflow files in the current directory.

Preconditions:
  - TASKS.md and SESSIONSTATE.md must NOT exist in the target directory.

Writes:
  1. TASKS.md — generated with a single placeholder phase/task
  2. SESSIONSTATE.md — generated with empty active task and [none] state
  3. TASKS-COMPLETED.md — empty log (header only)
  4. AGENTS.md — project-specific agent rules copy
  5. SPECIFICATION.md — project-specific spec copy
  6. .tsm/ directory — shadow/ and backups/ subdirectories
  7. .gitignore — .tsm/ entry appended (idempotent)

Example:
  tsm new-project --name "My App"
"""


def _templates(name: str, now: datetime) -> dict[str, str]:
    """Build template content for all 5 project files.

    Each value is the full file content with ``<Project Name>`` already
    substituted.
    """
    now_str = now.strftime("%Y-%m-%dT%H:%M")
    today = now.strftime("%Y-%m-%d")

    tasks_md = f"""\
# {name} — Phase Task List

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
"""

    sessionstate_md = f"""\
*Last updated: {now_str}*

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
"""

    tasks_completed_md = """\
# Completed Tasks Log

---
"""

    agents_md = """\
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
"""

    specification_md = f"""\
# {name} — Technical Specification

**Version:** 0.1
**Date:** {today}

---

## Overview

[Describe what this project builds]

---

## Architecture

[Describe the technical architecture]

---

## Key decisions

[Record important technical decisions and their rationale]
"""

    return {
        "TASKS.md": tasks_md,
        "SESSIONSTATE.md": sessionstate_md,
        "TASKS-COMPLETED.md": tasks_completed_md,
        "AGENTS.md": agents_md,
        "SPECIFICATION.md": specification_md,
    }


def new_project(target_dir: Path, name: str | None = None) -> None:
    """Scaffold a new tsm project in *target_dir*.

    Args:
        target_dir: Directory to create project files in.
        name: Optional project name.  If None, prompts the user.
    """
    target_dir = target_dir.resolve()

    # ── Abort conditions (§7.9) ───────────────────────────────────────────
    if (target_dir / "TASKS.md").exists():
        print(
            "❌ TASKS.md already exists in this directory.\n"
            "   Use 'tsm status' to check the current project state.\n"
            "   Run 'tsm new-project' only in an empty project directory."
        )
        return

    if (target_dir / "SESSIONSTATE.md").exists():
        print(
            "❌ SESSIONSTATE.md already exists in this directory.\n"
            "   Use 'tsm status' to check the current project state.\n"
            "   Run 'tsm new-project' only in an empty project directory."
        )
        return

    # ── Name resolution (§7.9) ────────────────────────────────────────────
    if name is None:
        raw = input(
            "Project name (used in file headers, press Enter to use directory name):\n> "
        )
        name = raw.strip() or target_dir.name

    now = datetime.now()

    # ── Create 5 workflow files (§7.9) ────────────────────────────────────
    templates = _templates(name, now)
    for filename, content in templates.items():
        (target_dir / filename).write_text(content, encoding="utf-8")

    # ── Create .tsm/ directory (§3.3 first-run behaviour) ─────────────────
    shadow_dir = target_dir / ".tsm" / "shadow"
    backup_dir = target_dir / ".tsm" / "backups"
    shadow_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    # ── Update .gitignore (§3.3, idempotent) ──────────────────────────────
    gitignore_path = target_dir / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(".tsm/\n", encoding="utf-8")
        print(
            "Added .tsm/ to .gitignore — shadow files and backups will not be "
            "committed."
        )
    else:
        lines = gitignore_path.read_text(encoding="utf-8").splitlines()
        if ".tsm/" not in lines:
            content = gitignore_path.read_bytes()
            if content and not content.endswith(b"\n"):
                gitignore_path.write_bytes(content + b"\n.tsm/\n")
            else:
                gitignore_path.write_bytes(content + b".tsm/\n")
            print(
                "Added .tsm/ to .gitignore — shadow files and backups will not be "
                "committed."
            )

    # ── Post-creation output (§7.9) ───────────────────────────────────────
    print(
        f'✅ Created project files for "{name}" in {target_dir}\n'
        f"\n"
        f"  TASKS.md              — master task list (edit this to plan your work)\n"
        f"  SESSIONSTATE.md       — session state (managed by tsm)\n"
        f"  TASKS-COMPLETED.md    — completion log (managed by tsm)\n"
        f"  AGENTS.md             — AI agent rules (edit to add project constraints)\n"
        f"  SPECIFICATION.md      — technical spec (fill in before starting work)\n"
        f"\n"
        f"Next steps:\n"
        f"  1. Fill in SPECIFICATION.md with your project's technical design\n"
        f"  2. Fill in TASKS.md with your phases and atomic tasks\n"
        f"  3. Add project-specific rules to AGENTS.md\n"
        f"  4. Run 'tsm init-phase <phase-id>' to begin your first phase\n"
        f"  5. Run 'tsm vibe-check' to validate your TASKS.md structure"
    )
