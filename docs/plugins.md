# Plugins

EvoForge integrates optimizers, simulators, surrogate models, analysis tools,
visualization tools, and report generators through explicit plugin contracts.

Plugins expose a stable `plugin_id`, receive validated configuration through
`configure(...)`, and exchange EvoForge domain objects such as `Problem`,
`Solution`, `EvaluationRecord`, and `Dataset`.

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

Install:

```bash
uv sync --extra pymoo
```

Register:

```python
from evoforge.adapters.pymoo import register_pymoo_plugins

registry = register_pymoo_plugins()
```

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
