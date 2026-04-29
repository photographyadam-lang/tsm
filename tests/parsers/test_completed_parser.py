# tests/parsers/test_completed_parser.py — 3 tests for P2-T04
#
# Tests for parse_completed_file() covering all §9.4 requirements:
#   - Parse fixture TASKS-COMPLETED.md → at least 1 (phase_name, rows) tuple
#   - Missing file → [] without raising
#   - Each row dict has exactly 5 keys: task, description, complexity, commit, notes

from pathlib import Path

from tsm.parsers.completed_parser import parse_completed_file


# ---------------------------------------------------------------------------
# Fixture path
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
COMPLETED_FIXTURE = FIXTURE_DIR / "TASKS-COMPLETED.md"


# ===================================================================
# 1. Parse fixture file → at least 1 (phase_name, rows) tuple
# ===================================================================

class TestParseCompletedFile:
    """parse_completed_file on the TASKS-COMPLETED.md fixture."""

    def test_parse_completed_file_returns_tuples(self):
        """Returns a list with at least 1 (phase_name, rows) tuple."""
        result = parse_completed_file(COMPLETED_FIXTURE)
        assert isinstance(result, list), "Result must be a list"
        assert len(result) >= 1, "Expected at least 1 phase section"
        for phase_name, rows in result:
            assert isinstance(phase_name, str), "Phase name must be a string"
            assert isinstance(rows, list), "Rows must be a list"


# ===================================================================
# 2. Missing file → [] without raising
# ===================================================================

class TestParseCompletedFileMissing:
    """parse_completed_file on a nonexistent path."""

    def test_parse_completed_file_missing_returns_empty_list(self):
        """Returns [] without raising FileNotFoundError."""
        missing = FIXTURE_DIR / "NONEXISTENT_COMPLETED.md"
        result = parse_completed_file(missing)
        assert result == [], f"Expected [], got {result}"


# ===================================================================
# 3. Each row dict has exactly 5 canonical keys
# ===================================================================

class TestParseCompletedFileRowDict:
    """Row dicts contain exactly 5 keys: task, description, complexity, commit, notes."""

    def test_parse_completed_file_row_dict_keys(self):
        """Each row dict has exactly 5 keys: task, description, complexity, commit, notes."""
        result = parse_completed_file(COMPLETED_FIXTURE)
        assert len(result) >= 1, "Expected at least 1 phase section"
        for phase_name, rows in result:
            for row in rows:
                assert isinstance(row, dict), "Each row must be a dict"
                assert len(row) == 5, (
                    f"Expected 5 keys, got {len(row)}: {list(row.keys())}"
                )
                expected_keys = {"task", "description", "complexity", "commit", "notes"}
                assert set(row.keys()) == expected_keys, (
                    f"Expected keys {expected_keys}, got {set(row.keys())}"
                )
