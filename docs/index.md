# EvoForge

**EvoForge** is an extensible framework for Simulation-Based Optimization using Evolutionary Computation and Surrogate Models.

It provides a configuration-driven experiment runtime, domain model, plugin registry, command-line interface, local output artifacts, and optional adapters for external optimization and machine-learning libraries.

---

## Features

- YAML experiment configuration.
- Typed configuration validation.
- Framework-native problem, solution, evaluation, and dataset objects.
- Explicit plugin registration.
- Command-line experiment execution.
- Structured local output artifacts.
- Built-in random search and sphere benchmark plugins.
- Optional `pymoo.ga` optimizer adapter.
- Optional `sklearn.random_forest` surrogate adapter.

---

## Quick Start

Install dependencies:

```bash
uv sync
```

Run the built-in example:

```bash
uv run evoforge run examples/sphere_random_search.yaml
```

The example writes artifacts to:

```text
results/sphere_random_search/
```
