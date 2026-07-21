---
title: API Design
version: 0.1.0
status: Draft
project: EvoForge
authors:
  - Alan Diaz Manriquez
language: English
last_updated: 2026-07-21
---

# API Design

## Purpose

This document defines the initial public API design of EvoForge.

The API design translates the domain model and architecture into user-facing and developer-facing interfaces that will guide implementation, documentation, tests, and software review.

---

## Scope

This document describes the intended API shape, configuration models, core abstractions, and expected user workflows.

It does not provide final Python implementation code. Class names and method names in this document represent the target design and may be refined during implementation review.

---

## API Design Goals

The EvoForge API should be:

- Simple for researchers to use.
- Explicit enough to support reproducibility.
- Modular enough to support plugins and adapters.
- Stable enough to support future research products.
- Typed enough to support validation, testing, and documentation.
- Compatible with both Python-based and YAML-based workflows.

---

## Primary User Workflows

EvoForge shall support two primary workflows.

### Workflow 1 -- YAML-Driven Experiment

Researchers define an experiment using a YAML configuration file and execute it through the Python API or command-line interface.

Conceptual Python usage:

```python
from evoforge import Experiment

experiment = Experiment.from_config("experiments/aquacrop_nsga2.yaml")
result = experiment.run()
```

Conceptual CLI usage:

```bash
evoforge run experiments/aquacrop_nsga2.yaml
```

This workflow is the preferred path for reproducible experiments and publication-oriented research.

Related decision:

- ADR-0002 -- Configuration Management

---

### Workflow 2 -- Programmatic Experiment

Researchers or developers construct experiments directly in Python.

Conceptual usage:

```python
from evoforge import Experiment
from evoforge.config import ExperimentConfig

config = ExperimentConfig(
    name="aquacrop_nsga2_baseline",
    seed=42,
    problem={...},
    optimizer={...},
    evaluator={...},
    outputs={...},
)

experiment = Experiment(config)
result = experiment.run()
```

This workflow supports advanced use cases, interactive exploration, notebooks, and programmatic experiment generation.

---

## Configuration API

Configuration is the primary reproducibility contract in EvoForge.

The initial configuration API should include the following typed models:

- `ExperimentConfig`
- `MetadataConfig`
- `ProblemConfig`
- `VariableConfig`
- `ObjectiveConfig`
- `ConstraintConfig`
- `OptimizerConfig`
- `EvaluatorConfig`
- `SimulatorConfig`
- `SurrogateConfig`
- `DatasetConfig`
- `AnalysisConfig`
- `VisualizationConfig`
- `ReportConfig`
- `OutputConfig`

These models shall validate YAML configuration files before experiment execution.

---

## Conceptual YAML Structure

The following example illustrates the intended structure of an EvoForge experiment configuration.

```yaml
experiment:
  name: aquacrop_nsga2_baseline
  description: Baseline simulation-based optimization experiment using AquaCrop and NSGA-II.
  seed: 42

problem:
  name: irrigation_management
  type: multi_objective
  variables:
    - name: irrigation_day_1
      type: continuous
      bounds: [0.0, 40.0]
      unit: mm
    - name: irrigation_day_2
      type: continuous
      bounds: [0.0, 40.0]
      unit: mm
  objectives:
    - name: yield
      direction: maximize
    - name: water_use
      direction: minimize
  constraints: []

optimizer:
  plugin: pymoo.nsga2
  parameters:
    population_size: 100
    generations: 200

evaluator:
  type: simulator
  simulator:
    plugin: aquacrop_ospy
    parameters:
      weather_file: data/weather.csv
      soil_profile: data/soil.yaml

surrogate:
  enabled: false

outputs:
  directory: results/aquacrop_nsga2_baseline
  save_evaluations: true
  save_metadata: true
  save_figures: true

analysis:
  enabled: true
  methods:
    - descriptive_statistics

visualization:
  enabled: true
  plots:
    - convergence
    - pareto_front

report:
  enabled: true
  format: markdown
```

This structure is illustrative, not final. It will be refined during implementation planning.

---

## Core Runtime API

The central runtime API shall revolve around the `Experiment` object.

Conceptual responsibilities:

- Load and validate configuration.
- Initialize plugins and adapters.
- Coordinate the experiment lifecycle.
- Execute optimization workflows.
- Store evaluation records and metadata.
- Produce results, artifacts, statistics, visualizations, and reports.

Conceptual interface:

```python
class Experiment:
    @classmethod
    def from_config(cls, path: str) -> "Experiment":
        ...

    def run(self) -> "ExperimentResult":
        ...
```

Related domain entity:

- EVF-TERM-001 -- Experiment

Related requirements:

- FR-001 -- Experiment Management
- FR-006 -- Experiment Reproducibility
- FR-007 -- Data Management

---

## Plugin Contract API

Plugins are the mechanism by which EvoForge integrates external libraries and simulators.

Initial plugin contracts should include:

- `OptimizerPlugin`
- `SimulatorPlugin`
- `SurrogatePlugin`
- `AnalysisPlugin`
- `VisualizationPlugin`
- `ReportPlugin`

Each plugin should expose:

- A stable plugin identifier.
- A configuration schema or validation model.
- A setup or initialization method.
- One or more execution methods.
- Metadata required for reproducibility.

Conceptual optimizer plugin:

```python
class OptimizerPlugin:
    plugin_id: str

    def configure(self, config: "OptimizerConfig") -> None:
        ...

    def optimize(self, problem: "Problem", evaluator: "EvaluationProvider") -> "OptimizationResult":
        ...
```

Conceptual simulator plugin:

```python
class SimulatorPlugin:
    plugin_id: str

    def configure(self, config: "SimulatorConfig") -> None:
        ...

    def evaluate(self, solution: "Solution") -> "EvaluationRecord":
        ...
```

These contracts will be refined after the Plugin Registry design is specified.

Related decision:

- ADR-0001 -- Plugin-First Architecture

---

## Result API

Experiment execution shall produce an `ExperimentResult`.

Conceptual responsibilities:

- Reference the experiment configuration.
- Reference produced datasets.
- Reference evaluation records.
- Reference generated artifacts.
- Expose summary statistics.
- Expose report locations.
- Preserve reproducibility metadata.

Conceptual interface:

```python
class ExperimentResult:
    experiment_id: str
    status: str
    output_directory: str
    dataset_path: str | None
    report_path: str | None
```

Related domain entities:

- EVF-TERM-009 -- Evaluation Record
- EVF-TERM-010 -- Dataset
- EVF-TERM-018 -- Report

---

## API Boundaries

The EvoForge public API should expose stable user-facing concepts and hide implementation details.

Public API should include:

- Experiment construction.
- Configuration loading.
- Configuration validation.
- Experiment execution.
- Plugin registration or discovery.
- Access to experiment results.

Internal API should include:

- Low-level lifecycle management.
- Internal execution state.
- Internal data serialization details.
- Plugin loading internals.
- Adapter-specific implementation details.

---

## Open Questions

- Should `Experiment.from_config()` accept only file paths, or also dictionaries and already validated config objects?
- Should plugin registration be explicit in Python, automatic through package entry points, or both?
- Should `Experiment.run()` always be synchronous in the first version?
- Should the first API expose notebook-friendly helper methods?
- Should configuration models be permissive for plugin-specific parameters or strict by default?
- Should result paths be represented as strings or path objects?

---

## References

- `docs/01_Project_Principles.md`
- `docs/02_System_Requirements.md`
- `docs/03_Domain_Model.md`
- `docs/04_Architecture_Overview.md`
- `docs/04_Architecture_Decisions/ADR-0001-plugin-first.md`
- `docs/04_Architecture_Decisions/ADR-0002-configuration-management.md`
