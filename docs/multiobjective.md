# Multiobjective Optimization

The optional `pymoo.nsga2` optimizer uses pymoo's `NSGA2`, `ElementwiseProblem`,
and `minimize` APIs. It supports at least two objectives with any mixture of
minimization and maximization. Variables must be continuous with finite,
strictly increasing bounds. Constraints, integer/discrete/categorical variables,
and surrogate-assisted multiobjective optimization are outside the current scope.

## Installation and Smoke Example

```bash
uv sync --python 3.12 --extra pymoo
uv run --python 3.12 --extra pymoo evoforge run examples/zdt1_nsga2.yaml
```

The example has 30 continuous variables in [0, 1], two minimizing objectives
`f1` and `f2`, population 20, evaluator budget 45, and explicit experiment and
optimizer seed 42. It writes to `results/zdt1_nsga2/`. Its small budget deliberately
cuts a population batch; it is a smoke example, not a convergence benchmark.

`example.zdt1` is a `SimulatorPlugin` registered with the pymoo adapter. It calls
`pymoo.problems.get_problem("zdt1", n_var=30).evaluate(...)`; EvoForge does not
reimplement the ZDT1 equations. `n_var` can be configured to an integer >= 2.
The evaluator requires exactly `f1`/`f2` as minimizing objectives and [0, 1]
continuous inputs, in the problem's declared variable order. It is a deterministic
analytic benchmark, not a physical simulator or a learned prediction.

Programmatic registration uses the existing helper:

```python
from evoforge.adapters.pymoo import register_pymoo_plugins
from evoforge.core import Experiment

registry = register_pymoo_plugins()
result = Experiment.from_config("examples/zdt1_nsga2.yaml", registry=registry).run()
front = result.non_dominated_records
```

The helper registers `pymoo.ga`, `pymoo.nsga2`, and `example.zdt1`, without loading
pymoo or NumPy. The CLI uses this same registration. Scientific imports remain
inside the optional pymoo adapter package; missing dependencies produce an
installation hint when evaluation/optimization is requested.

## Parameters and Strict Budget

| Optimizer parameter | Default | Validation |
| --- | --- | --- |
| `pop_size` | 20 | Integer >= 2. |
| `n_evaluations` | 100 | Integer >= 1; strict evaluator-call limit. |
| `seed` | null | Integer in [0, 2^32), or null to generate and record one. |
| `verbose` | false | Boolean. |

Unknown parameters and implicit string/float conversions to integer parameters
are rejected. Set the optimizer seed explicitly for reproducible numeric traces;
`experiment.seed` is metadata and does not implicitly replace optimizer settings.
Generated seeds are recorded as `optimizer_seed`. Timestamps and wall times are
not reproducible, and numeric reproducibility across library versions/platforms
is not guaranteed.

`n_evaluations` is checked **before every evaluator call**, independently of
pymoo's between-batch termination check. It need not be a multiple of the
population size and may be smaller than a population. When another call would
exceed the budget, an adapter-internal stop exception interrupts the batch.
All already obtained records, including those from the partial batch, are kept.
The incomplete batch is not required to complete pymoo's population survival
step; the returned observed front is computed from the saved evaluations rather
than pymoo's final population or `res.F`.

This cap counts calls, not generations or unique candidates. Repeated candidates
consume calls when evaluated. No padding, extra evaluations, or random fallback
are performed to complete a generation. If pymoo terminates early for another
reason, metadata reports actual calls and `budget_reached: false`.
The existing `pymoo.ga` budget semantics are unchanged.

## Objectives and Observed Front

The adapter builds pymoo's minimization vector in declared objective order,
negating only maximizing objectives. Original objective values in
`EvaluationRecord` remain unchanged. Result names must match the problem exactly;
values must be finite real numbers, excluding booleans. A record for another
solution, a constraint result, or a record marked as a surrogate prediction is
rejected. Invalid results and evaluator exceptions propagate as execution errors;
they are not converted into successful evaluations.

Within `Experiment`, these errors carry [runtime context](errors.md) and retain
their original cause. Unlike a normal budget stop, a direct NSGA-II exception
does not promise partial runtime output or an `ExperimentResult`.

Returned finite records explicitly marked `failed` or `pending` remain in the
evaluation history and consume calls. They receive an internal infinite penalty
for optimization and are excluded from the observed front. Infinite penalties
are internal only and do not replace original stored values.

The observed non-dominated set uses pymoo's `NonDominatedSorting` over all
successful real observations, with the same direction conversion. It includes
partial-batch evaluations and may include observations discarded by population
survival. Failed, pending, and known prediction records are excluded. Equal
non-dominated objective vectors retain their associated observations in original
evaluation order. There is no independent sorting of solutions and values.
This is an **observed** set, not a claim to recover the true Pareto front.

## Generated Files

- `config.json`: validated effective configuration.
- `metadata.json`: experiment seed plus optimizer seed, requested population and
  evaluator budget, effective `evaluator_calls`, successful/failed record counts,
  observed front size, `budget_reached`, `budget_guard_triggered`, and termination
  reason (`evaluation_budget_reached` or `optimizer_terminated`).
- `evaluation_records.json`: all returned real records with original objectives,
  linked variable assignments, source, status, call index, seed, and elapsed time.
- `non_dominated.json`: full records selected from that history, preserving the
  same solutions, objective values, source, status, timestamps, and call indices.
  It is an empty list when no successful real records are available.
- `manifest.json`: artifact list, labeling the front as
  `observed_non_dominated_records`.

`ExperimentResult.records` exposes the real history and
`ExperimentResult.non_dominated_records` exposes the observed front. There is no
single preferred `best_record` for multiobjective optimization. The optimizer
returns a library-independent `OptimizationResult`; the core handles its records
and metadata without importing pymoo or performing non-dominated sorting itself.

All output remains under ignored `results/`. Existing single-objective and
surrogate runs retain their files and public behavior; the surrogate workflow
continues to reject multiobjective configurations.

## Verification

```bash
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop pytest
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop ruff check .
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop mkdocs build --strict
```

Tests cover real NSGA-II execution and CLI output, exact divisible/non-divisible
budgets, mixed directions, original-record association, failed/predicted record
exclusion, invalid parameters/results, and numeric reproducibility. Existing GA,
surrogate, AquaCrop, and pilot-script regressions run in the same suite.

The implementation follows pymoo's public
[NSGA-II](https://pymoo.org/algorithms/moo/nsga2.html) and
[ZDT benchmark](https://pymoo.org/problems/multi/zdt.html) APIs.
