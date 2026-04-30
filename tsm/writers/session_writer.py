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
    * ``## Active task`` — re-emits ``state.active_task_raw`` verbatim.
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

    # ── --- ── ## Active task (verbatim) ─────────────────────────────────
    parts.append("---")
    # NOTE: No blank line here — active_task_raw already starts with \n
    # (the section block produced by _split_sections begins with the content
    #  after the --- line, which is \n from the blank line in the source).
    if state.active_task_raw:
        parts.append(state.active_task_raw.rstrip("\n"))
    else:
        # Empty / no active task — emit the heading and [none] marker.
        parts.append("## Active task")
        parts.append("")
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


def write_session_file(content: str, shadow_path: str) -> None:
    """Write ``content`` to ``shadow_path`` (typically under ``.tsm/shadow/``).

    Creates parent directories if they do not exist.
    """
    p = Path(shadow_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
