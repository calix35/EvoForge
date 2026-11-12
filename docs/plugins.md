# Plugins

EvoForge integrates optimizers, simulators and surrogate models through explicit
plugin contracts. Analysis, visualization and report contracts are defined but
have no operational runtime plugins in v0.2.0.

Plugins expose a stable `plugin_id`, receive validated configuration through
`configure(...)`, and exchange EvoForge domain objects such as `Problem`,
`Solution`, `EvaluationRecord`, and `Dataset`.

See [current contracts and 0.x compatibility](plugin_compatibility.md) for exact
method shapes and structural-check limits, and [errors and result retention](errors.md)
for contextual exceptions and the distinct direct/assisted failure policies.

---

## Plugin Registry

### User-Owned Simulator Walkthrough

The runnable [custom simulator example](https://github.com/calix35/EvoForge/blob/main/examples/custom_simulator.py)
defines `ShiftedSphere` in user code. It provides a `plugin_id`,
`configure(SimulatorConfig)` and `evaluate(Solution) -> EvaluationRecord`.
The class is about twenty source lines; the complete file includes imports and
a runnable setup. Its objective is a shifted quadratic named `loss`.

1. Implement the class in your own module; do not edit the EvoForge core.
2. Select `user.shifted_sphere` in `config.evaluator.simulator` and declare `loss`.
3. Register the instance with `registry.register(ShiftedSphere())`.
4. Pass that registry to `Experiment(config, registry)` and run it.

```bash
uv run --locked --no-sync python examples/custom_simulator.py
```

The example uses built-in random search and needs no scientific extras. It writes
five real observations under `results/custom_simulator`. Custom registration is
programmatic; the CLI does not automatically import arbitrary user modules.
The example uses the v0.2.0 public interfaces, and is an additional documentation
example rather than a change to the archived v0.2.0 core. A production adapter
must additionally validate its supported problem scope, units, inputs and any
external process behavior. See the [0.x compatibility policy](plugin_compatibility.md).

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
