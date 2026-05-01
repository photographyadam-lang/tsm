# TodoFlow — Technical Specification

**Version:** 0.1
**Date:** 2026-05-01

---

## Overview

TodoFlow is a feature-rich to-do list application that runs in the terminal. Users can create, organise, prioritise, and track tasks through an interactive CLI/TUI. The app persists data to a local JSON file and supports categories, due dates, recurring tasks, and productivity reporting.

---

## Architecture

```
┌─────────────────────────────────────────┐
│           CLI / TUI Layer               │
│  (argparse commands + Rich TUI menus)   │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│           Service Layer                 │
│  (TaskManager, Scheduler, Reporter)     │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│           Persistence Layer             │
│  (JSON file I/O + in-memory cache)      │
└─────────────────────────────────────────┘
```

**Key components:**
- **CLI Layer** — `argparse`-based command dispatch (`add`, `list`, `done`, `delete`, etc.)
- **TUI Layer** — `rich`/`textual` interactive menu for browsing and managing tasks
- **Service Layer** — Business logic: task CRUD, recurring-task engine, stats aggregation
- **Persistence Layer** — JSON file store with atomic writes and an in-memory cache for fast reads

---

## Key decisions

1. **JSON over SQLite** — For a terminal-based app, a single JSON file keeps setup trivial (no schema migrations, no dependencies) and is human-editable.
2. **Recurring tasks via cron-like expressions** — A lightweight parser maps expressions like `daily`, `weekly mon` to next-due computations rather than requiring an external scheduler.
3. **Rich for TUI** — The `rich` library gives us colourised tables, progress bars, and panels without the complexity of a full GUI framework.
