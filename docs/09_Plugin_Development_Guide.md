---
title: Plugin Development Guide
version: 0.1.0
status: Draft
project: EvoForge
authors:
  - Alan Diaz Manriquez
language: English
last_updated: 2026-07-30
---

# Plugin Development Guide

## Purpose

This document explains the initial plugin development model used by EvoForge.

The current plugin system is intentionally simple: plugins are registered explicitly in a `PluginRegistry` and must satisfy one of the plugin contracts defined by EvoForge.

---

## Plugin Principles

EvoForge plugins should follow these principles:

- Expose a stable `plugin_id`.
- Keep external library details outside the framework core.
- Receive validated configuration through `configure(...)`.
- Use EvoForge domain objects for inputs and outputs.
- Avoid modifying the core runtime.
- Include tests for plugin behavior.

---

## Current Plugin Contracts

The MVP defines contracts for:

- `OptimizerPlugin`
- `SimulatorPlugin`
- `SurrogatePlugin`
- `AnalysisPlugin`
- `VisualizationPlugin`
- `ReportPlugin`

These contracts are defined in:

```text
src/evoforge/plugins/contracts.py
```

---

## Example Optimizer Plugin

Conceptual optimizer plugins receive a `Problem` and an evaluator, then return evaluation records or another result that the experiment runtime can interpret.

```python
from evoforge.domain import EvaluationRecord, Problem, Solution


class MyOptimizer:
    plugin_id = "my.optimizer"

    def configure(self, config: object) -> None:
        self.config = config

    def optimize(self, problem: Problem, evaluator: object) -> list[EvaluationRecord]:
        solution = Solution(
            problem=problem,
            values={variable.name: 0.0 for variable in problem.variables},
        )
        return [evaluator.evaluate(solution)]
```

---

## Example Simulator Plugin

Simulator plugins evaluate a `Solution` and return an `EvaluationRecord`.

```python
from evoforge.domain import EvaluationRecord, Solution


class MySimulator:
    plugin_id = "my.simulator"

    def configure(self, config: object) -> None:
        self.config = config

    def evaluate(self, solution: Solution) -> EvaluationRecord:
        objective_name = "score"
        if solution.problem is not None:
            objective_name = solution.problem.objectives[0].name

        return EvaluationRecord(
            solution=solution,
            objective_values={objective_name: 0.0},
            source=self.plugin_id,
        )
```

---

## Explicit Registration

Plugins are registered explicitly through `PluginRegistry`.

```python
from evoforge.plugins import PluginRegistry

registry = PluginRegistry()
registry.register(MyOptimizer())
registry.register(MySimulator())
```

The registry rejects duplicate plugin IDs and raises a clear error when a requested plugin is missing.

---

## Built-In Example Plugins

The MVP includes built-in example plugins:

- `example.random_search`
- `example.sphere`

They are defined in:

```text
src/evoforge/adapters/examples/plugins.py
```

They can be registered with:

```python
from evoforge.adapters.examples import register_builtin_example_plugins

registry = register_builtin_example_plugins()
```

These plugins are intended for testing, examples, documentation, and architecture validation. They are not intended to replace production optimizer or simulator integrations.

---

## Current Limitations

The MVP plugin system does not yet support:

- Automatic plugin discovery.
- External plugin packages.
- Versioned plugin metadata.
- Plugin capability declarations.
- Plugin-specific schema discovery.

These features should be introduced through future ADRs and implementation milestones.

---

## References

- `docs/04_Architecture_Decisions/ADR-0001-plugin-first.md`
- `docs/04_Architecture_Overview.md`
- `docs/05_API_Design.md`
- `docs/07_MVP_Architecture_Review.md`
