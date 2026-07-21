# Task 4 Report: Full-Release Future Adaptation Evidence

## Status

DONE

## Changed Files

- `src/icml_2026_repro/future_adaptation_evidence.py`
  - Added the 52-trajectory official evaluator/simulator sweep.
  - Added the deterministic residual-patch fixture.
  - Added the composed future-adaptation evidence builder.
  - Enforced exact pinned NAPE HEAD and clean worktree checks in every public evidence producer.
- `src/icml_2026_repro/online_trace.py`
  - Renamed `build_claim_2_evidence` to `build_online_trace_evidence` without changing trace behavior.
- `src/icml_2026_repro/cli.py`
  - Updated the online trace builder import and call after the rename.
- `src/icml_2026_repro/__init__.py`
  - Updated the public online trace export after the rename.
- `tests/test_future_adaptation_evidence.py`
  - Added release summary, target preservation, residual patch, malformed input, empty release, unequal final state, determinism, composition, and checkout integrity coverage.
- `tests/test_online_trace.py`
  - Updated tests to use the renamed online trace builder.
- `tests/test_cli.py`
  - Updated CLI test patches to use the renamed online trace builder.

## Commits

- `333fd9f452f28374a19e9b5b4cbca271843b9ef7` - `feat: exercise NAPE future adaptation across the release`
- The report is committed separately after this document is written.

## TDD Evidence

### Red

Command:

```text
uv run pytest tests/test_future_adaptation_evidence.py -q
```

Output before implementation:

```text
ERROR collecting tests/test_future_adaptation_evidence.py
ImportError: cannot import name 'future_adaptation_evidence' from 'icml_2026_repro'
1 error in 0.37s
```

The test module could not collect because the required production module did not exist.

### Green

Command:

```text
uv run pytest tests/test_future_adaptation_evidence.py -q
```

Output:

```text
.............                                                            [100%]
13 passed in 15.52s
```

The asserted release summary is `52/50/52/0/52/0`; the residual fixture reports one missing operation and preserves the target.

## Verification

Required focused and upstream future-edit command:

```text
uv run pytest tests/test_future_adaptation_evidence.py tests/test_online_trace.py external/NAPE/tests/test_future_edits.py -q
```

Output:

```text
..........................................................               [100%]
58 passed in 16.37s
```

First pre-commit run:

```text
uv run pre-commit run -a
```

Output summary:

```text
AST, whitespace, prettier, ruff, and pytest passed.
ty failed with 7 diagnostics: three object comparison types, three invariant evaluator list arguments, and one uncast test evidence value.
```

The implementation was corrected with a typed trajectory row and explicit union-list/test casts; no ignores were added.

Final pre-commit run:

```text
uv run pre-commit run -a
```

Output:

```text
check python ast.........................................................Passed
fix end of files.........................................................Passed
trim trailing whitespace.................................................Passed
check for merge conflicts................................................Passed
fix requirements.txt.................................(no files to check)Skipped
prettier-format..........................................................Passed
ruff format..............................................................Passed
ruff (legacy alias)......................................................Passed
ty.......................................................................Passed
pytest...................................................................Passed
```

After writing this report, a further full pre-commit run reformatted
`tests/test_future_adaptation_evidence.py` and exited 1 because hooks changed the file;
all type checks and tests still passed. The hooks were rerun after accepting that
format-only delta, producing the same all-passed output above with exit code 0.

Diff integrity command:

```text
git diff --check
```

Output: empty, exit code 0.

## Self-Review

- Confirmed each release trajectory uses the sorted file order, exact next operation, deterministic `ZZ999` false positive, cached initial/target states, required evaluator arguments, simulator indices `1/1`, and final zero FP/FN/mismatch comparison.
- Confirmed per-trajectory counts come directly from `operations_removed`, `inverse_ops_added`, and `metadata["missing_ops_count"]`.
- Confirmed only `NotImplementedError` enters the explicit unsupported-operation skip path; malformed or short trajectories fail with the source filename.
- Confirmed all three new public evidence producers independently verify pinned HEAD and clean NAPE worktree, while the composed builder also calls the independently verified online trace.
- Confirmed the online trace implementation changed only its public function name and docstring; its trace logic is untouched.
- Confirmed no stale runtime or test imports reference `build_claim_2_evidence`.

## Concerns

None.
