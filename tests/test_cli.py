import json

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
