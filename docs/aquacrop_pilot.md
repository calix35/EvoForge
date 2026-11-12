# AquaCrop Comparison Pilot

`scripts/compare_aquacrop.py` compares direct `pymoo.ga` against the existing
surrogate-assisted workflow with `sklearn.random_forest`, using the same
`aquacrop.irrigation` simulator. The small YAML examples are unchanged.
This is an execution and measurement pilot, not evidence of a speed improvement
or of surrogate accuracy.

## Environment and Smoke Test

Use Python 3.12 and the lockfile:

```bash
uv sync --python 3.12 --extra pymoo --extra sklearn --extra aquacrop
```

Start with a single paired seed and a reduced budget:

```bash
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop python scripts/compare_aquacrop.py \
  --seeds 0 --real-budget 4 --pop-size 2 --initial-size 2 \
  --candidates-per-update 1 --search-budget 4 --n-estimators 4 \
  --output results/aquacrop_pilot_smoke
```

This runs exactly one pair, targeting four real simulator calls per method.
The script refuses to overwrite an existing output directory. For a repeat,
choose another `--output` path. Failures or early termination may reduce the
effective calls; the script records these and exits nonzero if any run does not
complete its budget successfully.

## Default Pilot

With no budget arguments, the script prepares these settings:

| Setting | Default |
| --- | --- |
| Seeds | 0 through 9, in that order |
| Real budget per method and seed | 60 calls, including failed attempts |
| GA population, both methods | 20 |
| Surrogate initial real design | 20 |
| Candidates per surrogate update | 4 |
| Predictions per surrogate search | 200 |
| Random forest trees | 100 |

All settings are configurable with `--seeds`, `--real-budget`, `--pop-size`,
`--initial-size`, `--candidates-per-update`, `--search-budget`, and
`--n-estimators`. Use `--help` to inspect the interface.

The full command below schedules **twenty method executions**. It is provided
for a later full pilot; the initial validation uses only the smoke test above.

```bash
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop python scripts/compare_aquacrop.py \
  --output results/aquacrop_pilot_full
```

The scenario is derived from `aquacrop_irrigation_ga.yaml`: Maize, ClayLoam,
May 1 through October 31, 2018, planting May 1, 70% TAW initial moisture,
and `MaxIrrSeason=300` mm. Four continuous SMT variables have [0, 100] bounds.
`dry_yield` is maximized in tonnes/ha; seasonal irrigation is recorded in mm.
Climate comes from the installed `champion_climate.txt`, with no runtime download.
See the [adapter guide](aquacrop.md) for units, data format, and license notices.

Each method receives the paired experiment/optimizer seed; the random forest's
`random_state` is also set explicitly. The assisted runtime records derived search
seeds in its iteration metadata. The two methods do not use identical initial
candidates: their existing initialization algorithms remain unchanged.

## Call Accounting and Order

The direct pymoo adapter terminates by evaluations checked between population
batches, not at an arbitrary individual-call boundary. The pilot therefore
rejects `real_budget` values that are smaller than the population or not a
multiple of it. Both the default 60/20 and smoke-test 4/2 settings are compatible.
A simulator wrapper also counts attempts **before** invocation and blocks any
call after the budget. If an optimizer unexpectedly requests an additional call,
the direct run is stopped with `real_budget_guard`, preserving its real records.
The simulator itself is never invoked beyond the limit. The generic adapter's
behavior outside this script is unchanged.

Effective wrapper calls are compared with runtime record counts. Results carry
`budget_complete`, status, and termination reason: an early duplicate stop or an
optimizer returning too few records is not presented as a full-budget result.
The surrogate runtime continues to enforce its own real and prediction budgets.
Each update is clipped to remaining real budget; no final fit is required after
the real budget is consumed.

Simulator exceptions consume budget and are saved as failed observations.
Direct execution stops on a simulator exception. The existing assisted runtime
can continue after failed real calls, trains only on successful real records,
and fails if its initial data are insufficient. Thus paired runs with failures
require separate inspection rather than an assumption of equal completed work.
No failed observation or prediction is eligible as the reported real best.

Methods run sequentially. For the first listed seed the order is direct then
surrogate; for the next listed seed it is surrogate then direct, alternating by
position in the supplied seed list. The actual global order is saved. Every
execution constructs fresh plugin instances. No artificial simulator delays
are introduced.

## Timing Policy

The script imports the optional library entry points once before the pair loop
and saves `startup_import_seconds`. Per-execution `elapsed_seconds` is measured
with a monotonic wall clock around plugin construction and `Experiment.run()`.
It includes configuration, simulator preparation and execution, surrogate
training, prediction search, candidate selection, and runtime output writing.
There is no untimed simulation or model-fit warm-up. Remaining first-use lazy
imports and cache effects can still occur inside timed runs; alternating order
reduces a systematic first-method bias but does not eliminate those effects.

Config derivation, Git/version collection, source snapshots, and final
pilot-specific persistence (trajectory, provenance, and summaries) are outside
the per-execution timer. The timing policy is saved in every run's metadata.
These are wall times for the complete execution, not just simulator times;
training and search are never subtracted.

## Artifacts

The output root contains:

- `pilot.json`: settings, versions, timing policy, climate hash, Git revision,
  dirty state, full porcelain status, tracked implementation diff, and run order.
- `source_snapshot/`: actual local Python source, scripts, example configs,
  `pyproject.toml`, and `uv.lock`, including untracked adapter implementations.
  SHA-256 values are recorded in metadata. Climate data and manuscripts are not
  copied. The snapshot identifies this dirty checkout rather than implying that
  the recorded Git revision alone reproduces it.
- `summary.csv` and `summary.json`: updated after each completed method execution.

Each `seed_NNNN/direct/` or `seed_NNNN/surrogate/` directory contains:

- `config.json`: effective validated experiment configuration.
- `metadata.json`: runtime diagnostics plus a `pilot` section with seed, order,
  versions, Git state, source hashes, start time, timing policy, effective calls,
  blocked extra calls, budget status, errors, and climate provenance.
- `evaluation_records.json`: actual real evaluations, including failures;
  omitted only if no real calls were made.
- `predictions.json`: separate, unvalidated predictions; empty for direct GA.
- `failures.json`: failed real evaluation records, possibly empty.
- `trajectory.json` and `trajectory.csv`: best successful real yield and its
  irrigation after each real call, including failed calls. Before the first
  success the best is null (empty in CSV). The CSV is omitted if no calls occurred.
- `run_summary.json` and `manifest.json`: summary and generated artifact list.

Summary rows include method, seed, execution order, status, termination reason,
best real `dry_yield` in t/ha, irrigation of that same solution in mm, effective
real calls, failed calls, prediction calls, elapsed seconds, error, budget
completion, and output path. Ties retain the first successful real best.
The corresponding solution is recoverable from the real evaluation records.
Climate hashes from successful observations are checked against the pilot's
initial hash; a mismatch marks a run failed.

Filter by status and budget completion before making paired comparisons. Tiny
budgets and a single smoke-test seed do not support performance conclusions.
Keep the lockfile, source snapshot, and original climate file matching the
recorded hash when reproducing a run. Results remain under ignored `results/`.

## Script Tests

```bash
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop pytest tests/scripts
```

These tests use cheap fake plugins with small budgets. They cover configuration,
alternating order, reproducible numeric traces, exact call accounting, unexpected
overshoot, incomplete runs, failure preservation, best-real trajectories, source
snapshots, and inclusion of training/search in elapsed time. They do not execute
the full twenty-run pilot.
