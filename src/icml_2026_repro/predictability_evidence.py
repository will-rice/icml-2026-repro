"""Recompute released predictability evidence from the NAPE release."""

import json
import math
import statistics
from pathlib import Path

from icml_2026_repro.audit import (
    GITHUB_REVISION,
    REPOSITORY_ROOT,
    read_git_head,
    read_git_worktree_status,
)


def verify_nape_checkout(nape_path: Path) -> None:
    """Require the exact clean NAPE checkout used for predictability evidence."""
    revision = read_git_head(nape_path)
    if revision != GITHUB_REVISION:
        raise ValueError(f"NAPE checkout is at {revision}, expected {GITHUB_REVISION}")
    status = read_git_worktree_status(nape_path)
    if status:
        raise ValueError(f"NAPE checkout is dirty: {', '.join(status.splitlines())}")


def aggregate_predictability(raw_path: Path) -> dict[str, object]:
    """Aggregate validated released predictable-state outputs."""
    verify_nape_checkout(raw_path.parents[1])
    trajectory_paths = sorted(path for path in raw_path.iterdir() if path.is_dir())
    rows: list[tuple[int, int, float]] = []
    trajectory_ids: set[str] = set()
    for trajectory_path in trajectory_paths:
        predictable_state_path = trajectory_path / "predictable_state.json"
        if not predictable_state_path.is_file():
            raise ValueError(f"{trajectory_path.name}: missing predictable_state.json")
        predictable_state = json.loads(predictable_state_path.read_text(encoding="utf-8"))
        if not isinstance(predictable_state, dict):
            raise ValueError(f"{trajectory_path.name}: JSON must be an object")

        trajectory_name = predictable_state.get("trajectory_name")
        if not isinstance(trajectory_name, str):
            raise ValueError(f"{trajectory_path.name}: trajectory_name must be a string")
        if trajectory_name != trajectory_path.name:
            raise ValueError(f"{trajectory_path.name}: trajectory_name does not match directory")
        if trajectory_name in trajectory_ids:
            raise ValueError(f"duplicate trajectory_name: {trajectory_name}")
        trajectory_ids.add(trajectory_name)

        predictable_count = predictable_state.get("predictable_count")
        if isinstance(predictable_count, bool) or not isinstance(predictable_count, int):
            raise ValueError(f"{trajectory_path.name}: predictable_count must be an integer")
        final_state_size = predictable_state.get("final_state_size")
        if isinstance(final_state_size, bool) or not isinstance(final_state_size, int):
            raise ValueError(f"{trajectory_path.name}: final_state_size must be an integer")
        if final_state_size <= 0:
            raise ValueError(f"{trajectory_path.name}: final_state_size must be positive")
        coverage_pct = predictable_state.get("coverage_pct")
        if (
            isinstance(coverage_pct, bool)
            or not isinstance(coverage_pct, int | float)
            or not math.isfinite(coverage_pct)
        ):
            raise ValueError(f"{trajectory_path.name}: coverage_pct must be a finite number")
        if not 0 <= coverage_pct <= 100:
            raise ValueError(f"{trajectory_path.name}: coverage_pct must be within [0, 100]")
        if not isinstance(predictable_state.get("predictable_properties"), dict):
            raise ValueError(f"{trajectory_path.name}: predictable_properties must be an object")

        calculated_coverage_pct = 100 * predictable_count / final_state_size
        if not math.isclose(coverage_pct, calculated_coverage_pct, abs_tol=1e-2):
            raise ValueError(f"{trajectory_path.name}: coverage_pct does not match counts")
        rows.append((predictable_count, final_state_size, coverage_pct))

    if not rows:
        raise ValueError("no predictable-state outputs found")
    total_predictable = sum(row[0] for row in rows)
    total_final = sum(row[1] for row in rows)
    coverages = [row[2] for row in rows]
    return {
        "claim": (
            "Approximately 68% of final spreadsheet properties are empirically predictable "
            "by the released frontier-model oracle pipeline."
        ),
        "source_revision": GITHUB_REVISION,
        "input_path": "external/NAPE/data/raw/*/predictable_state.json",
        "counting_definition": (
            "Weighted coverage is 100 times the sum of predictable_count divided by the sum "
            "of final_state_size."
        ),
        "observed": {
            "trajectories": len(rows),
            "predictable_properties": total_predictable,
            "final_state_properties": total_final,
            "weighted_coverage_pct": 100 * total_predictable / total_final,
            "mean_coverage_pct": statistics.mean(coverages),
            "median_coverage_pct": statistics.median(coverages),
            "trajectories_above_50_pct": sum(value > 50 for value in coverages),
        },
        "evidence_scope": "released_oracle_output_recomputation",
        "limitation": "The original paid frontier-model oracle calls were not rerun.",
        "verdict": "reproduced_from_released_outputs",
    }


def build_predictability_evidence() -> dict[str, object]:
    """Build predictability evidence from the exact clean pinned NAPE checkout."""
    nape_path = REPOSITORY_ROOT / "external" / "NAPE"
    verify_nape_checkout(nape_path)
    return aggregate_predictability(nape_path / "data" / "raw")
