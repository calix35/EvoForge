# Plugin Contracts and Compatibility

The current protocols use standard-library typing. They specify structure and
method signatures for authors and type checkers; they do not negotiate interface
versions or provide a runtime semantic compatibility guarantee.

## Current Contracts

Every plugin has a stable nonempty `plugin_id: str` and
`configure(config: object) -> None`. Runtime configuration currently passes
`OptimizerConfig`, `SimulatorConfig`, or `SurrogateConfig` to the corresponding
active roles. Plugin-specific parameter validation remains the plugin's job.
No registry discovery or automatic dependency installation is performed.

| Protocol | Method | Current runtime semantics and limits |
| --- | --- | --- |
| `OptimizerPlugin` | `optimize(problem: Problem, evaluator: object) -> Any` | Uses the supplied `evaluate(Solution)` interface. Direct results recognized as real records are `EvaluationRecord`, `Dataset`, lists/tuples of records, and `OptimizationResult`. Other `Any` values remain `raw_result` but do not automatically become evaluation artifacts. |
| `SimulatorPlugin` | `evaluate(solution: Solution) -> EvaluationRecord` | Real evaluation with matching variable assignments and objective names, finite real values, and an honest status. Scope and constraint enforcement are adapter-specific, not supplied by the protocol. |
| `SurrogatePlugin` | `fit(dataset: Dataset) -> None`; `predict(solution: Solution) -> EvaluationRecord` | Assisted runtime fits successful real observations only. Predictions must match the requested solution/objective and be finite/successful. Assisted orchestration remains single-objective, bounded continuous, unconstrained. Model `save`/`load` methods are optional adapter APIs, not protocol requirements. |
| `AnalysisPlugin` | `analyze(dataset: Dataset) -> Any` | Contract only; current experiment runtime does not execute statistical analysis. |
| `VisualizationPlugin` | `visualize(dataset: Dataset) -> Any` | Contract only; current experiment runtime does not execute visualization. |
| `ReportPlugin` | `generate(dataset: Dataset, artifacts: dict[str, Any]) -> Any` | Contract only; current experiment runtime does not execute report generation. |

`OptimizationResult` is a library-independent observation container; it can carry
metadata and non-dominated records. Its presence does not make arbitrary plugin
results Pareto-optimal or validated. The NSGA-II adapter computes its observed
front using pymoo and successful real observations. A protocol's generic `Any`
return is not permission to relabel predictions as real results.

The evaluator passed to an optimizer may be a runtime wrapper or a prediction
evaluator. Depend on `evaluate(solution)`, not object identity, a particular
simulator class, private attributes, or the ability to reconfigure it. Direct and
assisted execution have distinct [failure policies](errors.md).

## Structural Checks Are Limited

`@runtime_checkable` lets the registry use `isinstance(plugin, contract)` to
check required members. It does **not** fully verify argument signatures,
annotations, return values, finite data, thread safety, objective direction,
units, supported variables, or scientific semantics. A class with an
`optimize(self)` method can pass the structural check yet fail when called as
`optimize(problem, evaluator)`. Tests explicitly demonstrate this distinction.

Registration validates IDs and rejects duplicates. Typed lookup rejects missing
members, but untyped lookup does not select/check a role. It is possible to
implement multiple protocols intentionally. Plugin authors should use static
type checking, contract tests with doubles, and real dependency integration tests
for the exact scope they claim. Registry acceptance alone is not certification.

The current GA, NSGA-II, random forest, AquaCrop, and benchmark adapters have
different [documented scopes](plugins.md). There is no generic constraint-solving
or unit-conversion layer in the protocol. Pin and test each concrete adapter's
supported behavior; do not infer new capabilities from a shared method name.

## Policy During 0.x

EvoForge's interfaces are still evolving. This policy does not promise indefinite
backward compatibility:

- Patch releases aim to avoid intentional breaking changes to documented plugin
  calls and configuration/output semantics. Correctness fixes may tighten
  validation and reject previously accepted invalid inputs; these changes must
  be documented, including affected inputs and migration guidance.
- Minor 0.x releases may change protocols, supported return shapes, configuration
  fields, error surfaces, or artifact formats incompatibly. Such changes should
  be identified in release/change documentation with affected plugin roles and
  configuration examples. Authors must retest before expanding supported ranges.
- Deprecation notices or transition paths should be provided when practical,
  but 0.x has no guaranteed deprecation duration or permanent legacy mode.
- `plugin_id` is a stable semantic identifier, not a transient class name or
  version-negotiation token. Do not silently reuse an existing ID for a different
  algorithm/model. A materially different implementation should use another ID;
  interface/configuration changes under an existing concept require an explicit
  compatibility/migration note rather than a silent semantic replacement.
- Old YAML is not automatically migrated. Removed IDs, changed required fields,
  or unsupported parameters may fail lookup or configuration validation. Any
  aliases or migrations must be explicit, documented, and tested.

Third-party distributions should declare the EvoForge version ranges they have
actually tested and the needed external-library dependencies. Releasing a new
plugin package does not by itself establish compatibility with every EvoForge
0.x release. There is no protocol version field, handshake, automatic fallback,
or runtime version-negotiation system in this implementation.

## Preserving an Earlier Experiment

Keep the exact EvoForge and plugin source/distributions, dependency lockfile,
`pyproject.toml`, effective config, external inputs, and generated provenance.
For dirty or untracked plugin code, retain the code itself; a revision and dirty
flag cannot reconstruct local edits. Preserve climate data matching its recorded
SHA-256 and the conditions under which it may be reused.

Recreate the older project in a separate environment using
`uv sync --locked --python 3.12` with its required extras. Do not substitute the
latest interfaces into an old experiment and assume the old config has identical
meaning. When migrating, retain the original config/results, adapt a separate
copy, and rerun contract/integration tests against the new interfaces. This is a
manual migration and verification process, not recovery or resume support.

See [reproducibility](reproducibility.md) for platform/Python/library limits.
Even matching seeds and lockfiles do not promise numerical identity across
different environments or changed interfaces.
