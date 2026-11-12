# EvoForge

**EvoForge** is an extensible framework for Simulation-Based Optimization using Evolutionary Computation and Surrogate Models.

EvoForge provides a configuration-driven experiment runtime, domain model, plugin registry, command-line interface, local output artifacts, and optional adapters for external optimization and machine-learning libraries.

---

## Features

EvoForge currently supports:

- YAML-based experiment configuration.
- Typed configuration validation.
- Lightweight domain objects.
- Plugin contracts and explicit plugin registry.
- Experiment runtime.
- Local output artifacts.
- Typer-based CLI.
- Built-in example plugins for a random search optimizer and sphere benchmark simulator.
- Optional `pymoo` GA optimizer adapter.
- Optional `pymoo.nsga2` multiobjective adapter with strict evaluator budgets.
- Optional `scikit-learn` random forest surrogate adapter.
- Optional sequential surrogate-assisted optimization with strict simulator budgets.
- Optional AquaCrop-OSPy 3.1.0 irrigation simulator adapter.

---

## Quick Start

Install the development environment with `uv`:

```bash
uv sync
```

Run the test suite:

```bash
uv run pytest
```

Run lint checks:

```bash
uv run ruff check .
```

Run the built-in example:

```bash
uv run evoforge run examples/sphere_random_search.yaml
```

The example writes output artifacts to:

```text
results/sphere_random_search/
```

Run the optional `pymoo` GA example:

```bash
uv sync --extra pymoo
uv run --extra pymoo evoforge run examples/sphere_pymoo_ga.yaml
```

The `pymoo` adapter is optional. EvoForge core modules do not import `pymoo`
directly.

For a two-objective smoke example, run `examples/zdt1_nsga2.yaml` with the same
optional extra. The [multiobjective guide](docs/multiobjective.md) documents
NSGA-II, original objective values, and observed non-dominated output.

Install the optional `scikit-learn` surrogate adapter dependencies:

```bash
uv sync --extra sklearn
```

The `sklearn.random_forest` adapter is optional. It validates the surrogate
extension point and can be used programmatically to fit and predict from
EvoForge datasets.

Run the complete surrogate-assisted sphere example:

```bash
uv sync --extra pymoo --extra sklearn
uv run --extra pymoo --extra sklearn evoforge run examples/sphere_surrogate.yaml
```

This workflow trains the random forest on real simulator observations, searches
its predictions with pymoo GA, and validates selected candidates with the
simulator. Only real successful evaluations can become the final best result.
See [configuration](docs/configuration.md#surrogate-assisted-workflow) for budgets,
failure handling, and supported problems.

For a real crop-water simulation, see the [AquaCrop adapter guide](docs/aquacrop.md).
It includes direct GA and surrogate-assisted irrigation examples, Python 3.12
installation, units, climate-data provenance, and third-party license notices.

---

## Documentation

The documentation site is hosted at [calix35.github.io/EvoForge](https://calix35.github.io/EvoForge/).
Version-specific compatibility changes are recorded in [CHANGELOG.md](CHANGELOG.md).
Citation metadata are provided in [CITATION.cff](CITATION.cff).

Every persisted experiment records best-effort runtime provenance, plugin
classes/distribution versions, configured/effective seeds, and available
Git/lockfile information. See [reproducibility and validation](docs/reproducibility.md)
for `uv sync --locked`, optional extras, coverage reports, and reconstruction limits.

Serve the local documentation site:

```bash
uv run mkdocs serve
```

Then open:

```text
http://127.0.0.1:8000
```

---

## License

EvoForge is released under the [MIT License](LICENSE).

---
