import json
from pathlib import Path
from typing import cast

import pytest

import icml_2026_repro.benchmark_evidence as benchmark_evidence
from icml_2026_repro.benchmark_evidence import audit_benchmark_release, build_benchmark_evidence


NAPE_PATH = Path(__file__).resolve().parents[1] / "external" / "NAPE"
REQUIRED_RAW_FILES = [
    "operations.txt",
    "predictable_state.json",
    "sheet_image.png",
    "spreadsheet.xlsx",
]


def test_audit_benchmark_release_reproduces_paper_statistics():
    evidence = audit_benchmark_release(NAPE_PATH)
    artifact_audit = cast(dict[str, object], evidence["artifact_audit"])
    construction_pipeline = cast(dict[str, dict[str, object]], evidence["construction_pipeline"])

    assert evidence["observed"] == {
        "trajectories": 52,
        "operations": 11907,
        "minimum_sequence_length": 35,
        "maximum_sequence_length": 821,
        "mean_sequence_length": pytest.approx(228.98076923076923),
        "paper_rounded_mean": 229,
        "median_sequence_length": 164,
    }
    assert artifact_audit["matched_trajectory_ids"] == 52
    assert artifact_audit["required_files_per_trajectory"] == REQUIRED_RAW_FILES
    assert construction_pipeline["human_annotation"]["evidence_scope"] == (
        "release_provenance_only"
    )
    assert evidence["verdict"] == "reproduced"


@pytest.fixture
def minimal_nape_release(tmp_path):
    nape_path = tmp_path / "NAPE"
    trajectories_path = nape_path / "data" / "trajectories"
    raw_path = nape_path / "data" / "raw"
    trajectories_path.mkdir(parents=True)
    for name, operations in {"first": ["one", "two"], "second": ["three"]}.items():
        (trajectories_path / f"{name}.json").write_text(
            json.dumps({"name": name, "operations": operations}), encoding="utf-8"
        )
        trajectory_raw_path = raw_path / name
        trajectory_raw_path.mkdir(parents=True)
        for required_file in REQUIRED_RAW_FILES:
            (trajectory_raw_path / required_file).write_text("fixture\n", encoding="utf-8")
    for source_path in benchmark_evidence.PIPELINE_SOURCES.values():
        path = nape_path / source_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    return nape_path


def test_audit_benchmark_release_rejects_duplicate_trajectory_names(minimal_nape_release):
    (minimal_nape_release / "data" / "trajectories" / "third.json").write_text(
        json.dumps({"name": "first", "operations": ["four"]}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="duplicate trajectory name"):
        audit_benchmark_release(minimal_nape_release)


def test_audit_benchmark_release_rejects_filename_name_mismatch(minimal_nape_release):
    trajectory_path = minimal_nape_release / "data" / "trajectories" / "first.json"
    trajectory_path.write_text(
        json.dumps({"name": "other", "operations": ["one"]}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="filename/name mismatch"):
        audit_benchmark_release(minimal_nape_release)


def test_audit_benchmark_release_rejects_unequal_trajectory_and_raw_ids(minimal_nape_release):
    (minimal_nape_release / "data" / "raw" / "second").rename(
        minimal_nape_release / "data" / "raw" / "other"
    )

    with pytest.raises(ValueError, match="trajectory/raw ID sets differ"):
        audit_benchmark_release(minimal_nape_release)


def test_audit_benchmark_release_rejects_missing_required_raw_files(minimal_nape_release):
    (minimal_nape_release / "data" / "raw" / "first" / "sheet_image.png").unlink()

    with pytest.raises(ValueError, match="missing required raw files"):
        audit_benchmark_release(minimal_nape_release)


def test_audit_benchmark_release_rejects_non_string_operations(minimal_nape_release):
    trajectory_path = minimal_nape_release / "data" / "trajectories" / "first.json"
    trajectory_path.write_text(
        json.dumps({"name": "first", "operations": ["one", 2]}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="operations must be a non-empty list of strings"):
        audit_benchmark_release(minimal_nape_release)


def test_audit_benchmark_release_rejects_empty_release(minimal_nape_release):
    for trajectory_path in (minimal_nape_release / "data" / "trajectories").glob("*.json"):
        trajectory_path.unlink()

    with pytest.raises(ValueError, match="no trajectory JSON files"):
        audit_benchmark_release(minimal_nape_release)


def test_build_benchmark_evidence_rejects_mismatched_revision(monkeypatch):
    monkeypatch.setattr(benchmark_evidence, "read_git_head", lambda _: "wrong-revision")

    with pytest.raises(ValueError, match="wrong-revision.*expected"):
        build_benchmark_evidence()


def test_build_benchmark_evidence_rejects_dirty_checkout(monkeypatch):
    monkeypatch.setattr(
        benchmark_evidence,
        "read_git_head",
        lambda _: benchmark_evidence.GITHUB_REVISION,
    )
    monkeypatch.setattr(benchmark_evidence, "read_git_worktree_status", lambda _: " M data/raw")

    with pytest.raises(ValueError, match="checkout is dirty"):
        build_benchmark_evidence()
