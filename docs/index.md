---
title: EvoForge Documentation
version: 0.1.0
status: Draft
project: EvoForge
authors:
  - Alan Diaz Manriquez
language: English
last_updated: 2026-07-30
---

# EvoForge

**EvoForge** is an extensible research framework for Simulation-Based Optimization using Evolutionary Computation and Surrogate Models.

The project is being developed as scientific software to support reproducible optimization experiments, framework-oriented research, graduate theses, and multiple scientific publications.

---

## Documentation Map

- [Project Vision](00_Project_Vision.md): Defines why EvoForge exists and what it aims to become.
- [Project Principles](01_Project_Principles.md): Defines the engineering and research principles that guide the project.
- [System Requirements](02_System_Requirements.md): Defines what EvoForge must provide as a framework.
- [Domain Model](03_Domain_Model.md): Defines the core concepts and relationships of the EvoForge domain.
- [Architecture Overview](04_Architecture_Overview.md): Defines the high-level software architecture.
- [API Design](05_API_Design.md): Defines the initial public API and configuration workflow.
- [Implementation Plan](06_Implementation_Plan.md): Defines the incremental implementation milestones.
- [MVP Architecture Review](07_MVP_Architecture_Review.md): Reviews the first functional architecture prototype.

---

## Current Status

EvoForge has completed its first functional MVP architecture prototype.

The current MVP supports configuration validation, domain objects, plugin contracts, experiment orchestration, local output artifacts, CLI execution, and a built-in example adapter prototype.

Run the current example with:

```bash
uv run evoforge run examples/sphere_random_search.yaml
```
