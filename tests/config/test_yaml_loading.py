from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from evoforge.config import ExperimentConfig, load_experiment_config


def valid_config_data() -> dict:
    return {
        "experiment": {
            "name": "aquacrop_nsga2_baseline",
            "description": "Baseline simulation-based optimization experiment.",
            "seed": 42,
        },
        "problem": {
            "name": "irrigation_management",
            "type": "multi_objective",
            "variables": [
                {
                    "name": "irrigation_day_1",
                    "type": "continuous",
                    "bounds": [0.0, 40.0],
                    "unit": "mm",
                }
            ],
            "objectives": [
                {"name": "yield", "direction": "maximize"},
                {"name": "water_use", "direction": "minimize"},
            ],
        },
        "optimizer": {
            "plugin": "pymoo.nsga2",
            "parameters": {"population_size": 100, "generations": 200},
        },
        "evaluator": {
            "type": "simulator",
            "simulator": {
                "plugin": "aquacrop_ospy",
                "parameters": {"weather_file": "data/weather.csv"},
            },
        },
        "outputs": {"directory": "results/aquacrop_nsga2_baseline"},
    }


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def test_valid_yaml_loading(tmp_path: Path) -> None:
    config_path = tmp_path / "experiment.yaml"
    write_yaml(config_path, valid_config_data())

    config = load_experiment_config(config_path)

    assert isinstance(config, ExperimentConfig)
    assert config.experiment.name == "aquacrop_nsga2_baseline"
    assert config.problem.variables[0].type == "continuous"
    assert config.optimizer.parameters["generations"] == 200


def test_missing_required_fields(tmp_path: Path) -> None:
    data = valid_config_data()
    del data["problem"]
    config_path = tmp_path / "missing_problem.yaml"
    write_yaml(config_path, data)

    with pytest.raises(ValidationError, match="problem"):
        load_experiment_config(config_path)


def test_invalid_objective_direction(tmp_path: Path) -> None:
    data = valid_config_data()
    data["problem"]["objectives"][0]["direction"] = "increase"
    config_path = tmp_path / "invalid_objective.yaml"
    write_yaml(config_path, data)

    with pytest.raises(ValidationError, match="direction"):
        load_experiment_config(config_path)


def test_invalid_variable_type(tmp_path: Path) -> None:
    data = valid_config_data()
    data["problem"]["variables"][0]["type"] = "decimal"
    config_path = tmp_path / "invalid_variable.yaml"
    write_yaml(config_path, data)

    with pytest.raises(ValidationError, match="type"):
        load_experiment_config(config_path)


def test_default_values_where_appropriate(tmp_path: Path) -> None:
    config_path = tmp_path / "defaults.yaml"
    write_yaml(config_path, valid_config_data())

    config = load_experiment_config(config_path)

    assert config.problem.constraints == []
    assert config.surrogate.enabled is False
    assert config.surrogate.parameters == {}
    assert config.dataset.enabled is True
    assert config.dataset.path is None
    assert config.dataset.format == "csv"
    assert config.outputs.save_evaluations is True
    assert config.outputs.save_metadata is True
    assert config.outputs.save_figures is False
    assert config.analysis.enabled is False
    assert config.analysis.methods == []
    assert config.visualization.enabled is False
    assert config.visualization.plots == []
    assert config.report.enabled is False
    assert config.report.format == "markdown"


def test_simulator_evaluator_requires_simulator_config(tmp_path: Path) -> None:
    data = valid_config_data()
    del data["evaluator"]["simulator"]
    config_path = tmp_path / "missing_simulator.yaml"
    write_yaml(config_path, data)

    with pytest.raises(ValidationError, match="simulator"):
        load_experiment_config(config_path)


def test_enabled_surrogate_requires_plugin(tmp_path: Path) -> None:
    data = valid_config_data()
    data["surrogate"] = {"enabled": True}
    config_path = tmp_path / "enabled_surrogate_without_plugin.yaml"
    write_yaml(config_path, data)

    with pytest.raises(ValidationError, match="plugin"):
        load_experiment_config(config_path)


def test_categorical_variable_requires_values(tmp_path: Path) -> None:
    data = valid_config_data()
    data["problem"]["variables"][0] = {
        "name": "management_strategy",
        "type": "categorical",
    }
    config_path = tmp_path / "categorical_without_values.yaml"
    write_yaml(config_path, data)

    with pytest.raises(ValidationError, match="categorical"):
        load_experiment_config(config_path)
