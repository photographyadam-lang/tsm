# tsm/__main__.py — CLI entry point and load_project bootstrap (Phase 5, P5-T01)
#
# Implements §3.1 entry point, §5.6 LoadedProject construction contract,
# §6.2 --yes behaviour, §10.1 exit code contract, §14 CLI-first constraint.
#
# Public API:
#   main() -> None                         — entry point (called by console_scripts)
#   load_project(root: Path) -> LoadedProject  — factory (may be imported by TUI)
#
# Constraints:
#   - sys.exit() is ONLY called in this module — no other module calls it
#   - Exit codes: 0 success, 1 precondition failure, 2 parse error, 3 write error
#   - load_project() is NOT reimplemented in any command module
#   - confirm → apply flow and --yes flag live here, not in command functions

import sys
from pathlib import Path

from tsm.models import LoadedProject
from tsm.parsers.tasks_parser import parse_tasks_file
from tsm.parsers.session_parser import parse_session_file
from tsm.project import ensure_tsm_dir, find_project_root
from tsm.shadow import apply, confirm_prompt


# ── Custom exceptions for exit-code mapping (§10.1) ─────────────────────────


class TsmError(Exception):
    """Base class for all tsm errors."""


class PreconditionError(TsmError):
    """Maps to exit code 1 — a precondition was not met."""


class ParseError(TsmError):
    """Maps to exit code 2 — a file could not be parsed."""


class WriteError(TsmError):
    """Maps to exit code 3 — a write operation failed."""


# ── Known command definitions ────────────────────────────────────────────────

# Write commands (return list[PendingWrite], use confirm→apply flow)
_WRITE_COMMANDS = frozenset({"advance", "init-phase", "complete-phase", "phase", "task"})

# Read-only commands (print to stdout, no PendingWrite)
_READ_COMMANDS = frozenset({"status", "vibe-check", "undo", "deps"})

# No-root commands (do not need project discovery)
_NO_ROOT_COMMANDS = frozenset({"help", "new-project"})

_ALL_COMMANDS = _WRITE_COMMANDS | _READ_COMMANDS | _NO_ROOT_COMMANDS


# ── load_project() — §5.6 construction contract ─────────────────────────────


def load_project(root: Path) -> LoadedProject:
    """Build a :class:`LoadedProject` from a valid project root directory.

    Construction order (exactly):
      1. ``ensure_tsm_dir(root)`` → :class:`ProjectContext`
      2. ``parse_tasks_file(ctx.tasks_path)`` → phase_overview, phases
      3. ``parse_session_file(ctx.sessionstate_path)`` → session
      4. Return ``LoadedProject(...)``

    Args:
        root: The project root directory (must contain ``TASKS.md`` and
              ``SESSIONSTATE.md``).

    Returns:
        A fully-populated :class:`LoadedProject`.

    Raises:
        ParseError: If either ``TASKS.md`` or ``SESSIONSTATE.md`` cannot be
                    parsed.
    """
    ctx = ensure_tsm_dir(root)
    try:
        phase_overview, phases = parse_tasks_file(Path(ctx.tasks_path))
        session = parse_session_file(Path(ctx.sessionstate_path))
    except Exception as exc:
        raise ParseError(str(exc)) from exc

    return LoadedProject(
        project_context=ctx,
        phases=phases,
        phase_overview=phase_overview,
        session=session,
    )


# ── main() — CLI entry point ────────────────────────────────────────────────


def main() -> None:
    """Entry point for the ``tsm`` CLI.

    Called by the ``tsm`` console_scripts entry point (``pyproject.toml``)
    and by ``python -m tsm``.

    Exit codes (§10.1):
        * 0 — success
        * 1 — :class:`PreconditionError` (or :class:`ValueError` from commands)
        * 2 — :class:`ParseError`
        * 3 — :class:`WriteError`
    """
    try:
        _dispatch()
    except PreconditionError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)
    except ParseError as exc:
        print(f"❌ Parse error: {exc}", file=sys.stderr)
        sys.exit(2)
    except WriteError as exc:
        print(f"❌ Write error: {exc}", file=sys.stderr)
        sys.exit(3)
    except TsmError as exc:
        # Generic tsm error → exit 1 (precondition-like)
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)


def _dispatch() -> None:
    """Parse ``sys.argv`` and route to the appropriate command handler."""
    args = sys.argv[1:]  # strip program name

    # ── Handle --help flag anywhere in args ──────────────────────────────
    if "--help" in args or "-h" in args:
        _handle_help(args)
        return

    # ── Extract --yes flag before dispatching (§6.2) ─────────────────────
    yes_flag = "--yes" in args
    args = [a for a in args if a != "--yes"]

    # ── No subcommand → launch TUI if in a project root (§8.1) ──────────
    if not args:
        root = find_project_root(Path.cwd())
        if root is not None:
            from tsm.app import TsmApp

            try:
                loaded = load_project(root)
            except (ParseError, Exception) as exc:
                print(f"❌ Could not load project: {exc}")
                sys.exit(2)
            try:
                TsmApp(loaded).run()
            except Exception as exc:
                print(f"❌ TUI error: {exc}")
                sys.exit(1)
            return
        # Not in a project root → show help
        _run_help_command(None)
        return

    command = args[0]
    rest = args[1:]

    # ── Unknown command ──────────────────────────────────────────────────
    if command not in _ALL_COMMANDS:
        print(f"Unknown command: {command}")
        sys.exit(1)

    # ── No-root commands (§3.1) ──────────────────────────────────────────
    if command == "help":
        _handle_help(args)
        return

    if command == "new-project":
        _handle_new_project(rest)
        return

    # ── Commands requiring a project root ────────────────────────────────
    root = find_project_root(Path.cwd())
    if root is None:
        print(
            "❌ No project root found — TASKS.md and SESSIONSTATE.md must "
            "both be present.\n"
            "   Run 'tsm new-project' first to scaffold a new project, or "
            "navigate into a project directory."
        )
        sys.exit(1)

    # Build LoadedProject (may raise ParseError → caught in main())
    try:
        loaded = load_project(root)
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(str(exc)) from exc

    # ── Write commands ───────────────────────────────────────────────────
    if command in _WRITE_COMMANDS:
        _handle_write_command(command, loaded, rest, yes_flag)
        return

    # ── Read-only commands ───────────────────────────────────────────────
    if command in _READ_COMMANDS:
        if yes_flag:
            print(f"Warning: --yes has no effect on {command}.")
        _handle_read_command(command, loaded, rest)
        return


# ── Command handlers ────────────────────────────────────────────────────────


def _handle_help(args: list[str]) -> None:
    """Handle ``help`` and ``--help`` invocations.

    If the first positional argument is ``"help"`` followed by another arg,
    the second arg is the command name to look up.
    """
    # Remove --help/-h flags and the "help" keyword to find the command name
    filtered = [a for a in args if a not in ("--help", "-h")]
    if filtered and filtered[0] == "help":
        # tsm help [command]  or  tsm --help [command]
        cmd = filtered[1] if len(filtered) > 1 else None
        _run_help_command(cmd)
    else:
        # tsm --help  (no "help" keyword)
        _run_help_command(None)


def _run_help_command(command: str | None) -> None:
    """Import and run ``help_command``."""
    from tsm.commands.help import help_command

    help_command(command)


def _handle_new_project(rest: list[str]) -> None:
    """Handle ``tsm new-project [--name <name>]``."""
    name = None
    i = 0
    while i < len(rest):
        if rest[i] == "--name" and i + 1 < len(rest):
            name = rest[i + 1]
            i += 2
        else:
            i += 1

    from tsm.commands.new_project import new_project

    new_project(Path.cwd(), name=name)


def _handle_write_command(
    command: str, loaded: LoadedProject, rest: list[str], yes_flag: bool
) -> None:
    """Dispatch a write command (advance, init-phase, complete-phase, phase)."""
    try:
        if command == "advance":
            # Advance can take an optional commit message
            commit_msg = _join_rest(rest)
            from tsm.commands.advance import advance

            pending_writes = advance(loaded, commit_message=commit_msg)
        elif command == "init-phase":
            if not rest:
                print("Usage: tsm init-phase <phase-id>")
                sys.exit(1)
            phase_id = rest[0]
            from tsm.commands.init_phase import init_phase

            pending_writes = init_phase(loaded, phase_id=phase_id)
        elif command == "complete-phase":
            from tsm.commands.complete_phase import complete_phase

            pending_writes = complete_phase(loaded)
        elif command == "phase":
            if not rest:
                print("Usage: tsm phase <add|edit|move|remove> [args...]")
                sys.exit(1)
            subcommand = rest[0]
            sub_args = rest[1:]
            from tsm.commands.phase import (
                phase_add,
                phase_edit,
                phase_move,
                phase_remove,
            )

            if subcommand == "add":
                # tsm phase add <name> [--after <phase-id>] [--status <status>]
                if not sub_args:
                    print("Usage: tsm phase add <name> [--after <phase-id>] [--status <status>]")
                    sys.exit(1)
                name = sub_args[0]
                after = None
                status = "Pending"
                i = 1
                while i < len(sub_args):
                    if sub_args[i] == "--after" and i + 1 < len(sub_args):
                        after = sub_args[i + 1]
                        i += 2
                    elif sub_args[i] == "--status" and i + 1 < len(sub_args):
                        status = sub_args[i + 1]
                        i += 2
                    else:
                        i += 1
                pending_writes = phase_add(loaded, name, after_phase_id=after, status=status)
            elif subcommand == "edit":
                # tsm phase edit <phase-id> [--name <name>] [--status <status>]
                if not sub_args:
                    print("Usage: tsm phase edit <phase-id> [--name <name>] [--status <status>]")
                    sys.exit(1)
                phase_id = sub_args[0]
                name = None
                status = None
                i = 1
                while i < len(sub_args):
                    if sub_args[i] == "--name" and i + 1 < len(sub_args):
                        name = sub_args[i + 1]
                        i += 2
                    elif sub_args[i] == "--status" and i + 1 < len(sub_args):
                        status = sub_args[i + 1]
                        i += 2
                    else:
                        i += 1
                pending_writes = phase_edit(loaded, phase_id, name=name, status=status)
            elif subcommand == "move":
                # tsm phase move <phase-id> --after <phase-id>
                if len(sub_args) < 3:
                    print("Usage: tsm phase move <phase-id> --after <phase-id>")
                    sys.exit(1)
                phase_id = sub_args[0]
                after = None
                i = 1
                while i < len(sub_args):
                    if sub_args[i] == "--after" and i + 1 < len(sub_args):
                        after = sub_args[i + 1]
                        break
                    i += 1
                if after is None:
                    print("Usage: tsm phase move <phase-id> --after <phase-id>")
                    sys.exit(1)
                pending_writes = phase_move(loaded, phase_id, after)
            elif subcommand == "remove":
                # tsm phase remove <phase-id> [--force]
                if not sub_args:
                    print("Usage: tsm phase remove <phase-id> [--force]")
                    sys.exit(1)
                phase_id = sub_args[0]
                force = "--force" in sub_args
                pending_writes = phase_remove(loaded, phase_id, force=force)
            else:
                print(f"Unknown phase subcommand: {subcommand}")
                print("Usage: tsm phase <add|edit|move|remove> [args...]")
                sys.exit(1)
        elif command == "task":
            if not rest:
                print("Usage: tsm task <add|edit|move|remove> [args...]")
                sys.exit(1)
            subcommand = rest[0]
            sub_args = rest[1:]
            from tsm.commands.task import (
                task_add,
                task_edit,
                task_move,
                task_remove,
            )

            if subcommand == "add":
                # tsm task add <phase-id> <title> [--after <task-id>]
                if len(sub_args) < 2:
                    print(
                        "Usage: tsm task add <phase-id> <title> "
                        "[--after <task-id>]"
                    )
                    sys.exit(1)
                phase_id = sub_args[0]
                # Title may be multiple words — collect until --after
                title_parts = []
                after_task_id = None
                i = 1
                while i < len(sub_args):
                    if sub_args[i] == "--after" and i + 1 < len(sub_args):
                        after_task_id = sub_args[i + 1]
                        break
                    title_parts.append(sub_args[i])
                    i += 1
                title = " ".join(title_parts)
                pending_writes = task_add(
                    ctx, phase_id, title, after_task_id=after_task_id
                )
            elif subcommand == "edit":
                # tsm task edit <task-id> --field <name> --value <value>
                if len(sub_args) < 5:
                    print(
                        "Usage: tsm task edit <task-id> "
                        "--field <name> --value <value>"
                    )
                    sys.exit(1)
                task_id = sub_args[0]
                field = None
                value = None
                i = 1
                while i < len(sub_args):
                    if sub_args[i] == "--field" and i + 1 < len(sub_args):
                        field = sub_args[i + 1]
                        i += 2
                    elif sub_args[i] == "--value" and i + 1 < len(sub_args):
                        value = sub_args[i + 1]
                        i += 2
                    else:
                        i += 1
                if field is None or value is None:
                    print(
                        "Usage: tsm task edit <task-id> "
                        "--field <name> --value <value>"
                    )
                    sys.exit(1)
                pending_writes = task_edit(ctx, task_id, field, value)
            elif subcommand == "move":
                # tsm task move <task-id> --phase <phase-id> [--after <task-id>]
                if len(sub_args) < 4:
                    print(
                        "Usage: tsm task move <task-id> "
                        "--phase <phase-id> [--after <task-id>]"
                    )
                    sys.exit(1)
                task_id = sub_args[0]
                target_phase_id = None
                after_task_id = None
                i = 1
                while i < len(sub_args):
                    if sub_args[i] == "--phase" and i + 1 < len(sub_args):
                        target_phase_id = sub_args[i + 1]
                        i += 2
                    elif sub_args[i] == "--after" and i + 1 < len(sub_args):
                        after_task_id = sub_args[i + 1]
                        i += 2
                    else:
                        i += 1
                if target_phase_id is None:
                    print(
                        "Usage: tsm task move <task-id> "
                        "--phase <phase-id> [--after <task-id>]"
                    )
                    sys.exit(1)
                pending_writes = task_move(
                    ctx, task_id, target_phase_id, after_task_id=after_task_id
                )
            elif subcommand == "remove":
                # tsm task remove <task-id> [--force]
                if not sub_args:
                    print("Usage: tsm task remove <task-id> [--force]")
                    sys.exit(1)
                task_id = sub_args[0]
                force = "--force" in sub_args
                pending_writes = task_remove(ctx, task_id, force=force)
            else:
                print(f"Unknown task subcommand: {subcommand}")
                print("Usage: tsm task <add|edit|move|remove> [args...]")
                sys.exit(1)
        else:
            # Should never reach here
            return
    except ValueError as exc:
        raise PreconditionError(str(exc)) from exc

    # Confirm → apply flow (§6.2)
    if confirm_prompt(pending_writes, yes=yes_flag):
        try:
            apply(pending_writes)
            print("✅ Changes applied successfully:")
            for pw in pending_writes:
                print(f"   • {pw.target_file}:")
                for line in pw.summary_lines:
                    print(f"     {line}")
        except Exception as exc:
            raise WriteError(str(exc)) from exc


def _handle_read_command(command: str, loaded: LoadedProject, rest: list[str]) -> None:
    """Dispatch a read-only command (status, vibe-check, undo, deps)."""
    if command == "status":
        from tsm.commands.status import status

        status(loaded)
    elif command == "vibe-check":
        from tsm.commands.vibe_check import vibe_check

        vibe_check(loaded)
    elif command == "undo":
        from tsm.commands.undo import undo

        undo(loaded.project_context)
    elif command == "deps":
        from tsm.commands.deps import deps_command

        # Parse deps arguments
        task_id: str | None = None
        tree = False
        blocked = False
        check = False

        for arg in rest:
            if arg == "--tree":
                tree = True
            elif arg == "--blocked":
                blocked = True
            elif arg == "--check":
                check = True
            elif arg.startswith("-"):
                print(f"Unknown flag: {arg}")
                return
            else:
                task_id = arg

        deps_command(loaded, task_id=task_id, tree=tree, blocked=blocked, check=check)


# ── Internal helpers ────────────────────────────────────────────────────────


def _join_rest(rest: list[str]) -> str:
    """Join remaining arguments into a single string for commit messages."""
    return " ".join(rest).strip()


# ── python -m tsm support ──────────────────────────────────────────────────

if __name__ == "__main__":
    main()
