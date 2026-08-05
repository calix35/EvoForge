from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from evoforge.adapters.examples import ExampleSphereSimulator
from evoforge.adapters.pymoo import register_pymoo_plugins
from evoforge.adapters.pymoo.plugins import PymooGAOptimizer
from evoforge.cli.main import app
from evoforge.config import ExperimentConfig, OptimizerConfig
from evoforge.core import Experiment, ExperimentStatus
from evoforge.domain import (
    DecisionVariable,
    Objective,
    ObjectiveDirection,
    Problem,
    VariableType,
)
from evoforge.plugins import OptimizerPlugin, PluginRegistry


def load_pymoo_example_config(output_directory: Path) -> ExperimentConfig:
    data = yaml.safe_load(
        Path("examples/sphere_pymoo_ga.yaml").read_text(encoding="utf-8")
    )
    data["outputs"]["directory"] = str(output_directory)
    return ExperimentConfig.model_validate(data)


def make_registry() -> PluginRegistry:
    registry = register_pymoo_plugins()
    registry.register(ExampleSphereSimulator())
    return registry


def test_pymoo_plugin_registration() -> None:
    registry = register_pymoo_plugins()

    plugin = registry.get("pymoo.ga", OptimizerPlugin)

    assert plugin.plugin_id == "pymoo.ga"


def test_pymoo_plugin_configuration() -> None:
    plugin = PymooGAOptimizer()

    plugin.configure(
        OptimizerConfig(
            plugin="pymoo.ga",
            parameters={
                "pop_size": 8,
                "n_evaluations": 16,
                "seed": 123,
                "verbose": True,
            },
        )
    )

    assert plugin.pop_size == 8
    assert plugin.n_evaluations == 16
    assert plugin.seed == 123
    assert plugin.verbose is True


def test_pymoo_rejects_invalid_parameters() -> None:
    plugin = PymooGAOptimizer()

    with pytest.raises(ValueError, match="pop_size must be at least 1"):
        plugin.configure(
            OptimizerConfig(
                plugin="pymoo.ga",
                parameters={"pop_size": 0},
            )
        )


def test_pymoo_successful_execution_on_sphere_example(tmp_path: Path) -> None:
    pytest.importorskip("pymoo")
    experiment = Experiment(
        config=load_pymoo_example_config(tmp_path / "sphere_pymoo_ga"),
        registry=make_registry(),
    )

    result = experiment.run()

    assert result.status is ExperimentStatus.COMPLETED
    assert result.experiment_id == "sphere_pymoo_ga"
    assert len(result.records) >= 40
    assert all("sphere" in record.objective_values for record in result.records)


def test_pymoo_rejects_unsupported_variable_types() -> None:
    problem = Problem(
        name="unsupported",
        variables=(
            DecisionVariable(
                name="category",
                type=VariableType.CATEGORICAL,
                values=("a", "b"),
            ),
        ),
        objectives=(Objective(name="score", direction=ObjectiveDirection.MINIMIZE),),
    )
    plugin = PymooGAOptimizer()
    plugin.configure(OptimizerConfig(plugin="pymoo.ga"))

    with pytest.raises(ValueError, match="continuous and integer variables only"):
        plugin.optimize(problem, ExampleSphereSimulator())


def test_pymoo_missing_dependency_error_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = Problem(
        name="sphere",
        variables=(
            DecisionVariable(
                name="x",
                type=VariableType.CONTINUOUS,
                bounds=(-5.0, 5.0),
            ),
        ),
        objectives=(Objective(name="sphere", direction=ObjectiveDirection.MINIMIZE),),
    )
    plugin = PymooGAOptimizer()
    plugin.configure(OptimizerConfig(plugin="pymoo.ga"))

    real_import = __import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("pymoo"):
            raise ImportError("missing pymoo")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError, match="uv sync --extra pymoo"):
        plugin.optimize(problem, ExampleSphereSimulator())


def test_pymoo_reproducible_behavior_with_fixed_seed(tmp_path: Path) -> None:
    pytest.importorskip("pymoo")
    first = Experiment(
        config=load_pymoo_example_config(tmp_path / "first"),
        registry=make_registry(),
    ).run()
    second = Experiment(
        config=load_pymoo_example_config(tmp_path / "second"),
        registry=make_registry(),
    ).run()

    first_trace = _record_trace(first.records)
    second_trace = _record_trace(second.records)

    assert first_trace == second_trace


def test_cli_runs_with_pymoo_sphere_example(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    pytest.importorskip("pymoo")
    runner = CliRunner()
    example_path = Path("examples/sphere_pymoo_ga.yaml").resolve()

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["run", str(example_path)])

    assert result.exit_code == 0
    assert "Experiment sphere_pymoo_ga finished with status completed" in result.output
    assert Path("results/sphere_pymoo_ga/config.json").exists()
    assert Path("results/sphere_pymoo_ga/metadata.json").exists()
    assert Path("results/sphere_pymoo_ga/evaluation_records.json").exists()
    assert Path("results/sphere_pymoo_ga/manifest.json").exists()


def _record_trace(records: Any) -> list[tuple[dict[str, Any], dict[str, float]]]:
    return [
        (record.solution.values, record.objective_values)
        for record in records
    ]
