"""Typed configuration models for EvoForge experiment definitions."""

from math import isfinite
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvoForgeConfigModel(BaseModel):
    """Base class for strict EvoForge configuration sections."""

    model_config = ConfigDict(extra="forbid")


class MetadataConfig(EvoForgeConfigModel):
    """Top-level experiment metadata."""

    name: str
    description: str | None = None
    seed: int | None = None


class VariableConfig(EvoForgeConfigModel):
    """Decision variable declaration."""

    name: str
    type: Literal[
        "continuous",
        "discrete",
        "categorical",
        "integer",
        "binary",
        "structured",
    ]
    bounds: list[float] | None = None
    values: list[Any] | None = None
    unit: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_domain(self) -> Self:
        """Validate variable metadata according to the declared variable type."""

        if self.type in {"continuous", "integer"}:
            if self.bounds is None or len(self.bounds) != 2:
                msg = f"{self.type} variables require exactly two bounds."
                raise ValueError(msg)

        if self.type in {"categorical", "discrete"}:
            if not self.values:
                msg = f"{self.type} variables require at least one allowed value."
                raise ValueError(msg)

        return self


class ObjectiveConfig(EvoForgeConfigModel):
    """Optimization objective declaration."""

    name: str
    direction: Literal["minimize", "maximize"]


class ConstraintConfig(EvoForgeConfigModel):
    """Problem constraint declaration."""

    name: str
    expression: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ProblemConfig(EvoForgeConfigModel):
    """Optimization problem declaration."""

    name: str
    type: Literal["single_objective", "multi_objective"]
    variables: list[VariableConfig] = Field(min_length=1)
    objectives: list[ObjectiveConfig] = Field(min_length=1)
    constraints: list[ConstraintConfig] = Field(default_factory=list)


class OptimizerConfig(EvoForgeConfigModel):
    """Optimizer plugin selection and parameters."""

    plugin: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class SimulatorConfig(EvoForgeConfigModel):
    """Simulator plugin selection and parameters."""

    plugin: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class EvaluatorConfig(EvoForgeConfigModel):
    """Evaluation provider configuration."""

    type: Literal["simulator", "surrogate", "function", "hybrid"]
    simulator: SimulatorConfig | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_evaluator_source(self) -> Self:
        """Validate required evaluator source configuration."""

        if self.type == "simulator" and self.simulator is None:
            msg = "simulator evaluator requires a simulator configuration."
            raise ValueError(msg)

        return self


class SurrogateWorkflowConfig(EvoForgeConfigModel):
    """Budgets for sequential surrogate-assisted optimization."""

    initial_size: int = Field(ge=2, strict=True)
    real_budget: int = Field(ge=2, strict=True)
    search_budget: int = Field(ge=1, strict=True)
    candidates_per_update: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def validate_sizes(self) -> Self:
        if self.initial_size > self.real_budget:
            raise ValueError("initial_size must not exceed real_budget.")
        if self.candidates_per_update > self.search_budget:
            raise ValueError("candidates_per_update must not exceed search_budget.")
        if self.candidates_per_update > self.real_budget - self.initial_size:
            raise ValueError("candidates_per_update exceeds remaining real budget.")
        return self


class SurrogateConfig(EvoForgeConfigModel):
    """Optional surrogate model configuration."""

    enabled: bool = False
    plugin: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    workflow: SurrogateWorkflowConfig | None = None

    @model_validator(mode="after")
    def validate_enabled_surrogate(self) -> Self:
        """Validate surrogate plugin selection when surrogate use is enabled."""

        if self.enabled and self.plugin is None:
            msg = "enabled surrogate configuration requires a plugin."
            raise ValueError(msg)

        return self


class DatasetConfig(EvoForgeConfigModel):
    """Dataset persistence configuration."""

    enabled: bool = True
    path: str | None = None
    format: Literal["csv", "jsonl", "parquet"] = "csv"


class OutputConfig(EvoForgeConfigModel):
    """Output artifact configuration."""

    directory: str
    save_evaluations: bool = True
    save_metadata: bool = True
    save_figures: bool = False


class AnalysisConfig(EvoForgeConfigModel):
    """Statistical analysis configuration."""

    enabled: bool = False
    methods: list[str] = Field(default_factory=list)


class VisualizationConfig(EvoForgeConfigModel):
    """Visualization configuration."""

    enabled: bool = False
    plots: list[str] = Field(default_factory=list)


class ReportConfig(EvoForgeConfigModel):
    """Report generation configuration."""

    enabled: bool = False
    format: Literal["markdown", "html", "pdf"] = "markdown"


class ExperimentConfig(EvoForgeConfigModel):
    """Validated EvoForge experiment configuration."""

    experiment: MetadataConfig
    problem: ProblemConfig
    optimizer: OptimizerConfig
    evaluator: EvaluatorConfig
    surrogate: SurrogateConfig = Field(default_factory=SurrogateConfig)
    dataset: DatasetConfig = Field(default_factory=DatasetConfig)
    outputs: OutputConfig
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    visualization: VisualizationConfig = Field(default_factory=VisualizationConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)

    @model_validator(mode="after")
    def validate_surrogate_workflow(self) -> Self:
        if not self.surrogate.enabled:
            return self
        if self.surrogate.workflow is None:
            raise ValueError("Enabled surrogate requires workflow budgets.")
        if self.evaluator.type != "simulator":
            raise ValueError("Surrogate workflow requires a simulator evaluator.")
        if (
            self.problem.type != "single_objective"
            or len(self.problem.objectives) != 1
            or self.problem.constraints
        ):
            raise ValueError(
                "Surrogate workflow requires one objective, no constraints."
            )
        for variable in self.problem.variables:
            if (
                variable.type != "continuous"
                or variable.bounds is None
                or not all(isfinite(v) for v in variable.bounds)
                or variable.bounds[0] >= variable.bounds[1]
            ):
                raise ValueError(
                    "Surrogate workflow requires finite, nondegenerate "
                    "continuous bounds."
                )
        return self
