# FaceGAN Claim-by-Claim Reproduction Design

## Goal

Produce an executable, public reproduction of "No Distillation Needed:
Single-Pass Real-Time Talking Heads via Acausal Noise Shaping" (arXiv
2610.11070). The reproduction must distinguish exact tests from proxy tests,
record the paper and observed numbers side by side, and publish an illustrated
report and self-contained marimo notebook on `main`.

Formal runs execute on the SSH host alias `green` through OpenResearch. Every
experiment uses the same committed command; variants differ only through code
and constants committed to their experiment branches.

## Evidence Tiers

### Tier 1: Exact mechanism and systems tests

These claims do not require the authors' private dataset or trained weights and
can be tested directly:

1. A causal, time-invariant generator that uses fresh i.i.d. noise cannot have
   a perfect positive-measure spectral stopband while retaining non-zero
   one-step innovation.
2. For a normalized spectrum bounded by `epsilon` over fraction `delta`, the
   Kolmogorov-Szego bound is `innovation_variance <= epsilon**delta`; the
   paper's 40 dB, `delta=0.9` example gives approximately `2.5e-4`.
3. Acausal shaping of synthetic noise can make the downstream input
   predictable from its past without adding observed-audio lookahead.
4. A faithful FaceGAN-shaped transformer has one generator evaluation per
   emitted frame, bounded attention state, offline/streaming equivalence, and
   no sequence-length-dependent state growth.
5. Generator latency and throughput can be measured without trained weights
   because the implemented forward path has no data-dependent branching.

### Tier 2: Controlled proxy ablation

Train small causal and acausal generators on the same synthetic
audio-conditioned low-dimensional motion process. Keep parameter budget,
training data, optimizer, steps, receptive-field width, and seeds fixed. Measure
whether the acausal synthetic-noise path improves the diversity-versus-
smoothness frontier rather than merely smoothing all outputs.

This is a mechanistic proxy for Tables 4 and 5, not a reproduction of their
facial-motion numbers. Use at least three deterministic seeds when the compute
window permits. If the first seed shows a broken setup, repair the shared setup
before spending the remaining seeds.

### Tier 3: Paper-only evidence

The following claims require the unreleased 469.6-hour dataset, fixed 64-clip
test set, motion encoder and renderer, model weights, baseline outputs, or user
study stimuli:

- Table 2 FED, FPD, Similarity, Sync Score, expression variance, and pose
  variance;
- Figure 3 qualitative lip articulation;
- Table 3 perceptual preferences;
- the full-scale learned ablations in Tables 4 and 5.

Do not substitute another dataset and label the result exact. Record these
claims as unattempted at exact scale, explain the missing artifact, and connect
the Tier 2 proxy only to the mechanism it actually tests.

## Claim Ledger and Assessment Rules

Every report row contains the paper result, observed result, compute cost,
substitution or downscaling, and one assessment from:

- `aligned`: the observed effect agrees in direction and relevant magnitude
  under a directly comparable setup;
- `partially aligned`: the direction agrees but the setup or magnitude is not
  directly comparable;
- `inconclusive under this setup`: uncertainty or proxy limitations prevent a
  directional conclusion;
- `not attempted`: required artifacts or resources were unavailable.

Never describe a paper claim as wrong, failed, or not reproduced. A divergent
result is phrased as "this run did not show the reported effect," followed by
the measured difference and the relevant uncertainty.

## Experiment Tree

Create a new FaceGAN baseline lineage from the current `main` tip. Do not edit,
merge, rebase, or reuse the completed NAPE experiment branches.

1. **Causal spectral baseline:** causal current-noise control and analytic
   Kolmogorov-Szego checks.
2. **Acausal noise shaping:** child of the causal baseline; only the synthetic
   noise pathway changes.
3. **Matched-width learned proxy:** children under the better-supported shaping
   node for causal and acausal learned variants with identical budgets.
4. **Streaming architecture benchmark:** child of the validated acausal node;
   adds the faithful transformer and streaming benchmark without changing the
   established mechanism test.

Sibling nodes represent co-equal options within one decision. Later rounds
descend from the supported winner. Each node description records hypotheses,
run IDs, metrics, limitations, and conclusions; raw IDs do not appear in the
public README.

## Implementation

### Package structure

Keep the reproduction in a self-contained `facegan_reproduction/` directory
with its own `pyproject.toml`, lockfile, package, tests, evidence, and notebook.
The existing NAPE environment and source tree remain unchanged. Within the new
directory, add `src/facegan_repro/`:

- `config.py`: fixed experiment constants and the single variant selection;
- `spectral.py`: PSD, stopband, linear-innovation, and analytic-bound metrics;
- `processes.py`: deterministic causal and acausal stochastic processes;
- `proxy.py`: shared synthetic dataset, generator, training loop, and metrics;
- `model.py`: FaceGAN-shaped noise and conditioning stacks;
- `streaming.py`: explicit bounded state and streaming decode;
- `benchmark.py`: synchronized warmup/timing and hardware metadata;
- `figures.py`: deterministic evidence-bearing SVG/PNG plots;
- `evidence.py`: typed result schema and JSON serialization;
- `cli.py`: one command that runs the configured experiment and logs all
  evidence needed by `orx logs`.

Required CLI inputs are not configurable flags. The run contract is fixed and
all scientific choices live in committed constants.

### Numerical methods

Use PyTorch tensors with an explicit batch dimension throughout. Estimate
spectra from repeated long stationary sequences with a fixed windowing rule.
Estimate one-step linear innovation using a held-out least-squares autoregressor
whose order is fixed before comparing variants. Report confidence intervals
over independent sequences and training seeds.

The acausal analytic process may sample future synthetic noise before emission,
but it may not inspect future conditioning values. Tests must perturb future
audio and prove that the current output is unchanged while perturbing the
pre-sampled future noise may change it.

### Learned proxy

The synthetic target combines a causal audio-determined component with a
smooth stochastic component. Causal and acausal variants share training and
inference code; only the noise-attention mask differs. Evaluate held-out
conditioning with multiple latent draws. Primary metrics are stopband power,
one-step innovation, sample diversity, temporal variance, conditioning error,
and wall-clock cost.

### Streaming benchmark

Mirror the paper's dimensions where memory permits: two bidirectional noise
layers, six causal conditioning layers, width 512, eight heads, feed-forward
width 2048, and 137 output channels. The benchmark records the exact GPU,
PyTorch/CUDA versions, dtype, batch/concurrent-stream count, warmup, repetitions,
median and tail latency, and peak allocated memory.

Paper H200 fp32 figures are comparison references, not universal thresholds.
The report compares raw measurements only when hardware and precision match;
otherwise it reports normalized real-time capacity and clearly names the
hardware substitution.

## Run Contract

The fixed command is:

```bash
uv run --project facegan_reproduction facegan-repro && uv run --project facegan_reproduction pytest -q
```

It must print a compact final JSON summary containing every assessment metric,
timing, seed, variant, commit, and environment field needed for later analysis.
Formal training, evaluation, profiling, and artifact generation occur only via
`orx exp run --backend ssh --host green`.

## Tests

Use functional pytest tests with minimal mocking. Required checks include:

- the paper's numeric `epsilon**delta` example;
- PSD normalization and stopband integration on known signals;
- innovation estimation on white noise and deterministic band-limited signals;
- strict audio causality and intentional noise acausality;
- identical causal/acausal parameter counts and attended-width accounting;
- offline/streaming numerical equivalence;
- bounded cache size across short and long streams;
- evidence-schema completeness and deterministic serialization;
- report image references resolve to valid rendered files.

Run `uv run pre-commit run -a`, the full pytest suite, and marimo validation
before publication. Fix type errors rather than suppressing them.

## Report and Notebook

Write the dashboard report under the project's Files directory, with figures in
an adjacent `images/` directory. Put the strongest observed result immediately
below the title. Prefer four evidence-bearing figures when supported:

1. headline diversity-versus-stopband result;
2. analytic/numerical innovation bound;
3. learned proxy across seeds;
4. latency, scaling, or bounded-state diagnostic.

Copy the final self-contained report and its images to
`facegan_reproduction/report/` on `main`. Publish the tutorial-style notebook at
`facegan_reproduction/facegan_tutorial.py`, containing the already-produced
evidence so opening it does not rerun training. Optional interactive simulations
must be small and explicitly separate from formal evidence.

Because the repository is public, add and verify the Molab badge. The README's
top reproduction section names the central claim, paper and observed numbers,
substitutions, `green` compute, report/notebook links, and an experiment log with
the exact command copied from `orx exp status`. `main` is listed as "Not run as
an experiment (publication surface)" unless a formal run is actually launched
from it.

## Completion Criteria

The reproduction is complete when:

- every paper claim is represented in the claim ledger;
- all feasible Tier 1 claims have formal run evidence;
- the Tier 2 proxy has enough seeds for a defensible directional assessment or
  is explicitly inconclusive;
- terminal run logs have been analyzed and experiment descriptions updated;
- the report contains no broken images and clearly separates paper, observed,
  proxy, partial, and unattempted evidence;
- the notebook passes `marimo check`;
- tests and `uv run pre-commit run -a` pass;
- reader-facing artifacts are committed and pushed to public `main`.
