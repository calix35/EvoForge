"""Lightweight built-in example plugins."""

from __future__ import annotations

import random
from typing import Any

from evoforge.config import OptimizerConfig, SimulatorConfig
from evoforge.domain import (
    EvaluationRecord,
    Problem,
    Solution,
    VariableType,
)
from evoforge.plugins import PluginRegistry


class ExampleRandomSearchOptimizer:
    """Simple random search optimizer using only the Python standard library."""

    plugin_id = "example.random_search"

    def __init__(self) -> None:
        self.iterations = 10
        self.seed: int | None = None

    def configure(self, config: object) -> None:
        optimizer_config = _require_config(config, OptimizerConfig)
        self.iterations = int(optimizer_config.parameters.get("iterations", 10))
        self.seed = _optional_int(optimizer_config.parameters.get("seed"))

    def optimize(self, problem: Problem, evaluator: object) -> list[EvaluationRecord]:
        if self.iterations < 1:
            msg = "Random search iterations must be at least 1."
            raise ValueError(msg)

        rng = random.Random(self.seed)
        records: list[EvaluationRecord] = []
        for _ in range(self.iterations):
            solution = Solution(
                problem=problem,
                values={
                    variable.name: _sample_variable_value(variable, rng)
                    for variable in problem.variables
                },
            )
            records.append(evaluator.evaluate(solution))
        return records


class ExampleSphereSimulator:
    """Sphere benchmark simulator using sum(x_i^2)."""

    plugin_id = "example.sphere"

    def configure(self, config: object) -> None:
        _require_config(config, SimulatorConfig)

    def evaluate(self, solution: Solution) -> EvaluationRecord:
        objective_name = "sphere"
        if solution.problem is not None:
            objective_name = solution.problem.objectives[0].name

        return EvaluationRecord(
            solution=solution,
            objective_values={objective_name: _sphere_value(solution.values)},
            source=self.plugin_id,
        )


def register_builtin_example_plugins(
    registry: PluginRegistry | None = None,
) -> PluginRegistry:
    """Register built-in example plugins into a plugin registry."""

    plugin_registry = registry if registry is not None else PluginRegistry()
    plugin_registry.register(ExampleRandomSearchOptimizer())
    plugin_registry.register(ExampleSphereSimulator())
    return plugin_registry


def _sample_variable_value(variable: Any, rng: random.Random) -> Any:
    if variable.type is VariableType.CONTINUOUS:
        if variable.bounds is None:
            msg = f"Continuous variable {variable.name!r} requires bounds."
            raise ValueError(msg)
        lower, upper = variable.bounds
        return rng.uniform(lower, upper)

    if variable.type is VariableType.INTEGER:
        if variable.bounds is None:
            msg = f"Integer variable {variable.name!r} requires bounds."
            raise ValueError(msg)
        lower, upper = variable.bounds
        return rng.randint(int(lower), int(upper))

    if variable.type is VariableType.BINARY:
        return rng.choice((0, 1))

    if variable.type in {VariableType.CATEGORICAL, VariableType.DISCRETE}:
        if not variable.values:
            msg = f"{variable.type.value} variable {variable.name!r} requires values."
            raise ValueError(msg)
        return rng.choice(variable.values)

    msg = f"Variable type {variable.type.value!r} is not supported by random search."
    raise NotImplementedError(msg)


def _sphere_value(values: dict[str, Any]) -> float:
    total = 0.0
    for value in values.values():
        if isinstance(value, bool):
            numeric_value = float(int(value))
        elif isinstance(value, int | float):
            numeric_value = float(value)
        else:
            continue
        total += numeric_value * numeric_value
    return total


def _require_config(config: object, expected_type: type[Any]) -> Any:
    if not isinstance(config, expected_type):
        msg = f"Expected {expected_type.__name__}."
        raise TypeError(msg)
    return config


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
