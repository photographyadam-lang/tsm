# tsm/app.py — Full TUI wiring (Phase 6, P6-T05)
#
# Implements §8.1–§8.5 of the specification.
#
# TsmApp is a Textual App with a two-panel layout:
#   - Left panel:  TaskTree (phases & tasks)
#   - Right panel: TaskDetail (default), VibecheckPanel (vibe-check),
#                  or HelpPanel (help)
#   - Bottom bar:  Context-aware command buttons
#
# Keybindings per §8.4:
#   a  advance           — mark active task complete, promote next
#   i  init-phase        — initialise a new phase
#   c  complete-phase    — mark current phase done, rotate
#   v  vibe-check        — run integrity validation
#   u  undo              — revert most recent apply
#   s  status            — print session status to CLI
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
    # Which panel is shown on the right: "detail", "vibe", or "help"
    right_panel_mode: reactive[str] = reactive("detail")  # type: ignore[assignment]

    BINDINGS = [
        ("a", "advance", "Advance active task"),
        ("i", "init_phase", "Initialise phase"),
        ("c", "complete_phase", "Complete phase"),
        ("v", "vibe_check", "Run vibe check"),
        ("u", "undo", "Undo last apply"),
        ("s", "status", "Print status"),
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

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Build the widget tree.

        Layout:

        .. code-block::

            ┌─────────────────────┬──────────────────────┐
            │                     │                       │
            │    TaskTree         │   TaskDetail /        │
            │    (left panel)     │   VibecheckPanel /    │
            │                     │   HelpPanel           │
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

        # Build the command bar label
        parts: list[str] = []

        def _btn(label: str, disabled: bool = False) -> str:
            style = "dim" if disabled else "bold"
            return f"[{style}]{label}[/]"

        parts.append(_btn("[a] Advance"))
        parts.append(_btn("[i] Init", disabled=init_disabled))
        parts.append(_btn("[c] Complete", disabled=complete_disabled))
        parts.append(_btn("[v] Vibe"))
        parts.append(_btn("[u] Undo", disabled=undo_disabled))
        parts.append(_btn("[s] Status"))
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

        # Update command bar
        self._update_command_bar()

    # ── Dismissal handlers from VibecheckPanel / HelpPanel ────────────────────

    def on_vibecheck_panel_dismissed(self, event: Message) -> None:
        """Handle VibecheckPanel dismissal — restore TaskDetail."""
        event.stop()
        self.right_panel_mode = "detail"

    def on_help_panel_dismissed(self, event: Message) -> None:
        """Handle HelpPanel dismissal — restore TaskDetail."""
        event.stop()
        self.right_panel_mode = "detail"
