# Development

## Setup

Install dependencies:

```bash
uv sync --locked --python 3.12
```

---

## Checks

Run tests:

```bash
uv run --locked --no-sync pytest --cov=src/evoforge --cov-branch --cov-report=term-missing --cov-report=xml --cov-report=json --cov-report=html
```

Run lint checks:

```bash
uv run --locked --no-sync ruff check .
```

Build documentation:

```bash
uv run --locked --no-sync mkdocs build --strict
```

Serve documentation locally:

```bash
uv run mkdocs serve
```

---

## Continuous Integration

The GitHub Actions workflow runs tests, lint checks, and documentation builds
on pushes and pull requests in base and full-extra environments. Both use the
lockfile without modifying it. The full environment explicitly imports pymoo,
scikit-learn, and AquaCrop before running tests. Coverage reports measure lines
and branches of `src/evoforge` and are uploaded for each environment, without a
coverage threshold. See [reproducibility and validation](reproducibility.md)
for full-extra installation, report interpretation, metadata fields, and test
scope and limitations.
