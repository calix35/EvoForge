# Getting Started

## Installation

EvoForge uses `uv` for dependency and environment management.

Install the base environment:

```bash
uv sync
```

Run commands inside the managed environment with:

```bash
uv run <command>
```

---

## Run the Built-In Example

Run the random-search sphere example:

```bash
uv run evoforge run examples/sphere_random_search.yaml
```

The run creates an output directory:

```text
results/sphere_random_search/
├── config.json
├── evaluation_records.json
├── manifest.json
└── metadata.json
```

The `results/` directory contains generated execution artifacts and should not
be committed.

---

## Optional Dependencies

Install the optional `pymoo` adapter dependencies:

```bash
uv sync --extra pymoo
```

Install the optional `scikit-learn` adapter dependencies:

```bash
uv sync --extra sklearn
```

Install both optional adapter groups:

```bash
uv sync --extra pymoo --extra sklearn
```

---

## Validation

Run the test suite:

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
