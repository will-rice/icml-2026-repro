import json

import pytest

from icml_2026_repro import cli


def test_build_bundle_writes_portable_evidence_files(tmp_path, monkeypatch):
    claim_1 = {
        "observed": {"actions": 3, "trajectories": 2},
        "verdict": "falsified",
    }
    claim_2 = {
        "summary": {"accepted": 1, "rejected": 1},
        "verdict": "verified",
    }
    monkeypatch.setattr(cli, "build_claim_1_evidence", lambda: claim_1)
    monkeypatch.setattr(cli, "build_claim_2_evidence", lambda output_dir: claim_2)

    result = cli.build_bundle(tmp_path)

    assert result == tmp_path
    expected_files = {
        "claim_1_audit.json",
        "claim_2_trace.json",
        "environment.json",
        "README.md",
    }
    assert {path.name for path in tmp_path.iterdir()} == expected_files
    for filename in expected_files - {"README.md"}:
        json.loads((tmp_path / filename).read_text(encoding="utf-8"))
    assert str(tmp_path) not in "\n".join(
        path.read_text(encoding="utf-8") for path in tmp_path.iterdir()
    )
    bundle_readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "challenge-card wording" in bundle_readme
    assert "paper reports 52 trajectories and 11,907 steps/operations" in bundle_readme
    assert "paper's claimed counts" not in bundle_readme


def test_build_bundle_rejects_symlinked_output_directory_before_evidence_work(
    tmp_path, monkeypatch
):
    external_directory = tmp_path / "external"
    external_directory.mkdir()
    sentinel = external_directory / "sentinel.txt"
    sentinel.write_text("unchanged\n", encoding="utf-8")
    output_dir = tmp_path / "bundle"
    output_dir.symlink_to(external_directory, target_is_directory=True)
    monkeypatch.setattr(
        cli,
        "build_claim_1_evidence",
        lambda: pytest.fail("claim 1 evidence builder was called"),
    )
    monkeypatch.setattr(
        cli,
        "build_claim_2_evidence",
        lambda output_dir: pytest.fail("claim 2 evidence builder was called"),
    )

    with pytest.raises(RuntimeError, match="output directory must not be a symlink"):
        cli.build_bundle(output_dir)

    assert sentinel.read_text(encoding="utf-8") == "unchanged\n"
    assert {path.name for path in external_directory.iterdir()} == {"sentinel.txt"}


@pytest.mark.parametrize(
    "artifact_name",
    ["claim_1_audit.json", "claim_2_trace.json", "environment.json", "README.md"],
)
def test_build_bundle_rejects_symlinked_artifact_before_evidence_work(
    tmp_path, monkeypatch, artifact_name
):
    output_dir = tmp_path / "bundle"
    output_dir.mkdir()
    external_file = tmp_path / "external.txt"
    external_file.write_text("unchanged\n", encoding="utf-8")
    (output_dir / artifact_name).symlink_to(external_file)
    monkeypatch.setattr(
        cli,
        "build_claim_1_evidence",
        lambda: pytest.fail("claim 1 evidence builder was called"),
    )
    monkeypatch.setattr(
        cli,
        "build_claim_2_evidence",
        lambda output_dir: pytest.fail("claim 2 evidence builder was called"),
    )

    with pytest.raises(RuntimeError, match=f"{artifact_name} must not be a symlink"):
        cli.build_bundle(output_dir)

    assert external_file.read_text(encoding="utf-8") == "unchanged\n"
