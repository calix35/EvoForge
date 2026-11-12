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
    OptimizationResult,
    Problem,
    Solution,
    VariableType,
)
from evoforge.errors import ConfigurationError, PluginExecutionError, error_context
from evoforge.plugins import (
    OptimizerPlugin,
    PluginRegistry,
    SimulatorPlugin,
    SurrogatePlugin,
)

from .evaluation import SimulatorEvaluator, validate_record
from .provenance import collect_provenance
from .surrogate import SurrogateWorkflow


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
    predictions: tuple[EvaluationRecord, ...] = ()
    best_record: EvaluationRecord | None = None
    non_dominated_records: tuple[EvaluationRecord, ...] = ()


class Experiment:
    """Minimal orchestrator for validated EvoForge experiment configurations."""

    def __init__(
        self,
        config: ExperimentConfig,
        registry: PluginRegistry | None = None,
    ) -> None:
        self.config = config
        self.registry = registry if registry is not None else PluginRegistry()
        self.status = ExperimentStatus.CREATED

    @classmethod
    def from_config(
        cls,
        path: str | Path,
        registry: PluginRegistry | None = None,
    ) -> Experiment:
        """Create an experiment from a YAML configuration file."""

        with error_context(ConfigurationError, "load_config"):
            config = load_experiment_config(path)
        return cls(config=config, registry=registry)

    def run(self) -> ExperimentResult:
        """Run the minimal plugin-backed orchestration workflow."""

        self.status = ExperimentStatus.RUNNING

        try:
            with error_context(ConfigurationError, "build_problem"):
                problem = _build_problem(self.config.problem)
            optimizer = self._lookup(self.config.optimizer.plugin, OptimizerPlugin)
            with error_context(
                ConfigurationError, "configure", self.config.optimizer.plugin
            ):
                optimizer.configure(self.config.optimizer)

            evaluator = self._build_evaluator()
            metadata = self._reproducibility_metadata()
            predictions = None
            non_dominated_records = None
            best_record = None
            failed = False
            used_plugins = {"optimizer": optimizer, "simulator": evaluator}
            if self.config.surrogate.enabled:
                surrogate = self._lookup(self.config.surrogate.plugin, SurrogatePlugin)
                used_plugins["surrogate"] = surrogate
                workflow = SurrogateWorkflow(
                    self.config, problem, optimizer, evaluator, surrogate
                ).execute()
                raw_result = workflow
                records = tuple(workflow.records)
                predictions = tuple(workflow.predictions)
                best_record = workflow.best_record
                failed = workflow.failed
                metadata.update(workflow.metadata)
            else:
                with error_context(
                    PluginExecutionError, "optimize", self.config.optimizer.plugin
                ):
                    raw_result = optimizer.optimize(
                        problem, SimulatorEvaluator(evaluator)
                    )
                    records = _extract_records(raw_result)
                    for record in records:
                        validate_record(
                            record, Solution(record.solution.values, problem)
                        )
                if isinstance(raw_result, OptimizationResult):
                    metadata.update(raw_result.metadata)
                    non_dominated_records = raw_result.non_dominated_records
            metadata["provenance"] = collect_provenance(
                self.config, used_plugins, metadata, records
            )
            artifacts = OutputManager(self.config.outputs.directory).save_run_outputs(
                config=self.config,
                metadata=metadata,
                records=records,
                predictions=predictions,
                non_dominated_records=non_dominated_records,
            )
        except Exception:
            self.status = ExperimentStatus.FAILED
            raise

        self.status = ExperimentStatus.FAILED if failed else ExperimentStatus.COMPLETED
        return ExperimentResult(
            experiment_id=self.config.experiment.name,
            status=self.status,
            output_directory=self.config.outputs.directory,
            reproducibility_metadata=metadata,
            artifact_paths=artifacts.as_dict(),
            records=records,
            raw_result=raw_result,
            predictions=predictions or (),
            best_record=best_record,
            non_dominated_records=non_dominated_records or (),
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
            with error_context(ConfigurationError, "build_evaluator"):
                raise NotImplementedError(msg)

        simulator_config = self.config.evaluator.simulator
        if simulator_config is None:
            msg = "Simulator evaluator requires a simulator configuration."
            with error_context(ConfigurationError, "build_evaluator"):
                raise ValueError(msg)

        simulator = self._lookup(simulator_config.plugin, SimulatorPlugin)
        with error_context(ConfigurationError, "configure", simulator_config.plugin):
            simulator.configure(simulator_config)
        return simulator

    def _lookup(self, plugin_id, contract):
        with error_context(ConfigurationError, "lookup", plugin_id):
            return self.registry.get(plugin_id, contract)


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
    if isinstance(result, Dataset | OptimizationResult):
        return result.records
    if isinstance(result, list | tuple) and all(
        isinstance(item, EvaluationRecord) for item in result
    ):
        return tuple(result)
    return ()
