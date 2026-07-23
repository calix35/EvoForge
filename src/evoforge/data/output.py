"""Local file-based output management for EvoForge experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evoforge.config import ExperimentConfig
from evoforge.domain import EvaluationRecord


@dataclass(frozen=True)
class OutputArtifacts:
    """Paths written for a minimal experiment run."""

    output_directory: Path
    config_path: Path
    metadata_path: Path
    evaluation_records_path: Path | None
    manifest_path: Path

    def as_dict(self) -> dict[str, str | None]:
        """Return artifact paths as strings for public result objects."""

        return {
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

        path = self.output_directory / self.MANIFEST_FILENAME
        self._write_json(path, manifest)
        return path

    def save_run_outputs(
        self,
        config: ExperimentConfig,
        metadata: dict[str, Any],
        records: tuple[EvaluationRecord, ...] = (),
    ) -> OutputArtifacts:
        """Create the output directory and save standard run artifacts."""

        output_directory = self.create_output_directory()
        config_path = self.save_config(config)
        metadata_path = self.save_metadata(metadata)
        records_path = self.save_evaluation_records(records) if records else None
        manifest_path = output_directory / self.MANIFEST_FILENAME
        artifacts = OutputArtifacts(
            output_directory=output_directory,
            config_path=config_path,
            metadata_path=metadata_path,
            evaluation_records_path=records_path,
            manifest_path=manifest_path,
        )
        self.write_manifest(artifacts)
        return artifacts

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
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
