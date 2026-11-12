# Plugins

EvoForge integrates optimizers, simulators, surrogate models, analysis tools,
visualization tools, and report generators through explicit plugin contracts.

Plugins expose a stable `plugin_id`, receive validated configuration through
`configure(...)`, and exchange EvoForge domain objects such as `Problem`,
`Solution`, `EvaluationRecord`, and `Dataset`.

See [current contracts and 0.x compatibility](plugin_compatibility.md) for exact
method shapes and structural-check limits, and [errors and result retention](errors.md)
for contextual exceptions and the distinct direct/assisted failure policies.

---

## Plugin Registry

Plugins are registered explicitly:

```python
from evoforge.plugins import PluginRegistry

registry = PluginRegistry()
registry.register(my_plugin)
```

The registry rejects duplicate plugin IDs and raises a clear error when a
requested plugin is missing.

---

## Built-In Example Plugins

EvoForge includes two built-in example plugins:

- `example.random_search`
- `example.sphere`

Register them with:

```python
from evoforge.adapters.examples import register_builtin_example_plugins

registry = register_builtin_example_plugins()
```

---

## Optional pymoo Adapter

The optional `pymoo` adapter provides:

- `pymoo.ga`
- `pymoo.nsga2`
- `example.zdt1` (pymoo-backed benchmark evaluator)

Install:

```bash
uv sync --extra pymoo
```

Register:

```python
from evoforge.adapters.pymoo import register_pymoo_plugins

registry = register_pymoo_plugins()
```

See [multiobjective optimization](multiobjective.md) for NSGA-II scope, strict
evaluator budgets, mixed objective directions, and observed-front output.

---

## Optional scikit-learn Surrogate Adapter

The optional `scikit-learn` adapter provides:

- `sklearn.random_forest`

Install:

```bash
uv sync --extra sklearn
```

Register:

```python
from evoforge.adapters.sklearn import register_sklearn_plugins

registry = register_sklearn_plugins()
```

Minimal use:

```python
from evoforge.adapters.sklearn.plugins import RandomForestSurrogate
from evoforge.config import SurrogateConfig

surrogate = RandomForestSurrogate()
surrogate.configure(
    SurrogateConfig(
        enabled=True,
        plugin="sklearn.random_forest",
        parameters={"n_estimators": 100, "random_state": 42},
    )
)
surrogate.fit(dataset)
prediction = surrogate.predict(solution)
```

For complete orchestration, enable `surrogate.workflow` as described in
[configuration](configuration.md#surrogate-assisted-workflow). The CLI explicitly
registers `sklearn.random_forest` and `pymoo.ga`; their external dependencies are
loaded lazily. Programmatic callers register both helpers into the same registry.
Optimizers must call `evaluator.evaluate(Solution(...))`; in assisted mode this
returns predictions and may raise an internal search-budget stop exception.
The runtime handles that stop. Surrogates receive only successful real training
records and must return finite predictions for the requested solution/objective.

## Optional AquaCrop Adapter

`aquacrop.irrigation` implements `SimulatorPlugin` with AquaCrop-OSPy 3.1.0.
Install with `uv sync --python 3.12 --extra aquacrop`. Register programmatically:

```python
from evoforge.adapters.aquacrop import register_aquacrop_plugins

registry = register_aquacrop_plugins()
```

The CLI registers it by default without importing the external dependency.
See the [AquaCrop adapter guide](aquacrop.md) for scenario fields, units,
weather provenance, license notices, and runnable direct/surrogate examples.
