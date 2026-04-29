# tsm/models.py — Canonical data model (Phase 1, P1-T02)

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TaskStatus(Enum):
    COMPLETE = "complete"
    ACTIVE = "active"
    PENDING = "pending"
    BLOCKED = "blocked"
    NEEDS_REVIEW = "needs_review"
    IN_PROGRESS = "in_progress"


class TaskComplexity(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNSET = "unset"


@dataclass
class Task:
    id: str
    title: str
    status: TaskStatus
    complexity: TaskComplexity
    what: str
    prerequisite: str
    hard_deps: list[str]
    files: list[str]
    reviewer: str
    key_constraints: list[str]
    done_when: str
    phase_id: str
    subphase: Optional[str]
    raw_block: str


@dataclass
class Phase:
    id: str
    name: str
    status: str
    description: str
    tasks: list[Task] = field(default_factory=list)
    dependency_graph_raw: str = ""


@dataclass
class PhaseOverviewRow:
    phase_name: str
    description: str
    status: str


@dataclass
class SessionState:
    last_updated: datetime
    active_phase_name: str
    active_phase_spec: str
    active_task: Optional[Task]
    active_task_raw: str
    up_next: list[Task]
    completed: list[Task]
    out_of_scope_raw: str


@dataclass
class PendingWrite:
    target_file: str
    shadow_path: str
    live_path: str
    backup_path: str
    summary_lines: list[str]


@dataclass
class ProjectContext:
    root: str
    tasks_path: str
    sessionstate_path: str
    tasks_completed_path: str
    shadow_dir: str
    backup_dir: str
    history_log_path: str


@dataclass
class LoadedProject:
    project_context: ProjectContext
    phases: list[Phase]
    phase_overview: list[PhaseOverviewRow]
    session: SessionState


def slugify_phase_name(name: str, existing_slugs: list[str] | None = None) -> str:
    """Derive a Phase.id slug from a phase heading text string.

    Algorithm:
      1. Lowercase the entire string.
      2. Replace all whitespace sequences with a single hyphen.
      3. Strip all characters that are not alphanumeric (a-z, 0-9) or hyphens.
      4. Strip leading and trailing hyphens.
      5. Collision detection: if the resulting slug already appears in
         existing_slugs, append "-2". If "-2" also exists, try "-3", and so
         on until a unique slug is found.
    """
    if existing_slugs is None:
        existing_slugs = []
    slug = name.lower()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = slug.strip("-")
    if slug not in existing_slugs:
        return slug
    counter = 2
    while f"{slug}-{counter}" in existing_slugs:
        counter += 1
    return f"{slug}-{counter}"
