# Errors and Result Retention

EvoForge keeps two execution policies: direct runs stop on plugin exceptions;
the single-objective assisted workflow can continue after individual simulator
failures. There are no retries, checkpoint/resume, automatic recovery, or atomic
output transactions.

## Contextual Python Errors

Experiment boundaries expose these types from `evoforge.errors`:

| Type | Boundary |
| --- | --- |
| `ConfigurationError` | `load_config`, `build_problem`, `build_evaluator`, `lookup`, or plugin `configure`. |
| `PluginExecutionError` | `evaluate`, `optimize`, `fit`, or `predict`. |
| `OutputError` | `create_output_directory`, `write_results`, or `write_results:<filename>`. |

All derive from `EvoForgeError` (`RuntimeError`) and expose `stage`, `plugin_id`
(null for non-plugin stages), and `original_type`. The latter is the type of the
exception raised at that boundary; an adapter can already have its own nested
cause. Wrapping uses `raise ... from original`, preserving `__cause__` and its
Python traceback. The innermost contextual error is propagated unchanged: a
simulator's `evaluate` failure is not relabeled as an optimizer failure just
because it travels through `optimize`.

```python
from evoforge.errors import EvoForgeError

try:
    result = experiment.run()
except EvoForgeError as error:
    print(error.stage, error.plugin_id, error.original_type)
    original = error.__cause__
```

The registry itself retains its native API: direct `registry.get(...)` raises
`MissingPluginError` for a missing ID and `TypeError` for a structural mismatch.
Within `Experiment`, those become `ConfigurationError(stage="lookup")`, chained
to the registry exception. Calls to adapter methods outside `Experiment` retain
their native adapter/library exceptions. Plugin protocols are unchanged.

Interpreter controls (`KeyboardInterrupt`, `SystemExit`) are not caught as
plugin errors. Internal budget termination signals also remain control flow,
not plugin failures. NSGA-II's strict evaluator limit and the surrogate search
limit continue to preserve their budget-limited observations normally.

## What Is Retained

| Failure | Runtime result and retained outputs |
| --- | --- |
| YAML loading/validation, problem construction, lookup, initial optimizer/simulator configuration | Contextual exception; no new experiment result or experiment outputs. Existing files from an older run are not deleted. |
| Direct simulator evaluation or optimizer execution, including NSGA-II evaluation errors | Run becomes failed and raises. No `ExperimentResult` or runtime-generated partial evaluation artifacts are promised, even if the plugin already performed some evaluations. Plugin-local buffers are not runtime persistence. |
| Surrogate configuration inside the assisted workflow | Failed result with error metadata; usually no real observations yet. Config, metadata, and an empty predictions artifact can be saved if output writing succeeds. |
| One assisted simulator exception or invalid record | Counts as a real attempt and becomes a failed real record with error context. The workflow can continue; it trains/selects the best only from successful real records. Insufficient successful initial data still stops the workflow. |
| Assisted fit, search optimizer, prediction, or later optimizer configuration failure | Failed result keeps prior real records, successful predictions already collected, and the best successful real record if one exists. The offending prediction is not added as successful. Persistence still depends on successful output writing. |
| Any output creation, serialization, or write failure | `OutputError`; run becomes failed and returns no `ExperimentResult`. Earlier files may exist, be incomplete, or coexist with stale files from a previous run. They are not guaranteed usable or consistent; no rollback occurs. |
| `KeyboardInterrupt` or `SystemExit` | Propagates without plugin-error conversion or guaranteed final output/state update. An interrupted experiment may remain marked running in memory. |

The assisted workflow's failed simulator exception records use objective zero
only as a placeholder with status `failed`; it is never an observation eligible
for training, a real best, or a non-dominated set. A simulator-returned failed
record remains failed. Invalid types, wrong solution/objective association,
nonfinite/non-real values, and predictions masquerading as real records are
rejected at runtime evaluator boundaries. The direct runtime also validates
recognized optimizer-returned evaluation records.

Assisted error metadata preserves the existing `error` text and adds
`error_details` with category, stage, plugin ID, original type, and message.
Individual failed records carry the same details. The assisted
`result.raw_result.errors` list retains contextual exception objects and their
causes **in memory**. JSON artifacts contain serializable details, not live
exception chains or resumable state. Generic workflow diagnostics can still
use their existing termination reasons (for example insufficient data).

Files are written sequentially only after the execution path returns to output
persistence. A failed manifest write can therefore leave config, metadata, or
evaluation files already written, but that is not a checkpoint contract.
Best-effort [provenance collection](reproducibility.md) remains separate: absent
metadata is null rather than a reason to fail an otherwise valid computation.

## CLI Behavior

`evoforge run` exits nonzero for contextual configuration, plugin, and output
errors, and for failed assisted results. Messages include the stage, plugin ID
when relevant, original exception type, and underlying message. Default CLI
messages are concise rather than full Python tracebacks.

Only a `FileNotFoundError` during `load_config` is described as a missing
configuration file. A missing weather/input file during `evaluate` identifies
the simulator; a missing output location identifies the output stage. YAML
syntax and model validation retain their helpful configuration messages.

## Observable Changes

- `Experiment.from_config(...)` now wraps load/validation errors as
  `ConfigurationError`; the YAML loader itself is unchanged.
- `Experiment.run()` wraps lookup/configure/execution/write errors as described
  above. Catch these contextual types instead of assuming a raw library error
  will escape; the original remains in `__cause__`.
- Direct optimizers receive an evaluator wrapper exposing `evaluate(solution)`;
  they must not depend on the registered simulator object's identity, concrete
  class, arbitrary attributes, or reconfiguration methods.
- Recognized real evaluation records receive runtime semantic validation;
  previously tolerated invalid or predicted records can now fail explicitly.
- Assisted failed results add structured error details and in-memory error
  objects. Their continue/stop policy and successful result fields are retained.
- CLI missing-file classification is stage-specific and errors exit nonzero.

See [plugin compatibility](plugin_compatibility.md) for the 0.x change policy.
