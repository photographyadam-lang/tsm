# tsm/ui/help_panel.py — Help right panel (Phase 6, P6-T04)
#
# Implements §8.7 of the specification.
#
# HelpPanel is a Widget that displays the full tsm help output text in
# the right panel slot.  The content is identical to the output of
# help_command() from commands/help.py.  Escape or q dismisses the panel
# and signals the app to restore TaskDetail.
#
# Public API:
#   HelpPanel(help_text: str)  — constructor
#   HelpPanel.Dismissed        — message posted on dismiss
#
# Done-when criteria:
#   1. HelpPanel content is identical to the output of help_command() from
#      commands/help.py
#   2. Escape/q dismisses the panel and restores TaskDetail

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static


# ── HelpPanel widget ──────────────────────────────────────────────────────────


class HelpPanel(Widget):
    """Right-panel widget displaying the full ``tsm help`` output.

    The displayed text is identical to what ``help_command()`` from
    :mod:`tsm.commands.help` prints to stdout.  ``Escape`` or ``q``
    dismisses the panel and posts a :class:`Dismissed` message so the
    app can restore ``TaskDetail`` in the right panel slot.
    """

    # ── Custom message ───────────────────────────────────────────────────────

    class Dismissed(Message):
        """Emitted when the user presses ``Escape`` or ``q``.

        The app should restore ``TaskDetail`` in the right panel slot.
        """

        pass

    # ── Public API ───────────────────────────────────────────────────────────

    def __init__(self, help_text: str, **kwargs) -> None:
        """Initialise the help panel.

        Args:
            help_text: The full help text to display (identical to the
                output of ``help_command()`` from ``commands/help.py``).
        """
        super().__init__(**kwargs)
        self._help_text = help_text

    # ── Compose / mount ──────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Yield a scrollable container holding the rendered content."""
        with VerticalScroll(id="help-scroll"):
            yield Static(id="help-content")

    def on_mount(self) -> None:
        """Render help text on mount."""
        self._update_content()

    # ── Content rendering ────────────────────────────────────────────────────

    def _update_content(self) -> None:
        """Re-render the content :class:`Static` widget."""
        static: Static | None = self.query_one("#help-content", Static)
        if static is not None:
            static.update(self._build_renderable())

    def _build_renderable(self) -> Text:
        """Build a Rich :class:`Text` renderable from the help text.

        Appends a TUI keybindings reference after the CLI help text.
        """
        t = Text(self._help_text, style="bold")
        t.append("\n\n")
        t.append("── TUI keybindings ──────────────────────────────────────\n", style="bold underline")
        t.append("\n")
        bindings = [
            ("a", "Advance active task"),
            ("i", "Initialise phase"),
            ("c", "Complete phase"),
            ("d", "Show dependency tree (press again for blocked view)"),
            ("v", "Run vibe check"),
            ("r", "Repair workflow files"),
            ("u", "Undo last apply"),
            ("s", "Print status (to CLI)"),
            ("p", "Phase CRUD (add / edit / move / remove)"),
            ("t", "Task CRUD (add / edit / move / remove)"),
            ("?", "Show this help panel"),
            ("q", "Quit"),
        ]
        for key, desc in bindings:
            t.append(f"  [{key}] ", style="bold cyan")
            t.append(f"{desc}\n")
        t.append("\n")
        t.append("Press Escape or q to dismiss this panel.\n", style="italic")
        return t

    # ── Key handlers ──────────────────────────────────────────────────────

    def key_escape(self) -> None:
        """``Escape`` key → dismiss panel, restore ``TaskDetail``."""
        self.post_message(self.Dismissed())

    def key_q(self) -> None:
        """``q`` key → dismiss panel, restore ``TaskDetail``."""
        self.post_message(self.Dismissed())
