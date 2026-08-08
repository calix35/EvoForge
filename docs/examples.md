# Examples

## Built-In Random Search

Run:

```bash
uv run evoforge run examples/sphere_random_search.yaml
```

This example uses:

- Optimizer plugin: `example.random_search`
- Simulator plugin: `example.sphere`
- Output directory: `results/sphere_random_search`

---

## Optional pymoo GA

Install the optional dependency:

```bash
uv sync --extra pymoo
```

Run:

```bash
uv run --extra pymoo evoforge run examples/sphere_pymoo_ga.yaml
```

This example uses:

- Optimizer plugin: `pymoo.ga`
- Simulator plugin: `example.sphere`
- Output directory: `results/sphere_pymoo_ga`

The `pymoo` dependency is loaded only by the optional adapter package.
