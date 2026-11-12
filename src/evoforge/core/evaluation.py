"""Shared validation at evaluator boundaries."""

from math import isfinite
from numbers import Real

from evoforge.domain import EvaluationRecord, Solution
from evoforge.errors import PluginExecutionError, error_context


def validate_record(record, solution: Solution, *, prediction: bool = False):
    if not isinstance(record, EvaluationRecord):
        raise ValueError("Evaluator must return an EvaluationRecord.")
    if record.solution.values != solution.values:
        raise ValueError("Plugin returned a record for a different solution.")
    if solution.problem is not None and set(record.objective_values) != {
        objective.name for objective in solution.problem.objectives
    }:
        raise ValueError("Plugin returned unexpected objective names.")
    for value in (
        *record.objective_values.values(),
        *record.constraint_values.values(),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not isfinite(value)
        ):
            raise ValueError("Evaluation results must contain finite real numbers.")
    if not prediction and (
        record.metadata.get("evaluation_kind") in {"prediction", "surrogate"}
        or record.metadata.get("prediction_type") == "surrogate"
    ):
        raise ValueError("A prediction cannot be presented as a real evaluation.")
    return record


class SimulatorEvaluator:
    """Add evaluate context without changing the registered simulator object."""

    def __init__(self, simulator):
        self.simulator = simulator

    def evaluate(self, solution: Solution) -> EvaluationRecord:
        with error_context(PluginExecutionError, "evaluate", self.simulator.plugin_id):
            return validate_record(self.simulator.evaluate(solution), solution)
