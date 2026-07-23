import importlib
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from evoforge.domain import EvaluationRecord, Problem, Solution
from evoforge.plugins import PluginRegistry

cli_main = importlib.import_module("evoforge.cli.main")
runner = CliRunner()


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


@pytest.fixture(autouse=True)
def reset_cli_registry() -> None:
    cli_main._plugin_registry = None


def valid_config_data(output_directory: Path) -> dict[str, Any]:
    return {
        "experiment": {"name": "cli_run", "seed": 42},
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
        "outputs": {"directory": str(output_directory)},
    }


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def make_registry() -> PluginRegistry:
    registry = PluginRegistry()
    registry.register(FakeOptimizer())
    registry.register(FakeSimulator())
    return registry


def _sample_value(variable: Any) -> Any:
    if variable.values:
        return variable.values[0]
    if variable.bounds:
        return variable.bounds[0]
    return 0


def test_cli_help_works() -> None:
    result = runner.invoke(cli_main.app, ["--help"])

    assert result.exit_code == 0
    assert "run" in result.output


def test_invalid_configuration_fails_before_execution(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.yaml"
    data = valid_config_data(tmp_path / "outputs")
    del data["problem"]
    write_yaml(config_path, data)

    result = runner.invoke(cli_main.app, ["run", str(config_path)])

    assert result.exit_code == 1
    assert "Configuration validation failed" in result.output
    assert "problem" in result.output


def test_malformed_yaml_produces_helpful_error(tmp_path: Path) -> None:
    config_path = tmp_path / "malformed.yaml"
    config_path.write_text("experiment: [unterminated\n", encoding="utf-8")

    result = runner.invoke(cli_main.app, ["run", str(config_path)])

    assert result.exit_code == 1
    assert "Invalid YAML" in result.output


def test_missing_configuration_file_produces_helpful_error(tmp_path: Path) -> None:
    config_path = tmp_path / "missing.yaml"

    result = runner.invoke(cli_main.app, ["run", str(config_path)])

    assert result.exit_code == 1
    assert "Configuration file not found" in result.output


def test_run_command_works_with_fake_registered_plugins(tmp_path: Path) -> None:
    output_directory = tmp_path / "outputs"
    config_path = tmp_path / "experiment.yaml"
    write_yaml(config_path, valid_config_data(output_directory))
    cli_main._plugin_registry = make_registry()

    result = runner.invoke(cli_main.app, ["run", str(config_path)])

    assert result.exit_code == 0
    assert "Experiment cli_run finished with status completed" in result.output
    assert f"Output directory: {output_directory}" in result.output
    assert (output_directory / "config.json").exists()
    assert (output_directory / "metadata.json").exists()
    assert (output_directory / "evaluation_records.json").exists()
    assert (output_directory / "manifest.json").exists()


def test_missing_plugin_produces_helpful_error(tmp_path: Path) -> None:
    config_path = tmp_path / "experiment.yaml"
    write_yaml(config_path, valid_config_data(tmp_path / "outputs"))

    result = runner.invoke(cli_main.app, ["run", str(config_path)])

    assert result.exit_code == 1
    assert "Plugin lookup failed" in result.output
    assert "fake.optimizer" in result.output
