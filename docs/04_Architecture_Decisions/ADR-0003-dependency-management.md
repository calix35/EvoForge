---
title: ADR-0003 Dependency Management
version: 0.1.0
status: Proposed
project: EvoForge
---

# ADR-0003 -- Dependency Management

## Status

Proposed

---

## Context

EvoForge is intended to become an installable Python research framework with documentation, tests, examples, plugins, and reproducible experiment workflows.

The project requires a dependency management approach that supports local development, editable installs, test execution, documentation tooling, and future packaging.

The dependency manager should be simple enough for graduate students and contributors to use, while still supporting reproducible and modern Python development practices.

This decision is related to the following system requirements:

- FR-001 -- Experiment Management
- FR-006 -- Experiment Reproducibility
- FR-010 -- Extensibility

---

## Decision

EvoForge shall use `uv` for Python dependency and environment management.

The project shall define dependencies through `pyproject.toml`, and local development workflows shall use `uv` commands for environment creation, dependency installation, test execution, and tooling.

The initial implementation shall prefer a standard `src/` package layout and use `uv` as the primary development workflow.

---

## Rationale

`uv` provides a modern, fast, and reproducible workflow for Python projects. It supports virtual environments, dependency resolution, lockfiles, editable installs, and command execution with less friction than traditional `pip` plus manual virtual environment workflows.

Using `uv` also keeps the project aligned with modern Python packaging practices while remaining lightweight enough for research software development.

The main alternative considered was plain `venv` plus `pip`. This approach is widely understood and simple, but it requires more manual steps and provides weaker dependency workflow consistency.

Another alternative was Poetry. Poetry provides mature packaging workflows, but it adds more project-specific conventions and is less lightweight for the initial stage of EvoForge.

---

## Consequences

Positive consequences:

- Development environments can be created consistently.
- Dependencies can be managed through `pyproject.toml`.
- Test and tooling commands can be standardized.
- Future contributors can reproduce the development setup more easily.
- The workflow remains compatible with modern Python packaging.

Negative consequences:

- Contributors must install `uv`.
- Some users may be more familiar with plain `pip` or Conda workflows.
- Documentation must clearly explain the development setup.

---

## Related Documents

- `docs/01_Project_Principles.md`
- `docs/04_Architecture_Overview.md`
- `docs/05_API_Design.md`
- `docs/06_Implementation_Plan.md`

---

## Notes

- The initial implementation should include the minimal `uv`-compatible packaging setup.
- Installation instructions may later include alternative `pip` commands for users who only want to install EvoForge, but development documentation should prioritize `uv`.
