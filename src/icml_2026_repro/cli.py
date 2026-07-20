"""Command-line generation of the portable NAPE reproduction bundle."""

import errno
import json
import logging
import os
import platform
import stat
from pathlib import Path
from tempfile import TemporaryDirectory

from icml_2026_repro.audit import (
    DATASET_REPOSITORY,
    DATASET_REVISION,
    GITHUB_REPOSITORY,
    GITHUB_REVISION,
    build_claim_1_evidence,
)
from icml_2026_repro.online_trace import build_claim_2_evidence

BUNDLE_ARTIFACT_NAMES = (
    "claim_1_audit.json",
    "claim_2_trace.json",
    "environment.json",
    "README.md",
)


def main() -> None:
    """Generate the default reproduction bundle."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    bundle_path = build_bundle()
    logging.info("Wrote reproduction bundle to %s", bundle_path)


def build_bundle(output_dir: Path = Path("repro_bundle")) -> Path:
    """Build portable JSON evidence and operator documentation."""
    output_directory_fd = _open_output_directory(output_dir)
    try:
        _validate_artifact_destinations(output_directory_fd)
        claim_1 = build_claim_1_evidence()
        with TemporaryDirectory(prefix="nape-repro-internal-") as trace_directory:
            claim_2 = build_claim_2_evidence(Path(trace_directory))

        _write_json(output_directory_fd, "claim_1_audit.json", claim_1)
        _write_json(output_directory_fd, "claim_2_trace.json", claim_2)
        _write_json(output_directory_fd, "environment.json", _environment_manifest())
        _write_artifact(output_directory_fd, "README.md", _bundle_readme())
    finally:
        os.close(output_directory_fd)
    return output_dir


def _open_output_directory(output_dir: Path) -> int:
    """Open or create ``output_dir`` without following any symlink component."""
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    anchor = output_dir.anchor or "."
    components = output_dir.parts[1:] if output_dir.anchor else output_dir.parts
    opened_fds: list[int] = []
    try:
        try:
            current_fd = os.open(anchor, directory_flags)
        except OSError as error:
            raise RuntimeError(
                f"could not open output directory anchor: {error.strerror or error}"
            ) from error
        opened_fds.append(current_fd)

        for component in components:
            if component in ("", "."):
                continue
            next_fd = _open_output_directory_component(
                current_fd,
                component,
                directory_flags,
            )
            opened_fds.append(next_fd)
            current_fd = next_fd

        return opened_fds.pop()
    finally:
        for opened_fd in reversed(opened_fds):
            os.close(opened_fd)


def _open_output_directory_component(
    parent_fd: int,
    component: str,
    directory_flags: int,
) -> int:
    """Open or create one no-follow output directory component."""
    try:
        return os.open(component, directory_flags, dir_fd=parent_fd)
    except FileNotFoundError:
        try:
            os.mkdir(component, dir_fd=parent_fd)
        except FileExistsError:
            pass
        except OSError as error:
            raise RuntimeError(
                f"could not create output directory component {component!r}: "
                f"{error.strerror or error}"
            ) from error
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise RuntimeError(
                "output directory must not be a symlink and must contain only "
                f"directories: {component!r}"
            ) from error
        raise RuntimeError(
            f"could not open output directory component {component!r}: {error.strerror or error}"
        ) from error

    try:
        return os.open(component, directory_flags, dir_fd=parent_fd)
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise RuntimeError(
                "output directory must not be a symlink and must contain only "
                f"directories: {component!r}"
            ) from error
        raise RuntimeError(
            f"could not open output directory component {component!r}: {error.strerror or error}"
        ) from error


def _validate_artifact_destinations(output_directory_fd: int) -> None:
    """Reject pre-existing artifact symlinks before evidence generation."""
    for artifact_name in BUNDLE_ARTIFACT_NAMES:
        try:
            artifact_stat = os.stat(
                artifact_name,
                dir_fd=output_directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            continue
        except OSError as error:
            raise RuntimeError(
                f"could not inspect {artifact_name}: {error.strerror or error}"
            ) from error
        if stat.S_ISLNK(artifact_stat.st_mode):
            raise RuntimeError(f"{artifact_name} must not be a symlink")


def _write_json(output_directory_fd: int, artifact_name: str, value: object) -> None:
    """Write sorted, indented JSON with a stable trailing newline."""
    _write_artifact(
        output_directory_fd,
        artifact_name,
        json.dumps(value, indent=2, sort_keys=True) + "\n",
    )


def _write_artifact(output_directory_fd: int, artifact_name: str, contents: str) -> None:
    """Write an artifact relative to a verified directory without following symlinks."""
    artifact_flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        artifact_fd = os.open(
            artifact_name,
            artifact_flags,
            0o644,
            dir_fd=output_directory_fd,
        )
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise RuntimeError(f"{artifact_name} must not be a symlink") from error
        raise RuntimeError(
            f"could not open {artifact_name} for writing: {error.strerror or error}"
        ) from error

    try:
        remaining = memoryview(contents.encode("utf-8"))
        while remaining:
            try:
                bytes_written = os.write(artifact_fd, remaining)
            except OSError as error:
                raise RuntimeError(
                    f"could not write {artifact_name}: {error.strerror or error}"
                ) from error
            if bytes_written == 0:
                raise RuntimeError(f"could not write {artifact_name}: zero-byte write")
            remaining = remaining[bytes_written:]
    finally:
        os.close(artifact_fd)


def _environment_manifest() -> dict[str, object]:
    """Return portable runtime, source, and rerun metadata."""
    return {
        "commands": [
            "uv sync",
            "uv run nape-repro",
            "uv run pytest tests/test_cli.py -q",
            "uv run pytest -q",
            "uv run pytest external/NAPE/tests -q",
            "uv run pre-commit run -a",
            "uv run ty check src tests",
            "git diff --check",
        ],
        "pinned_revisions": {
            "dataset": {
                "repository": DATASET_REPOSITORY,
                "revision": DATASET_REVISION,
            },
            "github": {
                "repository": GITHUB_REPOSITORY,
                "revision": GITHUB_REVISION,
            },
        },
        "platform": {
            "machine": platform.machine(),
            "release": platform.release(),
            "system": platform.system(),
        },
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "schema": "icml-2026-repro-bundle/v1",
    }


def _bundle_readme() -> str:
    """Return the portable bundle artifact guide."""
    return """# NAPE Reproduction Evidence

This bundle is generated by `uv run nape-repro`.

- `claim_1_audit.json` contains the pinned GitHub and Hugging Face release counts,
  the challenge-card claim, the paper-reported counts, and the resulting verdict.
- `claim_2_trace.json` contains the official evaluator's prediction decisions,
  acceptance outcomes, and future-action counts for the deterministic fixture.
- `environment.json` records the Python/platform metadata, pinned revisions, and
  exact commands used to rerun the evidence.

For Claim 1, a trajectory is one JSON file or JSONL row, and an action is one
string in that trajectory's `operations` array. The action count is the sum of
those arrays; it does not count workbook cells, screenshots, or log events.

The challenge card says 58 trajectories and 13K actions.
The paper reports 52 trajectories and 11,907 steps/operations.
Its abstract summarizes this as approximately 12K. Both pinned release artifacts
reproduce those paper-reported counts, so the audit agrees with the paper and
falsifies the challenge-card wording.
"""
