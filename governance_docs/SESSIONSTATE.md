*Last updated: 2026-04-30T00:00*

---

## Active phase

Phase 6 — TUI — in progress.
Spec: `SPECIFICATION-task-session-manager-v1.4.md`

---

## Completed tasks

| Task | Description | Commit message |
| ---- | ----------- | -------------- |
| P6-T01 |
| P6-T02 | ui/task_detail.py — right panel 
| P6-T03 | ui/confirm_overlay.py — confirm-to-apply modal
| P6-T04 | ui/vibe_panel.py and ui/help_panel.py    

---

## Active task

### P6-T05 · app.py — full TUI wiring

**Status:** Ready
**Complexity:** high
**What:** Implement tsm/app.py with TsmApp(App). Compose two-panel layout: left panel hosts TaskTree, right panel hosts TaskDetail (default), VibecheckPanel (when vibe-check active), or HelpPanel (when help active). Fixed command bar footer per §8.1. Keybindings per §8.4: a → advance (prompt for commit message inline or via Input widget, then show ConfirmOverlay), i → init-phase (prompt for phase ID, then show ConfirmOverlay), c → complete-phase (show ConfirmOverlay), v → vibe-check (swap right panel to VibecheckPanel), u → undo (call shadow.undo directly, refresh), s → status (print to CLI or show in a read-only panel), ? → swap right panel to HelpPanel, q → quit. Context-aware command bar greying (§8.4): init-phase button greyed when active_task is set; complete-phase button greyed when any phase tasks are not complete; undo button greyed when history log has no undoable entry. After any write command applies, reload LoadedProject from disk and refresh both panels. Implements §8.1–§8.5.
**Prerequisite:** All P6-T01 through P6-T04 complete.
**Hard deps:** P6-T04
**Files:** tsm/app.py
**Reviewer:** Skip
**Key constraints:**
- All commands must already work via CLI before being wired into the TUI — do not add TUI-only code paths or bypass the command layer
- Context-aware greying is display-only — command functions still perform their own precondition checks; a greyed button that is somehow triggered must still abort cleanly
- After any write command applies, call load_project() again and refresh both panels from the new LoadedProject — do not mutate in-place
**Done when:**
- TUI launches without error against a valid project directory (tsm with no subcommand)
- All 8 keybindings (a, i, c, v, u, s, ?, q) dispatch to the correct handler
- ConfirmOverlay appears for advance, init-phase, and complete-phase; applying updates both panels
- Command bar greys out init-phase when active task is set
- Command bar greys out complete-phase when any tasks in the current phase are not complete
- Command bar greys out undo when history log is empty or all entries are [undone]

---

## Up next

| Task   | Description                                    | Hard deps | Complexity | Reviewer |
| ------ | ---------------------------------------------- | --------- | ---------- | -------- |
| P6-T05 | app.py — full TUI wiring                       | P6-T04    | high       | Skip     |

---

## Out of scope

- Network calls, LLM calls, telemetry of any kind (§14)
- General Markdown parser libraries — line iterator state machine only (§9.1)
- Multi-level undo — single-level only in v1.0 (§14)
- Dependency graph edge validation in vibe-check — display/preservation only in v1.0 (§14)
- --output json on read-only commands — deferred to v2 (§2.2)
- TUI-only code paths — all business logic stays in the command layer (§14)