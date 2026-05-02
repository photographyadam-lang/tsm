# tsm/ui/task_detail.py — Right panel (Phase 6, P6-T02)
#
# Implements §8.3 of the specification.
#
# TaskDetail is a Widget that displays full task metadata for a selected
# task.  It accepts a Task and the full phases list for dep status lookup.
#
# Public API:
#   TaskDetail(task: Task | None, phases: list[Phase])  — constructor
#   .display_task(task, phases)                          — update the displayed task
#
# Done-when criteria:
#   1. TaskDetail renders all fields for a high-complexity task with key
#      constraints present
#   2. Key constraints section is absent entirely (no heading, no empty list)
#      when task.key_constraints == []
#   3. All 4 Complexity color indicators (🔴 🟡 🟢 ⚪) render correctly for
#      the corresponding TaskComplexity values
#   4. Hard dep entries show the live status icon from the passed phases list

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from tsm.models import Phase, Task, TaskComplexity, TaskStatus


# ── Constants ────────────────────────────────────────────────────────────────

_STATUS_ICON: dict[TaskStatus, str] = {
    TaskStatus.COMPLETE: "\u2705",          # ✅
    TaskStatus.ACTIVE: "\u25b6",            # ▶
    TaskStatus.PENDING: "\u00b7",           # ·
    TaskStatus.BLOCKED: "\U0001f512",       # 🔒
    TaskStatus.NEEDS_REVIEW: "\U0001f50d",  # 🔍
    TaskStatus.IN_PROGRESS: "\U0001f504",   # 🔄
}

# (emoji, rich-style-string) for each complexity level
_COMPLEXITY_INDICATOR: dict[TaskComplexity, tuple[str, str]] = {
    TaskComplexity.HIGH: ("\U0001f534", "bold red"),        # 🔴
    TaskComplexity.MEDIUM: ("\U0001f7e1", "bold yellow"),   # 🟡
    TaskComplexity.LOW: ("\U0001f7e2", "bold green"),       # 🟢
    TaskComplexity.UNSET: ("\u26aa", "dim white"),           # ⚪
}

# ── Helpers ──────────────────────────────────────────────────────────────────


def _status_icon(status: TaskStatus) -> str:
    """Return the display icon for a task status.

    Falls back to a middle dot for any unrecognised status value.
    """
    return _STATUS_ICON.get(status, "\u00b7")


def _find_task_by_id(task_id: str, phases: list[Phase]) -> Task | None:
    """Search all phases for a task with the given *task_id*.

    Returns ``None`` if no task matches (dangling dep reference).
    """
    for phase in phases:
        for task in phase.tasks:
            if task.id == task_id:
                return task
    return None


def _find_phase_for_task(task: Task, phases: list[Phase]) -> Phase | None:
    """Return the :class:`Phase` whose id matches *task*.phase_id*.

    Returns ``None`` if the phase is not found (should not happen in a
    well-formed project).
    """
    for phase in phases:
        if phase.id == task.phase_id:
            return phase
    return None


# ── TaskDetail widget ────────────────────────────────────────────────────────


class TaskDetail(Widget):
    """Right-panel widget displaying full task metadata.

    Shows Task ID, Title, Status, Phase, Complexity with colour indicator,
    Hard deps with live status icons, Reviewer, Files, Key constraints
    (omitted entirely when empty), and Done when text (word-wrapped).
    """

    def __init__(
        self,
        task: Task | None = None,
        phases: list[Phase] | None = None,
        **kwargs,
    ) -> None:
        """Initialise the detail widget.

        Args:
            task: The :class:`Task` to display (or ``None`` for a placeholder).
            phases: The full list of :class:`Phase` objects for dep-status
                lookups.
        """
        super().__init__(**kwargs)
        self._detail_task = task
        self._phases = phases if phases is not None else []

    # ── compose / mount ──────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Yield a :class:`Static` widget that holds the rendered content."""
        yield Static(id="detail-content")

    def on_mount(self) -> None:
        """Render initial content on mount."""
        self._update_content()

    # ── Public API ───────────────────────────────────────────────────────────

    def display_task(self, task: Task, phases: list[Phase]) -> None:
        """Update the displayed task.

        Call this when the user selects a different task in the tree
        or the active task changes.
        """
        self._detail_task = task
        self._phases = phases
        self._update_content()

    # ── Content rendering ────────────────────────────────────────────────────

    def _update_content(self) -> None:
        """Re-render the content :class:`Static` widget."""
        static: Static | None = self.query_one("#detail-content", Static)
        if static is not None:
            static.update(self._build_renderable())

    def _build_renderable(self) -> RenderableType:
        """Build a Rich renderable from the current task data.

        Returns a placeholder when no task is set.
        """
        task = self._detail_task
        if task is None:
            return Text("No task selected", style="italic dim white")

        phases = self._phases
        lines: list[RenderableType] = []

        # ── Task ID & Title ──────────────────────────────────────────────
        lines.append(Text(f"Task:  {task.id}", style="bold white"))
        lines.append(Text(f"Title: {task.title}"))
        lines.append(Text(""))  # blank line separator

        # ── Status ───────────────────────────────────────────────────────
        status_icon = _status_icon(task.status)
        status_str = status_icon if status_icon else ""
        lines.append(
            Text(f"Status: {status_str} {task.status.value.title()}")
        )

        # ── Phase ────────────────────────────────────────────────────────
        phase = _find_phase_for_task(task, phases)
        phase_name = phase.name if phase is not None else task.phase_id
        lines.append(Text(f"Phase:  {phase_name}"))

        # ── Complexity with colour indicator ─────────────────────────────
        emoji, style = _COMPLEXITY_INDICATOR.get(
            task.complexity, ("\u26aa", "dim white")  # ⚪ fallback
        )
        complexity_label = task.complexity.value.title()
        complexity = Text("Complexity: ")
        complexity.append(f"{emoji} {complexity_label}", style=style)
        lines.append(complexity)

        # ── Hard deps ────────────────────────────────────────────────────
        if task.hard_deps:
            lines.append(Text("Hard deps:"))
            for dep_id in task.hard_deps:
                dep_task = _find_task_by_id(dep_id, phases)
                if dep_task is not None:
                    dep_icon = _status_icon(dep_task.status)
                    dep_line = Text(f"  {dep_id} {dep_icon}")
                else:
                    dep_line = Text(
                        f"  {dep_id} ?", style="dim white"
                    )
                lines.append(dep_line)
        else:
            lines.append(Text("Hard deps: None"))

        # ── Reviewer ─────────────────────────────────────────────────────
        reviewer = task.reviewer if task.reviewer else "(not set)"
        lines.append(Text(f"Reviewer: {reviewer}"))

        # ── Files ────────────────────────────────────────────────────────
        if task.files:
            lines.append(Text("Files:"))
            for file_entry in task.files:
                lines.append(Text(f"  {file_entry}"))
        else:
            lines.append(Text("Files: None"))

        # ── Key constraints (§8.3: omitted entirely when empty) ──────────
        if task.key_constraints:
            lines.append(Text("Key constraints:"))
            for constraint in task.key_constraints:
                lines.append(Text(f"  \u2022 {constraint}"))  # bullet •
        # When task.key_constraints == [], emit nothing — no heading, no list.

        # ── Done when (word-wrapped) ─────────────────────────────────────
        if task.done_when:
            lines.append(Text("Done when:"))
            for dw_line in task.done_when.strip().split("\n"):
                stripped = dw_line.strip()
                if stripped:
                    lines.append(Text(f"  {stripped}"))

        return Group(*lines)
