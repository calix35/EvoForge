from pathlib import Path

import yaml
from typer.testing import CliRunner

from evoforge.adapters.examples import (
    ExampleSphereSimulator,
    register_builtin_example_plugins,
)
from evoforge.cli.main import app
from evoforge.config import ExperimentConfig, SimulatorConfig
from evoforge.core import Experiment, ExperimentStatus
from evoforge.domain import (
    DecisionVariable,
    EvaluationRecord,
    Objective,
    ObjectiveDirection,
    Problem,
    Solution,
    VariableType,
)
from evoforge.plugins import OptimizerPlugin, PluginRegistry, SimulatorPlugin


def load_example_config(output_directory: Path) -> ExperimentConfig:
    data = yaml.safe_load(
        Path("examples/sphere_random_search.yaml").read_text(encoding="utf-8")
    )
    data["outputs"]["directory"] = str(output_directory)
    return ExperimentConfig.model_validate(data)


def test_random_search_plugin_registration() -> None:
    registry = register_builtin_example_plugins()

    optimizer = registry.get("example.random_search", OptimizerPlugin)
    simulator = registry.get("example.sphere", SimulatorPlugin)

    assert optimizer.plugin_id == "example.random_search"
    assert simulator.plugin_id == "example.sphere"


def test_register_builtin_example_plugins_uses_existing_registry() -> None:
    registry = PluginRegistry()

    result = register_builtin_example_plugins(registry)

    assert result is registry
    assert "example.random_search" in registry
    assert "example.sphere" in registry


def test_sphere_simulator_evaluation() -> None:
    problem = Problem(
        name="sphere_benchmark",
        variables=(
            DecisionVariable(
                name="x1",
                type=VariableType.CONTINUOUS,
                bounds=(-5.0, 5.0),
            ),
            DecisionVariable(
                name="x2",
                type=VariableType.CONTINUOUS,
                bounds=(-5.0, 5.0),
            ),
        ),
        objectives=(Objective(name="sphere", direction=ObjectiveDirection.MINIMIZE),),
    )
    solution = Solution(problem=problem, values={"x1": 3.0, "x2": 4.0})
    simulator = ExampleSphereSimulator()
    simulator.configure(SimulatorConfig(plugin="example.sphere"))

    record = simulator.evaluate(solution)

    assert record.objective_values == {"sphere": 25.0}
    assert record.source == "example.sphere"


def test_running_experiment_end_to_end_with_example_plugins(tmp_path: Path) -> None:
    output_directory = tmp_path / "sphere_run"
    experiment = Experiment(
        config=load_example_config(output_directory),
        registry=register_builtin_example_plugins(),
    )

    result = experiment.run()

    assert result.status is ExperimentStatus.COMPLETED
    assert result.experiment_id == "sphere_random_search"
    assert len(result.records) == 5
    assert all(isinstance(record, EvaluationRecord) for record in result.records)
    assert all("sphere" in record.objective_values for record in result.records)


def test_output_artifacts_are_created(tmp_path: Path) -> None:
    output_directory = tmp_path / "sphere_run"
    experiment = Experiment(
        config=load_example_config(output_directory),
        registry=register_builtin_example_plugins(),
    )

    result = experiment.run()

    assert Path(result.artifact_paths["config"]).exists()
    assert Path(result.artifact_paths["metadata"]).exists()
    assert Path(result.artifact_paths["evaluation_records"]).exists()
    assert Path(result.artifact_paths["manifest"]).exists()


def test_cli_runs_with_sphere_random_search_example(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    runner = CliRunner()
    example_path = Path("examples/sphere_random_search.yaml").resolve()

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["run", str(example_path)])

    assert result.exit_code == 0
    assert "Experiment sphere_random_search finished with status completed" in (
        result.output
    )
    assert Path("results/sphere_random_search/config.json").exists()
    assert Path("results/sphere_random_search/metadata.json").exists()
    assert Path("results/sphere_random_search/evaluation_records.json").exists()
    assert Path("results/sphere_random_search/manifest.json").exists()


def test_random_search_evaluates_mixed_supported_variables() -> None:
    config = load_example_config(Path("unused"))
    config.optimizer.parameters["iterations"] = 3
    problem = Problem(
        name="mixed",
        variables=(
            DecisionVariable("x", VariableType.CONTINUOUS, bounds=(0.0, 1.0)),
            DecisionVariable("i", VariableType.INTEGER, bounds=(1.0, 3.0)),
            DecisionVariable("b", VariableType.BINARY),
            DecisionVariable("c", VariableType.CATEGORICAL, values=("a", "b")),
            DecisionVariable("d", VariableType.DISCRETE, values=(10, 20)),
        ),
        objectives=(Objective("sphere", ObjectiveDirection.MINIMIZE),),
    )
    optimizer = register_builtin_example_plugins().get(
        "example.random_search",
        OptimizerPlugin,
    )
    simulator = ExampleSphereSimulator()
    optimizer.configure(config.optimizer)
    simulator.configure(SimulatorConfig(plugin="example.sphere"))

    records = optimizer.optimize(problem, simulator)

    assert len(records) == 3
    assert all(
        tuple(record.solution.values) == problem.variable_names for record in records
    )
