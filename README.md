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
- Optional `scikit-learn` random forest surrogate adapter.

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

Install the optional `scikit-learn` surrogate adapter dependencies:

```bash
uv sync --extra sklearn
```

The `sklearn.random_forest` adapter is optional. It validates the surrogate
extension point and can be used programmatically to fit and predict from
EvoForge datasets.

---

## Documentation

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
