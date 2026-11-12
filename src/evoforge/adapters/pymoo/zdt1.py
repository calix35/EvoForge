"""Optional ZDT1 evaluator delegating to pymoo's benchmark implementation."""

from __future__ import annotations

from math import isfinite
from numbers import Real

from pydantic import BaseModel, ConfigDict, Field

from evoforge.config import SimulatorConfig
from evoforge.domain import EvaluationRecord, ObjectiveDirection, Solution, VariableType


class _Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    n_var: int = Field(default=30, ge=2)


class ExampleZDT1Simulator:
    """Two minimizing objectives from pymoo's public ZDT1 problem API."""

    plugin_id = "example.zdt1"

    def __init__(self) -> None:
        self.n_var = 30

    def configure(self, config: object) -> None:
        if not isinstance(config, SimulatorConfig):
            raise TypeError("Expected SimulatorConfig.")
        self.n_var = _Parameters.model_validate(config.parameters).n_var

    def evaluate(self, solution: Solution) -> EvaluationRecord:
        problem = solution.problem
        if (
            problem is None
            or len(problem.variables) != self.n_var
            or {o.name for o in problem.objectives} != {"f1", "f2"}
            or any(
                o.direction is not ObjectiveDirection.MINIMIZE
                for o in problem.objectives
            )
            or problem.constraints
        ):
            raise ValueError(
                "example.zdt1 requires n_var inputs, f1/f2 to minimize, no constraints."
            )
        values = []
        for variable in problem.variables:
            value = solution.values[variable.name]
            if (
                variable.type is not VariableType.CONTINUOUS
                or variable.bounds != (0, 1)
                or isinstance(value, bool)
                or not isinstance(value, Real)
                or not isfinite(value)
                or not 0 <= value <= 1
            ):
                raise ValueError("example.zdt1 requires continuous inputs in [0, 1].")
            values.append(float(value))
        try:
            import numpy as np
            from pymoo.problems import get_problem
        except ImportError as error:
            raise RuntimeError(
                "Plugin 'example.zdt1' requires pymoo. "
                "Install it with 'uv sync --python 3.12 --extra pymoo'."
            ) from error
        objectives = get_problem("zdt1", n_var=self.n_var).evaluate(
            np.asarray([values]), return_values_of=["F"]
        )[0]
        if len(objectives) != 2 or not all(isfinite(v) for v in objectives):
            raise ValueError("pymoo ZDT1 returned invalid objective results.")
        return EvaluationRecord(
            solution,
            {"f1": float(objectives[0]), "f2": float(objectives[1])},
            source=self.plugin_id,
            metadata={"evaluation_kind": "real", "benchmark": "pymoo.zdt1"},
        )
