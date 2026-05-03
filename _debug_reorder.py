"""Debug script for reorder_task_blocks."""
from pathlib import Path
from tsm.writers.tasks_writer import reorder_task_blocks, _find_phase_by_id
from tsm.parsers.tasks_parser import parse_tasks_file
from tsm.models import slugify_phase_name

FIXTURE_DIR = Path("tests/fixtures")
FIXTURE_PATH = FIXTURE_DIR / "TASKS.md"

content = FIXTURE_PATH.read_text(encoding="utf-8")
print(f"Fixture length: {len(content)}")

lines = content.splitlines(keepends=True)

# Find phase boundaries
phase_start, phase_end = _find_phase_by_id(lines, "phase-1--fixture-alpha")
print(f"Phase 1: start={phase_start}, end={phase_end}")

# Find task headings and dep graph in Phase 1
task_hdrs = []
dep_graph = -1
for i in range(phase_start, phase_end):
    s = lines[i].rstrip("\n\r")
    if s.startswith("### "):
        if s == "### Dependency graph":
            dep_graph = i
        else:
            task_hdrs.append(i)

print(f"Task headings: {task_hdrs}")
print(f"Dep graph: {dep_graph}")

# Show boundaries between tasks
all_boundaries = sorted(task_hdrs + ([dep_graph] if dep_graph != -1 else []) + [phase_end])
print(f"All boundaries: {all_boundaries}")

print("\n--- Task blocks ---")
for i, hdr in enumerate(task_hdrs):
    next_b = [b for b in all_boundaries if b > hdr][0]
    block_text = "".join(lines[hdr:next_b])
    tid = hdr
    print(f"Task at line {hdr}, ends at {next_b} ({(lines[hdr].rstrip())})")
    # Show last 2 lines of block
    block_lines = block_text.splitlines(keepends=True)
    print(f"  Block has {len(block_lines)} lines")
    for bl in block_lines[-3:]:
        print(f"  | {bl.rstrip()}")

print("\n--- Pre-task content ---")
pre = "".join(lines[phase_start:task_hdrs[0]])
print(pre[:200])

print("\n--- Suffix (dep graph to end) ---")
if dep_graph != -1:
    suffix = "".join(lines[dep_graph:phase_end])
    print(suffix[:200])
else:
    print("No dep graph")

# Now test reorder
print("\n\n=== Testing reorder_task_blocks ===")
modified = reorder_task_blocks(
    content, phase_id="phase-1--fixture-alpha",
    ordered_task_ids=["FA-T04", "FA-T03", "FA-T02", "FA-T01"]
)
print(f"Modified length: {len(modified)}")

# Write and parse
tmp = FIXTURE_DIR / ".tmp_debug.md"
tmp.write_text(modified, encoding="utf-8")
try:
    overview, phases = parse_tasks_file(tmp)
    print(f"Parsed {len(phases)} phases")
    for p in phases:
        print(f"  Phase: {p.name}")
        for t in p.tasks:
            print(f"    Task: {t.id}")
except Exception as e:
    print(f"Parse error: {e}")
    # Print first 500 chars of modified
    print("--- First 500 chars of modified ---")
    print(modified[:500])
    print("--- Last 500 chars of modified ---")
    print(modified[-500:])
finally:
    if tmp.exists():
        tmp.unlink()
