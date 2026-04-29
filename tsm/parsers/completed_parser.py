# tsm/parsers/completed_parser.py — TASKS-COMPLETED.md parser (P2-T04)
#
# Implements parse_completed_file() per §9.4: identify phase sections by
# ## headings, collect rows from pipe-delimited tables, return list of
# (phase_name, rows) tuples. Missing file returns [] without raising.

from pathlib import Path


def _is_separator_row(row_line: str) -> bool:
    """Return True if the row is a pipe-table separator (|---|)."""
    return all(
        set(c.strip()).issubset({"-", ":", " "})
        for c in row_line.split("|")
        if c.strip()
    )


def _parse_pipe_table_row(row_line: str) -> list[str]:
    """Split a pipe-delimited table row into stripped cell values.

    Strips leading/trailing empty cells from the outer pipes.
    """
    cells = [c.strip() for c in row_line.split("|")]
    # Remove leading empty cell (from leading |)
    if cells and cells[0] == "":
        cells = cells[1:]
    # Remove trailing empty cell (from trailing |)
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def _parse_table_rows(lines: list[str]) -> list[list[str]]:
    """Parse pipe-delimited table lines into a list of raw cell lists.

    Skips the header row (first pipe row) and the separator row (|---|).
    Returns only data rows.
    """
    rows: list[list[str]] = []
    seen_header = False
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        if _is_separator_row(s):
            continue
        # Skip the first non-separator pipe row — it's the column header
        if not seen_header:
            seen_header = True
            continue
        rows.append(_parse_pipe_table_row(s))
    return rows


def parse_completed_file(path: Path) -> list[tuple[str, list[dict]]]:
    """Parse a TASKS-COMPLETED.md file into phase-section tuples.

    Args:
        path: Path to the TASKS-COMPLETED.md file.

    Returns:
        A list of (phase_name, rows) tuples in file order, where rows
        is a list of dicts each with keys: task, description, complexity,
        commit, notes. Returns [] if the file does not exist.
    """
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")

    # Normalize line endings
    if "\r\n" in content:
        content = content.replace("\r\n", "\n")

    lines = content.split("\n")

    result: list[tuple[str, list[dict]]] = []
    current_phase_name: str | None = None
    current_table_lines: list[str] = []

    for line in lines:
        s = line.strip()
        # Detect phase section headings
        if s.startswith("## "):
            # Flush previous phase section if we were collecting one
            if current_phase_name is not None:
                rows = _parse_table_rows(current_table_lines)
                dict_rows = [
                    _row_to_dict(cells)
                    for cells in rows
                ]
                result.append((current_phase_name, dict_rows))

            # Start new phase section
            current_phase_name = s[3:]  # strip "## " prefix
            current_table_lines = []
        else:
            if current_phase_name is not None:
                current_table_lines.append(line)

    # Flush last phase section
    if current_phase_name is not None:
        rows = _parse_table_rows(current_table_lines)
        dict_rows = [
            _row_to_dict(cells)
            for cells in rows
        ]
        result.append((current_phase_name, dict_rows))

    return result


def _row_to_dict(cells: list[str]) -> dict:
    """Convert a parsed table row (5 cells) into a dict with canonical keys.

    Keys: task, description, complexity, commit, notes.
    """
    keys = ["task", "description", "complexity", "commit", "notes"]
    # Pad with empty strings if fewer than 5 cells (malformed rows)
    padded = cells[:5] + [""] * max(0, 5 - len(cells))
    return dict(zip(keys, padded))
