"""Optional NSGA-II adapter with an individual evaluator-call budget."""

from __future__ import annotations

import random
from dataclasses import replace
from math import isfinite
from numbers import Real
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from evoforge.config import OptimizerConfig
from evoforge.domain import (
    EvaluationRecord,
    EvaluationStatus,
    ObjectiveDirection,
    OptimizationResult,
    Problem,
    Solution,
    VariableType,
)


class _Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    pop_size: int = Field(default=20, ge=2)
    n_evaluations: int = Field(default=100, ge=1)
    seed: int | None = Field(default=None, ge=0, lt=2**32)
    verbose: bool = False


class _BudgetReached(Exception):
    pass


class PymooNSGA2Optimizer:
    """Continuous, unconstrained multiobjective optimization with NSGA2."""

    plugin_id = "pymoo.nsga2"

    def __init__(self) -> None:
        self.parameters = _Parameters()

    def configure(self, config: object) -> None:
        if not isinstance(config, OptimizerConfig):
            raise TypeError("Expected OptimizerConfig.")
        self.parameters = _Parameters.model_validate(config.parameters)

    def optimize(self, problem: Problem, evaluator: object) -> OptimizationResult:
        _validate_problem(problem)
        try:
            from pymoo.algorithms.moo.nsga2 import NSGA2
            from pymoo.core.problem import ElementwiseProblem
            from pymoo.optimize import minimize
        except ImportError as error:
            raise RuntimeError(
                "Plugin 'pymoo.nsga2' requires pymoo. "
                "Install it with 'uv sync --python 3.12 --extra pymoo'."
            ) from error

        parameters = self.parameters
        seed = parameters.seed
        if seed is None:
            seed = random.SystemRandom().randrange(2**32)
        records: list[EvaluationRecord] = []
        calls = 0
        guard_triggered = False

        class WrappedProblem(ElementwiseProblem):
            def __init__(self) -> None:
                super().__init__(
                    n_var=len(problem.variables),
                    n_obj=len(problem.objectives),
                    xl=[v.bounds[0] for v in problem.variables],
                    xu=[v.bounds[1] for v in problem.variables],
                )

            def _evaluate(self, x: Any, out: dict, *_args, **_kwargs) -> None:
                nonlocal calls
                if calls >= parameters.n_evaluations:
                    raise _BudgetReached
                solution = Solution(
                    values={
                        v.name: float(x[i]) for i, v in enumerate(problem.variables)
                    },
                    problem=problem,
                )
                started = perf_counter()
                calls += 1
                record = evaluator.evaluate(solution)
                if not isinstance(record, EvaluationRecord):
                    raise ValueError("pymoo.nsga2 requires EvaluationRecord results.")
                if record.solution.values != solution.values:
                    raise ValueError("Evaluator returned a different solution.")
                if _prediction(record):
                    raise ValueError(
                        "pymoo.nsga2 requires real evaluations, not predictions."
                    )
                if record.constraint_values:
                    raise ValueError("pymoo.nsga2 does not support constraint results.")
                values = _objective_vector(problem, record)
                record = replace(
                    record,
                    solution=solution,
                    metadata={
                        **record.metadata,
                        "evaluation_kind": "real",
                        "call_index": calls,
                        "optimizer_seed": seed,
                        "elapsed_seconds": perf_counter() - started,
                    },
                )
                records.append(record)
                out["F"] = (
                    values
                    if record.status is EvaluationStatus.SUCCESS
                    else [float("inf")] * len(problem.objectives)
                )

        try:
            minimize(
                WrappedProblem(),
                NSGA2(pop_size=parameters.pop_size),
                ("n_eval", parameters.n_evaluations),
                seed=seed,
                verbose=parameters.verbose,
            )
        except _BudgetReached:
            guard_triggered = True

        observations = tuple(records)
        front = observed_non_dominated(problem, observations)
        successful = sum(r.status is EvaluationStatus.SUCCESS for r in observations)
        return OptimizationResult(
            records=observations,
            non_dominated_records=front,
            metadata={
                "optimizer_plugin": self.plugin_id,
                "optimizer_seed": seed,
                "pop_size": parameters.pop_size,
                "n_evaluations": parameters.n_evaluations,
                "evaluator_calls": calls,
                "successful_evaluations": successful,
                "failed_evaluations": len(observations) - successful,
                "non_dominated_count": len(front),
                "budget_guard_triggered": guard_triggered,
                "budget_reached": calls == parameters.n_evaluations,
                "termination_reason": (
                    "evaluation_budget_reached"
                    if calls == parameters.n_evaluations
                    else "optimizer_terminated"
                ),
            },
        )


def observed_non_dominated(
    problem: Problem, records: tuple[EvaluationRecord, ...]
) -> tuple[EvaluationRecord, ...]:
    """Select original real successful observations using pymoo's sorting utility."""
    _validate_problem(problem)
    successful = [
        r
        for r in records
        if r.status is EvaluationStatus.SUCCESS and not _prediction(r)
    ]
    if not successful:
        return ()
    import numpy as np
    from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting

    values = np.asarray([_objective_vector(problem, r) for r in successful])
    indices = NonDominatedSorting().do(values, only_non_dominated_front=True)
    # Preserve observation order and identity, including tied observations.
    return tuple(successful[int(i)] for i in sorted(indices))


def _prediction(record: EvaluationRecord) -> bool:
    return (
        record.metadata.get("evaluation_kind") in {"prediction", "surrogate"}
        or record.metadata.get("prediction_type") == "surrogate"
    )


def _objective_vector(problem: Problem, record: EvaluationRecord) -> list[float]:
    names = {objective.name for objective in problem.objectives}
    if set(record.objective_values) != names:
        raise ValueError("Evaluation objective names must match the problem exactly.")
    values = []
    for objective in problem.objectives:
        value = record.objective_values[objective.name]
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not isfinite(value)
        ):
            raise ValueError("Objective results must be finite real numbers.")
        values.append(
            float(value)
            if objective.direction is ObjectiveDirection.MINIMIZE
            else -float(value)
        )
    return values


def _validate_problem(problem: Problem) -> None:
    if len(problem.objectives) < 2:
        raise ValueError("pymoo.nsga2 requires at least two objectives.")
    if problem.constraints:
        raise ValueError("pymoo.nsga2 does not support constraints.")
    for variable in problem.variables:
        if (
            variable.type is not VariableType.CONTINUOUS
            or variable.bounds is None
            or not all(isfinite(v) for v in variable.bounds)
            or variable.bounds[0] >= variable.bounds[1]
        ):
            raise ValueError(
                "pymoo.nsga2 requires continuous variables "
                "with finite, increasing bounds."
            )
