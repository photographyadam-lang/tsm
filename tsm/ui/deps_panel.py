# tsm/ui/deps_panel.py — Dependency-inspection right panel (Phase 7)
#
# A right-panel widget that displays the dependency tree (default) or
# blocked-task list, rendered as styled Rich Text.
#
# Public API:
#   Depspanel(ctx: LoadedProject, mode="tree", task_id=None)  — constructor
#
# The panel posts a Depspanel.Dismissed message when the user presses Escape/q.

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Static

from tsm.models import LoadedProject, TaskStatus


# ── Display helpers (mirror deps.py status icons) ──────────────────────────

_STATUS_ICON: dict[TaskStatus, str] = {
    TaskStatus.COMPLETE: "✅",
    TaskStatus.ACTIVE: "▶",
    TaskStatus.PENDING: "·",
    TaskStatus.BLOCKED: "🔒",
    TaskStatus.NEEDS_REVIEW: "⚠️",
    TaskStatus.IN_PROGRESS: "▶",
}


def _status_icon(status: TaskStatus) -> str:
    return _STATUS_ICON.get(status, "·")


# ── Depspanel widget ───────────────────────────────────────────────────────


class Depspanel(Static):
    """Right-panel widget displaying dependency information.

    Supports two display modes:
      - ``"tree"`` (default): show the full dependency tree
      - ``"blocked"``: show only blocked tasks

    The panel is mounted into the right-panel container by ``TsmApp``
    when the user presses ``d`` (and optionally ``b`` for blocked view).
    """

    class Dismissed(Message):
        """Posted when the user dismisses the panel."""

    def __init__(
        self,
        ctx: LoadedProject,
        mode: str = "tree",
        task_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._ctx = ctx
        self._mode = mode
        self._task_id = task_id

    def on_mount(self) -> None:
        self._update_content()

    def _update_content(self) -> None:
        """Rebuild and re-display the renderable."""
        self.update(self._build_renderable())

    def _build_renderable(self) -> Text:
        """Build a Rich Text rendering of the dep information."""
        from tsm.deps import get_blocked_tasks

        if self._mode == "blocked":
            return self._render_blocked(get_blocked_tasks(self._ctx.phases))
        return self._render_tree()

    # ── Tree mode ──────────────────────────────────────────────────────────

    def _render_tree(self) -> Text:
        """Render the full dependency tree."""
        t = Text()
        t.append("  Dependency Tree\n", style="bold underline")
        t.append("\n")

        all_tasks: list = []
        for phase in self._ctx.phases:
            for task in phase.tasks:
                all_tasks.append(task)

        if not all_tasks:
            t.append("  (no tasks)\n", style="italic")
            return t

        max_title_len = max(len(task.title) for task in all_tasks)

        for phase in self._ctx.phases:
            phase_label = f"  {phase.name}\n"
            t.append(phase_label, style="bold")
            for task in phase.tasks:
                icon = _status_icon(task.status)
                deps_str = ""
                if task.hard_deps:
                    deps_str = "  ← " + ", ".join(task.hard_deps)
                title_padded = task.title.ljust(max_title_len)
                line = f"    {task.id}  {title_padded}  {icon}{deps_str}\n"
                t.append(line)
            t.append("\n")

        # Summary line
        from tsm.deps import detect_cycles

        blocked_count = len(get_blocked_tasks(self._ctx.phases))
        cycle = detect_cycles(self._ctx.phases)
        cycles = 1 if cycle else 0
        total = len(all_tasks)
        t.append("─" * 60 + "\n", style="dim")
        t.append(
            f"  {total} tasks  |  {blocked_count} blocked  |  {cycles} cycles\n"
        )
        return t

    # ── Blocked mode ───────────────────────────────────────────────────────

    def _render_blocked(self, blocked_tasks: list) -> Text:
        """Render the list of blocked tasks."""
        from tsm.commands.deps import _find_task

        t = Text()
        t.append("  Blocked tasks", style="bold underline")
        if blocked_tasks:
            t.append(f" ({len(blocked_tasks)})")
        t.append("\n\n")

        if not blocked_tasks:
            t.append("  ✅ No blocked tasks\n", style="green")
            return t

        for task in blocked_tasks:
            t.append(f"  {task.id}  {task.title}\n")
            waiting: list[str] = []
            for dep_id in task.hard_deps:
                dep_task = _find_task(self._ctx.phases, dep_id)
                if dep_task and dep_task.status != TaskStatus.COMPLETE:
                    from tsm.commands.deps import _STATUS_TEXT

                    label = _STATUS_TEXT.get(dep_task.status, dep_task.status.value)
                    waiting.append(f"{dep_id} ({label})")
            if waiting:
                t.append(f"          Waiting on: {', '.join(waiting)}\n", style="yellow")
        t.append("\n")
        t.append("─" * 60 + "\n", style="dim")
        return t

    # ── Key handler ────────────────────────────────────────────────────────

    def key_escape(self) -> None:
        """Escape → dismiss back to task detail."""
        self.post_message(self.Dismissed())

    def key_q(self) -> None:
        """q → dismiss back to task detail."""
        self.post_message(self.Dismissed())
