*Last updated: 2026-04-23T00:00*

---

## Active phase
Phase 1 — Foundation — in progress.
Spec: `SPECIFICATION-task-session-manager-v1.3.md`

---

## Completed tasks

| Task | Description | Commit message |
|---|---|---|

---

## Active task

### P1-T01 · Package scaffold and pyproject.toml

**Status:** Pending
**Complexity:** low
**What:** Create the full package directory structure as specified in §11.1: tsm/, tsm/commands/, tsm/parsers/, tsm/writers/, tsm/ui/, tests/, tests/fixtures/, tests/parsers/, tests/writers/, tests/commands/. Create stub __init__.py files in every package directory. Create pyproject.toml with name="tsm", requires-python=">=3.11", dependencies=["textual>=0.60.0"], and entry point tsm = "tsm.__main__:main" per §11.2. Create stub tsm/__main__.py with a main() function that prints "tsm: not yet implemented" and exits. Implements §11.1 and §11.2.
**Prerequisite:** None.
**Hard deps:** None
**Files:** pyproject.toml, tsm/__init__.py, tsm/__main__.py, tsm/app.py, tsm/models.py, tsm/project.py, tsm/shadow.py, tsm/commands/__init__.py, tsm/parsers/__init__.py, tsm/writers/__init__.py, tsm/ui/__init__.py, tests/__init__.py, tests/parsers/__init__.py, tests/writers/__init__.py, tests/commands/__init__.py
**Reviewer:** Skip
**Done when:**
- `pip install -e .` completes without errors
- `python -m tsm` executes and prints output without ImportError
- All package directories exist with __init__.py files
- `tsm` entry point resolves to `tsm.__main__:main`

---

## Up next

| Task | Description | Hard deps | Complexity | Reviewer |
|---|---|---|---|---|
| P1-T02 | models.py — dataclasses, enums, LoadedProject, slugify_phase_name | P1-T01 | medium | Skip |
| P1-T03 | project.py — discovery and .gitignore enforcement | P1-T02 | medium | Skip |
| P1-T04 | Test fixtures | P1-T01 | low | Skip |

---

## Out of scope

- Phase 6 TUI until all CLI commands are verified working end-to-end (§14 CLI-first constraint)
- Network calls, LLM calls, telemetry of any kind (§14)
- General Markdown parser libraries — line iterator state machine only (§9.1)
- Multi-level undo — single-level only in v1.0 (§14)
- Dependency graph edge validation in vibe-check — display/preservation only in v1.0 (§14)
