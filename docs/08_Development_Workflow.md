---
title: Development Workflow
version: 0.1.0
status: Draft
project: EvoForge
authors:
  - Alan Diaz Manriquez
language: English
last_updated: 2026-07-30
---

# Development Workflow

## Purpose

This document defines the initial development workflow for EvoForge contributors.

It describes how to install the project, run tests, run lint checks, serve documentation, and execute the current MVP example.

---

## Environment Setup

EvoForge uses `uv` for dependency and environment management.

Install dependencies:

```bash
uv sync
```

Run commands inside the managed environment:

```bash
uv run <command>
```

---

## Validation Commands

Run the full test suite:

```bash
uv run pytest
```

Run lint checks:

```bash
uv run ruff check .
```

Build the documentation:

```bash
uv run mkdocs build --strict
```

Serve documentation locally:

```bash
uv run mkdocs serve
```

---

## Running the MVP Example

Run the built-in random-search sphere example:

```bash
uv run evoforge run examples/sphere_random_search.yaml
```

Expected output artifacts:

```text
results/sphere_random_search/
├── config.json
├── evaluation_records.json
├── manifest.json
└── metadata.json
```

The `results/` directory is an execution artifact and should not be committed.

---

## Development Rules

Development should follow the architectural workflow defined for EvoForge:

1. Document the requirement or architectural rationale.
2. Implement one module at a time.
3. Add focused tests.
4. Run tests and lint checks.
5. Review against the architecture before committing.

---

## Commit Guidelines

Commits should be small and focused.

Recommended examples:

```text
Add configuration module
Add domain model module
Add plugin contracts and registry
Add minimal experiment runtime
```

Avoid combining unrelated documentation, refactoring, and feature work in the same commit.

---

## References

- `docs/01_Project_Principles.md`
- `docs/04_Architecture_Overview.md`
- `docs/06_Implementation_Plan.md`
- `docs/07_MVP_Architecture_Review.md`
