import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

import icml_2026_repro.future_adaptation_evidence as future_adaptation_evidence
from icml_2026_repro.audit import GITHUB_REVISION
from icml_2026_repro.future_adaptation_evidence import (
    audit_future_adaptation,
    audit_residual_patch_fixture,
    build_future_adaptation_evidence,
)

TRAJECTORY_PATH = (
    Path(__file__).resolve().parents[1] / "external" / "NAPE" / "data" / "trajectories"
)


def test_audit_future_adaptation_preserves_all_release_targets():
    evidence = audit_future_adaptation(TRAJECTORY_PATH)

    assert evidence["summary"] == {
        "trajectories": 52,
        "removal_cases": 50,
        "inverse_insertion_cases": 52,
        "residual_patch_cases": 0,
        "target_preserved_cases": 52,
        "skipped_cases": 0,
    }
    trajectories = cast(list[dict[str, object]], evidence["trajectories"])
    assert all(row["target_preserved"] for row in trajectories)


def test_residual_patch_fixture_synthesizes_missing_operation():
    evidence = audit_residual_patch_fixture()

    assert evidence["ground_truth"] == [
        "VALUE | Sheet1!A1 | 1",
        "VALUE | Sheet1!A2 | 1",
        "VALUE | Sheet1!A2 | 1",
        "VALUE | Sheet1!A2 | 1",
    ]
    assert evidence["prediction"] == [
        "VALUE | Sheet1!A1 | 1",
        "VALUE | Sheet1!A1 | 2",
    ]
    assert evidence["missing_ops_count"] == 1
    assert evidence["target_preserved"] is True


def test_audit_future_adaptation_rejects_malformed_operation_with_filename(tmp_path):
    trajectory_path = tmp_path / "malformed.json"
    trajectory_path.write_text(
        json.dumps(
            {
                "operations": [
                    "VALUE | Sheet1!A1 | 1",
                    "VALUE | Sheet1!not-a-range | 2",
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="malformed.json"):
        audit_future_adaptation(tmp_path)


def test_audit_future_adaptation_rejects_empty_release(tmp_path):
    with pytest.raises(ValueError, match="no trajectory files"):
        audit_future_adaptation(tmp_path)


def test_audit_future_adaptation_raises_when_final_state_is_unequal(monkeypatch):
    class UnequalComparator:
        def __init__(self, ignore_defaults):
            assert ignore_defaults is True

        def compare(self, predicted_state, true_state, skip_ops_diff):
            del predicted_state, true_state
            assert skip_ops_diff is True
            return SimpleNamespace(false_positives=1, false_negatives=0, mismatches=0)

    monkeypatch.setattr(future_adaptation_evidence, "StateComparator", UnequalComparator)

    with pytest.raises(RuntimeError, match="target state"):
        audit_future_adaptation(TRAJECTORY_PATH)


def test_audit_future_adaptation_is_deterministic():
    assert audit_future_adaptation(TRAJECTORY_PATH) == audit_future_adaptation(TRAJECTORY_PATH)


def test_build_future_adaptation_evidence_composes_official_evidence(tmp_path, monkeypatch):
    release_evidence = {"summary": {"trajectories": 52}}
    residual_evidence = {"missing_ops_count": 1}
    trace_evidence = {"summary": {"accepted": 1, "rejected": 1}}
    monkeypatch.setattr(
        future_adaptation_evidence,
        "audit_future_adaptation",
        lambda _: release_evidence,
    )
    monkeypatch.setattr(
        future_adaptation_evidence,
        "audit_residual_patch_fixture",
        lambda: residual_evidence,
    )
    monkeypatch.setattr(
        future_adaptation_evidence,
        "build_online_trace_evidence",
        lambda _: trace_evidence,
    )

    assert build_future_adaptation_evidence(tmp_path) == {
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


@pytest.mark.parametrize(
    "produce_evidence",
    [
        lambda output_dir: audit_future_adaptation(TRAJECTORY_PATH),
        lambda output_dir: audit_residual_patch_fixture(),
        build_future_adaptation_evidence,
    ],
)
def test_public_evidence_rejects_mismatched_nape_revision(tmp_path, monkeypatch, produce_evidence):
    monkeypatch.setattr(
        future_adaptation_evidence,
        "read_git_head",
        lambda _: "wrong-revision",
    )

    with pytest.raises(RuntimeError, match="wrong-revision.*expected"):
        produce_evidence(tmp_path)


@pytest.mark.parametrize(
    "produce_evidence",
    [
        lambda output_dir: audit_future_adaptation(TRAJECTORY_PATH),
        lambda output_dir: audit_residual_patch_fixture(),
        build_future_adaptation_evidence,
    ],
)
def test_public_evidence_rejects_dirty_nape_checkout(tmp_path, monkeypatch, produce_evidence):
    monkeypatch.setattr(future_adaptation_evidence, "read_git_worktree_status", lambda _: " M x")

    with pytest.raises(RuntimeError, match="dirty"):
        produce_evidence(tmp_path)
