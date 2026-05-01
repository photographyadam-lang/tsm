# tsm/ui/vibe_panel.py — Vibe-check right panel (Phase 6, P6-T04)
#
# Implements §8.6 of the specification.
#
# VibecheckPanel is a Widget that displays the results of a vibe check
# in the right panel slot.  It receives structured error/warning lists
# and renders them with colour coding: errors in red, warnings in yellow,
# in the §7.5 output format.  Escape or q dismisses the panel and signals
# the app to restore TaskDetail.
#
# Public API:
#   VibecheckPanel(errors, warnings, timestamp)  — constructor
#   VibecheckPanel.Dismissed                     — message posted on dismiss
#
# Done-when criteria:
#   1. VibecheckPanel renders errors before warnings
#   2. Error rows are visually distinct (red) from warning rows (yellow)
#   3. Escape/q dismisses the panel and restores TaskDetail

from __future__ import annotations

from datetime import datetime

from rich.console import Group, RenderableType
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static


# ── Constants ────────────────────────────────────────────────────────────────

_SEPARATOR = "\u2500" * 29  # ─────────────────────────────


# ── Helpers ──────────────────────────────────────────────────────────────────


def _render_vc_block(
    items: list[str], style: str, label_style: str
) -> list[RenderableType]:
    """Render a list of VC items as a coloured block.

    Each *item* is a multi-line string in the format::

        VC-XX  <source>
               <detail line 1>
               <detail line 2>  ...

    The first line (``VC-XX  <source>``) is rendered in *label_style*,
    and continuation lines are rendered in *style*.

    Args:
        items: List of VC message strings.
        style: Rich style for the detail/continuation lines (e.g. ``"red"``).
        label_style: Rich style for the ``VC-XX  <source>`` line
            (e.g. ``"bold red"``).

    Returns:
        A list of :class:`Text` renderables, with empty-line separators
        inserted between items.
    """
    result: list[RenderableType] = []
    for idx, item in enumerate(items):
        if idx > 0:
            result.append(Text(""))  # blank-line separator between items

        lines = item.split("\n")
        for i, line in enumerate(lines):
            stripped = line.rstrip("\n")
            if not stripped:
                continue
            if i == 0:
                # First line: VC-XX  <source> — bold label style
                result.append(Text(f"  {stripped}", style=label_style))
            else:
                # Continuation lines — content style (red/yellow)
                result.append(Text(f"  {stripped}", style=style))

    return result


# ── VibecheckPanel widget ────────────────────────────────────────────────────


class VibecheckPanel(Widget):
    """Right-panel widget displaying vibe-check results.

    Renders errors before warnings, with errors in red and warnings in
    yellow, matching the §7.5 CLI output format.  ``Escape`` or ``q``
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

    def __init__(
        self,
        errors: list[str],
        warnings: list[str],
        timestamp: str | None = None,
        **kwargs,
    ) -> None:
        """Initialise the vibe-check panel.

        Args:
            errors: List of error message strings in the §7.5 format.
            warnings: List of warning message strings in the §7.5 format.
            timestamp: Optional ISO-8601-like timestamp string (e.g.
                ``"2026-04-30T14:30"``).  If ``None``, the current time
                is used.
        """
        super().__init__(**kwargs)
        self._errors = errors
        self._warnings = warnings
        self._timestamp = timestamp or datetime.now().strftime("%Y-%m-%dT%H:%M")

    # ── Compose / mount ──────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Yield a scrollable container holding the rendered content."""
        with VerticalScroll(id="vibe-scroll"):
            yield Static(id="vibe-content")

    def on_mount(self) -> None:
        """Render initial content on mount."""
        self._update_content()

    # ── Content rendering ────────────────────────────────────────────────────

    def _update_content(self) -> None:
        """Re-render the content :class:`Static` widget."""
        static: Static | None = self.query_one("#vibe-content", Static)
        if static is not None:
            static.update(self._build_renderable())

    def _build_renderable(self) -> RenderableType:
        """Build a Rich renderable from the error and warning data.

        The layout follows the §7.5 format:

        .. code-block:: text

            ─────────────────────────────────
              Vibe Check — 2026-04-30T14:30
            ─────────────────────────────────

              ❌ 2 errors   ⚠️  1 warning

              ERRORS
              ───────
              VC-01  TASKS.md
                     Duplicate task ID: ...

              WARNINGS
              ─────────
              VC-11  TASKS.md · task-id
                     Missing required field(s): ...
        """
        lines: list[RenderableType] = []

        # ── Header ───────────────────────────────────────────────────────
        lines.append(Text(_SEPARATOR))
        lines.append(
            Text(f"  Vibe Check \u2014 {self._timestamp}", style="bold")
        )
        lines.append(Text(_SEPARATOR))
        lines.append(Text(""))

        # ── Count line ───────────────────────────────────────────────────
        err_count = len(self._errors)
        warn_count = len(self._warnings)

        count_parts: list[RenderableType] = []

        if err_count > 0:
            err_label = f"  \u274c {err_count} error"
            err_label += "s" if err_count > 1 else ""
            count_parts.append(Text(err_label, style="bold red"))

        if err_count > 0 and warn_count > 0:
            count_parts.append(Text("   "))

        if warn_count > 0:
            warn_label = f"\u26a0\ufe0f  {warn_count} warning"
            warn_label += "s" if warn_count > 1 else ""
            count_parts.append(Text(warn_label, style="bold yellow"))
        elif err_count == 0:
            count_parts.append(Text("  \u2705 No errors found."))

        if err_count > 0 or warn_count > 0:
            lines.append(Group(*count_parts))
        elif err_count == 0 and warn_count == 0:
            lines.append(
                Text(
                    "  \u2705 No errors found.  \u2705 No warnings.",
                    style="green",
                )
            )
        else:
            lines.append(Text("  \u2705 No errors found."))

        lines.append(Text(""))

        # ── ERRORS section ───────────────────────────────────────────────
        if self._errors:
            lines.append(Text("  ERRORS", style="bold red"))
            lines.append(Text("  " + "\u2500" * 7, style="red"))
            lines.extend(
                _render_vc_block(self._errors, style="red", label_style="bold red")
            )
            lines.append(Text(""))

        # ── WARNINGS section ─────────────────────────────────────────────
        if self._warnings:
            lines.append(Text("  WARNINGS", style="bold yellow"))
            lines.append(Text("  " + "\u2500" * 9, style="yellow"))
            lines.extend(
                _render_vc_block(
                    self._warnings, style="yellow", label_style="bold yellow"
                )
            )
            lines.append(Text(""))

        # ── Footer ───────────────────────────────────────────────────────
        lines.append(Text(_SEPARATOR))

        return Group(*lines)

    # ── Key handlers ──────────────────────────────────────────────────────

    def key_escape(self) -> None:
        """``Escape`` key → dismiss panel, restore ``TaskDetail``."""
        self.post_message(self.Dismissed())

    def key_q(self) -> None:
        """``q`` key → dismiss panel, restore ``TaskDetail``."""
        self.post_message(self.Dismissed())
