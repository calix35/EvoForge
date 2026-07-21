---
title: ADR-0001 Plugin-First Architecture
version: 0.1.0
status: Proposed
project: EvoForge
---

# ADR-0001 -- Plugin-First Architecture

## Status

Proposed

---

## Context

EvoForge is intended to support Simulation-Based Optimization experiments that integrate optimization algorithms, surrogate models, external simulators, statistical tools, visualization tools, and experiment management workflows.

The framework is expected to evolve across multiple research products, including framework architecture, surrogate model benchmarking, surrogate-assisted evolutionary optimization, agricultural simulation case studies, and framework generalization across domains.

Several mature libraries already exist for important parts of this workflow, including `pymoo` for evolutionary optimization, `scikit-learn` for machine learning models, and other libraries such as XGBoost, LightGBM, CatBoost, Plotly, SciPy, and domain-specific simulators such as AquaCrop-OSPy.

However, directly coupling the EvoForge core to these libraries would limit maintainability, extensibility, and scientific reuse. The core would become dependent on specific implementation details, making it harder to add new optimizers, surrogate models, simulators, or analysis tools without modifying central framework components.

This decision is directly related to the following system requirements:

- FR-003 -- Simulator Integration
- FR-004 -- Evolutionary Optimizers
- FR-005 -- Surrogate Models
- FR-010 -- Extensibility

---

## Decision

EvoForge shall adopt a plugin-first architecture.

The framework core shall define stable abstractions, contracts, and orchestration mechanisms, but it shall not depend directly on concrete external libraries such as `pymoo`, `scikit-learn`, XGBoost, LightGBM, CatBoost, Plotly, or AquaCrop-OSPy.

Concrete integrations shall be implemented as plugins, adapters, or extension modules that conform to the interfaces defined by the EvoForge core.

At minimum, the plugin-first design shall apply to:

- Optimization algorithms
- Surrogate models
- Simulation environments
- Sampling strategies
- Statistical analysis modules
- Visualization modules
- Reporting modules

The core shall be responsible for coordination, configuration, lifecycle management, data flow, and reproducibility. Plugins shall be responsible for integrating concrete technologies and domain-specific behavior.

---

## Rationale

This decision supports the long-term research vision of EvoForge as a reusable platform rather than a single-purpose implementation.

The plugin-first architecture provides several advantages:

- It allows EvoForge to integrate mature external libraries without reimplementing existing algorithms.
- It keeps the core framework stable while allowing integrations to evolve independently.
- It enables future researchers to add new algorithms, surrogate models, or simulators without modifying core components.
- It supports multiple application domains beyond the initial agricultural optimization case study.
- It improves testability by allowing plugins to be tested independently from the core orchestration layer.
- It supports reproducibility by standardizing how external tools are configured, invoked, and tracked.

The main alternative considered was a monolithic architecture in which EvoForge directly imports and coordinates specific libraries from the core. This alternative would be simpler during early prototyping, but it would make the framework harder to maintain, extend, and generalize.

Another alternative was to build separate standalone tools for each research product. This was rejected because it would duplicate infrastructure, weaken traceability, and reduce the scientific value of EvoForge as a unified research platform.

---

## Consequences

Positive consequences:

- The framework core remains independent of specific optimization, machine learning, simulation, and visualization libraries.
- New algorithms, surrogate models, simulators, and analysis tools can be added through plugins or adapters.
- The architecture supports long-term evolution across multiple articles, theses, and research projects.
- External libraries can be replaced or upgraded with reduced impact on the core.
- The design encourages clear interfaces and explicit contracts between components.

Negative consequences:

- The initial architecture requires more design effort than a direct monolithic implementation.
- Plugin interfaces must be carefully designed to avoid becoming too generic or too restrictive.
- Additional testing is required to validate the interaction between the core and plugins.
- Documentation must clearly explain how plugins are created, registered, configured, and executed.

---

## Related Documents

- `docs/00_Project_Vision.md`
- `docs/01_Project_Principles.md`
- `docs/02_System_Requirements.md`

---

## Notes

- This ADR establishes a foundational architectural constraint for EvoForge.
- Future ADRs may define specific plugin mechanisms, registry behavior, adapter conventions, and dependency management policies.
