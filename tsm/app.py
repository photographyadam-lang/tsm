# tsm/app.py — Full TUI wiring (Phase 6, P6-T05 / Phase 7)
#
# Implements §8.1–§8.5 of the specification.
#
# TsmApp is a Textual App with a two-panel layout:
#   - Left panel:  TaskTree (phases & tasks)
#   - Right panel: TaskDetail (default), VibecheckPanel (vibe-check),
#                  HelpPanel (help), or Depspanel (deps)
#   - Bottom bar:  Context-aware command buttons
#
# Keybindings per §8.4:
#   a  advance           — mark active task complete, promote next
#   i  init-phase        — initialise a new phase
#   c  complete-phase    — mark current phase done, rotate
#   v  vibe-check        — run integrity validation
#   u  undo              — revert most recent apply
#   s  status            — print session status to CLI
#   d  deps              — show dependency tree / blocked tasks
#   r  repair            — repair workflow files
#   p  phase             — phase CRUD: add / edit / move / remove
#   t  task              — task CRUD: add / edit / move / remove
#   ?  help              — show help panel
#   q  quit              — exit the TUI
#
# Constraints (§8.4):
#   - All commands must already work via CLI — the TUI wraps the command layer
#   - Context-aware greying is display-only — commands still self-validate
#   - After any write command applies, reload from disk and refresh both panels

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from tsm.models import LoadedProject, Task, TaskStatus


# ── Constants ────────────────────────────────────────────────────────────────

_COMMIT_PROMPT = "Enter commit message (or leave blank): "
_PHASE_ID_PROMPT = "Enter phase ID (e.g. phase-2): "

# CSS for the entire app
_CSS = """
TsmApp {
    background: $surface;
}

#app-layout {
    height: 100%;
}

.left-panel {
    width: 40%;
    height: 100%;
    border-right: solid $primary;
}

.right-panel {
    width: 60%;
    height: 100%;
}

#command-bar {
    height: 1;
    background: $panel;
    color: $text;
    dock: bottom;
    padding: 0 1;
    content-align: left middle;
}

#command-bar > Label {
    margin: 0 1;
}

.command-key {
    color: $accent;
}

.command-disabled {
    color: $text-disabled;
}

#right-panel-container {
    height: 100%;
}

/* InputScreen styling */
#input-dialog {
    width: 60%;
    height: auto;
    margin: 4 8;
    padding: 1 2;
    background: $surface;
    border: thick $primary;
}

#input-dialog > Label {
    margin-bottom: 1;
}

#input-dialog > Input {
    margin-bottom: 1;
}

#input-dialog > Horizontal {
    height: 3;
    align: center middle;
}

#input-dialog > Horizontal > Button {
    margin: 0 1;
}
"""


# ── InputScreen (generic modal prompt) ────────────────────────────────────────


class InputScreen(ModalScreen[str | None]):
    """Modal screen that prompts the user for a single line of text.

    Returns the entered string on confirm, or ``None`` on cancel.
    """

    def __init__(self, prompt: str, default: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._prompt = prompt
        self._default = default

    def compose(self) -> ComposeResult:
        with Vertical(id="input-dialog"):
            yield Label(self._prompt)
            yield Input(value=self._default, id="input-field")
            with Horizontal():
                yield Button("[Y] Confirm", id="btn-confirm", variant="primary")
                yield Button("[N] Cancel", id="btn-cancel", variant="default")

    def on_mount(self) -> None:
        """Focus the input field on mount."""
        input_field = self.query_one("#input-field", Input)
        if input_field is not None:
            input_field.focus()

    def key_escape(self) -> None:
        """Escape → cancel."""
        self.dismiss(None)

    def key_enter(self) -> None:
        """Enter → confirm with current input value."""
        input_field = self.query_one("#input-field", Input)
        self.dismiss(input_field.value if input_field else None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn-confirm":
            input_field = self.query_one("#input-field", Input)
            self.dismiss(input_field.value if input_field else None)
        elif event.button.id == "btn-cancel":
            self.dismiss(None)


# ── TsmApp ───────────────────────────────────────────────────────────────────


class TsmApp(App):
    """Textual TUI application for tsm.

    Composes a two-panel layout with a context-aware command bar.
    """

    CSS = _CSS

    # ── Reactive state ────────────────────────────────────────────────────────
    # Which panel is shown on the right: "detail", "vibe", "help", or "deps"
    right_panel_mode: reactive[str] = reactive("detail")  # type: ignore[assignment]

    BINDINGS = [
        ("a", "advance", "Advance active task"),
        ("i", "init_phase", "Initialise phase"),
        ("c", "complete_phase", "Complete phase"),
        ("v", "vibe_check", "Run vibe check"),
        ("u", "undo", "Undo last apply"),
        ("s", "status", "Print status"),
        ("d", "deps", "Show dependency tree"),
        ("r", "repair", "Repair workflow files"),
        ("p", "phase", "Phase CRUD"),
        ("t", "task", "Task CRUD"),
        ("?", "help", "Show help"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, loaded: LoadedProject, **kwargs) -> None:
        """Initialise the TUI app with a pre-loaded project.

        Args:
            loaded: A fully-populated :class:`LoadedProject` from
                ``load_project()`` in ``__main__.py``.
        """
        super().__init__(**kwargs)
        self._project: LoadedProject = loaded
        self._task_detail_widget = None
        self._vibe_panel_widget = None
        self._help_panel_widget = None
        self._deps_panel_widget = None

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Build the widget tree.

        Layout::

            ┌─────────────────────┬──────────────────────┐
            │                     │                       │
            │    TaskTree         │   TaskDetail /        │
            │    (left panel)     │   VibecheckPanel /    │
            │                     │   HelpPanel /         │
            │                     │   Depspanel           │
            ├─────────────────────┴──────────────────────┤
            │  [a]Advance [i]Init [c]Complete ...        │
            └────────────────────────────────────────────┘
        """
        from tsm.ui.task_detail import TaskDetail
        from tsm.ui.task_tree import TaskTree

        with Horizontal(id="app-layout"):
            # Left panel
            with Vertical(classes="left-panel"):
                yield TaskTree(self._project, id="task-tree")

            # Right panel (container that gets swapped)
            with Vertical(classes="right-panel", id="right-panel-container"):
                # Default: TaskDetail
                active_task = self._project.session.active_task
                detail = TaskDetail(
                    task=active_task,
                    phases=self._project.phases,
                    id="task-detail",
                )
                self._task_detail_widget = detail
                yield detail

        # Command bar at bottom
        yield Static(id="command-bar")

    def on_mount(self) -> None:
        """Render the initial command bar."""
        self._update_command_bar()

    # ── Command bar ───────────────────────────────────────────────────────────

    def _update_command_bar(self) -> None:
        """Re-render the command bar with context-aware greying.

        Greying rules (§8.4):
        - init-phase greyed when active_task is set
        - complete-phase greyed when any tasks in the current phase are
          not complete
        - undo greyed when history log has no undoable entry
        - deps greyed when no phases/tasks exist
        """
        project = self._project
        session = project.session

        # Determine button states
        init_disabled = session.active_task is not None

        # Complete-phase: greyed when any tasks in current phase are not complete
        complete_disabled = False
        if session.active_phase_name:
            current_phase = None
            for phase in project.phases:
                if phase.name == session.active_phase_name:
                    current_phase = phase
                    break
            if current_phase is not None:
                any_incomplete = any(
                    t.status != TaskStatus.COMPLETE for t in current_phase.tasks
                )
                complete_disabled = any_incomplete

        # Undo: greyed when history log has no undoable entry
        undo_disabled = True
        try:
            root = Path(project.project_context.root)
            history_log_path = root / ".tsm" / "history.log"
            if history_log_path.exists():
                content = history_log_path.read_text(encoding="utf-8").strip()
                if content:
                    # Check if any line does NOT contain [undone]
                    for line in content.splitlines():
                        if "[undone]" not in line:
                            undo_disabled = False
                            break
        except Exception:
            undo_disabled = True

        # Deps: greyed when no phases or no tasks
        has_tasks = any(
            len(phase.tasks) > 0 for phase in project.phases
        )
        deps_disabled = not has_tasks

        # Build the command bar label
        parts: list[str] = []

        def _btn(label: str, disabled: bool = False) -> str:
            style = "dim" if disabled else "bold"
            return f"[{style}]{label}[/]"

        parts.append(_btn("[a] Advance"))
        parts.append(_btn("[i] Init", disabled=init_disabled))
        parts.append(_btn("[c] Complete", disabled=complete_disabled))
        parts.append(_btn("[d] Deps", disabled=deps_disabled))
        parts.append(_btn("[v] Vibe"))
        parts.append(_btn("[r] Repair"))
        parts.append(_btn("[u] Undo", disabled=undo_disabled))
        parts.append(_btn("[s] Status"))
        parts.append(_btn("[p] Phase"))
        parts.append(_btn("[t] Task"))
        parts.append(_btn("[?] Help"))
        parts.append(_btn("[q] Quit"))

        bar = self.query_one("#command-bar", Static)
        if bar is not None:
            bar.update("  " + "  ".join(parts))

    # ── Right panel switching ─────────────────────────────────────────────────

    async def watch_right_panel_mode(
        self, old_mode: str, new_mode: str  # noqa: ARG002
    ) -> None:
        """React to ``right_panel_mode`` changes.

        Swaps the content of the right panel container.
        """
        container = self.query_one("#right-panel-container", Vertical)
        if container is None:
            return

        # Remove all children
        await container.remove_children()

        if new_mode == "detail":
            from tsm.ui.task_detail import TaskDetail

            active_task = self._project.session.active_task
            detail = TaskDetail(
                task=active_task,
                phases=self._project.phases,
                id="task-detail",
            )
            self._task_detail_widget = detail
            await container.mount(detail)

        elif new_mode == "vibe":
            from tsm.ui.vibe_panel import VibecheckPanel
            from tsm.commands.vibe_check import run_vibe_check

            errors, warnings, timestamp = run_vibe_check(self._project)
            panel = VibecheckPanel(
                errors=errors,
                warnings=warnings,
                timestamp=timestamp,
                id="vibe-panel",
            )
            self._vibe_panel_widget = panel
            await container.mount(panel)

        elif new_mode == "help":
            from tsm.ui.help_panel import HelpPanel
            from tsm.commands.help import get_help_text

            help_text = get_help_text(None)
            panel = HelpPanel(help_text=help_text, id="help-panel")
            self._help_panel_widget = panel
            await container.mount(panel)

        elif new_mode == "deps":
            from tsm.ui.deps_panel import Depspanel

            panel = Depspanel(
                ctx=self._project,
                mode="tree",
                id="deps-panel",
            )
            self._deps_panel_widget = panel
            await container.mount(panel)

        # Refresh command bar
        self._update_command_bar()

    # ── Task selection handler ────────────────────────────────────────────────

    def on_task_tree_task_selected(
        self, event: "TaskTree.TaskSelected"  # type: ignore[name-defined]
    ) -> None:
        """Handle task selection from the tree."""
        from tsm.ui.task_detail import TaskDetail

        # Only react if we're in detail mode
        if self.right_panel_mode != "detail":
            return

        detail = self.query_one("#task-detail", TaskDetail)
        if detail is not None:
            detail.display_task(event.task, self._project.phases)

    # ── Keybinding actions ────────────────────────────────────────────────────

    async def action_advance(self) -> None:
        """Advance the current active task.

        Flow:
          1. Prompt for commit message via InputScreen
          2. Call ``advance()`` to get pending writes
          3. Show ConfirmOverlay
          4. If confirmed, call ``shadow.apply()``
          5. Reload project from disk and refresh both panels
        """
        # Step 1: prompt for commit message
        commit_msg = await self.push_screen_with_result(
            InputScreen(_COMMIT_PROMPT, default="")
        )
        if commit_msg is None:
            return  # User cancelled

        # Step 2: call advance command
        from tsm.commands.advance import advance
        from tsm.shadow import apply

        try:
            pending_writes = advance(self._project, commit_message=commit_msg)
        except ValueError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        # Step 3: show confirm overlay
        from tsm.ui.confirm_overlay import ConfirmOverlay

        confirmed = await self.push_screen_with_result(
            ConfirmOverlay(pending_writes)
        )
        if not confirmed:
            return

        # Step 4: apply
        try:
            apply(pending_writes)
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error", timeout=5)
            return

        # Step 5: reload and refresh
        self._reload_and_refresh()

    async def action_init_phase(self) -> None:
        """Initialise a phase.

        Flow:
          1. Prompt for phase ID via InputScreen
          2. Call ``init_phase()`` to get pending writes
          3. Show ConfirmOverlay
          4. If confirmed, call ``shadow.apply()``
          5. Reload project from disk and refresh both panels
        """
        # Step 1: prompt for phase ID
        phase_id = await self.push_screen_with_result(
            InputScreen(_PHASE_ID_PROMPT, default="")
        )
        if phase_id is None or not phase_id.strip():
            return  # User cancelled or empty

        # Step 2: call init_phase command
        from tsm.commands.init_phase import init_phase
        from tsm.shadow import apply

        try:
            pending_writes = init_phase(self._project, phase_id=phase_id.strip())
        except ValueError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        # Step 3: show confirm overlay
        from tsm.ui.confirm_overlay import ConfirmOverlay

        confirmed = await self.push_screen_with_result(
            ConfirmOverlay(pending_writes)
        )
        if not confirmed:
            return

        # Step 4: apply
        try:
            apply(pending_writes)
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error", timeout=5)
            return

        # Step 5: reload and refresh
        self._reload_and_refresh()

    async def action_complete_phase(self) -> None:
        """Complete the current phase.

        Flow:
          1. Call ``complete_phase()`` to get pending writes
          2. Show ConfirmOverlay
          3. If confirmed, call ``shadow.apply()``
          4. Reload project from disk and refresh both panels
        """
        from tsm.commands.complete_phase import complete_phase
        from tsm.shadow import apply

        # Step 1: call complete_phase command
        try:
            pending_writes = complete_phase(self._project)
        except ValueError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        # Step 2: show confirm overlay
        from tsm.ui.confirm_overlay import ConfirmOverlay

        confirmed = await self.push_screen_with_result(
            ConfirmOverlay(pending_writes)
        )
        if not confirmed:
            return

        # Step 3: apply
        try:
            apply(pending_writes)
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error", timeout=5)
            return

        # Step 4: reload and refresh
        self._reload_and_refresh()

    def action_vibe_check(self) -> None:
        """Run vibe check — swap right panel to VibecheckPanel."""
        self.right_panel_mode = "vibe"

    def action_undo(self) -> None:
        """Undo the most recent apply operation.

        Calls ``shadow.undo()`` directly (same as CLI ``tsm undo``),
        then reloads the project from disk.
        """
        from tsm.shadow import undo as shadow_undo

        try:
            root = Path(self._project.project_context.root)
            shadow_undo(root)
        except Exception as exc:
            self.notify(f"Undo failed: {exc}", severity="error", timeout=5)
            return

        # Reload and refresh
        self._reload_and_refresh()

    def action_status(self) -> None:
        """Print session status to the CLI terminal.

        Calls ``status()`` from the command layer, which prints to stdout.
        """
        from tsm.commands.status import status

        status(self._project)

    # ── New commands: deps, repair, phase, task ───────────────────────────────

    def action_deps(self) -> None:
        """Show dependency tree — swap right panel to Depspanel.

        Re-presses ``d`` while the Depspanel is visible to toggle between
        the tree view and the blocked-tasks view.
        """
        if self.right_panel_mode == "deps":
            # Already showing deps — toggle between tree and blocked
            from tsm.ui.deps_panel import Depspanel

            container = self.query_one("#right-panel-container", Vertical)
            if container is not None and self._deps_panel_widget is not None:
                panel = self._deps_panel_widget
                # Cycle: tree → blocked → tree
                new_mode = "blocked" if panel._mode == "tree" else "tree"
                new_panel = Depspanel(
                    ctx=self._project,
                    mode=new_mode,
                    id="deps-panel",
                )
                self._deps_panel_widget = new_panel
                container.remove_children()
                container.mount(new_panel)
                new_panel._update_content()
            return

        self.right_panel_mode = "deps"

    async def action_repair(self) -> None:
        """Repair workflow files.

        Flow:
          1. Ask which files to repair (all / tasks / session / completed)
          2. Call ``repair()`` to get pending writes
          3. Show ConfirmOverlay
          4. If confirmed, call ``shadow.apply()``
          5. Reload project from disk and refresh both panels
        """
        from tsm.commands.repair import repair
        from tsm.shadow import apply

        # Step 1: ask user which files to repair
        choice = await self.push_screen_with_result(
            InputScreen(
                "Repair: [all] / [tasks] / [session] / [completed]: ",
                default="all",
            )
        )
        if choice is None:
            return  # User cancelled

        choice = choice.strip().lower()

        # Map user input to flags
        repair_tasks = choice in ("all", "tasks")
        repair_session = choice in ("all", "session")
        repair_completed = choice in ("all", "completed")

        if not repair_tasks and not repair_session and not repair_completed:
            self.notify(
                "Invalid choice. Use: all, tasks, session, or completed.",
                severity="error",
                timeout=5,
            )
            return

        # Step 2: call repair command
        try:
            pending_writes = repair(
                self._project,
                tasks=repair_tasks,
                session=repair_session,
                completed=repair_completed,
            )
        except ValueError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        if not pending_writes:
            self.notify("No repairs needed.", severity="information", timeout=3)
            return

        # Step 3: show confirm overlay
        from tsm.ui.confirm_overlay import ConfirmOverlay

        confirmed = await self.push_screen_with_result(
            ConfirmOverlay(pending_writes)
        )
        if not confirmed:
            return

        # Step 4: apply
        try:
            apply(pending_writes)
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error", timeout=5)
            return

        # Step 5: reload and refresh
        self._reload_and_refresh()

    async def action_phase(self) -> None:
        """Phase CRUD: add / edit / move / remove.

        Prompts for a sub-action, then gathers the required parameters
        via InputScreen prompts, calls the appropriate command function,
        and shows ConfirmOverlay before applying.
        """
        from tsm.shadow import apply

        # Step 1: ask which sub-action
        sub = await self.push_screen_with_result(
            InputScreen(
                "Phase action: [add] / [edit] / [move] / [remove]: ",
                default="add",
            )
        )
        if sub is None:
            return
        sub = sub.strip().lower()

        if sub == "add":
            await self._phase_add()
        elif sub == "edit":
            await self._phase_edit()
        elif sub == "move":
            await self._phase_move()
        elif sub == "remove":
            await self._phase_remove()
        else:
            self.notify(
                "Invalid phase action. Use: add, edit, move, or remove.",
                severity="error",
                timeout=5,
            )

    async def _phase_add(self) -> None:
        """Add a new phase."""
        from tsm.commands.phase import phase_add
        from tsm.shadow import apply

        # Prompt for phase name
        name = await self.push_screen_with_result(
            InputScreen("Phase name (e.g. 'Phase 8 — Foo'): ")
        )
        if name is None or not name.strip():
            return
        name = name.strip()

        # Prompt for optional after_phase_id
        after = await self.push_screen_with_result(
            InputScreen("Insert after phase ID (or blank for end): ")
        )
        after_phase_id = after.strip() if after and after.strip() else None

        try:
            pending_writes = phase_add(self._project, name=name, after_phase_id=after_phase_id)
        except ValueError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        # Show confirm overlay
        from tsm.ui.confirm_overlay import ConfirmOverlay

        confirmed = await self.push_screen_with_result(
            ConfirmOverlay(pending_writes)
        )
        if not confirmed:
            return

        try:
            apply(pending_writes)
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error", timeout=5)
            return

        self._reload_and_refresh()

    async def _phase_edit(self) -> None:
        """Edit a phase name and/or status."""
        from tsm.commands.phase import phase_edit
        from tsm.shadow import apply

        # Prompt for phase ID
        phase_id = await self.push_screen_with_result(
            InputScreen("Phase ID to edit: ")
        )
        if phase_id is None or not phase_id.strip():
            return
        phase_id = phase_id.strip()

        # Prompt for new name (optional)
        name = await self.push_screen_with_result(
            InputScreen("New name (or blank to skip): ")
        )
        name = name.strip() if name else None

        # Prompt for new status (optional)
        status = await self.push_screen_with_result(
            InputScreen("New status (or blank to skip): ")
        )
        status = status.strip() if status else None

        if name is None and status is None:
            self.notify("No changes provided.", severity="warning", timeout=3)
            return

        try:
            pending_writes = phase_edit(self._project, phase_id=phase_id, name=name, status=status)
        except ValueError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        from tsm.ui.confirm_overlay import ConfirmOverlay

        confirmed = await self.push_screen_with_result(
            ConfirmOverlay(pending_writes)
        )
        if not confirmed:
            return

        try:
            apply(pending_writes)
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error", timeout=5)
            return

        self._reload_and_refresh()

    async def _phase_move(self) -> None:
        """Move a phase to a new position."""
        from tsm.commands.phase import phase_move
        from tsm.shadow import apply

        phase_id = await self.push_screen_with_result(
            InputScreen("Phase ID to move: ")
        )
        if phase_id is None or not phase_id.strip():
            return
        phase_id = phase_id.strip()

        after = await self.push_screen_with_result(
            InputScreen("Move after phase ID: ")
        )
        if after is None or not after.strip():
            return
        after_phase_id = after.strip()

        try:
            pending_writes = phase_move(self._project, phase_id=phase_id, after_phase_id=after_phase_id)
        except ValueError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        from tsm.ui.confirm_overlay import ConfirmOverlay

        confirmed = await self.push_screen_with_result(
            ConfirmOverlay(pending_writes)
        )
        if not confirmed:
            return

        try:
            apply(pending_writes)
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error", timeout=5)
            return

        self._reload_and_refresh()

    async def _phase_remove(self) -> None:
        """Remove a phase and all its tasks."""
        from tsm.commands.phase import phase_remove
        from tsm.shadow import apply

        phase_id = await self.push_screen_with_result(
            InputScreen("Phase ID to remove: ")
        )
        if phase_id is None or not phase_id.strip():
            return
        phase_id = phase_id.strip()

        # Ask about force flag
        force_choice = await self.push_screen_with_result(
            InputScreen("Force removal? [yes] / [no]: ", default="no")
        )
        if force_choice is None:
            return
        force = force_choice.strip().lower() in ("yes", "y")

        try:
            pending_writes = phase_remove(self._project, phase_id=phase_id, force=force)
        except ValueError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        from tsm.ui.confirm_overlay import ConfirmOverlay

        confirmed = await self.push_screen_with_result(
            ConfirmOverlay(pending_writes)
        )
        if not confirmed:
            return

        try:
            apply(pending_writes)
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error", timeout=5)
            return

        self._reload_and_refresh()

    async def action_task(self) -> None:
        """Task CRUD: add / edit / move / remove.

        Prompts for a sub-action, then gathers the required parameters
        (using TaskFormOverlay for add and edit), calls the appropriate
        command function, and shows ConfirmOverlay before applying.
        """
        sub = await self.push_screen_with_result(
            InputScreen(
                "Task action: [add] / [edit] / [move] / [remove]: ",
                default="add",
            )
        )
        if sub is None:
            return
        sub = sub.strip().lower()

        if sub == "add":
            await self._task_add()
        elif sub == "edit":
            await self._task_edit()
        elif sub == "move":
            await self._task_move()
        elif sub == "remove":
            await self._task_remove()
        else:
            self.notify(
                "Invalid task action. Use: add, edit, move, or remove.",
                severity="error",
                timeout=5,
            )

    async def _task_add(self) -> None:
        """Add a new task using the interactive TaskFormOverlay."""
        from tsm.commands.task import task_add
        from tsm.shadow import apply

        # Step 1: ask which phase
        phase_id = await self.push_screen_with_result(
            InputScreen("Add to phase ID: ")
        )
        if phase_id is None or not phase_id.strip():
            return
        phase_id = phase_id.strip()

        # Step 2: launch TaskFormOverlay for add mode
        from tsm.ui.task_form import TaskFormOverlay

        form_result: dict | None = await self.push_screen_with_result(
            TaskFormOverlay(task=None)
        )
        if form_result is None:
            return  # User cancelled

        # Extract title — required
        title = str(form_result.get("title", "")).strip()
        if not title:
            self.notify("Title is required.", severity="error", timeout=5)
            return

        # Step 3: call task_add with the form data
        try:
            pending_writes = task_add(
                self._project,
                phase_id=phase_id,
                title=title,
            )
        except ValueError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        # Step 4: show confirm overlay
        from tsm.ui.confirm_overlay import ConfirmOverlay

        confirmed = await self.push_screen_with_result(
            ConfirmOverlay(pending_writes)
        )
        if not confirmed:
            return

        # Step 5: apply
        try:
            apply(pending_writes)
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error", timeout=5)
            return

        # Step 6: reload and refresh
        self._reload_and_refresh()

    async def _task_edit(self) -> None:
        """Edit a task using the interactive TaskFormOverlay."""
        from tsm.commands.task import task_edit
        from tsm.shadow import apply

        # Step 1: ask which task
        task_id = await self.push_screen_with_result(
            InputScreen("Task ID to edit: ")
        )
        if task_id is None or not task_id.strip():
            return
        task_id = task_id.strip()

        # Step 2: find the existing task to pre-populate the form
        from tsm.commands.task import _find_task_by_id

        existing_task = _find_task_by_id(self._project.phases, task_id)
        if existing_task is None:
            self.notify(f"Task '{task_id}' not found.", severity="error", timeout=5)
            return

        # Step 3: launch TaskFormOverlay in edit mode
        from tsm.ui.task_form import TaskFormOverlay

        form_result: dict | None = await self.push_screen_with_result(
            TaskFormOverlay(task=existing_task)
        )
        if form_result is None:
            return  # User cancelled

        # Step 4: apply each changed field
        combined_pending = []
        for field, value in form_result.items():
            try:
                pw = task_edit(
                    self._project,
                    task_id=task_id,
                    field=field,
                    value=value,
                )
                combined_pending.extend(pw)
            except ValueError as exc:
                self.notify(f"Edit failed for {field}: {exc}", severity="error", timeout=5)
                return

        if not combined_pending:
            self.notify("No changes made.", severity="information", timeout=3)
            return

        # Step 5: show confirm overlay
        from tsm.ui.confirm_overlay import ConfirmOverlay

        confirmed = await self.push_screen_with_result(
            ConfirmOverlay(combined_pending)
        )
        if not confirmed:
            return

        # Step 6: apply
        try:
            apply(combined_pending)
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error", timeout=5)
            return

        # Step 7: reload and refresh
        self._reload_and_refresh()

    async def _task_move(self) -> None:
        """Move a task to a different phase or reorder."""
        from tsm.commands.task import task_move
        from tsm.shadow import apply

        task_id = await self.push_screen_with_result(
            InputScreen("Task ID to move: ")
        )
        if task_id is None or not task_id.strip():
            return
        task_id = task_id.strip()

        target = await self.push_screen_with_result(
            InputScreen("Target phase ID: ")
        )
        if target is None or not target.strip():
            return
        target_phase_id = target.strip()

        after = await self.push_screen_with_result(
            InputScreen("After task ID (or blank for start): ")
        )
        after_task_id = after.strip() if after and after.strip() else None

        try:
            pending_writes = task_move(
                self._project,
                task_id=task_id,
                target_phase_id=target_phase_id,
                after_task_id=after_task_id,
            )
        except ValueError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        from tsm.ui.confirm_overlay import ConfirmOverlay

        confirmed = await self.push_screen_with_result(
            ConfirmOverlay(pending_writes)
        )
        if not confirmed:
            return

        try:
            apply(pending_writes)
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error", timeout=5)
            return

        self._reload_and_refresh()

    async def _task_remove(self) -> None:
        """Remove a task."""
        from tsm.commands.task import task_remove
        from tsm.shadow import apply

        task_id = await self.push_screen_with_result(
            InputScreen("Task ID to remove: ")
        )
        if task_id is None or not task_id.strip():
            return
        task_id = task_id.strip()

        force_choice = await self.push_screen_with_result(
            InputScreen("Force removal? [yes] / [no]: ", default="no")
        )
        if force_choice is None:
            return
        force = force_choice.strip().lower() in ("yes", "y")

        try:
            pending_writes = task_remove(self._project, task_id=task_id, force=force)
        except ValueError as exc:
            self.notify(str(exc), severity="error", timeout=5)
            return

        from tsm.ui.confirm_overlay import ConfirmOverlay

        confirmed = await self.push_screen_with_result(
            ConfirmOverlay(pending_writes)
        )
        if not confirmed:
            return

        try:
            apply(pending_writes)
        except Exception as exc:
            self.notify(f"Apply failed: {exc}", severity="error", timeout=5)
            return

        self._reload_and_refresh()

    # ── Help and quit ─────────────────────────────────────────────────────────

    def action_help(self) -> None:
        """Show help panel — swap right panel to HelpPanel."""
        self.right_panel_mode = "help"

    def action_quit(self) -> None:
        """Exit the TUI application."""
        self.exit()

    # ── Reload and refresh ────────────────────────────────────────────────────

    def _reload_and_refresh(self) -> None:
        """Reload the project from disk and refresh both panels.

        After any write command applies, ``load_project()`` is called again
        and both panels are refreshed from the new :class:`LoadedProject`.
        """
        from tsm.__main__ import load_project

        root = Path(self._project.project_context.root)
        try:
            self._project = load_project(root)
        except Exception as exc:
            self.notify(f"Reload failed: {exc}", severity="error", timeout=5)
            return

        # Refresh the TaskTree in the left panel
        from tsm.ui.task_tree import TaskTree

        tree = self.query_one("#task-tree", TaskTree)
        if tree is not None:
            tree._project = self._project
            tree._active_task_id = (
                self._project.session.active_task.id
                if self._project.session.active_task is not None
                else None
            )
            tree._build_tree()

        # Refresh the right panel if in detail mode
        if self.right_panel_mode == "detail":
            from tsm.ui.task_detail import TaskDetail

            detail = self.query_one("#task-detail", TaskDetail)
            if detail is not None:
                active_task = self._project.session.active_task
                if active_task is not None:
                    detail.display_task(active_task, self._project.phases)
                else:
                    # No active task — show a placeholder
                    detail.display_task(
                        Task(
                            id="[none]",
                            title="No active task",
                            status=TaskStatus.PENDING,
                            complexity=None,  # type: ignore[arg-type]
                            what="",
                            prerequisite="",
                            hard_deps=[],
                            files=[],
                            reviewer="",
                            key_constraints=[],
                            done_when="",
                            phase_id="",
                            subphase=None,
                            raw_block="[none]",
                        ),
                        self._project.phases,
                    )

        # If in deps mode, refresh the deps panel content
        if self.right_panel_mode == "deps" and self._deps_panel_widget is not None:
            self._deps_panel_widget._ctx = self._project
            self._deps_panel_widget._update_content()

        # Update command bar
        self._update_command_bar()

    # ── Dismissal handlers ────────────────────────────────────────────────────

    def on_vibecheck_panel_dismissed(self, event: Message) -> None:
        """Handle VibecheckPanel dismissal — restore TaskDetail."""
        event.stop()
        self.right_panel_mode = "detail"

    def on_help_panel_dismissed(self, event: Message) -> None:
        """Handle HelpPanel dismissal — restore TaskDetail."""
        event.stop()
        self.right_panel_mode = "detail"

    def on_depspanel_dismissed(self, event: Message) -> None:
        """Handle Depspanel dismissal — restore TaskDetail."""
        event.stop()
        self.right_panel_mode = "detail"
