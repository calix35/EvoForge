---
title: Implementation Plan
version: 0.1.0
status: Draft
project: EvoForge
authors:
  - Alan Diaz Manriquez
language: English
last_updated: 2026-08-05
---

# Implementation Plan

## Purpose

This document defines the initial implementation plan for EvoForge.

It translates the project vision, system requirements, domain model, architecture, API design, and ADRs into an ordered set of implementation milestones suitable for incremental, reviewable software development.

---

## Scope

This plan covers the first implementation phase of EvoForge: the foundation required to create a minimal but coherent framework prototype.

It does not cover full surrogate-assisted optimization experiments, AquaCrop integration, benchmark campaigns, or publication experiments. Those will be planned after the core framework foundation is implemented and validated.

---

## Implementation Principles

Implementation shall follow these rules:

- Implement one module at a time.
- Keep the framework core independent of concrete external libraries.
- Write tests for each implemented module.
- Prefer small, reviewable implementation tasks.
- Do not implement algorithms already available in mature libraries unless there is a documented reason.
- Keep documentation, tests, and implementation aligned.
- Do not add features that are not traceable to requirements, architecture, API design, or ADRs.

---

## Initial Repository Structure

The first implementation phase should evolve toward the following structure:

```text
EvoForge/
├── docs/
├── examples/
├── src/
│   └── evoforge/
│       ├── __init__.py
│       ├── config/
│       ├── core/
│       ├── domain/
│       ├── plugins/
│       ├── data/
│       ├── analysis/
│       ├── visualization/
│       └── cli/
├── tests/
│   ├── config/
│   ├── core/
│   ├── domain/
│   └── plugins/
├── pyproject.toml
├── README.md
├── ROADMAP.md
└── mkdocs.yml
```

This structure is provisional and may be refined during implementation review.

---

## Milestone 0 -- Project Packaging Foundation

### Goal

Create the Python packaging foundation for EvoForge without implementing framework behavior.

### Deliverables

- `pyproject.toml`
- `src/evoforge/__init__.py`
- `tests/`
- Basic development dependencies
- Basic test configuration
- Basic formatting and linting configuration

### Recommended technologies

- Python 3.12+
- `uv`
- `pytest`
- `ruff`
- `mypy` or deferred type checking policy
- `pydantic`
- `pyyaml`
- `typer`

### Acceptance Criteria

- The package can be installed in editable mode.
- Tests can be executed.
- Importing `evoforge` works.
- No domain or experiment behavior is implemented yet.

---

## Milestone 1 -- Configuration Module

### Goal

Implement the first version of the configuration system described in ADR-0002.

### Deliverables

- `evoforge.config`
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
- `OutputConfig`
- YAML loading function
- Validation tests
- Example YAML file

### Acceptance Criteria

- A YAML file can be loaded into an `ExperimentConfig`.
- Invalid configurations fail with clear validation errors.
- The conceptual YAML structure in `05_API_Design.md` has a working example.
- Tests cover valid and invalid configuration cases.

### Related Documents

- ADR-0002 -- Configuration Management
- `docs/05_API_Design.md`

---

## Milestone 2 -- Domain Model Module

### Goal

Implement lightweight domain objects that represent the core concepts defined in the Domain Model.

### Deliverables

- `evoforge.domain`
- `Problem`
- `DecisionVariable`
- `Objective`
- `Constraint`
- `Solution`
- `EvaluationRecord`
- `Dataset`
- Basic enums or value objects for variable types and objective directions
- Unit tests

### Acceptance Criteria

- Domain objects can be created independently of external libraries.
- Domain objects do not import optimizer, simulator, or machine learning libraries.
- Domain objects are consistent with `03_Domain_Model.md`.

---

## Milestone 3 -- Plugin Contracts and Registry

### Goal

Implement the first plugin contract layer without integrating external libraries yet.

### Deliverables

- `evoforge.plugins`
- Base plugin protocol or abstract classes
- `OptimizerPlugin`
- `SimulatorPlugin`
- `SurrogatePlugin`
- `AnalysisPlugin`
- `VisualizationPlugin`
- `PluginRegistry`
- Tests for registration and lookup

### Acceptance Criteria

- Plugins can be registered explicitly.
- Plugins can be retrieved by stable plugin identifier.
- The core does not depend on concrete external libraries.
- Tests cover duplicate plugin IDs and missing plugins.

### Related Documents

- ADR-0001 -- Plugin-First Architecture

---

## Milestone 4 -- Experiment Core

### Goal

Implement the first minimal `Experiment` runtime.

### Deliverables

- `evoforge.core`
- `Experiment`
- `Experiment.from_config(...)`
- `Experiment.run()`
- `ExperimentResult`
- Minimal lifecycle states
- Tests using fake plugins

### Acceptance Criteria

- An experiment can be created from a validated config object.
- `Experiment.from_config(...)` loads YAML and validates it.
- `Experiment.run()` can execute a minimal workflow using fake plugins.
- Results include status, output directory, and reproducibility metadata.

---

## Milestone 5 -- Data and Output Foundation

### Goal

Implement basic local file-based output management.

### Deliverables

- `evoforge.data`
- Experiment output directory creation
- Evaluation record serialization
- Metadata serialization
- Basic result artifact manifest
- Tests

### Acceptance Criteria

- Running a minimal experiment creates an output directory.
- Configuration and metadata are saved.
- Evaluation records can be serialized.
- Output paths are deterministic and testable.

---

## Milestone 6 -- CLI Foundation

### Goal

Implement the first command-line entry point.

### Deliverables

- `evoforge.cli`
- `evoforge run path/to/experiment.yaml`
- Helpful validation errors
- Tests for CLI invocation

### Acceptance Criteria

- A user can run a YAML-defined experiment from the command line.
- Invalid YAML configurations fail before execution.
- CLI behavior matches the API design.

---

## Milestone 7 -- First Concrete Adapter Prototype

### Goal

Implement one simple concrete adapter to validate the plugin architecture.

### Recommended Prototype

Use a lightweight benchmark or fake simulator rather than AquaCrop.

Possible options:

- Analytical benchmark function simulator.
- Random search optimizer plugin.
- Simple scikit-learn surrogate adapter using a tiny dataset.

### Acceptance Criteria

- The adapter validates the plugin-first architecture.
- The adapter can be used in an end-to-end example.
- The implementation does not compromise the core architecture.

---

## Milestone 8 -- First External Optimizer Adapter

### Goal

Validate external optimizer integration while keeping the framework core
independent from optimizer-specific dependencies.

### Implemented Adapter

- `pymoo.ga`

### Acceptance Criteria

- The adapter is isolated under `src/evoforge/adapters/pymoo/`.
- The optional dependency is installed through the `pymoo` extra.
- The adapter supports an executable single-objective example.
- Tests validate registration, configuration, execution, and reproducibility.

---

## Milestone 9 -- Minimal Surrogate Adapter

### Goal

Validate the surrogate model extension point with a real machine-learning
library while avoiding premature implementation of full surrogate-assisted
optimization strategies.

### Implemented Adapter

- `sklearn.random_forest`

### Acceptance Criteria

- The adapter is isolated under `src/evoforge/adapters/sklearn/`.
- The optional dependency is installed through the `sklearn` extra.
- The adapter trains from EvoForge `Dataset` objects.
- The adapter predicts EvoForge `EvaluationRecord` objects.
- Tests validate registration, configuration, fitting, prediction,
  persistence, and dependency error messages.
- Documentation clearly states that full surrogate-assisted optimization
  remains future work.

---

## Milestone 10 -- Hybrid Surrogate-Assisted Evaluation Prototype

### Goal

Connect the external optimizer and surrogate adapter foundations through a
minimal hybrid evaluation workflow.

This milestone will validate the central long-term purpose of EvoForge:
orchestrating optimizers, simulators, datasets, and surrogate models through a
single reproducible experiment workflow.

### Conceptual Workflow

```text
pymoo optimizer proposes candidate solutions
        |
        v
EvoForge converts candidates into Solution objects
        |
        v
The simulator evaluates an initial set of solutions
        |
        v
EvoForge stores EvaluationRecord objects in a Dataset
        |
        v
The surrogate adapter is trained from the Dataset
        |
        v
A hybrid evaluator decides when to use the simulator or surrogate
        |
        v
EvoForge records all simulator and surrogate evaluations with provenance
```

### Proposed Components

- `HybridEvaluator`
- `SurrogateAssistedEvaluator`
- Evaluation policy configuration
- Simulator evaluation budget
- Surrogate evaluation budget
- Surrogate retraining policy
- Evaluation provenance metadata

### Conceptual Configuration Pattern

```yaml
experiment:
  name: sphere_surrogate_assisted_ga
  seed: 42

optimizer:
  plugin: pymoo.ga
  parameters:
    pop_size: 40
    n_evaluations: 200
    seed: 42

evaluator:
  type: hybrid
  simulator:
    plugin: example.sphere
  parameters:
    initial_simulator_evaluations: 40
    surrogate_evaluations_per_generation: 30
    simulator_evaluations_per_generation: 5
    retrain_every: 1

surrogate:
  enabled: true
  plugin: sklearn.random_forest
  parameters:
    n_estimators: 100
    random_state: 42
```

### Acceptance Criteria

- The workflow can execute a minimal surrogate-assisted experiment.
- Simulator and surrogate evaluations are both recorded as
  `EvaluationRecord` objects.
- Evaluation records preserve whether each value came from the simulator or the
  surrogate model.
- The surrogate can be retrained from accumulated simulator evaluations.
- The implementation remains independent of concrete optimizer, simulator, and
  surrogate libraries outside adapter packages.
- The workflow is documented as an initial strategy prototype, not as a final
  surrogate-assisted optimization methodology.

---

## First Implementation Task

The first implementation task should focus only on Milestone 0.

```text
Implement only Milestone 0 from docs/06_Implementation_Plan.md.

Create the Python packaging foundation for EvoForge without implementing framework behavior.

Requirements:
- Use a src/ layout with package name evoforge.
- Add pyproject.toml for an installable Python package.
- Add src/evoforge/__init__.py with package metadata only.
- Add tests/ with a basic import test.
- Configure pytest.
- Use uv for dependency and environment management.
- Add development dependencies for pytest, pydantic, PyYAML, typer, ruff, and mkdocs-material if appropriate.
- Do not implement Experiment, configuration models, plugins, or domain objects yet.
- Keep changes minimal and consistent with the documentation.
- After implementation, run the test suite and report the result.
```

---

## Open Questions

- Should `mypy` be mandatory from Milestone 0 or introduced after the domain model stabilizes?
- Should plugin contracts use `typing.Protocol` or abstract base classes?
- Should domain objects use dataclasses, Pydantic models, or plain classes?
- Should configuration and domain objects be separate types or share models where practical?

---

## References

- `docs/01_Project_Principles.md`
- `docs/02_System_Requirements.md`
- `docs/03_Domain_Model.md`
- `docs/04_Architecture_Overview.md`
- `docs/05_API_Design.md`
- `docs/04_Architecture_Decisions/ADR-0001-plugin-first.md`
- `docs/04_Architecture_Decisions/ADR-0002-configuration-management.md`
- `docs/04_Architecture_Decisions/ADR-0003-dependency-management.md`
