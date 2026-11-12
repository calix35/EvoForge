"""Budget, provenance, failure, and real-adapter integration coverage."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from evoforge.adapters.examples import register_builtin_example_plugins
from evoforge.adapters.pymoo import register_pymoo_plugins
from evoforge.adapters.sklearn import register_sklearn_plugins
from evoforge.cli.main import app
from evoforge.config import ExperimentConfig, load_experiment_config
from evoforge.core import Experiment, ExperimentStatus
from evoforge.domain import Dataset, EvaluationRecord, EvaluationStatus, Solution


def config(tmp_path):
    cfg = load_experiment_config("examples/sphere_surrogate.yaml")
    cfg.outputs.directory = str(tmp_path / "run")
    return cfg


def registry():
    return register_sklearn_plugins(
        register_pymoo_plugins(register_builtin_example_plugins())
    )


class FakeSurrogate:
    plugin_id = "fake.surrogate"

    def __init__(self):
        self.datasets = []

    def configure(self, config):
        self.config = config

    def fit(self, dataset: Dataset):
        assert all(r.status is EvaluationStatus.SUCCESS for r in dataset.records)
        assert all(r.metadata["evaluation_kind"] == "real" for r in dataset.records)
        self.datasets.append(dataset)

    def predict(self, solution):
        return EvaluationRecord(solution, {"sphere": -1000.0}, source=self.plugin_id)


class RepeatedOptimizer:
    plugin_id = "fake.optimizer"

    def configure(self, config):
        self.config = config

    def optimize(self, problem, evaluator):
        # Deliberately ignore the configured search budget.
        return [
            evaluator.evaluate(
                Solution(
                    values={name: 0.0 for name in problem.variable_names},
                    problem=problem,
                )
            )
            for _ in range(100)
        ]


def fake_run(tmp_path, simulator=None, surrogate=None):
    cfg = config(tmp_path)
    cfg.optimizer.plugin = "fake.optimizer"
    cfg.surrogate.plugin = "fake.surrogate"
    reg = register_builtin_example_plugins()
    reg.register(RepeatedOptimizer())
    model = surrogate or FakeSurrogate()
    reg.register(model)
    if simulator:
        cfg.evaluator.simulator.plugin = simulator.plugin_id
        reg.register(simulator)
    return Experiment(cfg, reg).run(), model


def test_full_workflow_strict_budget_and_reproducibility(tmp_path):
    pytest.importorskip("pymoo")
    pytest.importorskip("sklearn")
    first = Experiment(config(tmp_path / "one"), registry()).run()
    second = Experiment(config(tmp_path / "two"), registry()).run()
    assert first.status is ExperimentStatus.COMPLETED
    assert len(first.records) == 13  # final batch is smaller than three
    assert first.reproducibility_metadata["simulator_calls"] == 13
    assert first.reproducibility_metadata["fit_count"] == 3
    assert (
        first.reproducibility_metadata["termination_reason"] == "real_budget_exhausted"
    )
    assert len(first.predictions) == 75  # 25, even with pymoo population size 12
    assert first.best_record in first.records
    assert all(r.metadata["evaluation_kind"] == "real" for r in first.records)
    assert all(r.metadata["evaluation_kind"] == "prediction" for r in first.predictions)
    for records in (first.records, first.predictions):
        assert all(r.metadata["elapsed_seconds"] >= 0 for r in records)
        assert all("seed" in r.metadata and "iteration" in r.metadata for r in records)

    def trace(result):
        return [(r.solution.values, r.objective_values) for r in result.records]

    assert trace(first) == trace(second)
    assert [r.objective_values for r in first.predictions] == [
        r.objective_values for r in second.predictions
    ]
    manifest = json.loads(Path(first.artifact_paths["manifest"]).read_text())
    assert manifest["artifacts"][-1]["kind"] == "unvalidated_predictions"
    saved = json.loads(Path(first.artifact_paths["evaluation_records"]).read_text())
    assert len(saved) == 13
    assert all(r["metadata"]["evaluation_kind"] == "real" for r in saved)


def test_duplicates_terminate_and_predictions_never_become_best(tmp_path):
    result, model = fake_run(tmp_path)
    assert result.status is ExperimentStatus.COMPLETED
    assert (
        result.reproducibility_metadata["termination_reason"] == "no_novel_candidates"
    )
    assert len(result.records) == 7
    assert len(result.predictions) == 50
    assert result.reproducibility_metadata["duplicate_candidates"] == 49
    assert [len(d) for d in model.datasets] == [6, 7]
    assert result.best_record.objective_values["sphere"] == 0.0
    assert result.best_record.source == "example.sphere"


def test_budget_exhaustion_skips_final_fit_and_preserves_best_real(tmp_path):
    class FailOnFinalFit(FakeSurrogate):
        def __init__(self):
            super().__init__()
            self.fit_calls = 0

        def fit(self, dataset):
            self.fit_calls += 1
            if self.fit_calls > 1:
                raise RuntimeError("Final training must not be required.")
            super().fit(dataset)

    class CountingSimulator:
        plugin_id = "fake.counting"

        def __init__(self):
            self.calls = 0

        def configure(self, config):
            pass

        def evaluate(self, solution):
            self.calls += 1
            return EvaluationRecord(
                solution,
                {"sphere": sum(value**2 for value in solution.values.values())},
                source=self.plugin_id,
            )

    cfg = config(tmp_path)
    cfg.surrogate.workflow.real_budget = 7
    cfg.surrogate.workflow.candidates_per_update = 1
    cfg = ExperimentConfig.model_validate(cfg.model_dump())
    cfg.optimizer.plugin = "fake.optimizer"
    cfg.surrogate.plugin = "fake.surrogate"
    simulator = CountingSimulator()
    cfg.evaluator.simulator.plugin = simulator.plugin_id
    model = FailOnFinalFit()
    reg = register_builtin_example_plugins()
    for plugin in (RepeatedOptimizer(), simulator, model):
        reg.register(plugin)

    result = Experiment(cfg, reg).run()

    assert result.status is ExperimentStatus.COMPLETED
    assert simulator.calls == len(result.records) == 7
    assert result.reproducibility_metadata["simulator_calls"] == 7
    assert result.reproducibility_metadata["fit_count"] == model.fit_calls == 1
    assert result.reproducibility_metadata["termination_reason"] == (
        "real_budget_exhausted"
    )
    assert "error" not in result.reproducibility_metadata
    assert result.best_record is result.records[-1]
    assert result.best_record.status is EvaluationStatus.SUCCESS
    assert result.best_record.source == simulator.plugin_id
    assert result.best_record.objective_values == {"sphere": 0.0}
    saved = json.loads(Path(result.artifact_paths["evaluation_records"]).read_text())
    assert len(saved) == 7
    assert saved[-1]["objective_values"] == {"sphere": 0.0}


class FailingSimulator:
    plugin_id = "fake.failing"

    def __init__(self, fail_all=False):
        self.calls = 0
        self.fail_all = fail_all

    def configure(self, config):
        pass

    def evaluate(self, solution):
        self.calls += 1
        if self.fail_all or self.calls == 1:
            raise RuntimeError("simulator unavailable")
        return EvaluationRecord(solution, {"sphere": 1.0}, source=self.plugin_id)


def test_simulator_failures_count_and_are_excluded_from_training(tmp_path):
    simulator = FailingSimulator()
    result, model = fake_run(tmp_path, simulator)
    assert simulator.calls == len(result.records) == 7
    assert result.records[0].status is EvaluationStatus.FAILED
    assert result.reproducibility_metadata["failed_evaluations"] == 1
    assert len(model.datasets[0]) == 5
    assert result.best_record.status is EvaluationStatus.SUCCESS


def test_real_adapters_exhaust_budget_including_simulator_failure(tmp_path):
    pytest.importorskip("pymoo")
    pytest.importorskip("sklearn")
    cfg = config(tmp_path)
    simulator = FailingSimulator()
    cfg.evaluator.simulator.plugin = simulator.plugin_id
    reg = registry()
    reg.register(simulator)
    result = Experiment(cfg, reg).run()
    assert simulator.calls == len(result.records) == 13
    assert result.status is ExperimentStatus.COMPLETED
    assert result.reproducibility_metadata["successful_evaluations"] == 12
    assert result.reproducibility_metadata["failed_evaluations"] == 1
    assert result.reproducibility_metadata["simulator_calls"] == 13
    assert result.best_record.status is EvaluationStatus.SUCCESS


def test_all_simulator_failures_are_saved_and_stop_before_training(tmp_path):
    simulator = FailingSimulator(fail_all=True)
    result, model = fake_run(tmp_path, simulator)
    assert result.status is ExperimentStatus.FAILED
    assert simulator.calls == 6
    assert not model.datasets
    assert result.best_record is None
    assert result.reproducibility_metadata["termination_reason"] == (
        "insufficient_successful_evaluations"
    )
    assert Path(result.artifact_paths["metadata"]).exists()


@pytest.mark.parametrize("stage", ["fit", "predict", "optimize"])
def test_plugin_failures_preserve_real_records(tmp_path, monkeypatch, stage):
    def fail(*args):
        raise RuntimeError("broken plugin")

    target = RepeatedOptimizer if stage == "optimize" else FakeSurrogate
    monkeypatch.setattr(target, stage, fail)
    result, _ = fake_run(tmp_path)
    assert result.status is ExperimentStatus.FAILED
    assert len(result.records) == 6
    assert result.best_record in result.records
    assert result.reproducibility_metadata["termination_reason"] == "plugin_failure"
    assert "broken plugin" in result.reproducibility_metadata["error"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("initial_size", 1),
        ("initial_size", 14),
        ("real_budget", 5),
        ("search_budget", 2),
        ("candidates_per_update", 8),
        ("real_budget", 6),
        ("initial_size", 2.5),
    ],
)
def test_incompatible_budgets_rejected(tmp_path, field, value):
    data = config(tmp_path).model_dump()
    data["surrogate"]["workflow"][field] = value
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(data)


@pytest.mark.parametrize("change", ["integer", "constraints", "multi", "bounds"])
def test_unsupported_problems_rejected_before_execution(tmp_path, change):
    data = config(tmp_path).model_dump()
    if change == "integer":
        data["problem"]["variables"][0]["type"] = "integer"
    elif change == "constraints":
        data["problem"]["constraints"] = [{"name": "limit"}]
    elif change == "multi":
        data["problem"]["type"] = "multi_objective"
    else:
        data["problem"]["variables"][0]["bounds"] = [0, float("inf")]
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(data)
    assert not (tmp_path / "run").exists()


def test_cli_surrogate_example(tmp_path, monkeypatch):
    pytest.importorskip("pymoo")
    pytest.importorskip("sklearn")
    example = Path("examples/sphere_surrogate.yaml").resolve()
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["run", str(example)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "results/sphere_surrogate/predictions.json").exists()


def test_maximization_selects_best_real_observation(tmp_path):
    cfg = config(tmp_path)
    cfg.problem.objectives[0].direction = "maximize"
    cfg.optimizer.plugin = "fake.optimizer"
    cfg.surrogate.plugin = "fake.surrogate"
    reg = register_builtin_example_plugins()
    reg.register(RepeatedOptimizer())
    reg.register(FakeSurrogate())
    result = Experiment(cfg, reg).run()
    assert result.best_record.objective_values["sphere"] == max(
        r.objective_values["sphere"] for r in result.records
    )
    assert result.best_record in result.records


def test_direct_execution_ignores_disabled_workflow(tmp_path):
    cfg = config(tmp_path)
    cfg.surrogate.enabled = False
    cfg.optimizer.plugin = "example.random_search"
    cfg.optimizer.parameters = {"iterations": 4, "seed": 42}
    result = Experiment(cfg, register_builtin_example_plugins()).run()
    assert len(result.records) == 4
    assert not result.predictions
    assert "predictions" not in result.artifact_paths
    assert "termination_reason" not in result.reproducibility_metadata
    assert result.status is ExperimentStatus.COMPLETED


@pytest.mark.parametrize("invalid", ["nonfinite", "failed", "different_solution"])
def test_invalid_simulator_records_cannot_train_or_win(tmp_path, invalid):
    class InvalidSimulator(FailingSimulator):
        def evaluate(self, solution):
            self.calls += 1
            if invalid == "different_solution":
                solution = Solution(
                    values={name: 0.0 for name in solution.values},
                    problem=solution.problem,
                )
            return EvaluationRecord(
                solution,
                {"sphere": float("nan") if invalid == "nonfinite" else 1.0},
                status=(
                    EvaluationStatus.FAILED
                    if invalid == "failed"
                    else EvaluationStatus.SUCCESS
                ),
            )

    result, model = fake_run(tmp_path, InvalidSimulator())
    assert result.status is ExperimentStatus.FAILED
    assert not model.datasets
    assert result.best_record is None
    assert all(r.status is EvaluationStatus.FAILED for r in result.records)
    assert all(
        r.objective_values["sphere"] == r.objective_values["sphere"]
        for r in result.records
    )


def test_initial_design_duplicate_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "evoforge.core.surrogate.random.Random.uniform", lambda *args: 0.0
    )
    result, model = fake_run(tmp_path)
    assert result.reproducibility_metadata["termination_reason"] == (
        "initial_design_duplicates"
    )
    assert len(result.records) == 1
    assert not model.datasets


def test_core_imports_without_optional_libraries():
    import subprocess
    import sys

    script = """
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'pymoo', 'sklearn', 'numpy'}:
        raise AssertionError(name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from evoforge.core import Experiment
"""
    subprocess.run([sys.executable, "-c", script], check=True)
