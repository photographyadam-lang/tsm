# tsm/ui/confirm_overlay.py — Confirm-to-apply modal (Phase 6, P6-T03)
#
# Implements §8.5 of the specification.
#
# ConfirmOverlay is a ModalScreen[bool] that displays the PendingWrite
# summary — target_file and summary_lines from each PendingWrite in the
# list — in the §6.2 format.  It responds to y/Y keys and a rendered
# [Y] Apply button → dismisses with True.  It responds to n/N/Escape
# keys and a rendered [N] Discard button → dismisses with False.
#
# The caller receives the bool result via Textual's
# push_screen_with_result() pattern.
#
# Public API:
#   ConfirmOverlay(pending_writes: list[PendingWrite])  — constructor
#
# Done-when criteria:
#   1. ConfirmOverlay displays all summary_lines from a list of 3
#      PendingWrites
#   2. y/Y keypress dismisses with True
#   3. n/N/Escape keypress dismisses with False
#   4. [Y] Apply and [N] Discard buttons trigger the same results as
#      their key equivalents

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from tsm.models import PendingWrite


# ── Constants ────────────────────────────────────────────────────────────────

_SEPARATOR = "\u2500" * 43  # ───────────────────────────────────────────
_HEADER = "  Pending changes \u2014 review before applying"


# ── ConfirmOverlay modal screen ──────────────────────────────────────────────


class ConfirmOverlay(ModalScreen[bool]):
    """Modal screen that displays a summary of pending writes and asks the
    user to confirm or discard.

    Returns ``True`` if the user confirmed (Apply), ``False`` if they
    declined (Discard).
    """

    def __init__(
        self, pending_writes: list[PendingWrite], **kwargs
    ) -> None:  # noqa: ANN003
        """Initialise the confirm overlay.

        Args:
            pending_writes: The list of :class:`PendingWrite` objects
                whose summary should be displayed.
        """
        super().__init__(**kwargs)
        self._pending_writes = pending_writes

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Yield the modal's widget tree.

        Layout:

        .. code-block:: text

            ┌─────────────────────────────────────┐
            │  ───────────────────────────────     │
            │    Pending changes — review...       │
            │  ───────────────────────────────     │
            │                                      │
            │    <target_file>                     │
            │      • <summary_line>                │
            │                                      │
            │  ───────────────────────────────     │
            │                                      │
            │       [Y] Apply    [N] Discard       │
            └─────────────────────────────────────┘
        """
        yield Vertical(
            # ── Separator / Header / Separator ────────────────────────
            Static(_SEPARATOR, classes="confirm-separator"),
            Static(_HEADER, classes="confirm-header"),
            Static(_SEPARATOR, classes="confirm-separator"),
            # ── Pending write details (empty placeholder; filled in
            #     on_mount) ────────────────────────────────────────────
            Static(Text(""), classes="confirm-summary"),
            # ── Bottom separator ──────────────────────────────────────
            Static(_SEPARATOR, classes="confirm-separator"),
            # ── Action buttons ────────────────────────────────────────
            Horizontal(
                Button("[Y] Apply", id="btn-apply", variant="primary"),
                Button("[N] Discard", id="btn-discard", variant="default"),
                classes="confirm-buttons",
            ),
            id="confirm-dialog",
        )

    def _render_summary(self) -> Text:
        """Build the full summary text from ``self._pending_writes``.

        Format matches the §6.2 CLI confirm output:

        ::

            <target_file>
              • <summary_line>
              • <summary_line>
            <target_file>
              • <summary_line>
        """
        result = Text()
        first = True

        for pw in self._pending_writes:
            if not first:
                result.append("\n")
            first = False

            # Target file in bold
            result.append(Text(f"  {pw.target_file}\n", style="bold"))

            for line in pw.summary_lines:
                result.append(Text(f"    \u2022 {line}\n"))  # bullet •

        # Remove trailing newline
        if result.plain.endswith("\n"):
            result.plain = result.plain.rstrip("\n")

        return result

    # ── Mount ────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        """Render the summary content into the static widget."""
        static: Static | None = self.query_one(".confirm-summary", Static)
        if static is not None:
            static.update(self._render_summary())

    # ── Key handlers ─────────────────────────────────────────────────────────

    def key_y(self) -> None:
        """``y`` or ``Y`` key → confirm (dismiss with ``True``)."""
        self.dismiss(True)

    def key_n(self) -> None:
        """``n`` or ``N`` key → discard (dismiss with ``False``)."""
        self.dismiss(False)

    def key_escape(self) -> None:
        """``Escape`` key → discard (dismiss with ``False``)."""
        self.dismiss(False)

    # ── Button handlers ──────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        ``[Y] Apply`` (id ``btn-apply``) → dismiss with ``True``.
        ``[N] Discard`` (id ``btn-discard``) → dismiss with ``False``.
        """
        event.stop()
        if event.button.id == "btn-apply":
            self.dismiss(True)
        elif event.button.id == "btn-discard":
            self.dismiss(False)
