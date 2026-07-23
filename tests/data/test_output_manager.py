import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evoforge.config import ExperimentConfig
from evoforge.data import OutputManager
from evoforge.domain import EvaluationRecord, Solution


def valid_config(output_directory: Path) -> ExperimentConfig:
    return ExperimentConfig.model_validate(
        {
            "experiment": {"name": "data_foundation", "seed": 7},
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
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_output_directory_creation(tmp_path: Path) -> None:
    output_manager = OutputManager(tmp_path / "experiment")

    output_directory = output_manager.create_output_directory()

    assert output_directory.exists()
    assert output_directory.is_dir()


def test_configuration_serialization(tmp_path: Path) -> None:
    config = valid_config(tmp_path / "experiment")
    output_manager = OutputManager(config.outputs.directory)
    output_manager.create_output_directory()

    path = output_manager.save_config(config)

    data = read_json(path)
    assert data["experiment"]["name"] == "data_foundation"
    assert data["outputs"]["directory"] == str(tmp_path / "experiment")


def test_metadata_serialization(tmp_path: Path) -> None:
    output_manager = OutputManager(tmp_path / "experiment")
    output_manager.create_output_directory()

    path = output_manager.save_metadata({"experiment_id": "data_foundation", "seed": 7})

    assert read_json(path) == {"experiment_id": "data_foundation", "seed": 7}


def test_evaluation_record_serialization(tmp_path: Path) -> None:
    output_manager = OutputManager(tmp_path / "experiment")
    output_manager.create_output_directory()
    record = EvaluationRecord(
        solution=Solution(values={"x": 0.5}),
        objective_values={"score": 1.0},
        source="fake.simulator",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    path = output_manager.save_evaluation_records((record,))

    data = read_json(path)
    assert data[0]["solution"]["values"] == {"x": 0.5}
    assert data[0]["objective_values"] == {"score": 1.0}
    assert data[0]["status"] == "success"
    assert data[0]["created_at"] == "2026-01-01T00:00:00+00:00"


def test_artifact_manifest_creation(tmp_path: Path) -> None:
    config = valid_config(tmp_path / "experiment")
    output_manager = OutputManager(config.outputs.directory)
    artifacts = output_manager.save_run_outputs(
        config=config,
        metadata={"experiment_id": "data_foundation", "seed": 7},
        records=(),
    )

    manifest = read_json(artifacts.manifest_path)
    artifact_names = [artifact["name"] for artifact in manifest["artifacts"]]

    assert manifest["output_directory"] == str(tmp_path / "experiment")
    assert artifact_names == ["config", "metadata"]

