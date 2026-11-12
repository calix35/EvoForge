# Configuration

EvoForge experiments are defined with YAML configuration files.

The main sections are:

- `experiment`: experiment metadata and optional seed.
- `problem`: variables, objectives, and constraints.
- `optimizer`: optimizer plugin and parameters.
- `evaluator`: evaluation source.
- `surrogate`: optional surrogate model configuration.
- `outputs`: output directory and artifact settings.

## Schema Validation Versus Runtime Support

The v0.2.0 configuration model recognizes `simulator`, `function`, `surrogate`,
and `hybrid` evaluator labels, but the current experiment runtime builds only
the `simulator` evaluator. The other labels are schema-level placeholders:
passing schema validation does not make them executable. The runtime rejects
them during evaluator construction, before optimization/evaluation begins,
with a contextual `ConfigurationError` chained to `NotImplementedError`.
Optimizer configuration can already have occurred at that point.

For the implemented assisted workflow, keep `evaluator.type: simulator` and
enable `surrogate.workflow`; do not select the standalone `surrogate` or
`hybrid` evaluator labels. Assisted configurations additionally reject
non-simulator evaluator types during model validation. Plugin-specific
parameters are validated by the selected adapter, not the generic schema.
Analysis, visualization and report configuration sections are contracts only;
enabling them does not invoke an operational runtime plugin. The runtime does
not currently honor every reserved output/dataset setting: JSON artifact
generation follows the implemented `OutputManager` behavior, rather than
providing generic CSV/Parquet persistence or figure output.

For `evaluator.simulator.plugin: aquacrop.irrigation`, scenario parameters are
validated inside the optional adapter. See [AquaCrop inputs and units](aquacrop.md#inputs-and-units).

---

## Minimal Example

```yaml
experiment:
  name: sphere_random_search
  description: Minimal random search run against the built-in sphere benchmark.
  seed: 42

problem:
  name: sphere_benchmark
  type: single_objective
  variables:
    - name: x1
      type: continuous
      bounds: [-5.0, 5.0]
    - name: x2
      type: continuous
      bounds: [-5.0, 5.0]
  objectives:
    - name: sphere
      direction: minimize
  constraints: []

optimizer:
  plugin: example.random_search
  parameters:
    iterations: 5
    seed: 42

evaluator:
  type: simulator
  simulator:
    plugin: example.sphere

outputs:
  directory: results/sphere_random_search
```

Run it with:

```bash
uv run evoforge run examples/sphere_random_search.yaml
```

---

## Output Artifacts

Each experiment writes structured artifacts to the configured output directory:

- `config.json`: validated configuration.
- `metadata.json`: run metadata.
- `evaluation_records.json`: evaluated solutions and objective values.
- `manifest.json`: list of generated artifacts.

## Surrogate-Assisted Workflow

Set `surrogate.enabled: true` to opt into the sequential workflow. Omit it or
set it to `false` to retain direct optimization against the simulator.
The initial scope is exactly one objective (minimize or maximize), no constraints,
and continuous variables with finite bounds and a strictly positive interval.
Unsupported problems and incompatible budgets fail configuration validation
before any simulator call.

```yaml
surrogate:
  enabled: true
  plugin: sklearn.random_forest
  parameters:
    n_estimators: 24
  workflow:
    initial_size: 6
    real_budget: 13
    search_budget: 25
    candidates_per_update: 3
```

- `initial_size`: number of unique uniform random initial simulator evaluations,
  at least two. This is included in `real_budget`.
- `real_budget`: maximum simulator calls, including exceptions and failed records.
  It must leave room for at least one complete configured update batch.
- `search_budget`: maximum prediction calls per optimizer invocation. The runtime
  enforces this cap even if the optimizer evaluates in population-sized batches.
- `candidates_per_update`: maximum novel candidates validated per iteration;
  it cannot exceed `search_budget` or the initial remaining real budget.
  The final batch is clipped to the remaining budget.

The random forest is fitted only to successful, finite real observations.
The optimizer searches through a prediction evaluator. The runtime ranks all
successful predictions by objective direction and validates the best unique,
previously untested candidates. Failed real candidates are not retried. After
each batch it refits only if real budget remains for another search. Once the
real budget is exhausted, it preserves real results without another fit. Predicted values never
enter the training dataset or the final best-real selection.

Candidate equality uses exact numeric tuples in declared variable order.
An optimizer search containing only duplicates stops with `no_novel_candidates`;
there is no random fallback or unlimited retry loop. Initial sampling permits
at most `100 * initial_size` draws and stops with `initial_design_duplicates`
if it cannot fill the design, marking the run as failed. Normal completion
records `real_budget_exhausted`.
Early termination can therefore leave some real budget unused.

Simulator exceptions, invalid records, and nonfinite objectives become failed
real records and consume budget. Exception records use a placeholder objective
of zero with status `failed`; that value must never be treated as an observation.
Fewer than two successful initial observations stop the run as `failed` with
`insufficient_successful_evaluations`. Surrogate fitting, prediction, or optimizer
exceptions stop as `failed` with `plugin_failure`. Partial real observations,
predictions, and error metadata are saved if output writing succeeds; the CLI
exits nonzero for failed runs. See [errors and result retention](errors.md) for
configuration failures, original exception causes, and non-atomic output limits.
An exhausted duplicate search can complete successfully if a real best exists.

`ExperimentResult.records` and `evaluation_records.json` contain real calls only,
including failures. `ExperimentResult.predictions` and the separate
`predictions.json` contain unvalidated predictions. A prediction record's
`success` status means prediction succeeded, not simulator validation.
Every record includes `evaluation_kind`, iteration, seed, call index, elapsed
seconds, source, and timestamp. `ExperimentResult.best_record` is a successful
real observation or `None`. The metadata also saves its solution and objective.

`metadata.json` records termination reason, simulator/prediction call counts,
successful/failed real counts, fit count, duplicate count, effective seed,
model parameters, per-search seeds, training sizes, selection counts, and timings.
The manifest labels predictions as `unvalidated_predictions`.

`experiment.seed` controls the initial design and derived optimizer seeds.
The runtime overrides optimizer `seed`, `iterations`, and `n_evaluations` for
each surrogate search; these search budgets do not control real simulator calls.
Random forest `random_state` defaults to the effective experiment seed, but an
explicit model setting is preserved. An omitted experiment seed is generated
and recorded. Reproducibility concerns numeric traces in the same dependency
environment; timestamps and timings vary. Stochastic simulators must manage
their own randomness through their plugin configuration.
