---
title: ADR-0002 Configuration Management
version: 0.1.0
status: Proposed
project: EvoForge
---

# ADR-0002 -- Configuration Management

## Status

Proposed

---

## Context

EvoForge is intended to support reproducible Simulation-Based Optimization experiments involving multiple components: problems, optimizers, simulators, surrogate models, data management, statistical analysis, visualization, and reporting.

These experiments may contain many parameters, including decision variable definitions, objective definitions, optimizer settings, simulator settings, surrogate model settings, random seeds, output paths, execution options, and plugin-specific configuration.

If experiment configuration is defined only through Python code, reproducibility and comparability may become harder to preserve. Researchers need a configuration format that can be stored, versioned, shared, reviewed, and reused across experiments and publications.

At the same time, configuration must be validated before execution. Invalid, incomplete, or ambiguous configurations could lead to wasted simulation time, invalid experiments, or irreproducible results.

This decision is directly related to the following system requirements:

- FR-001 -- Experiment Management
- FR-006 -- Experiment Reproducibility
- FR-007 -- Data Management
- FR-010 -- Extensibility

---

## Decision

EvoForge shall use declarative YAML files as the primary format for experiment configuration.

Configuration files shall be validated using typed configuration models. The initial implementation shall use Pydantic as the validation and schema modeling library.

The configuration system shall support, at minimum:

- Experiment metadata.
- Random seeds.
- Problem definitions.
- Optimizer selection and parameters.
- Evaluation provider configuration.
- Simulator plugin configuration.
- Surrogate model plugin configuration.
- Dataset and output paths.
- Statistical analysis configuration.
- Visualization and reporting configuration.
- Plugin-specific parameter blocks.

Python APIs may also be provided for programmatic experiment construction, but YAML configuration shall be treated as the primary reproducibility artifact.

---

## Rationale

YAML is human-readable, widely used in scientific and engineering workflows, and suitable for version control. It allows researchers to define experiments without modifying Python source code.

Typed validation provides an explicit contract between user configuration and framework execution. Pydantic is appropriate for this role because it supports structured models, validation rules, defaults, serialization, nested configuration objects, and clear error messages.

This decision supports reproducibility by making experiment definitions explicit and persistent. It also supports documentation-driven development because configuration schemas can be documented, tested, and used as part of implementation planning.

The main alternative considered was configuring experiments only through Python code. This would provide flexibility, but it would make reproducibility less explicit and increase the risk of hidden execution logic.

Another alternative was to use JSON instead of YAML. JSON is simpler and strict, but it is less pleasant for researchers to write and maintain manually, especially for complex experiment definitions.

Another alternative was to use TOML. TOML is readable and well suited for project metadata, but YAML is more flexible for deeply nested experiment workflows and is more common in workflow configuration files.

---

## Consequences

Positive consequences:

- Experiment configurations can be stored, versioned, shared, reviewed, and reused.
- Experiments become easier to reproduce from a single configuration artifact.
- Configuration validation can catch errors before expensive simulations are executed.
- Pydantic models can become the basis for documentation, tests, and implementation tasks.
- Plugin-specific configuration can be modeled while preserving a common experiment structure.

Negative consequences:

- The configuration schema must be carefully designed and maintained.
- YAML can be permissive and may introduce ambiguity if validation is weak.
- Plugin configuration requires a strategy for validating both common and plugin-specific fields.
- Researchers may still need Python APIs for advanced dynamic workflows.

---

## Related Documents

- `docs/01_Project_Principles.md`
- `docs/02_System_Requirements.md`
- `docs/03_Domain_Model.md`
- `docs/04_Architecture_Overview.md`
- `docs/04_Architecture_Decisions/ADR-0001-plugin-first.md`

---

## Notes

- Future API design should define the first version of `ExperimentConfig` and related configuration models.
- Future implementation tasks should treat YAML loading and Pydantic validation as a focused, independent module.
- Plugin validation strategy should be revisited when the Plugin Registry design is specified.
