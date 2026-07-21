"""Audit NAPE's future-edit adaptation against complete target states."""

import json
from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

from next_action_pred_eval.core.operation import Operation
from next_action_pred_eval.core.state import StateBuilder
from next_action_pred_eval.core.symbolic import symbolic_to_operations
from next_action_pred_eval.evaluation import (
    FutureEditsManager,
    StateComparator,
    StepEvaluator,
)

from icml_2026_repro.audit import (
    GITHUB_REVISION,
    REPOSITORY_ROOT,
    read_git_head,
    read_git_worktree_status,
)
from icml_2026_repro.online_trace import build_online_trace_evidence

RESIDUAL_GROUND_TRUTH = [
    "VALUE | Sheet1!A1 | 1",
    "VALUE | Sheet1!A2 | 1",
    "VALUE | Sheet1!A2 | 1",
    "VALUE | Sheet1!A2 | 1",
]
RESIDUAL_PREDICTION = [
    "VALUE | Sheet1!A1 | 1",
    "VALUE | Sheet1!A1 | 2",
]


class TrajectoryEvidence(TypedDict):
    """Audited mutation counts for one trajectory."""

    name: str
    operations_removed: int
    inverse_ops_added: int
    missing_ops_count: int
    target_preserved: bool
    skipped: NotRequired[bool]
    reason: NotRequired[str]


def audit_future_adaptation(trajectory_path: Path) -> dict[str, object]:
    """Exercise official future-edit adaptation over a trajectory release."""
    _verify_nape_checkout()
    trajectory_files = sorted(trajectory_path.glob("*.json"))
    if not trajectory_files:
        raise ValueError(f"no trajectory files found in {trajectory_path}")

    rows: list[TrajectoryEvidence] = []
    for path in trajectory_files:
        symbolic_operations = _read_symbolic_operations(path)
        try:
            operations = _parse_operations(symbolic_operations, path.name)
            if len(operations) < 2:
                raise ValueError(f"{path.name}: trajectory must contain at least two operations")
            predicted = [
                operations[1],
                *symbolic_to_operations(
                    [f"VALUE | {operations[0].cell_range.sheet}!ZZ999 | 987654321"]
                ),
            ]
            rows.append(_audit_mutation(path.stem, operations, predicted))
        except NotImplementedError as error:
            rows.append(
                {
                    "name": path.stem,
                    "operations_removed": 0,
                    "inverse_ops_added": 0,
                    "missing_ops_count": 0,
                    "target_preserved": False,
                    "skipped": True,
                    "reason": str(error),
                }
            )

    summary = {
        "trajectories": len(rows),
        "removal_cases": sum(row["operations_removed"] > 0 for row in rows),
        "inverse_insertion_cases": sum(row["inverse_ops_added"] > 0 for row in rows),
        "residual_patch_cases": sum(row["missing_ops_count"] > 0 for row in rows),
        "target_preserved_cases": sum(row["target_preserved"] is True for row in rows),
        "skipped_cases": sum(row.get("skipped") is True for row in rows),
    }
    return {"trajectories": rows, "summary": summary}


def audit_residual_patch_fixture() -> dict[str, object]:
    """Exercise the evaluator's residual missing-operation synthesis path."""
    _verify_nape_checkout()
    operations = _parse_operations(RESIDUAL_GROUND_TRUTH, "residual fixture")
    predicted = _parse_operations(RESIDUAL_PREDICTION, "residual fixture prediction")
    evidence = _audit_mutation("residual_patch_fixture", operations, predicted)
    if evidence["missing_ops_count"] != 1:
        raise RuntimeError("residual fixture did not synthesize exactly one missing operation")
    return {
        "ground_truth": list(RESIDUAL_GROUND_TRUTH),
        "prediction": list(RESIDUAL_PREDICTION),
        "operations_removed": evidence["operations_removed"],
        "inverse_ops_added": evidence["inverse_ops_added"],
        "missing_ops_count": evidence["missing_ops_count"],
        "target_preserved": evidence["target_preserved"],
    }


def build_future_adaptation_evidence(output_dir: Path) -> dict[str, object]:
    """Compose full-release, residual, and online-orchestrator evidence."""
    _verify_nape_checkout()
    release_evidence = audit_future_adaptation(
        REPOSITORY_ROOT / "external" / "NAPE" / "data" / "trajectories"
    )
    residual_evidence = audit_residual_patch_fixture()
    trace_evidence = build_online_trace_evidence(output_dir)
    return {
        "claim": (
            "Online evaluation predicts after each user action, accepts or rejects "
            "predictions, removes satisfied future operations, prepends inverses for "
            "false positives, and patches residual differences to preserve the target state."
        ),
        "source_revision": GITHUB_REVISION,
        "input_path": "external/NAPE/data/trajectories/*.json",
        "release_sweep": release_evidence,
        "residual_patch_fixture": residual_evidence,
        "orchestrator_trace": trace_evidence,
        "evidence_scope": "official_evaluator_full_release_and_deterministic_fixture",
        "verdict": "reproduced",
    }


def _verify_nape_checkout() -> None:
    """Require the exact clean NAPE checkout used by the evaluator imports."""
    nape_path = REPOSITORY_ROOT / "external" / "NAPE"
    revision = read_git_head(nape_path)
    if revision != GITHUB_REVISION:
        raise RuntimeError(f"NAPE checkout is at {revision}, expected {GITHUB_REVISION}")
    status = read_git_worktree_status(nape_path)
    if status:
        changed_paths = ", ".join(status.splitlines())
        raise RuntimeError(f"NAPE checkout is dirty: {changed_paths}")


def _read_symbolic_operations(path: Path) -> list[str]:
    """Read and validate one trajectory's symbolic operation list."""
    try:
        trajectory = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path.name}: could not read trajectory: {error}") from error
    if not isinstance(trajectory, dict):
        raise ValueError(f"{path.name}: trajectory must be a JSON object")
    symbolic_operations = trajectory.get("operations")
    if not isinstance(symbolic_operations, list) or not all(
        isinstance(operation, str) for operation in symbolic_operations
    ):
        raise ValueError(f"{path.name}: operations must be a list of strings")
    return cast(list[str], symbolic_operations)


def _parse_operations(symbolic_operations: list[str], source_name: str) -> list[Operation]:
    """Parse every symbolic operation or reject a partially parsed sequence."""
    operations = symbolic_to_operations(symbolic_operations)
    if len(operations) != len(symbolic_operations):
        raise ValueError(f"{source_name}: one or more operations could not be parsed")
    return operations


def _audit_mutation(
    name: str,
    operations: list[Operation],
    predicted: list[Operation],
) -> TrajectoryEvidence:
    """Run one official evaluator/simulator mutation and verify its target."""
    initial_state = StateBuilder().apply_operations(operations[:1])
    target_state = StateBuilder().apply_operations(operations)
    evaluation = StepEvaluator().evaluate(
        ground_truth_operations=cast(list[Operation | str], operations[1:3]),
        predicted_operations=cast(list[Operation | str], predicted),
        all_future_operations=cast(list[Operation | str], operations[1:]),
        initial_state_cache=initial_state,
        lookahead_state_cache=target_state,
        skip_ops_diff=True,
    )
    rebuilt_operations, changes = FutureEditsManager().simulate_future_edits(
        current_gt=operations,
        start_idx=1,
        end_idx=1,
        predicted_ops=predicted,
        eval_result=evaluation,
        initial_state=initial_state,
        final_target_state=target_state,
    )
    rebuilt_state = StateBuilder().apply_operations(rebuilt_operations)
    comparison = StateComparator(ignore_defaults=True).compare(
        rebuilt_state,
        target_state,
        skip_ops_diff=True,
    )
    target_preserved = (
        comparison.false_positives == 0
        and comparison.false_negatives == 0
        and comparison.mismatches == 0
    )
    if not target_preserved:
        raise RuntimeError(
            f"{name}: rebuilt sequence did not preserve the target state "
            f"(FP={comparison.false_positives}, FN={comparison.false_negatives}, "
            f"mismatches={comparison.mismatches})"
        )

    metadata = cast(dict[str, Any], changes["metadata"])
    return {
        "name": name,
        "operations_removed": len(cast(list[Operation], changes["operations_removed"])),
        "inverse_ops_added": len(cast(list[Operation], changes["inverse_ops_added"])),
        "missing_ops_count": cast(int, metadata["missing_ops_count"]),
        "target_preserved": target_preserved,
    }
