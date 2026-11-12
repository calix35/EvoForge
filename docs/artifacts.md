# JSON Artifacts and Evaluation Records

This describes the v0.2.0 output format. It is a field-level description, not a
separate JSON Schema validator or a guarantee that arbitrary plugin metadata
has a fixed structure. Output changes follow the [0.x policy](plugin_compatibility.md).

| File | Top-level JSON type | Contents |
| --- | --- | --- |
| `config.json` | Object | Validated configuration with section defaults. This may include reserved schema fields; see [runtime support](configuration.md#schema-validation-versus-runtime-support). |
| `metadata.json` | Object | Experiment/plugin identifiers, seed and available provenance; workflow-specific diagnostics such as assisted termination reason and counters. |
| `evaluation_records.json` | Array of record objects | Returned real observations, including failed assisted attempts. Omitted when the real record tuple is empty. |
| `predictions.json` | Array of record objects | Assisted predictions, possibly empty; absent in ordinary direct runtime output. |
| `non_dominated.json` | Array of record objects | Original successful observations selected by the NSGA-II adapter, possibly empty; absent when that result is not supplied. |
| `manifest.json` | Object | `output_directory` string and `artifacts` array, whose entries contain string `name`, relative `path`, and `kind`. |

Each record contains:

| Field | Type and meaning |
| --- | --- |
| `solution` | Object with `problem` (name or null), `values` (variable-name/value mapping), and `metadata` (object). The full problem declaration is in the config. |
| `objective_values` | Objective-name/number mapping. Original objective direction/units are not encoded by negating these stored values. |
| `constraint_values` | Constraint-name/number mapping, possibly empty. |
| `source` | Plugin/source string or null. |
| `status` | `success`, `failed`, or `pending`. |
| `created_at` | ISO-format timestamp; built-in records use UTC by default. |
| `metadata` | Object with plugin/workflow-specific fields, such as evaluation kind, timing, iteration or serializable error details. |

Constraint definitions in config/domain objects and numeric `constraint_values`
are storage mechanisms. There is no generic feasibility convention, expression
interpreter, penalty method, or automatic constraint enforcement in the core.
The supported NSGA-II, AquaCrop and assisted paths reject optimization constraints.
Do not infer constrained optimization support from an available record field.
Constraint semantics and units must be defined by a supported adapter; a nonempty
constraint mapping alone is not a feasibility certificate.

Consumers must inspect status and provenance before analysis. A failed assisted
exception can carry a zero objective placeholder: it is excluded from training
and best-real selection. A successful prediction means model inference succeeded,
not that the simulator validated it. The manifest labels prediction artifacts
`unvalidated_predictions`, but it is a file inventory rather than a per-evaluation
failure log, checkpoint, checksum catalog, or atomic-completion certificate.

Direct exceptions do not guarantee persisted partial history. Assisted failures
can retain earlier observations and error details if output writing succeeds.
There is no generic simulator timeout or resume mechanism. Output-write errors
may leave inconsistent or stale files. See [errors and retention](errors.md) for
the exact policies. Do not infer resumability from a manifest or directory alone.
