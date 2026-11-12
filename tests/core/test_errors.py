"""Context, chaining, CLI classification, and failure retention with doubles."""

import importlib
import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from evoforge.config import ExperimentConfig
from evoforge.core import Experiment, ExperimentStatus
from evoforge.domain import EvaluationRecord, Solution
from evoforge.errors import ConfigurationError, OutputError, PluginExecutionError
from evoforge.plugins import MissingPluginError, OptimizerPlugin, PluginRegistry

cli = importlib.import_module("evoforge.cli.main")


class Faults:
    def __init__(self, stage=None, error=None, at=1):
        self.stage = stage
        self.error = error if error is not None else ArithmeticError("plugin broke")
        self.at = at
        self.calls = {}

    def check(self, stage):
        self.calls[stage] = self.calls.get(stage, 0) + 1
        if self.stage == stage and self.calls[stage] == self.at:
            raise self.error


class Optimizer:
    plugin_id = "fake.optimizer"

    def __init__(self, faults):
        self.faults = faults

    def configure(self, config):
        self.faults.check("optimizer.configure")

    def optimize(self, problem, evaluator):
        self.faults.check("optimize")
        iteration = self.faults.calls["optimize"]
        return [
            evaluator.evaluate(Solution({"x": iteration / 10 + i / 100}, problem))
            for i in range(2)
        ]


class Simulator:
    plugin_id = "fake.simulator"

    def __init__(self, faults):
        self.faults = faults

    def configure(self, config):
        self.faults.check("simulator.configure")

    def evaluate(self, solution):
        self.faults.check("evaluate")
        return EvaluationRecord(
            solution, {"score": solution.values["x"]}, source=self.plugin_id
        )


class Surrogate:
    plugin_id = "fake.surrogate"

    def __init__(self, faults):
        self.faults = faults

    def configure(self, config):
        self.faults.check("surrogate.configure")

    def fit(self, dataset):
        self.faults.check("fit")

    def predict(self, solution):
        self.faults.check("predict")
        return EvaluationRecord(
            solution,
            {"score": 0.0},
            source=self.plugin_id,
            metadata={"evaluation_kind": "prediction"},
        )


def config(tmp_path, assisted=False):
    return ExperimentConfig.model_validate(
        {
            "experiment": {"name": "error_test", "seed": 42},
            "problem": {
                "name": "test",
                "type": "single_objective",
                "variables": [{"name": "x", "type": "continuous", "bounds": [0, 1]}],
                "objectives": [{"name": "score", "direction": "minimize"}],
            },
            "optimizer": {"plugin": "fake.optimizer"},
            "evaluator": {
                "type": "simulator",
                "simulator": {"plugin": "fake.simulator"},
            },
            "surrogate": {
                "enabled": assisted,
                "plugin": "fake.surrogate",
                "workflow": {
                    "initial_size": 3,
                    "real_budget": 5,
                    "search_budget": 2,
                    "candidates_per_update": 1,
                },
            },
            "outputs": {"directory": str(tmp_path / "output")},
        }
    )


def registry(faults):
    result = PluginRegistry()
    for plugin in (Optimizer(faults), Simulator(faults), Surrogate(faults)):
        result.register(plugin)
    return result


@pytest.mark.parametrize(
    "stage,plugin_id,error_type",
    [
        ("optimizer.configure", "fake.optimizer", ConfigurationError),
        ("simulator.configure", "fake.simulator", ConfigurationError),
        ("optimize", "fake.optimizer", PluginExecutionError),
        ("evaluate", "fake.simulator", PluginExecutionError),
    ],
)
def test_direct_errors_are_chained_with_innermost_context(
    tmp_path, stage, plugin_id, error_type
):
    marker = FileNotFoundError("external input absent")
    faults = Faults(stage, marker)
    experiment = Experiment(config(tmp_path), registry(faults))
    with pytest.raises(error_type) as captured:
        experiment.run()
    error = captured.value
    assert error.plugin_id == plugin_id
    assert error.stage == ("configure" if ".configure" in stage else stage)
    assert error.original_type == "FileNotFoundError"
    assert error.__cause__ is marker
    assert "external input absent" in str(error)
    assert experiment.status is ExperimentStatus.FAILED
    assert not (tmp_path / "output").exists()


def test_direct_failure_after_one_evaluation_does_not_promise_partial_output(tmp_path):
    faults = Faults("evaluate", at=2)
    experiment = Experiment(config(tmp_path), registry(faults))
    with pytest.raises(PluginExecutionError):
        experiment.run()
    assert faults.calls["evaluate"] == 2
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize(
    "stage,expected_records,expected_predictions,category",
    [
        ("surrogate.configure", 0, 0, ConfigurationError),
        ("fit", 3, 0, PluginExecutionError),
        ("optimize", 3, 0, PluginExecutionError),
        ("predict", 3, 1, PluginExecutionError),
        ("optimizer.configure", 3, 0, ConfigurationError),
    ],
)
def test_assisted_fatal_errors_keep_observations_and_chain(
    tmp_path, stage, expected_records, expected_predictions, category
):
    faults = Faults(stage, at=2 if stage in {"predict", "optimizer.configure"} else 1)
    result = Experiment(config(tmp_path, True), registry(faults)).run()
    assert result.status is ExperimentStatus.FAILED
    assert len(result.records) == expected_records
    assert len(result.predictions) == expected_predictions
    error = result.raw_result.errors[-1]
    assert isinstance(error, category)
    assert error.__cause__ is faults.error
    assert error.original_type == "ArithmeticError"
    data = json.loads((tmp_path / "output/metadata.json").read_text())
    assert data["error_details"] == error.as_dict()
    assert (tmp_path / "output/predictions.json").exists()
    assert (tmp_path / "output/evaluation_records.json").exists() == bool(
        expected_records
    )
    if expected_records:
        assert result.best_record in result.records


def test_assisted_simulator_failure_can_continue_and_is_never_success(tmp_path):
    faults = Faults("evaluate", KeyError("bad simulation"))
    result = Experiment(config(tmp_path, True), registry(faults)).run()
    assert result.status is ExperimentStatus.COMPLETED
    assert faults.calls["evaluate"] == len(result.records) == 5
    failed = result.records[0]
    assert failed.status.value == "failed"
    assert failed.metadata["error_details"]["stage"] == "evaluate"
    assert failed.metadata["error_details"]["plugin_id"] == "fake.simulator"
    assert failed.metadata["error_details"]["original_type"] == "KeyError"
    assert result.raw_result.errors[0].__cause__ is faults.error
    assert result.best_record.status.value == "success"


@pytest.mark.parametrize("wrong_type", [False, True])
def test_runtime_lookup_configuration_context(tmp_path, wrong_type):
    reg = registry(Faults()) if wrong_type else PluginRegistry()
    cfg = config(tmp_path)
    if wrong_type:
        cfg.optimizer.plugin = "fake.simulator"
    with pytest.raises(ConfigurationError) as captured:
        Experiment(cfg, reg).run()
    error = captured.value
    assert error.stage == "lookup"
    assert error.plugin_id == cfg.optimizer.plugin
    assert isinstance(error.__cause__, TypeError if wrong_type else MissingPluginError)


def test_runtime_checkable_does_not_validate_signatures(tmp_path):
    class WrongSignature(Optimizer):
        def optimize(self):
            return None

    plugin = WrongSignature(Faults())
    assert isinstance(plugin, OptimizerPlugin)
    reg = PluginRegistry()
    reg.register(plugin)
    reg.register(Simulator(Faults()))
    with pytest.raises(PluginExecutionError) as captured:
        Experiment(config(tmp_path), reg).run()
    assert captured.value.stage == "optimize"
    assert isinstance(captured.value.__cause__, TypeError)


@pytest.mark.parametrize("signal", [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize(
    "stage",
    [
        "optimizer.configure",
        "evaluate",
        "optimize",
        "surrogate.configure",
        "fit",
        "predict",
    ],
)
def test_control_signals_are_not_plugin_errors(tmp_path, signal, stage):
    faults = Faults(stage, signal())
    with pytest.raises(signal):
        Experiment(
            config(tmp_path, stage in {"surrogate.configure", "fit", "predict"}),
            registry(faults),
        ).run()
    assert not (tmp_path / "output").exists()


def test_missing_yaml_is_configuration_error_with_cause(tmp_path):
    with pytest.raises(ConfigurationError) as captured:
        Experiment.from_config(tmp_path / "missing.yaml")
    assert captured.value.stage == "load_config"
    assert isinstance(captured.value.__cause__, FileNotFoundError)


def test_output_error_keeps_cause_and_does_not_claim_atomic_writes(
    tmp_path, monkeypatch
):
    original = Path.write_text
    marker = PermissionError("manifest denied")

    def fail_manifest(path, *args, **kwargs):
        if path.name == "manifest.json":
            raise marker
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_manifest)
    experiment = Experiment(config(tmp_path), registry(Faults()))
    with pytest.raises(OutputError) as captured:
        experiment.run()
    assert captured.value.__cause__ is marker
    assert captured.value.stage == "write_results:manifest.json"
    assert captured.value.plugin_id is None
    assert experiment.status is ExperimentStatus.FAILED
    assert (tmp_path / "output/evaluation_records.json").exists()
    assert not (tmp_path / "output/manifest.json").exists()


@pytest.mark.parametrize("stage", ["evaluate", "optimizer.configure", "optimize"])
def test_cli_external_file_error_is_not_missing_configuration(
    tmp_path, monkeypatch, stage
):
    cfg = config(tmp_path)
    path = tmp_path / "experiment.yaml"
    path.write_text(yaml.safe_dump(cfg.model_dump(mode="json")))
    monkeypatch.setattr(
        cli,
        "_plugin_registry",
        registry(Faults(stage, FileNotFoundError("weather.csv missing"))),
    )
    result = CliRunner().invoke(cli.app, ["run", str(path)])
    assert result.exit_code == 1
    assert "Configuration file not found" not in result.output
    assert "weather.csv missing" in result.output
    assert "FileNotFoundError" in result.output
    assert (
        "fake.simulator" in result.output
        if stage == "evaluate"
        else "fake.optimizer" in result.output
    )


def test_cli_output_failure_has_nonzero_exit_and_output_context(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    path = tmp_path / "experiment.yaml"
    path.write_text(yaml.safe_dump(cfg.model_dump(mode="json")))
    monkeypatch.setattr(cli, "_plugin_registry", registry(Faults()))
    original = Path.write_text

    def fail_output(path, *args, **kwargs):
        if path.name == "metadata.json":
            raise FileNotFoundError("output volume missing")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_output)
    result = CliRunner().invoke(cli.app, ["run", str(path)])
    assert result.exit_code == 1
    assert "Output error" in result.output
    assert "write_results:metadata.json" in result.output
    assert "FileNotFoundError" in result.output
    assert "Configuration file not found" not in result.output


@pytest.mark.parametrize("bad", ["object", "nan", "prediction", "wrong_names"])
@pytest.mark.parametrize("assisted", [False, True])
def test_invalid_simulator_results_never_become_success(tmp_path, bad, assisted):
    class Invalid(Simulator):
        def evaluate(self, solution):
            if bad == "object":
                return object()
            if bad == "wrong_names":
                return EvaluationRecord(Solution(solution.values), {"other": 1.0})
            return EvaluationRecord(
                solution,
                {"score": float("nan") if bad == "nan" else 1.0},
                metadata={"evaluation_kind": "prediction"}
                if bad == "prediction"
                else {},
            )

    reg = PluginRegistry()
    faults = Faults()
    for plugin in (Optimizer(faults), Invalid(faults), Surrogate(faults)):
        reg.register(plugin)
    experiment = Experiment(config(tmp_path, assisted), reg)
    if assisted:
        result = experiment.run()
        assert result.status is ExperimentStatus.FAILED
        assert all(r.status.value == "failed" for r in result.records)
        assert result.best_record is None
    else:
        with pytest.raises(PluginExecutionError) as captured:
            experiment.run()
        assert captured.value.stage == "evaluate"
        assert isinstance(captured.value.__cause__, ValueError)


@pytest.mark.parametrize("signal", [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("stage", ["evaluate", "optimize"])
def test_assisted_controls_propagate_without_failed_records(tmp_path, signal, stage):
    faults = Faults(stage, signal())
    with pytest.raises(signal):
        Experiment(config(tmp_path, True), registry(faults)).run()
    assert not (tmp_path / "output").exists()


def test_direct_invalid_optimizer_record_without_evaluator_is_rejected(tmp_path):
    class InvalidOptimizer(Optimizer):
        def optimize(self, problem, evaluator):
            return EvaluationRecord(
                Solution({"x": 0.1}, problem), {"score": float("nan")}
            )

    faults = Faults()
    reg = PluginRegistry()
    reg.register(InvalidOptimizer(faults))
    reg.register(Simulator(faults))
    with pytest.raises(PluginExecutionError) as captured:
        Experiment(config(tmp_path), reg).run()
    assert captured.value.stage == "optimize"
    assert captured.value.plugin_id == "fake.optimizer"
    assert isinstance(captured.value.__cause__, ValueError)
    assert "evaluate" not in faults.calls


def test_invalid_prediction_retains_only_real_observations(tmp_path):
    class InvalidSurrogate(Surrogate):
        def predict(self, solution):
            return object()

    faults = Faults()
    reg = PluginRegistry()
    for plugin in (Optimizer(faults), Simulator(faults), InvalidSurrogate(faults)):
        reg.register(plugin)
    result = Experiment(config(tmp_path, True), reg).run()
    assert result.status is ExperimentStatus.FAILED
    assert len(result.records) == 3
    assert result.predictions == ()
    assert result.reproducibility_metadata["error_details"]["stage"] == "predict"
    assert isinstance(result.raw_result.errors[-1].__cause__, ValueError)


def test_directory_creation_error_is_output_error(tmp_path):
    marker = tmp_path / "output"
    marker.write_text("already a file")
    with pytest.raises(OutputError) as captured:
        Experiment(config(tmp_path), registry(Faults())).run()
    assert captured.value.stage == "create_output_directory"
    assert isinstance(captured.value.__cause__, FileExistsError)


def test_cli_structurally_wrong_plugin_has_lookup_context(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    cfg.optimizer.plugin = "fake.simulator"
    path = tmp_path / "experiment.yaml"
    path.write_text(yaml.safe_dump(cfg.model_dump(mode="json")))
    monkeypatch.setattr(cli, "_plugin_registry", registry(Faults()))
    result = CliRunner().invoke(cli.app, ["run", str(path)])
    assert result.exit_code == 1
    assert "Plugin lookup failed" in result.output
    assert "fake.simulator" in result.output
    assert "TypeError" in result.output
