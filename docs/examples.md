# Examples

## Optional NSGA-II and ZDT1

```bash
uv sync --python 3.12 --extra pymoo
uv run --python 3.12 --extra pymoo evoforge run examples/zdt1_nsga2.yaml
```

This smoke example uses 30 variables, two minimizing objectives, and a strict
45-call evaluator budget with population 20. Both the full real history and the
observed non-dominated set are saved under `results/zdt1_nsga2/`. See the
[multiobjective guide](multiobjective.md) for budget and result semantics.

## Built-In Random Search

Run:

```bash
uv run evoforge run examples/sphere_random_search.yaml
```

This example uses:

- Optimizer plugin: `example.random_search`
- Simulator plugin: `example.sphere`
- Output directory: `results/sphere_random_search`

---

## Optional pymoo GA

Install the optional dependency:

```bash
uv sync --extra pymoo
```

Run:

```bash
uv run --extra pymoo evoforge run examples/sphere_pymoo_ga.yaml
```

This example uses:

- Optimizer plugin: `pymoo.ga`
- Simulator plugin: `example.sphere`
- Output directory: `results/sphere_pymoo_ga`

The `pymoo` dependency is loaded only by the optional adapter package.

## Surrogate-Assisted Sphere

```bash
uv sync --extra pymoo --extra sklearn
uv run --extra pymoo --extra sklearn evoforge run examples/sphere_surrogate.yaml
```

The example uses `pymoo.ga`, `sklearn.random_forest`, and `example.sphere`.
Six initial real calls are followed by updates of at most three candidates,
up to a strict total of thirteen simulator calls. Each surrogate search allows
twenty-five prediction calls. Artifacts are written to `results/sphere_surrogate/`,
including separate `predictions.json`. This is a workflow example, not a claim
that surrogate assistance improves this inexpensive benchmark.

See [configuration](configuration.md#surrogate-assisted-workflow) for termination
and failure semantics.

## AquaCrop Irrigation

The optional [AquaCrop adapter](aquacrop.md) provides two executable examples:

```bash
uv sync --python 3.12 --extra pymoo --extra sklearn --extra aquacrop
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop evoforge run examples/aquacrop_irrigation_ga.yaml
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop evoforge run examples/aquacrop_irrigation_surrogate.yaml
```

Both maximize simulated dry maize yield for a single 2018 season with ClayLoam,
70% TAW initial moisture, and a 300 mm seasonal irrigation cap. They use the
climate file shipped with AquaCrop and different output directories. The guide
describes the small demonstration budgets, data provenance, and limitations.
