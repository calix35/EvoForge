# EvoForge

**EvoForge** is an extensible framework for Simulation-Based Optimization using Evolutionary Computation and Surrogate Models.

> Status: MVP architecture prototype completed. Under active research and development.

---

## Vision

EvoForge aims to provide a modular, extensible and reproducible framework for conducting simulation-based optimization experiments by integrating state-of-the-art evolutionary algorithms, surrogate models and simulation environments.

---

## Current MVP

The current MVP supports:

- YAML-based experiment configuration.
- Typed configuration validation.
- Lightweight domain objects.
- Plugin contracts and explicit plugin registry.
- Minimal experiment runtime.
- Local output artifacts.
- Typer-based CLI.
- Built-in example plugins for a random search optimizer and sphere benchmark simulator.

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

## Research Roadmap

EvoForge is being developed as the foundation for a multi-product research line:

- Product 1: Framework architecture and core implementation.
- Product 2: Surrogate model benchmark.
- Product 3: Surrogate-assisted evolutionary optimization.
- Product 4: Simulation-based agricultural optimization with AquaCrop.
- Product 5: Framework generalization across simulation domains.
