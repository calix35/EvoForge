"""Library-independent sequential surrogate orchestration."""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from math import isfinite
from time import perf_counter
from typing import Any

from evoforge.config import ExperimentConfig
from evoforge.domain import (
    Dataset,
    EvaluationRecord,
    EvaluationStatus,
    ObjectiveDirection,
    Problem,
    Solution,
)
from evoforge.errors import (
    ConfigurationError,
    EvoForgeError,
    PluginExecutionError,
    _ControlFlowSignal,
    error_context,
)
from evoforge.plugins import OptimizerPlugin, SimulatorPlugin, SurrogatePlugin

from .evaluation import validate_record


class _SearchBudgetReached(_ControlFlowSignal):
    pass


@dataclass
class SurrogateRun:
    """Separate real observations, predictions, and execution diagnostics."""

    records: list[EvaluationRecord] = field(default_factory=list)
    predictions: list[EvaluationRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    best_record: EvaluationRecord | None = None
    failed: bool = False
    errors: list[EvoForgeError] = field(default_factory=list)


class SurrogateWorkflow:
    """Execute bounded searches and validate unique candidates with a simulator."""

    def __init__(
        self,
        config: ExperimentConfig,
        problem: Problem,
        optimizer: OptimizerPlugin,
        simulator: SimulatorPlugin,
        surrogate: SurrogatePlugin,
    ) -> None:
        self.config = config
        self.problem = problem
        self.optimizer = optimizer
        self.simulator = simulator
        self.surrogate = surrogate
        self.budgets = config.surrogate.workflow
        assert self.budgets is not None
        self.seed = (
            config.experiment.seed
            if config.experiment.seed is not None
            else random.SystemRandom().randrange(2**32)
        )
        self.rng = random.Random(self.seed)
        self.run = SurrogateRun(
            metadata={
                "workflow": "surrogate_assisted",
                "surrogate_plugin": surrogate.plugin_id,
                "effective_seed": self.seed,
                "iterations": [],
                "fit_count": 0,
                "duplicate_candidates": 0,
                "prediction_calls": 0,
                "fit_seconds": 0.0,
            }
        )
        self.seen: set[tuple[float, ...]] = set()
        self.iteration = 0
        self.search_seed = self.seed
        self.search_start = 0

    def execute(self) -> SurrogateRun:
        started = perf_counter()
        reason = "real_budget_exhausted"
        try:
            surrogate_config = self.config.surrogate.model_copy(deep=True)
            surrogate_config.parameters.setdefault("random_state", self.seed)
            with error_context(
                ConfigurationError, "configure", self.surrogate.plugin_id
            ):
                self.surrogate.configure(surrogate_config)
            self.run.metadata["surrogate_parameters"] = surrogate_config.parameters
            attempts = 0
            while len(self.run.records) < self.budgets.initial_size:
                attempts += 1
                if attempts > self.budgets.initial_size * 100:
                    reason = "initial_design_duplicates"
                    self.run.failed = True
                    break
                solution = Solution(
                    problem=self.problem,
                    values={
                        v.name: self.rng.uniform(*v.bounds)
                        for v in self.problem.variables
                    },
                )
                self._evaluate_real(solution)

            while reason == "real_budget_exhausted":
                if len(self.run.records) >= self.budgets.real_budget:
                    break
                successful = [r for r in self.run.records if _successful(r)]
                if len(successful) < 2:
                    reason = "insufficient_successful_evaluations"
                    self.run.failed = True
                    break
                fit_started = perf_counter()
                with error_context(
                    PluginExecutionError, "fit", self.surrogate.plugin_id
                ):
                    self.surrogate.fit(Dataset.from_records(successful))
                self.run.metadata["fit_count"] += 1
                fit_seconds = perf_counter() - fit_started
                self.run.metadata["fit_seconds"] += fit_seconds
                self.iteration += 1
                self.search_seed = self.rng.randrange(2**32)
                optimizer_config = self.config.optimizer.model_copy(deep=True)
                optimizer_config.parameters.update(
                    seed=self.search_seed,
                    n_evaluations=self.budgets.search_budget,
                    iterations=self.budgets.search_budget,
                )
                with error_context(
                    ConfigurationError, "configure", self.optimizer.plugin_id
                ):
                    self.optimizer.configure(optimizer_config)
                self.search_start = len(self.run.predictions)
                search_started = perf_counter()
                try:
                    with error_context(
                        PluginExecutionError, "optimize", self.optimizer.plugin_id
                    ):
                        self.optimizer.optimize(self.problem, self)
                except _SearchBudgetReached:
                    pass
                predictions = self.run.predictions[self.search_start :]
                candidates: dict[tuple[float, ...], EvaluationRecord] = {}
                for record in predictions:
                    key = self._key(record.solution)
                    if key in self.seen or key in candidates:
                        self.run.metadata["duplicate_candidates"] += 1
                    elif _successful(record):
                        candidates[key] = record
                objective = self.problem.objectives[0]
                ranked = sorted(
                    candidates.values(),
                    key=lambda r: r.objective_values[objective.name],
                    reverse=objective.direction is ObjectiveDirection.MAXIMIZE,
                )
                count = min(
                    self.budgets.candidates_per_update,
                    self.budgets.real_budget - len(self.run.records),
                )
                self.run.metadata["iterations"].append(
                    {
                        "iteration": self.iteration,
                        "optimizer_seed": self.search_seed,
                        "training_records": len(successful),
                        "predictions": len(predictions),
                        "selected": min(count, len(ranked)),
                        "fit_seconds": fit_seconds,
                        "search_seconds": perf_counter() - search_started,
                    }
                )
                if not ranked:
                    reason = "no_novel_candidates"
                    break
                for prediction in ranked[:count]:
                    self._evaluate_real(prediction.solution)
        except _ControlFlowSignal:
            raise
        except Exception as error:
            reason = "plugin_failure"
            self.run.failed = True
            self.run.metadata["error"] = f"{type(error).__name__}: {error}"
            if isinstance(error, EvoForgeError):
                self.run.errors.append(error)
                self.run.metadata["error_details"] = error.as_dict()

        successful = [r for r in self.run.records if _successful(r)]
        if successful:
            objective = self.problem.objectives[0]
            self.run.best_record = sorted(
                successful,
                key=lambda r: r.objective_values[objective.name],
                reverse=objective.direction is ObjectiveDirection.MAXIMIZE,
            )[0]
        else:
            self.run.failed = True
        self.run.metadata.update(
            termination_reason=reason,
            simulator_calls=len(self.run.records),
            successful_evaluations=len(successful),
            failed_evaluations=len(self.run.records) - len(successful),
            successful_predictions=len(self.run.predictions),
            elapsed_seconds=perf_counter() - started,
            best_real_values=(
                self.run.best_record.objective_values if self.run.best_record else None
            ),
            best_real_solution=(
                self.run.best_record.solution.values if self.run.best_record else None
            ),
        )
        return self.run

    def evaluate(self, solution: Solution) -> EvaluationRecord:
        """Optimizer-facing prediction evaluator with an exact per-search cap."""
        if len(self.run.predictions) - self.search_start >= self.budgets.search_budget:
            raise _SearchBudgetReached
        with error_context(PluginExecutionError, "predict", self.surrogate.plugin_id):
            self._key(solution)
            started = perf_counter()
            self.run.metadata["prediction_calls"] += 1
            record = self.surrogate.predict(solution)
            validate_record(record, solution, prediction=True)
            record = self._annotate(record, solution, "prediction", started)
            if not _successful(record):
                raise ValueError("Surrogate returned an invalid prediction.")
        self.run.predictions.append(record)
        return record

    def _evaluate_real(self, solution: Solution) -> None:
        key = self._key(solution)
        if key in self.seen:
            self.run.metadata["duplicate_candidates"] += 1
            return
        if len(self.run.records) >= self.budgets.real_budget:
            return
        self.seen.add(key)
        started = perf_counter()
        try:
            with error_context(
                PluginExecutionError, "evaluate", self.simulator.plugin_id
            ):
                record = validate_record(self.simulator.evaluate(solution), solution)
                record = self._annotate(record, solution, "real", started)
                if not _successful(record):
                    record = replace(record, status=EvaluationStatus.FAILED)
        except _ControlFlowSignal:
            raise
        except Exception as error:
            if isinstance(error, EvoForgeError):
                self.run.errors.append(error)
            record = EvaluationRecord(
                solution=solution,
                objective_values={self.problem.objectives[0].name: 0.0},
                status=EvaluationStatus.FAILED,
                source=self.simulator.plugin_id,
                metadata={
                    "error": f"{type(error).__name__}: {error}",
                    "error_details": error.as_dict()
                    if isinstance(error, EvoForgeError)
                    else None,
                },
            )
            record = self._annotate(record, solution, "real", started)
        self.run.records.append(record)

    def _annotate(
        self,
        record: EvaluationRecord,
        solution: Solution,
        kind: str,
        started: float,
    ) -> EvaluationRecord:
        if record.solution.values != solution.values:
            raise ValueError("Plugin returned a record for a different solution.")
        if set(record.objective_values) != {self.problem.objectives[0].name}:
            raise ValueError("Plugin returned unexpected objective names.")
        source = (
            self.simulator.plugin_id if kind == "real" else self.surrogate.plugin_id
        )
        return replace(
            record,
            solution=solution,
            source=record.source or source,
            metadata={
                **record.metadata,
                "evaluation_kind": kind,
                "iteration": self.iteration,
                "seed": self.seed if kind == "real" else self.search_seed,
                "elapsed_seconds": perf_counter() - started,
                "call_index": (
                    len(self.run.records) + 1
                    if kind == "real"
                    else len(self.run.predictions) + 1
                ),
            },
        )

    def _key(self, solution: Solution) -> tuple[float, ...]:
        if set(solution.values) != set(self.problem.variable_names):
            raise ValueError("Candidate variable names do not match the problem.")
        key = tuple(float(solution.values[v.name]) for v in self.problem.variables)
        for value, variable in zip(key, self.problem.variables, strict=True):
            if (
                not isfinite(value)
                or not variable.bounds[0] <= value <= variable.bounds[1]
            ):
                raise ValueError("Candidate lies outside finite variable bounds.")
        return key


def _successful(record: EvaluationRecord) -> bool:
    return record.status is EvaluationStatus.SUCCESS and all(
        isfinite(value) for value in record.objective_values.values()
    )
