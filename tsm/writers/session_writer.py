# tsm/writers/session_writer.py — Full reconstruction renderer (Phase 3, P3-T04)
#
# Two public functions:
#   render_sessionstate(state: SessionState) -> str
#   write_session_file(content: str, shadow_path: str) -> None
#
# Constraints (§9.3):
#   - Full reconstruction only — never targeted line replacement on
#     SESSIONSTATE.md; this is the sole purpose of this module.
#   - *Last updated:* uses datetime.now() at render time, not at command
#     invocation time.
#   - active_task_raw is re-emitted verbatim unless the calling command
#     has explicitly replaced it with a new Task.raw_block value.
#   - out_of_scope_raw is re-emitted exactly as stored — no normalization,
#     stripping, or modification of any kind.

from datetime import datetime
from pathlib import Path

from tsm.models import SessionState


# ── Public API ──────────────────────────────────────────────────────────────


def render_sessionstate(state: SessionState) -> str:
    """Render a ``SessionState`` into the canonical SESSIONSTATE.md format.

    Full reconstruction per §9.3 renderer invariants.  The output is
    designed to round-trip through ``parse_session_file()``.

    **Renderer invariants:**

    * ``*Last updated: YYYY-MM-DDTHH:MM*`` — always the current time at
      render, never a passed-in parameter.
    * ``---`` between every section.
    * ``## Active phase`` section from ``state.active_phase_name`` and
      ``state.active_phase_spec``.
    * ``## Completed tasks`` as a 3-column pipe-delimited table.
    * ``## Active task`` — always emitted with a ``## Active task``
      heading, followed by the task's markdown content (stripped of any
      duplicate heading that may have been carried through from a
      round-trip parse).
    * ``## Up next`` as a 5-column pipe-delimited table that **always**
      includes the Complexity column.
    * ``## Out of scope`` — re-emits ``state.out_of_scope_raw`` verbatim.
    """
    parts: list[str] = []

    # ── *Last updated:* ──────────────────────────────────────────────────
    now = datetime.now()
    parts.append(f"*Last updated: {now.strftime('%Y-%m-%dT%H:%M')}*")
    parts.append("")

    # ── --- ── ## Active phase ─────────────────────────────────────────────
    parts.append("---")
    parts.append("")
    parts.append("## Active phase")
    parts.append("")
    parts.append(state.active_phase_name)
    # The parser stores the spec value including backticks (``Spec: `path```),
    # so we re-emit it as-is without adding extra backticks.
    parts.append(f"Spec: {state.active_phase_spec}")
    parts.append("")

    # ── --- ── ## Completed tasks ─────────────────────────────────────────
    parts.append("---")
    parts.append("")
    parts.append("## Completed tasks")
    parts.append("")
    parts.append("| Task | Description | Commit message |")
    parts.append("|------|-------------|----------------|")
    for task in state.completed:
        # The parser stores the commit message in the ``what`` field.
        parts.append(f"| {task.id} | {task.title} | {task.what} |")
    parts.append("")

    # ── --- ── ## Active task ─────────────────────────────────────────────
    parts.append("---")
    parts.append("")
    parts.append("## Active task")
    parts.append("")
    # The raw block may come from two sources:
    #   1. TASKS.md raw_block (starts with "### P2-T01 · ...") — no
    #      heading, just the task content.
    #   2. Session parser round-trip (starts with "\n## Active task\n...")
    #      — includes the heading that was emitted on a previous render.
    # We strip the heading in case (2) so that the renderer always
    # produces exactly one ## Active task heading.
    raw = state.active_task_raw or ""
    if raw.strip() and raw.strip() != "[none]":
        content = _strip_active_task_heading(raw)
        parts.append(content.rstrip("\n"))
    else:
        parts.append("[none]")
    parts.append("")

    # ── --- ── ## Up next (5-column, always includes Complexity) ──────────
    parts.append("---")
    parts.append("")
    parts.append("## Up next")
    parts.append("")
    parts.append("| Task | Description | Hard deps | Complexity | Reviewer |")
    parts.append("|------|-------------|-----------|------------|----------|")
    for task in state.up_next:
        deps_str = ", ".join(task.hard_deps) if task.hard_deps else "\u2014"
        complexity = task.complexity.value if task.complexity else "unset"
        parts.append(
            f"| {task.id} | {task.title} | {deps_str} | {complexity} | {task.reviewer} |"
        )
    parts.append("")

    # ── --- ── ## Out of scope (verbatim) ─────────────────────────────────
    parts.append("---")
    # NOTE: Same reasoning as active_task_raw — the raw block already
    # carries its own leading \n from the --- section split.
    if state.out_of_scope_raw:
        parts.append(state.out_of_scope_raw.rstrip("\n"))
    else:
        parts.append("## Out of scope")
    parts.append("")

    return "\n".join(parts)


def _strip_active_task_heading(raw: str) -> str:
    """Remove the ``## Active task`` heading line from *raw* if present.

    The session parser stores the full section block (including the
    ``## Active task`` heading) as ``active_task_raw``.  Commands that
    initialise or advance a phase set ``active_task_raw`` from
    ``Task.raw_block`` (which starts with ``### P2-T01 · ...`` and has
    **no** ``## `` heading).  This helper normalises both forms so the
    renderer can always emit the heading itself.

    Strips the heading line and any leading blank lines that followed it,
    so the result is clean content starting with the task-level ``###``
    heading or inline content.

    Returns the content with the heading line and subsequent blank lines
    removed.
    """
    lines = raw.split("\n")
    # Filter out any line that is exactly "## Active task" (possibly with
    # leading whitespace from the section block)
    filtered = [l for l in lines if not l.strip().startswith("## Active task")]
    # Strip leading blank lines that were after the removed heading
    while filtered and filtered[0].strip() == "":
        filtered = filtered[1:]
    return "\n".join(filtered)


def write_session_file(content: str, shadow_path: str) -> None:
    """Write ``content`` to ``shadow_path`` (typically under ``.tsm/shadow/``).

    Creates parent directories if they do not exist.
    """
    p = Path(shadow_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

    # ── --- ── ## Up next (5-column, always includes Complexity) ──────────
    parts.append("---")
    parts.append("")
    parts.append("## Up next")
    parts.append("")
    parts.append("| Task | Description | Hard deps | Complexity | Reviewer |")
    parts.append("|------|-------------|-----------|------------|----------|")
    for task in state.up_next:
        deps_str = ", ".join(task.hard_deps) if task.hard_deps else "\u2014"
        complexity = task.complexity.value if task.complexity else "unset"
        parts.append(
            f"| {task.id} | {task.title} | {deps_str} | {complexity} | {task.reviewer} |"
        )
    parts.append("")

    # ── --- ── ## Out of scope (verbatim) ─────────────────────────────────
    parts.append("---")
    # NOTE: Same reasoning as active_task_raw — the raw block already
    # carries its own leading \n from the --- section split.
    if state.out_of_scope_raw:
        parts.append(state.out_of_scope_raw.rstrip("\n"))
    else:
        parts.append("## Out of scope")
    parts.append("")

    return "\n".join(parts)


def write_session_file(content: str, shadow_path: str) -> None:
    """Write ``content`` to ``shadow_path`` (typically under ``.tsm/shadow/``).

    Creates parent directories if they do not exist.
    """
    p = Path(shadow_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
