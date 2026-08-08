# Configuration

EvoForge experiments are defined with YAML configuration files.

The main sections are:

- `experiment`: experiment metadata and optional seed.
- `problem`: variables, objectives, and constraints.
- `optimizer`: optimizer plugin and parameters.
- `evaluator`: evaluation source.
- `surrogate`: optional surrogate model configuration.
- `outputs`: output directory and artifact settings.

---

## Minimal Example

```yaml
experiment:
  name: sphere_random_search
  description: Minimal random search run against the built-in sphere benchmark.
  seed: 42

problem:
  name: sphere_benchmark
  type: single_objective
  variables:
    - name: x1
      type: continuous
      bounds: [-5.0, 5.0]
    - name: x2
      type: continuous
      bounds: [-5.0, 5.0]
  objectives:
    - name: sphere
      direction: minimize
  constraints: []

optimizer:
  plugin: example.random_search
  parameters:
    iterations: 5
    seed: 42

evaluator:
  type: simulator
  simulator:
    plugin: example.sphere

outputs:
  directory: results/sphere_random_search
```

Run it with:

```bash
uv run evoforge run examples/sphere_random_search.yaml
```

---

## Output Artifacts

Each experiment writes structured artifacts to the configured output directory:

- `config.json`: validated configuration.
- `metadata.json`: run metadata.
- `evaluation_records.json`: evaluated solutions and objective values.
- `manifest.json`: list of generated artifacts.
