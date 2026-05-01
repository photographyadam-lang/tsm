# tsm/ui/task_tree.py — Left panel (Phase 6, P6-T01)
#
# Implements §8.2 of the specification.
#
# TaskTree is a Widget that composes a Textual Tree widget to display
# phases and tasks from a LoadedProject. Phases are top-level tree
# nodes, collapsed by default; the phase containing the active task is
# auto-expanded on mount. Task rows display: status icon + Task ID +
# title truncated to 30 characters.
#
# Public API:
#   TaskTree(project: LoadedProject)  — constructor
#   TaskTree.TaskSelected             — message emitted on Enter for a task node
#
# Done-when criteria:
#   1. TaskTree mounts without error when given a LoadedProject built from
#      the test fixture
#   2. The phase containing the active task is expanded; all other phases
#      are collapsed
#   3. Complete tasks and phases render visually distinct from pending/active
#      ones
#   4. Selecting a task node emits the expected message or updates the
#      expected reactive

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Tree

from tsm.models import LoadedProject, Phase, Task, TaskStatus


# ── Constants ────────────────────────────────────────────────────────────────

_STATUS_ICON: dict[TaskStatus, str] = {
    TaskStatus.COMPLETE: "✅",
    TaskStatus.ACTIVE: "▶",
    TaskStatus.PENDING: "·",
    TaskStatus.BLOCKED: "🔒",
    TaskStatus.NEEDS_REVIEW: "🔍",
    TaskStatus.IN_PROGRESS: "🔄",
}

_PHASE_ICON_COMPLETE = "✅"
_PHASE_ICON_ACTIVE = "▶"

_MAX_TITLE_LENGTH = 30


# ── Helpers ──────────────────────────────────────────────────────────────────


def _status_icon(status: TaskStatus) -> str:
    """Return the display icon for a task status.

    Falls back to a middle dot for any unrecognised status value.
    """
    return _STATUS_ICON.get(status, "·")


def _truncate(text: str, max_len: int = _MAX_TITLE_LENGTH) -> str:
    """Truncate *text* to *max_len* characters, appending ``…`` if cut."""
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


# ── TaskTree widget ──────────────────────────────────────────────────────────


class TaskTree(Widget):
    """Left-panel widget displaying phases and tasks in a collapsible tree.

    Phases are top-level tree nodes, collapsed by default.  The phase
    containing the active task is auto-expanded on mount.

    Task rows display: ``<status-icon> <Task-ID> · <title>`` with the
    title truncated to 30 characters.

    Active task is rendered in bold (accent).  Complete tasks and phases
    are rendered in a muted (dim) style.

    Keyboard navigation: arrow keys move through nodes, Enter on a phase
    node expands or collapses it, Enter on a task node emits a
    :class:`TaskSelected` message for the right panel to display.
    """

    # ── Custom message ───────────────────────────────────────────────────────

    class TaskSelected(Message):
        """Emitted when a non-phase (task) node is activated via Enter.

        Attributes:
            task: The :class:`Task` object that was selected.
        """

        def __init__(self, task: Task) -> None:
            self.task = task
            super().__init__()

    # ── Public API ───────────────────────────────────────────────────────────

    def __init__(self, project: LoadedProject, **kwargs) -> None:  # noqa: ANN003
        """Initialise the tree widget.

        Args:
            project: A fully-populated :class:`LoadedProject` whose
                ``phases`` and ``session`` will be used to build the
                tree.
        """
        super().__init__(**kwargs)
        self._project = project
        self._tree = Tree[str]("Phases & Tasks")

        # Determine which task (if any) is active, for highlighting
        self._active_task_id: str | None = None
        if project.session.active_task is not None:
            self._active_task_id = project.session.active_task.id

    def compose(self) -> ComposeResult:
        """Yield the inner :class:`Tree` widget."""
        yield self._tree

    def on_mount(self) -> None:
        """Build the tree from the :class:`LoadedProject` data.

        Called automatically by Textual after the widget tree is mounted.
        """
        self._build_tree()

    # ── Tree construction ────────────────────────────────────────────────────

    def _build_tree(self) -> None:
        """Populate the tree with phase and task nodes."""
        # Clear any existing nodes (safe to call even on first build)
        self._tree.clear()

        # Determine which phase holds the active task
        active_phase_id: str | None = None
        if self._project.session.active_task is not None:
            active_phase_id = self._project.session.active_task.phase_id

        for phase in self._project.phases:
            # ── Phase node ───────────────────────────────────────────────
            phase_label = self._format_phase_label(phase)
            phase_node = self._tree.root.add(phase_label, data=None)

            # ── Task nodes (children of this phase) ──────────────────────
            for task in phase.tasks:
                task_label = self._format_task_label(task)
                phase_node.add_leaf(task_label, data=task)

            # ── Expand/collapse phase ────────────────────────────────────
            is_active_phase = phase.id == active_phase_id
            if is_active_phase:
                phase_node.expand()
            else:
                phase_node.collapse()

    # ── Label formatting ────────────────────────────────────────────────────

    def _format_phase_label(self, phase: Phase) -> Text:
        """Build a styled label for a phase tree node.

        Uses ``✅`` prefix when the phase status is complete, otherwise
        ``▶``.  Complete phases are rendered in a dim (muted) style.
        """
        all_complete = all(
            task.status == TaskStatus.COMPLETE for task in phase.tasks
        )
        label_text = f"{_PHASE_ICON_COMPLETE if all_complete else _PHASE_ICON_ACTIVE} {phase.name}"

        if all_complete:
            return Text(label_text, style="dim")
        return Text(label_text)

    def _format_task_label(self, task: Task) -> Text:
        """Build a styled label for a task tree node.

        Format: ``<status-icon> <task-id> · <truncated-title>``.

        Complete tasks are dimmed; the active task (if any) is rendered
        in bold; all other tasks use normal weight.
        """
        title = _truncate(task.title)
        label_text = f"{_status_icon(task.status)} {task.id} · {title}"

        if task.status == TaskStatus.COMPLETE:
            return Text(label_text, style="dim")
        if task.id == self._active_task_id:
            return Text(label_text, style="bold")
        return Text(label_text)

    # ── Event handlers ───────────────────────────────────────────────────────

    def on_tree_node_selected(  # type: ignore[name-defined]
        self, event: Tree.NodeSelected[str]
    ) -> None:
        """Handle node selection (Enter key).

        - If the selected node carries a :class:`Task` as its data,
          emit :class:`TaskSelected`.
        - If the selected node is a phase (data is ``None``), let the
          Tree widget handle the toggle normally (it already expands/
          collapses on Enter for non-leaf nodes).
        """
        task: Task | None = event.node.data
        if task is not None:
            self.post_message(self.TaskSelected(task))
