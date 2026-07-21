"""Lightweight EvoForge domain model objects."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class VariableType(StrEnum):
    """Supported decision variable types."""

    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    CATEGORICAL = "categorical"
    INTEGER = "integer"
    BINARY = "binary"
    STRUCTURED = "structured"


class ObjectiveDirection(StrEnum):
    """Supported optimization directions."""

    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class EvaluationStatus(StrEnum):
    """Basic status values for evaluation records."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


@dataclass(frozen=True)
class DecisionVariable:
    """A problem input that can be assigned in a solution."""

    name: str
    type: VariableType
    bounds: tuple[float, float] | None = None
    values: tuple[Any, ...] | None = None
    unit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_name(self.name, "Decision variable")
        object.__setattr__(self, "type", VariableType(self.type))

        if self.bounds is not None:
            if len(self.bounds) != 2:
                msg = "Variable bounds must contain exactly two values."
                raise ValueError(msg)
            lower, upper = self.bounds
            if lower > upper:
                msg = "Variable lower bound must be less than or equal to upper bound."
                raise ValueError(msg)
            object.__setattr__(self, "bounds", tuple(self.bounds))

        if self.values is not None and len(self.values) == 0:
            msg = "Variable values must not be empty when provided."
            raise ValueError(msg)
        if self.values is not None:
            object.__setattr__(self, "values", tuple(self.values))

        bounded_types = {VariableType.CONTINUOUS, VariableType.INTEGER}
        valued_types = {VariableType.DISCRETE, VariableType.CATEGORICAL}

        if self.type in bounded_types and self.bounds is None:
            msg = f"{self.type.value} variables require bounds."
            raise ValueError(msg)

        if self.type in valued_types and not self.values:
            msg = f"{self.type.value} variables require allowed values."
            raise ValueError(msg)


@dataclass(frozen=True)
class Objective:
    """A quantity that should be optimized."""

    name: str
    direction: ObjectiveDirection
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_name(self.name, "Objective")
        object.__setattr__(self, "direction", ObjectiveDirection(self.direction))


@dataclass(frozen=True)
class Constraint:
    """A condition used to assess solution feasibility."""

    name: str
    expression: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_name(self.name, "Constraint")


@dataclass(frozen=True)
class Problem:
    """An optimization problem definition."""

    name: str
    variables: tuple[DecisionVariable, ...]
    objectives: tuple[Objective, ...]
    constraints: tuple[Constraint, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_name(self.name, "Problem")
        if not self.variables:
            msg = "Problem must define at least one decision variable."
            raise ValueError(msg)
        if not self.objectives:
            msg = "Problem must define at least one objective."
            raise ValueError(msg)

        _require_unique_names(
            (variable.name for variable in self.variables),
            "variable",
        )
        _require_unique_names(
            (objective.name for objective in self.objectives),
            "objective",
        )
        _require_unique_names(
            (constraint.name for constraint in self.constraints),
            "constraint",
        )

    @property
    def variable_names(self) -> tuple[str, ...]:
        """Names of decision variables declared by the problem."""

        return tuple(variable.name for variable in self.variables)


@dataclass(frozen=True)
class Solution:
    """A concrete assignment of values to decision variables."""

    values: dict[str, Any]
    problem: Problem | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.values:
            msg = "Solution must contain at least one variable assignment."
            raise ValueError(msg)

        for name in self.values:
            _require_name(name, "Solution variable")

        if self.problem is not None:
            expected_names = set(self.problem.variable_names)
            provided_names = set(self.values)
            if provided_names != expected_names:
                missing = sorted(expected_names - provided_names)
                extra = sorted(provided_names - expected_names)
                msg = (
                    "Solution variable names must match the linked problem. "
                    f"Missing: {missing}; extra: {extra}."
                )
                raise ValueError(msg)


@dataclass(frozen=True)
class EvaluationRecord:
    """The recorded result of evaluating a solution."""

    solution: Solution
    objective_values: dict[str, float]
    constraint_values: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    status: EvaluationStatus = EvaluationStatus.SUCCESS
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", EvaluationStatus(self.status))
        if not self.objective_values:
            msg = "EvaluationRecord must contain at least one objective value."
            raise ValueError(msg)

        for name in self.objective_values:
            _require_name(name, "Objective value")
        for name in self.constraint_values:
            _require_name(name, "Constraint value")

        if self.solution.problem is not None:
            expected_objectives = {
                objective.name for objective in self.solution.problem.objectives
            }
            provided_objectives = set(self.objective_values)
            if provided_objectives != expected_objectives:
                missing = sorted(expected_objectives - provided_objectives)
                extra = sorted(provided_objectives - expected_objectives)
                msg = (
                    "Evaluation objective names must match the linked problem. "
                    f"Missing: {missing}; extra: {extra}."
                )
                raise ValueError(msg)


@dataclass(frozen=True)
class Dataset:
    """A collection of evaluation records."""

    records: tuple[EvaluationRecord, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_records(
        cls,
        records: list[EvaluationRecord] | tuple[EvaluationRecord, ...],
        metadata: dict[str, Any] | None = None,
    ) -> Dataset:
        """Create a dataset from evaluation records."""

        return cls(records=tuple(records), metadata=metadata or {})

    def __len__(self) -> int:
        return len(self.records)


def _require_name(name: str, label: str) -> None:
    if not name or not name.strip():
        msg = f"{label} name must not be empty."
        raise ValueError(msg)


def _require_unique_names(names: Iterable[str], label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for name in names:
        if name in seen:
            duplicates.add(name)
        seen.add(name)
    if duplicates:
        msg = f"Duplicate {label} names are not allowed: {sorted(duplicates)}."
        raise ValueError(msg)
