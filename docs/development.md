# Development

## Setup

Install dependencies:

```bash
uv sync
```

---

## Checks

Run tests:

```bash
uv run pytest
```

Run lint checks:

```bash
uv run ruff check .
```

Build documentation:

```bash
uv run mkdocs build --strict
```

Serve documentation locally:

```bash
uv run mkdocs serve
```

---

## Continuous Integration

The GitHub Actions workflow runs tests, lint checks, and documentation builds
on pushes and pull requests.
