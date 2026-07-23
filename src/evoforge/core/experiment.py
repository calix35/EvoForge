"""Minimal Experiment runtime for EvoForge."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from evoforge.config import (
    ConstraintConfig,
    ExperimentConfig,
    ObjectiveConfig,
    ProblemConfig,
    VariableConfig,
    load_experiment_config,
)
from evoforge.data import OutputManager
from evoforge.domain import (
    Constraint,
    Dataset,
    DecisionVariable,
    EvaluationRecord,
    Objective,
    ObjectiveDirection,
    Problem,
    VariableType,
)
from evoforge.plugins import OptimizerPlugin, PluginRegistry, SimulatorPlugin


class ExperimentStatus(StrEnum):
    """Minimal lifecycle states for an EvoForge experiment."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ExperimentResult:
    """Minimal result returned by an experiment run."""

    experiment_id: str
    status: ExperimentStatus
    output_directory: str
    reproducibility_metadata: dict[str, Any] = field(default_factory=dict)
    artifact_paths: dict[str, str | None] = field(default_factory=dict)
    records: tuple[EvaluationRecord, ...] = field(default_factory=tuple)
    raw_result: Any | None = None


class Experiment:
    """Minimal orchestrator for validated EvoForge experiment configurations."""

    def __init__(
        self,
        config: ExperimentConfig,
        registry: PluginRegistry | None = None,
    ) -> None:
        self.config = config
        self.registry = registry or PluginRegistry()
        self.status = ExperimentStatus.CREATED

    @classmethod
    def from_config(
        cls,
        path: str | Path,
        registry: PluginRegistry | None = None,
    ) -> Experiment:
        """Create an experiment from a YAML configuration file."""

        return cls(config=load_experiment_config(path), registry=registry)

    def run(self) -> ExperimentResult:
        """Run the minimal plugin-backed orchestration workflow."""

        self.status = ExperimentStatus.RUNNING

        try:
            problem = _build_problem(self.config.problem)
            optimizer = self.registry.get(
                self.config.optimizer.plugin,
                OptimizerPlugin,
            )
            optimizer.configure(self.config.optimizer)

            evaluator = self._build_evaluator()
            raw_result = optimizer.optimize(problem, evaluator)
            records = _extract_records(raw_result)
            metadata = self._reproducibility_metadata()
            artifacts = OutputManager(self.config.outputs.directory).save_run_outputs(
                config=self.config,
                metadata=metadata,
                records=records,
            )
        except Exception:
            self.status = ExperimentStatus.FAILED
            raise

        self.status = ExperimentStatus.COMPLETED
        return ExperimentResult(
            experiment_id=self.config.experiment.name,
            status=self.status,
            output_directory=self.config.outputs.directory,
            reproducibility_metadata=metadata,
            artifact_paths=artifacts.as_dict(),
            records=records,
            raw_result=raw_result,
        )

    def _reproducibility_metadata(self) -> dict[str, Any]:
        simulator_plugin = (
            self.config.evaluator.simulator.plugin
            if self.config.evaluator.simulator is not None
            else None
        )
        return {
            "experiment_id": self.config.experiment.name,
            "seed": self.config.experiment.seed,
            "optimizer_plugin": self.config.optimizer.plugin,
            "evaluator_type": self.config.evaluator.type,
            "simulator_plugin": simulator_plugin,
        }

    def _build_evaluator(self) -> SimulatorPlugin:
        if self.config.evaluator.type != "simulator":
            msg = (
                "The minimal Experiment runtime only supports simulator "
                "evaluators in this initial implementation."
            )
            raise NotImplementedError(msg)

        simulator_config = self.config.evaluator.simulator
        if simulator_config is None:
            msg = "Simulator evaluator requires a simulator configuration."
            raise ValueError(msg)

        simulator = self.registry.get(simulator_config.plugin, SimulatorPlugin)
        simulator.configure(simulator_config)
        return simulator


def _build_problem(config: ProblemConfig) -> Problem:
    return Problem(
        name=config.name,
        variables=tuple(_build_variable(variable) for variable in config.variables),
        objectives=tuple(
            _build_objective(objective) for objective in config.objectives
        ),
        constraints=tuple(
            _build_constraint(constraint) for constraint in config.constraints
        ),
        metadata={"type": config.type},
    )


def _build_variable(config: VariableConfig) -> DecisionVariable:
    return DecisionVariable(
        name=config.name,
        type=VariableType(config.type),
        bounds=tuple(config.bounds) if config.bounds is not None else None,
        values=tuple(config.values) if config.values is not None else None,
        unit=config.unit,
        metadata=config.metadata,
    )


def _build_objective(config: ObjectiveConfig) -> Objective:
    return Objective(
        name=config.name,
        direction=ObjectiveDirection(config.direction),
    )


def _build_constraint(config: ConstraintConfig) -> Constraint:
    return Constraint(
        name=config.name,
        expression=config.expression,
        metadata=config.parameters,
    )


def _extract_records(result: Any) -> tuple[EvaluationRecord, ...]:
    if isinstance(result, EvaluationRecord):
        return (result,)
    if isinstance(result, Dataset):
        return result.records
    if isinstance(result, list | tuple) and all(
        isinstance(item, EvaluationRecord) for item in result
    ):
        return tuple(result)
    return ()
