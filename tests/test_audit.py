import json

import pytest

from icml_2026_repro.audit import audit_trajectory_directory


def test_audit_trajectory_directory_counts_files_and_operations(tmp_path):
    for name, operations in {"a": ["one", "two"], "b": ["three"]}.items():
        (tmp_path / f"{name}.json").write_text(
            json.dumps({"name": name, "operations": operations}), encoding="utf-8"
        )

    result = audit_trajectory_directory(tmp_path, revision="abc123")

    assert result.trajectories == 2
    assert result.actions == 3
    assert result.revision == "abc123"


def test_audit_trajectory_directory_rejects_missing_operations(tmp_path):
    (tmp_path / "bad.json").write_text(json.dumps({"name": "bad"}), encoding="utf-8")

    with pytest.raises(ValueError, match="operations"):
        audit_trajectory_directory(tmp_path, revision="abc123")
