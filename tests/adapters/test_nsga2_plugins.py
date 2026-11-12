"""Real NSGA-II integration, exact budgets, and original objective provenance."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from evoforge.adapters.pymoo import register_pymoo_plugins
from evoforge.adapters.pymoo.nsga2 import PymooNSGA2Optimizer, observed_non_dominated
from evoforge.adapters.pymoo.zdt1 import ExampleZDT1Simulator
from evoforge.cli.main import app
from evoforge.config import OptimizerConfig, load_experiment_config
from evoforge.core import Experiment, ExperimentStatus
from evoforge.domain import (
    Constraint,
    DecisionVariable,
    EvaluationRecord,
    EvaluationStatus,
    Objective,
    OptimizationResult,
    Problem,
    Solution,
    VariableType,
)
from evoforge.plugins import DuplicatePluginError, OptimizerPlugin, SimulatorPlugin

pytest.importorskip("pymoo")


def problem():
    return Problem(
        "mixed",
        (DecisionVariable("x", "continuous", (0, 1)),),
        (Objective("cost", "minimize"), Objective("benefit", "maximize")),
    )


class Evaluator:
    def __init__(self):
        self.calls = 0
        self.records = []

    def evaluate(self, solution):
        self.calls += 1
        value = solution.values["x"]
        record = EvaluationRecord(
            solution, {"benefit": value, "cost": value}, source="fake.real"
        )
        self.records.append(record)
        return record


def optimizer(budget=13):
    plugin = PymooNSGA2Optimizer()
    plugin.configure(
        OptimizerConfig(
            plugin=plugin.plugin_id,
            parameters={"pop_size": 8, "n_evaluations": budget, "seed": 42},
        )
    )
    return plugin


def test_registration():
    registry = register_pymoo_plugins()
    assert isinstance(registry.get("pymoo.nsga2"), OptimizerPlugin)
    assert isinstance(registry.get("example.zdt1"), SimulatorPlugin)
    assert isinstance(registry.get("pymoo.ga"), OptimizerPlugin)
    with pytest.raises(DuplicatePluginError):
        register_pymoo_plugins(registry)


@pytest.mark.parametrize("budget", [1, 7, 8, 13, 16, 17])
def test_exact_call_budget_preserves_partial_population_records(budget):
    evaluator = Evaluator()
    result = optimizer(budget).optimize(problem(), evaluator)
    assert isinstance(result, OptimizationResult)
    assert evaluator.calls == len(result.records) == budget
    assert result.metadata["evaluator_calls"] == budget
    assert result.metadata["optimizer_seed"] == 42
    assert result.metadata["budget_reached"] is True
    assert result.metadata["termination_reason"] == "evaluation_budget_reached"
    assert result.metadata["budget_guard_triggered"] is (budget % 8 != 0)
    assert [r.metadata["call_index"] for r in result.records] == list(
        range(1, budget + 1)
    )
    assert all(r.metadata["optimizer_seed"] == 42 for r in result.records)
    for original, stored in zip(evaluator.records, result.records, strict=True):
        assert original.solution is stored.solution
        assert original.objective_values == stored.objective_values
        assert stored.objective_values["benefit"] >= 0  # no negation in saved records


def test_reproducible_numeric_traces_and_front():
    plugin = optimizer(17)
    first = plugin.optimize(problem(), Evaluator())
    second = plugin.optimize(problem(), Evaluator())
    for name in ("records", "non_dominated_records"):
        assert [
            (r.solution.values, r.objective_values) for r in getattr(first, name)
        ] == [(r.solution.values, r.objective_values) for r in getattr(second, name)]


def test_mixed_directions_used_inside_pymoo(monkeypatch):
    import pymoo.optimize

    captured = []

    def minimize(wrapped, algorithm, termination, **kwargs):
        output = {}
        wrapped._evaluate([0.25], output)
        captured.append(output["F"])

    monkeypatch.setattr(pymoo.optimize, "minimize", minimize)
    result = optimizer().optimize(problem(), Evaluator())
    assert captured == [[0.25, -0.25]]
    assert result.records[0].objective_values == {"cost": 0.25, "benefit": 0.25}


def test_observed_front_retains_original_records_and_filters_failed_predictions():
    p = problem()

    def record(x, cost, benefit, **kwargs):
        return EvaluationRecord(
            Solution({"x": x}, p), {"cost": cost, "benefit": benefit}, **kwargs
        )

    first = record(0.1, 1.0, 1.0)
    dominated = record(0.2, 2.0, 0.5)
    second = record(0.3, 2.0, 3.0)
    tied = record(0.4, 1.0, 1.0)
    failed = record(0.5, 0.0, 100.0, status=EvaluationStatus.FAILED)
    predicted = record(0.6, 0.0, 100.0, metadata={"evaluation_kind": "prediction"})
    pending = record(0.7, 0.0, 100.0, status=EvaluationStatus.PENDING)
    front = observed_non_dominated(
        p, (first, dominated, second, tied, failed, predicted, pending)
    )
    assert len(front) == 3
    assert front[0] is first
    assert front[1] is second
    assert front[2] is tied
    assert observed_non_dominated(p, (failed, predicted)) == ()


@pytest.mark.parametrize(
    "parameters",
    [
        {"pop_size": 0},
        {"pop_size": 1},
        {"pop_size": 2.5},
        {"n_evaluations": 0},
        {"n_evaluations": True},
        {"n_evaluations": "10"},
        {"seed": -1},
        {"seed": 2**32},
        {"verbose": "false"},
        {"unknown": 1},
    ],
)
def test_invalid_parameters(parameters):
    with pytest.raises(ValidationError):
        PymooNSGA2Optimizer().configure(
            OptimizerConfig(plugin="pymoo.nsga2", parameters=parameters)
        )


@pytest.mark.parametrize(
    "change",
    ["single", "integer", "categorical", "constraint", "infinite", "zero_width"],
)
def test_unsupported_problem_rejected_before_evaluation(change):
    p = problem()
    if change == "single":
        p = replace(p, objectives=(p.objectives[0],))
    elif change == "constraint":
        p = replace(p, constraints=(Constraint("limit"),))
    else:
        var = p.variables[0]
        if change == "integer":
            var = replace(var, type=VariableType.INTEGER)
        elif change == "categorical":
            var = DecisionVariable("x", "categorical", values=("a", "b"))
        else:
            var = replace(var, bounds=(0, float("inf") if change == "infinite" else 0))
        p = replace(p, variables=(var,))
    evaluator = Evaluator()
    with pytest.raises(ValueError):
        optimizer().optimize(p, evaluator)
    assert evaluator.calls == 0


@pytest.mark.parametrize(
    "kind",
    [
        "nan",
        "inf",
        "string",
        "bool",
        "names",
        "solution",
        "prediction",
        "constraint",
        "not_record",
    ],
)
def test_invalid_evaluation_results(kind):
    class Invalid(Evaluator):
        def evaluate(self, solution):
            record = super().evaluate(solution)
            if kind == "not_record":
                return object()
            if kind == "names":
                return EvaluationRecord(Solution(solution.values), {"wrong": 1.0})
            if kind == "solution":
                return replace(record, solution=Solution({"x": -1.0}))
            if kind == "prediction":
                return replace(record, metadata={"prediction_type": "surrogate"})
            if kind == "constraint":
                return replace(record, constraint_values={"limit": 1.0})
            value = {
                "nan": float("nan"),
                "inf": float("inf"),
                "string": "1",
                "bool": True,
            }[kind]
            return replace(record, objective_values={"cost": value, "benefit": 1.0})

    evaluator = Invalid()
    with pytest.raises(ValueError):
        optimizer().optimize(problem(), evaluator)
    assert evaluator.calls == 1


def test_failed_real_records_saved_but_excluded_from_front():
    class Failed(Evaluator):
        def evaluate(self, solution):
            record = super().evaluate(solution)
            return replace(record, status=EvaluationStatus.FAILED)

    result = optimizer(3).optimize(problem(), Failed())
    assert len(result.records) == 3
    assert result.non_dominated_records == ()
    assert result.metadata["failed_evaluations"] == 3


def test_optional_dependency_error(monkeypatch):
    original = __import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] == "pymoo":
            raise ImportError("missing pymoo")
        return original(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded)
    with pytest.raises(RuntimeError, match="uv sync --python 3.12 --extra pymoo"):
        optimizer().optimize(problem(), Evaluator())


def test_zdt1_delegates_to_pymoo():
    import numpy as np
    from pymoo.problems import get_problem

    config = load_experiment_config("examples/zdt1_nsga2.yaml")
    plugin = ExampleZDT1Simulator()
    plugin.configure(config.evaluator.simulator)
    p = Problem(
        "zdt1",
        tuple(
            DecisionVariable(v.name, v.type, tuple(v.bounds))
            for v in config.problem.variables
        ),
        (Objective("f1", "minimize"), Objective("f2", "minimize")),
    )
    solution = Solution({v.name: 0.25 for v in p.variables}, p)
    record = plugin.evaluate(solution)
    expected = get_problem("zdt1", n_var=30).evaluate(np.full((1, 30), 0.25))[0]
    assert list(record.objective_values.values()) == list(expected)
    assert record.source == "example.zdt1"


def test_runtime_and_serialization_preserve_observed_front(tmp_path):
    config = load_experiment_config("examples/zdt1_nsga2.yaml")
    config.outputs.directory = str(tmp_path / "zdt1")
    result = Experiment(config, register_pymoo_plugins()).run()
    assert result.status is ExperimentStatus.COMPLETED
    assert len(result.records) == 45
    assert result.non_dominated_records
    assert all(
        any(front is r for r in result.records)
        for front in result.non_dominated_records
    )
    real = json.loads(Path(result.artifact_paths["evaluation_records"]).read_text())
    front = json.loads(Path(result.artifact_paths["non_dominated"]).read_text())
    assert all(record in real for record in front)
    assert [r["objective_values"] for r in front] == [
        r.objective_values for r in result.non_dominated_records
    ]
    assert result.reproducibility_metadata["evaluator_calls"] == 45
    manifest = json.loads(Path(result.artifact_paths["manifest"]).read_text())
    assert manifest["artifacts"][-1]["kind"] == "observed_non_dominated_records"


def test_cli_zdt1_example(tmp_path, monkeypatch):
    example = Path("examples/zdt1_nsga2.yaml").resolve()
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["run", str(example)])
    assert result.exit_code == 0, result.output
    output = tmp_path / "results/zdt1_nsga2"
    assert len(json.loads((output / "evaluation_records.json").read_text())) == 45
    assert (output / "non_dominated.json").exists()


def test_surrogate_multiobjective_still_rejected():
    config = load_experiment_config("examples/zdt1_nsga2.yaml").model_dump()
    config["surrogate"] = {
        "enabled": True,
        "plugin": "sklearn.random_forest",
        "workflow": {
            "initial_size": 2,
            "real_budget": 4,
            "search_budget": 4,
            "candidates_per_update": 1,
        },
    }
    from evoforge.config import ExperimentConfig

    with pytest.raises(ValidationError, match="one objective"):
        ExperimentConfig.model_validate(config)


def test_more_than_two_objectives():
    p = replace(
        problem(), objectives=(*problem().objectives, Objective("third", "maximize"))
    )

    class Three(Evaluator):
        def evaluate(self, solution):
            self.calls += 1
            value = solution.values["x"]
            return EvaluationRecord(
                solution,
                {"cost": value, "benefit": value, "third": 1.0},
                source="fake.real",
            )

    result = optimizer(9).optimize(p, Three())
    assert len(result.records) == 9
    assert all(len(r.objective_values) == 3 for r in result.records)


@pytest.mark.parametrize(
    "change", ["dimension", "names", "direction", "bounds", "value"]
)
def test_zdt1_rejects_invalid_inputs(change):
    from evoforge.config import SimulatorConfig

    p = Problem(
        "zdt1",
        (
            DecisionVariable("x", "continuous", (0, 1)),
            DecisionVariable("y", "continuous", (0, 1)),
        ),
        (Objective("f1", "minimize"), Objective("f2", "minimize")),
    )
    simulator = ExampleZDT1Simulator()
    simulator.configure(SimulatorConfig(plugin="example.zdt1", parameters={"n_var": 2}))
    values = {"x": 0.5, "y": 0.5}
    if change == "dimension":
        simulator.n_var = 3
    elif change == "names":
        p = replace(p, objectives=(Objective("a", "minimize"), p.objectives[1]))
    elif change == "direction":
        p = replace(p, objectives=(Objective("f1", "maximize"), p.objectives[1]))
    elif change == "bounds":
        p = replace(
            p, variables=(replace(p.variables[0], bounds=(0, 2)), p.variables[1])
        )
    else:
        values["x"] = float("nan")
    with pytest.raises(ValueError):
        simulator.evaluate(Solution(values, p))
