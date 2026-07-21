from datetime import datetime

import pytest

from evoforge.domain import (
    Constraint,
    Dataset,
    DecisionVariable,
    EvaluationRecord,
    EvaluationStatus,
    Objective,
    ObjectiveDirection,
    Problem,
    Solution,
    VariableType,
)


def make_problem() -> Problem:
    return Problem(
        name="irrigation_management",
        variables=(
            DecisionVariable(
                name="irrigation_day_1",
                type=VariableType.CONTINUOUS,
                bounds=(0.0, 40.0),
                unit="mm",
            ),
            DecisionVariable(
                name="cultivar",
                type=VariableType.CATEGORICAL,
                values=("A", "B"),
            ),
        ),
        objectives=(
            Objective(name="yield", direction=ObjectiveDirection.MAXIMIZE),
            Objective(name="water_use", direction=ObjectiveDirection.MINIMIZE),
        ),
        constraints=(Constraint(name="max_water_budget"),),
    )


def test_create_valid_problem() -> None:
    problem = make_problem()

    assert problem.name == "irrigation_management"
    assert problem.variable_names == ("irrigation_day_1", "cultivar")
    assert len(problem.objectives) == 2
    assert problem.constraints[0].name == "max_water_budget"


def test_create_valid_decision_variable_objects() -> None:
    continuous = DecisionVariable(
        name="irrigation_day_1",
        type="continuous",
        bounds=(0.0, 40.0),
    )
    categorical = DecisionVariable(
        name="cultivar",
        type=VariableType.CATEGORICAL,
        values=("A", "B"),
    )
    binary = DecisionVariable(name="enabled", type=VariableType.BINARY)

    assert continuous.type is VariableType.CONTINUOUS
    assert continuous.bounds == (0.0, 40.0)
    assert categorical.values == ("A", "B")
    assert binary.type is VariableType.BINARY


def test_invalid_variable_bounds_or_missing_values() -> None:
    with pytest.raises(ValueError, match="lower bound"):
        DecisionVariable(
            name="bad_bounds",
            type=VariableType.CONTINUOUS,
            bounds=(10.0, 1.0),
        )

    with pytest.raises(ValueError, match="require bounds"):
        DecisionVariable(name="missing_bounds", type=VariableType.INTEGER)

    with pytest.raises(ValueError, match="require allowed values"):
        DecisionVariable(name="missing_values", type=VariableType.CATEGORICAL)


def test_create_solution_objects_linked_to_variable_names() -> None:
    problem = make_problem()
    solution = Solution(
        problem=problem,
        values={"irrigation_day_1": 20.0, "cultivar": "A"},
    )

    assert solution.problem is problem
    assert solution.values["cultivar"] == "A"

    with pytest.raises(ValueError, match="must match the linked problem"):
        Solution(problem=problem, values={"irrigation_day_1": 20.0})


def test_create_evaluation_record_objects() -> None:
    problem = make_problem()
    solution = Solution(
        problem=problem,
        values={"irrigation_day_1": 20.0, "cultivar": "A"},
        metadata={"source": "unit-test"},
    )
    record = EvaluationRecord(
        solution=solution,
        objective_values={"yield": 8.5, "water_use": 120.0},
        constraint_values={"max_water_budget": 0.0},
        source="simulator",
        status=EvaluationStatus.SUCCESS,
    )

    assert record.solution is solution
    assert record.status is EvaluationStatus.SUCCESS
    assert isinstance(record.created_at, datetime)
    assert record.objective_values["yield"] == 8.5

    with pytest.raises(ValueError, match="objective names"):
        EvaluationRecord(
            solution=solution,
            objective_values={"yield": 8.5},
        )


def test_create_dataset_objects_from_evaluation_records() -> None:
    solution = Solution(values={"irrigation_day_1": 20.0})
    record = EvaluationRecord(
        solution=solution,
        objective_values={"yield": 8.5},
    )

    dataset = Dataset.from_records([record], metadata={"name": "baseline"})

    assert len(dataset) == 1
    assert dataset.records == (record,)
    assert dataset.metadata["name"] == "baseline"
