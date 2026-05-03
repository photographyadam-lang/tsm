"""Debug reorder_task_blocks — trace exact line indices."""
from pathlib import Path
from tsm.writers.tasks_writer import reorder_task_blocks, _find_phase_by_id

TASKS_CLEAN = "tests/fixtures/TASKS.md"

content = Path(TASKS_CLEAN).read_text(encoding="utf-8")
lines = content.splitlines(keepends=True)

print(f"Total lines: {len(lines)}")
print()

# Find Phase 1 boundaries
phase_start, phase_end = _find_phase_by_id(lines, "phase-1--fixture-alpha")
print(f"Phase 1: lines[{phase_start}:{phase_end}]")
for i in range(phase_start, phase_end):
    stripped = lines[i].rstrip("\n\r")
    marker = ""
    if stripped == "---":
        marker = "  <--- SEPARATOR"
    if stripped.startswith("### "):
        marker = "  <--- HEADING"
    print(f"  line[{i:3d}]: {stripped!r}{marker}")
print(f"  phase_end = line[{phase_end}]")
print()

# Find Phase 2 boundaries
phase2_start, phase2_end = _find_phase_by_id(lines, "phase-2--fixture-beta")
print(f"Phase 2: lines[{phase2_start}:{phase2_end}]")
for i in range(phase2_start, phase2_end):
    stripped = lines[i].rstrip("\n\r")
    marker = ""
    if stripped == "---":
        marker = "  <--- SEPARATOR"
    if stripped.startswith("### "):
        marker = "  <--- HEADING"
    print(f"  line[{i:3d}]: {stripped!r}{marker}")
print(f"  phase_end = line[{phase_end}]")
print()

# Test reorder
result = reorder_task_blocks(
    content,
    phase_id="phase-1--fixture-alpha",
    ordered_task_ids=["FA-T04", "FA-T03", "FA-T02", "FA-T01"],
)

# Parse the result
from tsm.parsers.tasks_parser import parse_tasks_file
import tempfile
tmp = Path(tempfile.mktemp(suffix=".md"))
tmp.write_text(result, encoding="utf-8")
try:
    overview, phases = parse_tasks_file(tmp)
    for p in phases:
        print(f"Phase: {p.name}")
        for t in p.tasks:
            print(f"  {t.id}: {t.title}")
finally:
    tmp.unlink()
