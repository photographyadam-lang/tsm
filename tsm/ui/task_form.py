# tsm/ui/task_form.py — TaskFormOverlay widget (Phase 7, P7-T06)
#
# Implements §15.3 interactive edit path of the specification.
#
# TaskFormOverlay is a ModalScreen[dict | None] providing labelled input
# fields for all editable task fields.  It supports two modes:
#
#   Add mode  (task=None)     — all fields start blank
#   Edit mode (task=Task)     — fields pre-populated from the existing task
#
# On confirm: dismisses with a dict of field_name -> new_value for changed
# fields only.  Unchanged fields are absent from the dict.
# On cancel/Escape: dismisses with None.
#
# Public API:
#   TaskFormOverlay(task: Task | None = None)  — constructor
#
# Done-when criteria:
#   1. TaskFormOverlay mounts without error in both add mode and edit mode
#   2. In edit mode, all fields are pre-populated with the task's current values
#   3. Confirm dismisses with dict containing only changed fields
#   4. Cancel/Escape dismisses with None
#   5. Required field (title) shows validation error if empty on confirm attempt

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, TextArea

from tsm.models import Task, TaskComplexity


# ── Constants ──────────────────────────────────────────────────────────────────

_TITLE = "  Task form"

# Complexity select options: (display, value)
_COMPLEXITY_OPTIONS: list[tuple[str, str]] = [
    ("High", "high"),
    ("Medium", "medium"),
    ("Low", "low"),
    ("Unset", "unset"),
]

# Reviewer select options
_REVIEWER_OPTIONS: list[tuple[str, str]] = [
    ("Skip", "Skip"),
    ("Self", "Self"),
]

# CSS for the overlay — uses the same dialog styling conventions as
# InputScreen in app.py.
_CSS = """
TaskFormOverlay {
    align: center middle;
}

#task-form-dialog {
    width: 70%;
    height: 90%;
    background: $surface;
    border: thick $primary;
    padding: 1 2;
}

#task-form-dialog > #form-title {
    dock: top;
    height: 1;
    margin-bottom: 1;
    text-style: bold;
}

#task-form-dialog > #form-scroll {
    height: 1fr;
    overflow-y: auto;
}

#task-form-dialog > #form-scroll > .form-field {
    margin-bottom: 1;
}

#task-form-dialog > #form-scroll > .form-field > Label {
    margin-bottom: 0;
    text-style: bold;
}

#task-form-dialog > #form-scroll > .form-field > Input,
#task-form-dialog > #form-scroll > .form-field > Select,
#task-form-dialog > #form-scroll > .form-field > TextArea {
    width: 100%;
}

#task-form-dialog > #form-scroll > .form-field > TextArea {
    height: 5;
}

#task-form-dialog > #form-scroll > .form-field > #input-what {
    height: 6;
}

#task-form-dialog > #form-scroll > .form-field > #input-done_when {
    height: 6;
}

#task-form-dialog > #form-scroll > .form-field > #input-key_constraints {
    height: 4;
}

#task-form-dialog > .form-buttons {
    dock: bottom;
    height: 3;
    align: center middle;
}

#task-form-dialog > .form-buttons > Button {
    margin: 0 1;
}

.field-error {
    color: $error;
}
"""


# ── TaskFormOverlay modal screen ──────────────────────────────────────────────


class TaskFormOverlay(ModalScreen[dict | None]):
    """Modal form for adding or editing a task.

    In **add mode** (``task=None``) all fields start blank.
    In **edit mode** (``task=Task``) all fields are pre-populated.

    On confirm: dismisses with a ``dict`` containing only changed fields.
    On cancel / Escape: dismisses with ``None``.
    """

    CSS = _CSS

    def __init__(
        self, task: Task | None = None, **kwargs
    ) -> None:  # noqa: ANN003
        """Initialise the task form overlay.

        Args:
            task: An optional :class:`Task` to pre-populate fields for
                edit mode.  ``None`` means add mode (all fields blank).
        """
        super().__init__(**kwargs)
        self._task = task

        # Snapshot original values for change detection in edit mode.
        if task is not None:
            self._original: dict[str, object] = {
                "title": task.title,
                "complexity": task.complexity.value,
                "what": task.what if task.what else "",
                "prerequisite": task.prerequisite if task.prerequisite else "",
                "hard_deps": ", ".join(task.hard_deps) if task.hard_deps else "",
                "files": ", ".join(task.files) if task.files else "",
                "reviewer": task.reviewer if task.reviewer else "",
                "key_constraints": (
                    "\n".join(task.key_constraints)
                    if task.key_constraints
                    else ""
                ),
                "done_when": task.done_when if task.done_when else "",
            }
        else:
            self._original = {}

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Yield the modal's widget tree.

        Layout:

        .. code-block:: text

            ┌───────────────────────────────────────────┐
            │  Task form                                │
            │                                           │
            │  ┌─────────────────────────────────────┐  │
            │  │  Title:  [________________________]  │  │
            │  │  Complexity:  [Select v]             │  │
            │  │  What:                              │  │
            │  │  [................................]  │  │
            │  │  Prerequisite:  [________________]   │  │
            │  │  Hard deps:  [_____________________] │  │
            │  │  Files:  [_________________________] │  │
            │  │  Reviewer:  [Select v]               │  │
            │  │  Key constraints:                    │  │
            │  │  [................................]  │  │
            │  │  Done when:                          │  │
            │  │  [................................]  │  │
            │  └─────────────────────────────────────┘  │
            │                                           │
            │        [Y] Confirm    [N] Cancel           │
            └───────────────────────────────────────────┘
        """
        is_edit = self._task is not None

        with Vertical(id="task-form-dialog"):
            yield Static(_TITLE, id="form-title")

            with ScrollableContainer(id="form-scroll"):
                # ── Title (required) ────────────────────────────────────
                with Vertical(classes="form-field"):
                    yield Label("Title *")
                    yield Input(
                        value=self._original.get("title", ""),
                        id="input-title",
                        placeholder="Task title (required)",
                    )

                # ── Complexity ──────────────────────────────────────────
                with Vertical(classes="form-field"):
                    yield Label("Complexity")
                    yield Select(
                        options=_COMPLEXITY_OPTIONS,
                        value=self._original.get("complexity", "unset"),
                        id="select-complexity",
                        prompt="Select complexity",
                    )

                # ── What (multiline) ────────────────────────────────────
                with Vertical(classes="form-field"):
                    yield Label("What")
                    yield TextArea(
                        text=self._original.get("what", ""),
                        id="input-what",
                    )

                # ── Prerequisite ────────────────────────────────────────
                with Vertical(classes="form-field"):
                    yield Label("Prerequisite")
                    yield Input(
                        value=self._original.get("prerequisite", ""),
                        id="input-prerequisite",
                        placeholder="e.g. P6-T05 complete",
                    )

                # ── Hard deps ───────────────────────────────────────────
                with Vertical(classes="form-field"):
                    yield Label("Hard deps")
                    yield Input(
                        value=self._original.get("hard_deps", ""),
                        id="input-hard_deps",
                        placeholder="Comma-separated task IDs, or None",
                    )

                # ── Files ───────────────────────────────────────────────
                with Vertical(classes="form-field"):
                    yield Label("Files")
                    yield Input(
                        value=self._original.get("files", ""),
                        id="input-files",
                        placeholder="Comma-separated file paths",
                    )

                # ── Reviewer ────────────────────────────────────────────
                with Vertical(classes="form-field"):
                    yield Label("Reviewer")
                    # Dynamically include the current reviewer value if it
                    # is not already in the static options list.
                    reviewer_val: str = self._original.get("reviewer", "Skip")
                    reviewer_options = list(_REVIEWER_OPTIONS)
                    if not any(opt[1] == reviewer_val for opt in reviewer_options):
                        reviewer_options.insert(0, (reviewer_val, reviewer_val))
                    yield Select(
                        options=reviewer_options,
                        value=reviewer_val,
                        id="select-reviewer",
                        prompt="Select reviewer",
                    )

                # ── Key constraints (multiline) ─────────────────────────
                with Vertical(classes="form-field"):
                    yield Label("Key constraints")
                    yield TextArea(
                        text=self._original.get("key_constraints", ""),
                        id="input-key_constraints",
                    )

                # ── Done when (multiline) ───────────────────────────────
                with Vertical(classes="form-field"):
                    yield Label("Done when")
                    yield TextArea(
                        text=self._original.get("done_when", ""),
                        id="input-done_when",
                    )

            # ── Validation error display ──────────────────────────────────
            yield Static("", id="form-error", classes="field-error")

            # ── Action buttons ────────────────────────────────────────────
            with Horizontal(classes="form-buttons"):
                yield Button("[Y] Confirm", id="btn-confirm", variant="primary")
                yield Button("[N] Cancel", id="btn-cancel", variant="default")

    # ── Mount ────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        """Focus the title input on mount."""
        title_input = self.query_one("#input-title", Input)
        if title_input is not None:
            title_input.focus()

    # ── Field value helpers ──────────────────────────────────────────────────

    def _get_field_value(self, field_name: str) -> str:
        """Read the current value of a form field by name.

        Args:
            field_name: The field name (matches widget id suffix).

        Returns:
            The current value as a string.
        """
        # Input fields
        if field_name in ("title", "prerequisite", "hard_deps", "files"):
            widget = self.query_one(f"#input-{field_name}", Input)
            return widget.value if widget is not None else ""

        # Select fields
        if field_name in ("complexity", "reviewer"):
            widget = self.query_one(f"#select-{field_name}", Select)
            val = widget.value if widget is not None else ""
            return str(val) if val is not None else ""

        # TextArea fields
        if field_name in ("what", "key_constraints", "done_when"):
            widget = self.query_one(f"#input-{field_name}", TextArea)
            return widget.text if widget is not None else ""

        return ""

    def _collect_changes(self) -> dict[str, object]:
        """Build a dict of changed fields.

        For each editable field, compare the current form value to the
        original task value (edit mode) or to an empty/default baseline
        (add mode).  Only fields whose value differs are included.

        Returns:
            A dict mapping field names to their new values.  Returns an
            empty dict if nothing changed.
        """
        changes: dict[str, object] = {}
        field_names = [
            "title",
            "complexity",
            "what",
            "prerequisite",
            "hard_deps",
            "files",
            "reviewer",
            "key_constraints",
            "done_when",
        ]

        for field_name in field_names:
            current = self._get_field_value(field_name)

            # Determine the original baseline.
            if field_name in self._original:
                original = self._original[field_name]
                # Normalise: treat None/"" the same as empty string for
                # comparison purposes.
                orig_str = str(original) if original else ""
            else:
                orig_str = ""

            # Normalise current value for comparison.
            cur_str = current if current else ""

            if cur_str != orig_str:
                # Convert to appropriate Python type for the caller.
                if field_name == "hard_deps":
                    parsed = self._parse_comma_list(cur_str)
                    changes[field_name] = parsed
                elif field_name == "files":
                    parsed = self._parse_comma_list(cur_str)
                    changes[field_name] = parsed
                elif field_name == "key_constraints":
                    parsed = self._parse_bullet_list(cur_str)
                    changes[field_name] = parsed
                else:
                    changes[field_name] = cur_str

        return changes

    @staticmethod
    def _parse_comma_list(value: str) -> list[str]:
        """Parse a comma-separated string into a list of stripped items.

        Returns an empty list for blank/``None``/``"None"`` input.
        """
        stripped = value.strip()
        if not stripped or stripped.lower() == "none":
            return []
        return [item.strip() for item in stripped.split(",") if item.strip()]

    @staticmethod
    def _parse_bullet_list(value: str) -> list[str]:
        """Parse a multiline string into a list of non-empty lines.

        Leading dashes and whitespace are stripped from each line.
        Returns an empty list for blank input.
        """
        stripped = value.strip()
        if not stripped:
            return []
        lines = []
        for line in stripped.split("\n"):
            line = line.strip()
            if line:
                # Strip leading "- " if present (markdown bullet syntax).
                if line.startswith("- "):
                    line = line[2:]
                lines.append(line)
        return lines

    # ── Confirm logic ────────────────────────────────────────────────────────

    def _validate(self) -> str | None:
        """Validate form fields before confirming.

        Returns:
            An error message string if validation fails, or ``None`` if
            the form is valid.
        """
        title = self._get_field_value("title").strip()
        if not title:
            return "Title is required."
        return None

    def action_confirm(self) -> None:
        """Validate and confirm the form.

        If validation passes, collect changed fields and dismiss with the
        changes dict.  If validation fails, show the error message.
        """
        error = self._validate()
        error_static = self.query_one("#form-error", Static)
        if error is not None:
            if error_static is not None:
                error_static.update(error)
            return

        # Clear any previous error.
        if error_static is not None:
            error_static.update("")

        changes = self._collect_changes()
        self.dismiss(changes)

    # ── Key handlers ─────────────────────────────────────────────────────────

    def key_enter(self) -> None:
        """Enter key → confirm (same as clicking Confirm button)."""
        self.action_confirm()

    def key_escape(self) -> None:
        """Escape key → cancel (dismiss with ``None``)."""
        self.dismiss(None)

    # ── Button handlers ──────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        ``[Y] Confirm`` (id ``btn-confirm``) → validate and dismiss with
        changes dict.
        ``[N] Cancel`` (id ``btn-cancel``) → dismiss with ``None``.
        """
        event.stop()
        if event.button.id == "btn-confirm":
            self.action_confirm()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)
