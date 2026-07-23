from pathlib import Path
from typing import Any

import pytest
import yaml

from evoforge.config import ExperimentConfig
from evoforge.core import Experiment, ExperimentResult, ExperimentStatus
from evoforge.domain import EvaluationRecord, Problem, Solution
from evoforge.plugins import MissingPluginError, PluginRegistry


class FakeOptimizer:
    plugin_id = "fake.optimizer"

    def configure(self, config: object) -> None:
        self.config = config

    def optimize(self, problem: Problem, evaluator: object) -> EvaluationRecord:
        solution = Solution(
            problem=problem,
            values={
                variable.name: _sample_value(variable) for variable in problem.variables
            },
        )
        return evaluator.evaluate(solution)


class FakeSimulator:
    plugin_id = "fake.simulator"

    def configure(self, config: object) -> None:
        self.config = config

    def evaluate(self, solution: Solution) -> EvaluationRecord:
        return EvaluationRecord(
            solution=solution,
            objective_values={"score": 1.0},
            source=self.plugin_id,
        )


def valid_config_data(output_directory: str = "results/minimal_run") -> dict[str, Any]:
    return {
        "experiment": {"name": "minimal_run", "seed": 42},
        "problem": {
            "name": "benchmark",
            "type": "single_objective",
            "variables": [
                {"name": "x", "type": "continuous", "bounds": [0.0, 1.0]},
            ],
            "objectives": [
                {"name": "score", "direction": "minimize"},
            ],
        },
        "optimizer": {"plugin": "fake.optimizer"},
        "evaluator": {
            "type": "simulator",
            "simulator": {"plugin": "fake.simulator"},
        },
        "outputs": {"directory": output_directory},
    }


def make_config(output_directory: str = "results/minimal_run") -> ExperimentConfig:
    return ExperimentConfig.model_validate(valid_config_data(output_directory))


def make_registry() -> PluginRegistry:
    registry = PluginRegistry()
    registry.register(FakeOptimizer())
    registry.register(FakeSimulator())
    return registry


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def _sample_value(variable: Any) -> Any:
    if variable.values:
        return variable.values[0]
    if variable.bounds:
        return variable.bounds[0]
    return 0


def test_creating_experiment_from_experiment_config() -> None:
    config = make_config()
    registry = make_registry()

    experiment = Experiment(config=config, registry=registry)

    assert experiment.config is config
    assert experiment.registry is registry
    assert experiment.status is ExperimentStatus.CREATED


def test_creating_experiment_from_yaml_using_from_config(tmp_path: Path) -> None:
    config_path = tmp_path / "experiment.yaml"
    write_yaml(config_path, valid_config_data())
    registry = make_registry()

    experiment = Experiment.from_config(config_path, registry=registry)

    assert experiment.config.experiment.name == "minimal_run"
    assert experiment.registry is registry


def test_running_minimal_workflow_with_fake_optimizer_and_simulator(
    tmp_path: Path,
) -> None:
    experiment = Experiment(
        config=make_config(str(tmp_path / "minimal_run")),
        registry=make_registry(),
    )

    result = experiment.run()

    assert isinstance(result, ExperimentResult)
    assert result.status is ExperimentStatus.COMPLETED
    assert result.experiment_id == "minimal_run"
    assert result.records[0].objective_values == {"score": 1.0}
    assert result.records[0].source == "fake.simulator"


def test_missing_optimizer_plugin_error() -> None:
    registry = PluginRegistry()
    registry.register(FakeSimulator())
    experiment = Experiment(config=make_config(), registry=registry)

    with pytest.raises(MissingPluginError, match="fake.optimizer"):
        experiment.run()

    assert experiment.status is ExperimentStatus.FAILED


def test_result_includes_status_output_directory_and_seed_metadata(
    tmp_path: Path,
) -> None:
    output_directory = tmp_path / "minimal_run"
    experiment = Experiment(
        config=make_config(str(output_directory)),
        registry=make_registry(),
    )

    result = experiment.run()

    assert result.status is ExperimentStatus.COMPLETED
    assert result.output_directory == str(output_directory)
    assert result.reproducibility_metadata["seed"] == 42


def test_run_creates_deterministic_output_artifacts_using_fake_plugins(
    tmp_path: Path,
) -> None:
    output_directory = tmp_path / "minimal_run"
    experiment = Experiment(
        config=make_config(str(output_directory)),
        registry=make_registry(),
    )

    result = experiment.run()

    expected_paths = {
        "output_directory": str(output_directory),
        "config": str(output_directory / "config.json"),
        "metadata": str(output_directory / "metadata.json"),
        "evaluation_records": str(output_directory / "evaluation_records.json"),
        "manifest": str(output_directory / "manifest.json"),
    }
    assert result.artifact_paths == expected_paths
    for path in expected_paths.values():
        assert path is not None
        assert Path(path).exists()

    manifest = yaml.safe_load((output_directory / "manifest.json").read_text())
    assert [artifact["name"] for artifact in manifest["artifacts"]] == [
        "config",
        "metadata",
        "evaluation_records",
    ]
