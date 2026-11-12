"""Local file-based output management for EvoForge experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evoforge.config import ExperimentConfig
from evoforge.domain import EvaluationRecord
from evoforge.errors import OutputError, error_context


@dataclass(frozen=True)
class OutputArtifacts:
    """Paths written for a minimal experiment run."""

    output_directory: Path
    config_path: Path
    metadata_path: Path
    evaluation_records_path: Path | None
    manifest_path: Path
    predictions_path: Path | None = None
    non_dominated_path: Path | None = None

    def as_dict(self) -> dict[str, str | None]:
        """Return artifact paths as strings for public result objects."""

        paths = {
            "output_directory": str(self.output_directory),
            "config": str(self.config_path),
            "metadata": str(self.metadata_path),
            "evaluation_records": (
                str(self.evaluation_records_path)
                if self.evaluation_records_path is not None
                else None
            ),
            "manifest": str(self.manifest_path),
        }
        if self.predictions_path is not None:
            paths["predictions"] = str(self.predictions_path)
        if self.non_dominated_path is not None:
            paths["non_dominated"] = str(self.non_dominated_path)
        return paths


class OutputManager:
    """Manage deterministic local output files for an experiment run."""

    CONFIG_FILENAME = "config.json"
    METADATA_FILENAME = "metadata.json"
    EVALUATION_RECORDS_FILENAME = "evaluation_records.json"
    MANIFEST_FILENAME = "manifest.json"

    def __init__(self, output_directory: str | Path) -> None:
        self.output_directory = Path(output_directory)

    def create_output_directory(self) -> Path:
        """Create the configured output directory if needed."""

        with error_context(OutputError, "create_output_directory"):
            self.output_directory.mkdir(parents=True, exist_ok=True)
        return self.output_directory

    def save_config(self, config: ExperimentConfig) -> Path:
        """Save a validated experiment configuration as JSON."""

        path = self.output_directory / self.CONFIG_FILENAME
        self._write_json(path, config.model_dump(mode="json"))
        return path

    def save_metadata(self, metadata: dict[str, Any]) -> Path:
        """Save reproducibility metadata as JSON."""

        path = self.output_directory / self.METADATA_FILENAME
        self._write_json(path, metadata)
        return path

    def save_evaluation_records(self, records: tuple[EvaluationRecord, ...]) -> Path:
        """Save evaluation records as JSON."""

        path = self.output_directory / self.EVALUATION_RECORDS_FILENAME
        serialized_records = [
            _serialize_evaluation_record(record) for record in records
        ]
        self._write_json(path, serialized_records)
        return path

    def write_manifest(self, artifacts: OutputArtifacts) -> Path:
        """Write a basic artifact manifest."""

        manifest = {
            "output_directory": str(artifacts.output_directory),
            "artifacts": [
                {
                    "name": "config",
                    "path": artifacts.config_path.name,
                    "kind": "configuration",
                },
                {
                    "name": "metadata",
                    "path": artifacts.metadata_path.name,
                    "kind": "reproducibility_metadata",
                },
            ],
        }
        if artifacts.evaluation_records_path is not None:
            manifest["artifacts"].append(
                {
                    "name": "evaluation_records",
                    "path": artifacts.evaluation_records_path.name,
                    "kind": "evaluation_records",
                }
            )
        if artifacts.predictions_path is not None:
            manifest["artifacts"].append(
                {
                    "name": "predictions",
                    "path": artifacts.predictions_path.name,
                    "kind": "unvalidated_predictions",
                }
            )
        if artifacts.non_dominated_path is not None:
            manifest["artifacts"].append(
                {
                    "name": "non_dominated",
                    "path": artifacts.non_dominated_path.name,
                    "kind": "observed_non_dominated_records",
                }
            )

        path = self.output_directory / self.MANIFEST_FILENAME
        self._write_json(path, manifest)
        return path

    @error_context(OutputError, "write_results")
    def save_run_outputs(
        self,
        config: ExperimentConfig,
        metadata: dict[str, Any],
        records: tuple[EvaluationRecord, ...] = (),
        predictions: tuple[EvaluationRecord, ...] | None = None,
        non_dominated_records: tuple[EvaluationRecord, ...] | None = None,
    ) -> OutputArtifacts:
        """Create the output directory and save standard run artifacts."""

        output_directory = self.create_output_directory()
        config_path = self.save_config(config)
        metadata_path = self.save_metadata(metadata)
        records_path = self.save_evaluation_records(records) if records else None
        manifest_path = output_directory / self.MANIFEST_FILENAME
        predictions_path = None
        non_dominated_path = None
        if non_dominated_records is not None:
            non_dominated_path = output_directory / "non_dominated.json"
            self._write_json(
                non_dominated_path,
                [
                    _serialize_evaluation_record(record)
                    for record in non_dominated_records
                ],
            )
        if predictions is not None:
            predictions_path = output_directory / "predictions.json"
            self._write_json(
                predictions_path,
                [_serialize_evaluation_record(record) for record in predictions],
            )
        artifacts = OutputArtifacts(
            output_directory=output_directory,
            config_path=config_path,
            metadata_path=metadata_path,
            evaluation_records_path=records_path,
            manifest_path=manifest_path,
            predictions_path=predictions_path,
            non_dominated_path=non_dominated_path,
        )
        self.write_manifest(artifacts)
        return artifacts

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        with error_context(OutputError, f"write_results:{path.name}"):
            path.write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )


def _serialize_evaluation_record(record: EvaluationRecord) -> dict[str, Any]:
    return {
        "solution": {
            "problem": record.solution.problem.name
            if record.solution.problem is not None
            else None,
            "values": record.solution.values,
            "metadata": record.solution.metadata,
        },
        "objective_values": record.objective_values,
        "constraint_values": record.constraint_values,
        "metadata": record.metadata,
        "source": record.source,
        "status": record.status.value,
        "created_at": record.created_at.isoformat(),
    }
