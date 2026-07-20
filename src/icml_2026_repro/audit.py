"""Audit released trajectory files."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReleaseCounts:
    """Counts of trajectories and actions in a released source revision."""

    source: str
    revision: str
    trajectories: int
    actions: int


def audit_trajectory_directory(path: Path, revision: str) -> ReleaseCounts:
    """Count trajectories and operations in JSON files under ``path``."""
    trajectory_paths = sorted(path.glob("*.json"))
    action_count = 0
    for trajectory_path in trajectory_paths:
        trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
        operations = trajectory.get("operations")
        if not isinstance(operations, list) or not all(
            isinstance(operation, str) for operation in operations
        ):
            raise ValueError(f"{trajectory_path.name}: operations must be a list of strings")
        action_count += len(operations)
    return ReleaseCounts(
        source="github:Tej-55/NAPE",
        revision=revision,
        trajectories=len(trajectory_paths),
        actions=action_count,
    )
