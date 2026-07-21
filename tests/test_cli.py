import errno
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

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
    monkeypatch.setattr(cli, "build_online_trace_evidence", lambda output_dir: claim_2)

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


def test_build_bundle_accepts_raw_macos_temporary_directory_alias(monkeypatch):
    if cli.platform.system() != "Darwin":
        pytest.skip("macOS root alias regression")

    with TemporaryDirectory(prefix="nape-repro-alias-") as temporary_directory:
        raw_temporary_path = Path(temporary_directory)
        root_component = raw_temporary_path.parts[1]
        if root_component not in {"var", "tmp"} or not (Path("/") / root_component).is_symlink():
            pytest.skip("temporary directory does not use a standard macOS root alias")
        output_dir = raw_temporary_path / "bundle"
        monkeypatch.setattr(
            cli,
            "build_claim_1_evidence",
            lambda: {"verdict": "falsified"},
        )
        monkeypatch.setattr(
            cli,
            "build_online_trace_evidence",
            lambda output_dir: {"verdict": "verified"},
        )

        result = cli.build_bundle(output_dir)

        assert result == output_dir
        assert {path.name for path in output_dir.iterdir()} == set(cli.BUNDLE_ARTIFACT_NAMES)


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
        "build_online_trace_evidence",
        lambda output_dir: pytest.fail("claim 2 evidence builder was called"),
    )

    with pytest.raises(RuntimeError, match="output directory must not be a symlink"):
        cli.build_bundle(output_dir)

    assert sentinel.read_text(encoding="utf-8") == "unchanged\n"
    assert {path.name for path in external_directory.iterdir()} == {"sentinel.txt"}


def test_build_bundle_rejects_symlinked_output_ancestor_before_evidence_work(tmp_path, monkeypatch):
    external_directory = tmp_path / "external"
    external_directory.mkdir()
    sentinel = external_directory / "sentinel.txt"
    sentinel.write_text("unchanged\n", encoding="utf-8")
    linked_ancestor = tmp_path / "link"
    linked_ancestor.symlink_to(external_directory, target_is_directory=True)
    monkeypatch.setattr(
        cli,
        "build_claim_1_evidence",
        lambda: pytest.fail("claim 1 evidence builder was called"),
    )
    monkeypatch.setattr(
        cli,
        "build_online_trace_evidence",
        lambda output_dir: pytest.fail("claim 2 evidence builder was called"),
    )

    with pytest.raises(RuntimeError, match="output directory.*symlink"):
        cli.build_bundle(linked_ancestor / "bundle")

    assert sentinel.read_text(encoding="utf-8") == "unchanged\n"
    assert {path.name for path in external_directory.iterdir()} == {"sentinel.txt"}


@pytest.mark.parametrize("alias_name", ["var", "tmp"])
def test_build_bundle_rejects_user_symlink_named_like_macos_root_alias(
    tmp_path, monkeypatch, alias_name
):
    external_directory = tmp_path / "external"
    external_directory.mkdir()
    sentinel = external_directory / "sentinel.txt"
    sentinel.write_text("unchanged\n", encoding="utf-8")
    user_alias = tmp_path / alias_name
    user_alias.symlink_to(external_directory, target_is_directory=True)
    monkeypatch.setattr(
        cli,
        "build_claim_1_evidence",
        lambda: pytest.fail("claim 1 evidence builder was called"),
    )
    monkeypatch.setattr(
        cli,
        "build_online_trace_evidence",
        lambda output_dir: pytest.fail("claim 2 evidence builder was called"),
    )

    with pytest.raises(RuntimeError, match="output directory.*symlink"):
        cli.build_bundle(user_alias / "bundle")

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
        "build_online_trace_evidence",
        lambda output_dir: pytest.fail("claim 2 evidence builder was called"),
    )

    with pytest.raises(RuntimeError, match=f"{artifact_name} must not be a symlink"):
        cli.build_bundle(output_dir)

    assert external_file.read_text(encoding="utf-8") == "unchanged\n"


@pytest.mark.parametrize("artifact_name", cli.BUNDLE_ARTIFACT_NAMES)
def test_build_bundle_replaces_hard_link_without_changing_external_inode(
    tmp_path, monkeypatch, artifact_name
):
    output_dir = tmp_path / "bundle"
    output_dir.mkdir()
    external_file = tmp_path / "external.txt"
    external_file.write_text("unchanged\n", encoding="utf-8")
    os.link(external_file, output_dir / artifact_name)
    claim_1 = {"verdict": "falsified"}
    claim_2 = {"verdict": "verified"}
    monkeypatch.setattr(cli, "build_claim_1_evidence", lambda: claim_1)
    monkeypatch.setattr(cli, "build_online_trace_evidence", lambda output_dir: claim_2)

    cli.build_bundle(output_dir)

    assert external_file.read_text(encoding="utf-8") == "unchanged\n"
    assert not external_file.samefile(output_dir / artifact_name)
    artifact_text = (output_dir / artifact_name).read_text(encoding="utf-8")
    if artifact_name == "claim_1_audit.json":
        assert json.loads(artifact_text) == claim_1
    elif artifact_name == "claim_2_trace.json":
        assert json.loads(artifact_text) == claim_2
    elif artifact_name == "environment.json":
        assert json.loads(artifact_text)["schema"] == "icml-2026-repro-bundle/v1"
    else:
        assert artifact_text.startswith("# NAPE Reproduction Evidence\n")
    assert {path.name for path in output_dir.iterdir()} == set(cli.BUNDLE_ARTIFACT_NAMES)


def test_build_bundle_atomically_replaces_artifact_symlink_after_preflight(tmp_path, monkeypatch):
    output_dir = tmp_path / "bundle"
    external_file = tmp_path / "external.txt"
    external_file.write_text("unchanged\n", encoding="utf-8")
    claim_1 = {"verdict": "falsified"}

    def build_claim_1_with_symlink_swap():
        (output_dir / "claim_1_audit.json").symlink_to(external_file)
        return claim_1

    monkeypatch.setattr(cli, "build_claim_1_evidence", build_claim_1_with_symlink_swap)
    monkeypatch.setattr(
        cli,
        "build_online_trace_evidence",
        lambda output_dir: {"verdict": "verified"},
    )

    result = cli.build_bundle(output_dir)

    assert result == output_dir
    assert external_file.read_text(encoding="utf-8") == "unchanged\n"
    assert not (output_dir / "claim_1_audit.json").is_symlink()
    assert json.loads((output_dir / "claim_1_audit.json").read_text(encoding="utf-8")) == claim_1
    assert {path.name for path in output_dir.iterdir()} == set(cli.BUNDLE_ARTIFACT_NAMES)


@pytest.mark.parametrize("failing_operation", ["write", "replace"])
def test_build_bundle_removes_staging_file_after_artifact_failure(
    tmp_path, monkeypatch, failing_operation
):
    output_dir = tmp_path / "bundle"
    monkeypatch.setattr(
        cli,
        "build_claim_1_evidence",
        lambda: {"verdict": "falsified"},
    )
    monkeypatch.setattr(
        cli,
        "build_online_trace_evidence",
        lambda output_dir: {"verdict": "verified"},
    )
    if failing_operation == "write":

        def fail_write(file_descriptor, contents):
            del file_descriptor, contents
            raise OSError(errno.EIO, "simulated write failure")

        monkeypatch.setattr(cli.os, "write", fail_write)
    else:

        def fail_replace(source, destination, **kwargs):
            del source, destination, kwargs
            raise OSError(errno.EIO, "simulated replace failure")

        monkeypatch.setattr(cli.os, "replace", fail_replace)

    with pytest.raises(RuntimeError, match=f"could not {failing_operation} claim_1_audit.json"):
        cli.build_bundle(output_dir)

    assert list(output_dir.iterdir()) == []
