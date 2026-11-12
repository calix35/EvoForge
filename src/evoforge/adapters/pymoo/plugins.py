"""pymoo optimizer adapter plugins."""

from __future__ import annotations

from typing import Any

from evoforge.config import OptimizerConfig
from evoforge.domain import (
    EvaluationRecord,
    ObjectiveDirection,
    Problem,
    Solution,
    VariableType,
)


class PymooGAOptimizer:
    """Single-objective genetic algorithm optimizer backed by pymoo."""

    plugin_id = "pymoo.ga"

    def __init__(self) -> None:
        self.pop_size = 20
        self.n_evaluations = 100
        self.seed: int | None = None
        self.verbose = False
        self.last_run_metadata: dict[str, Any] = {}

    def configure(self, config: object) -> None:
        optimizer_config = _require_optimizer_config(config)
        parameters = optimizer_config.parameters
        self.pop_size = int(parameters.get("pop_size", self.pop_size))
        self.n_evaluations = int(parameters.get("n_evaluations", self.n_evaluations))
        self.seed = _optional_int(parameters.get("seed", self.seed))
        self.verbose = bool(parameters.get("verbose", self.verbose))
        self._validate_parameters()

    def optimize(self, problem: Problem, evaluator: object) -> list[EvaluationRecord]:
        """Optimize a supported EvoForge problem using pymoo GA."""

        self._validate_problem(problem)

        try:
            from pymoo.algorithms.soo.nonconvex.ga import GA
            from pymoo.optimize import minimize
            from pymoo.termination import get_termination
        except ImportError as error:
            msg = (
                "The optional 'pymoo' dependency is required to use plugin "
                "'pymoo.ga'. Install it with 'uv sync --extra pymoo'."
            )
            raise RuntimeError(msg) from error

        pymoo_problem = _EvoForgeElementwiseProblem(problem, evaluator)
        self.last_run_metadata = {"optimizer_seed": self.seed}
        algorithm = GA(pop_size=self.pop_size)
        termination = get_termination("n_eval", self.n_evaluations)
        minimize(
            pymoo_problem,
            algorithm,
            termination,
            seed=self.seed,
            verbose=self.verbose,
        )
        return pymoo_problem.records

    def _validate_parameters(self) -> None:
        if self.pop_size < 1:
            msg = "pymoo.ga pop_size must be at least 1."
            raise ValueError(msg)

        if self.n_evaluations < 1:
            msg = "pymoo.ga n_evaluations must be at least 1."
            raise ValueError(msg)

    def _validate_problem(self, problem: Problem) -> None:
        if len(problem.objectives) != 1:
            msg = "pymoo.ga supports single-objective problems only."
            raise ValueError(msg)

        unsupported = [
            variable.type.value
            for variable in problem.variables
            if variable.type not in {VariableType.CONTINUOUS, VariableType.INTEGER}
        ]
        if unsupported:
            msg = (
                "pymoo.ga supports continuous and integer variables only. "
                f"Unsupported variable types: {unsupported}."
            )
            raise ValueError(msg)

        for variable in problem.variables:
            if variable.bounds is None:
                msg = f"Variable {variable.name!r} requires bounds for pymoo.ga."
                raise ValueError(msg)


class _EvoForgeElementwiseProblem:
    """Lazy ElementwiseProblem wrapper around EvoForge evaluators."""

    def __new__(cls, problem: Problem, evaluator: object) -> Any:
        from pymoo.core.problem import ElementwiseProblem

        class EvoForgeProblem(ElementwiseProblem):
            def __init__(self) -> None:
                self.evoforge_problem = problem
                self.evaluator = evaluator
                self.records: list[EvaluationRecord] = []
                self.variable_names = [variable.name for variable in problem.variables]
                self.integer_names = {
                    variable.name
                    for variable in problem.variables
                    if variable.type is VariableType.INTEGER
                }
                xl = [variable.bounds[0] for variable in problem.variables]
                xu = [variable.bounds[1] for variable in problem.variables]
                super().__init__(
                    n_var=len(problem.variables),
                    n_obj=1,
                    xl=xl,
                    xu=xu,
                )

            def _evaluate(
                self,
                x: Any,
                out: dict[str, Any],
                *_args: Any,
                **_kwargs: Any,
            ) -> None:
                solution = Solution(
                    problem=self.evoforge_problem,
                    values=self._solution_values(x),
                )
                record = self.evaluator.evaluate(solution)
                self.records.append(record)
                objective = self.evoforge_problem.objectives[0]
                value = record.objective_values[objective.name]
                out["F"] = (
                    value
                    if objective.direction is ObjectiveDirection.MINIMIZE
                    else -value
                )

            def _solution_values(self, x: Any) -> dict[str, float | int]:
                values: dict[str, float | int] = {}
                for index, name in enumerate(self.variable_names):
                    raw_value = float(x[index])
                    if name in self.integer_names:
                        values[name] = int(round(raw_value))
                    else:
                        values[name] = raw_value
                return values

        return EvoForgeProblem()


def _require_optimizer_config(config: object) -> OptimizerConfig:
    if not isinstance(config, OptimizerConfig):
        msg = "Expected OptimizerConfig."
        raise TypeError(msg)
    return config


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
