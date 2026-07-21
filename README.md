# NAPE ICML 2026 Reproduction

This repository audits two claims presented by the ICML 2026 Agent
Reproducibility Challenge for [A Benchmark and Framework for Evaluating Next
Action Predictions in Spreadsheets](https://arxiv.org/abs/2606.13802). It
packages portable evidence and reruns the official online evaluator without
paid model inference.

## Results

- **Challenge-card Claim 1: falsified.** The challenge card says 58 trajectories
  and 13K actions. The paper itself reports 52 trajectories and 11,907
  steps/operations, summarized as approximately 12K in its abstract. Both
  pinned release artifacts agree with the paper, so this audit corroborates the
  paper and falsifies the challenge-card wording.
- **Claim 2: verified.** The official online orchestrator predicts after user
  actions, records accepted and rejected predictions, and updates future
  operations after an accepted prediction.

These results reproduce released benchmark cardinality and evaluator behavior.
They do not benchmark model quality or reproduce model-quality tables. The
run is CPU-only and uses no paid API calls; paid API cost is `$0.00`.

## Prerequisites

- Python 3.13 or newer
- [`uv`](https://docs.astral.sh/uv/)
- Network access for the pinned Hugging Face dataset audit
- The repository checkout, including the pinned `external/NAPE` submodule

Install the locked environment with:

```bash
uv sync
```

## Reproduce

Generate the four-file evidence bundle with:

```bash
uv run nape-repro
```

The command writes `repro_bundle/claim_1_audit.json`,
`repro_bundle/claim_2_trace.json`, `repro_bundle/environment.json`, and
`repro_bundle/README.md`. The bundle contains no credentials, access tokens, or
machine-specific absolute paths.

Run the focused package tests, the full root suite, and the official upstream
tests with:

```bash
uv run pytest tests/test_cli.py -q
uv run pytest -q
uv run pytest external/NAPE/tests -q
```

The upstream suite is expected to report 244 passing tests. Formatting and type
checks are:

```bash
uv run pre-commit run -a
uv run ty check src tests
git diff --check
```

## Challenge Validation

For the ICML 2026 Agent Reproducibility Challenge, download the current
`scripts/validate_icml_logbook.py` from the target Space and run:

```bash
uv run python scripts/validate_icml_logbook.py
```

The target Space is [`wrice/repro-a-benchmark-and-framework-for-evaluating-next-action-predictions-in-spreadsheets`](https://huggingface.co/spaces/wrice/repro-a-benchmark-and-framework-for-evaluating-next-action-predictions-in-spreadsheets).

## Pinned Sources

- [NAPE GitHub revision `ac0d10e4`](https://github.com/Tej-55/NAPE/tree/ac0d10e4dc345f982a5665a2c4bdb6b752d663f2)
- [NAPEval dataset revision `c7e28fe9`](https://huggingface.co/datasets/Tej-a55/napeval/tree/c7e28fe9b08ee2c0bfc429519cf100197b7e018c)
- [Paper: arXiv `2606.13802`](https://arxiv.org/abs/2606.13802)
