from pathlib import Path
from typing import Any

import pytest

from evoforge.adapters.sklearn import register_sklearn_plugins
from evoforge.adapters.sklearn.plugins import RandomForestSurrogate
from evoforge.config import SurrogateConfig
from evoforge.domain import (
    Dataset,
    DecisionVariable,
    EvaluationRecord,
    Objective,
    ObjectiveDirection,
    Problem,
    Solution,
    VariableType,
)
from evoforge.plugins import PluginRegistry, SurrogatePlugin

pytest.importorskip("sklearn")


def test_sklearn_surrogate_plugin_registration() -> None:
    registry = register_sklearn_plugins()

    plugin = registry.get("sklearn.random_forest", SurrogatePlugin)

    assert plugin.plugin_id == "sklearn.random_forest"


def test_register_sklearn_plugins_uses_existing_registry() -> None:
    registry = PluginRegistry()

    result = register_sklearn_plugins(registry)

    assert result is registry
    assert "sklearn.random_forest" in registry


def test_random_forest_surrogate_configuration() -> None:
    plugin = RandomForestSurrogate()

    plugin.configure(
        SurrogateConfig(
            enabled=True,
            plugin="sklearn.random_forest",
            parameters={
                "n_estimators": 8,
                "random_state": 123,
                "objective": "sphere",
            },
        )
    )

    assert plugin.n_estimators == 8
    assert plugin.random_state == 123
    assert plugin.objective_name == "sphere"


def test_random_forest_surrogate_fit_predict() -> None:
    plugin = RandomForestSurrogate()
    plugin.configure(
        SurrogateConfig(
            enabled=True,
            plugin="sklearn.random_forest",
            parameters={"n_estimators": 16, "random_state": 7},
        )
    )

    plugin.fit(make_sphere_dataset())
    prediction = plugin.predict(
        Solution(problem=make_sphere_problem(), values={"x1": 1.0, "x2": 2.0})
    )

    assert prediction.source == "sklearn.random_forest"
    assert set(prediction.objective_values) == {"sphere"}
    assert isinstance(prediction.objective_values["sphere"], float)
    assert prediction.metadata["prediction_type"] == "surrogate"
    assert prediction.metadata["training_records"] == 9


def test_random_forest_surrogate_can_be_saved_and_loaded(tmp_path: Path) -> None:
    dataset = make_sphere_dataset()
    solution = Solution(problem=make_sphere_problem(), values={"x1": 2.0, "x2": 1.0})
    first = RandomForestSurrogate()
    first.configure(
        SurrogateConfig(
            enabled=True,
            plugin="sklearn.random_forest",
            parameters={"n_estimators": 8, "random_state": 11},
        )
    )
    first.fit(dataset)
    model_path = first.save(tmp_path / "surrogate.joblib")

    second = RandomForestSurrogate()
    second.load(model_path)

    assert model_path.exists()
    assert second.predict(solution).objective_values == first.predict(
        solution
    ).objective_values


def test_random_forest_surrogate_rejects_prediction_before_fit() -> None:
    plugin = RandomForestSurrogate()

    with pytest.raises(RuntimeError, match="fitted before prediction"):
        plugin.predict(
            Solution(problem=make_sphere_problem(), values={"x1": 0.0, "x2": 0.0})
        )


def test_random_forest_surrogate_rejects_non_numeric_features() -> None:
    problem = Problem(
        name="categorical",
        variables=(
            DecisionVariable(
                name="crop",
                type=VariableType.CATEGORICAL,
                values=("maize", "wheat"),
            ),
        ),
        objectives=(Objective("yield", ObjectiveDirection.MAXIMIZE),),
    )
    dataset = Dataset.from_records(
        [
            EvaluationRecord(
                solution=Solution(problem=problem, values={"crop": "maize"}),
                objective_values={"yield": 1.0},
            )
        ]
    )
    plugin = RandomForestSurrogate()

    with pytest.raises(ValueError, match="numeric solution values only"):
        plugin.fit(dataset)


def test_random_forest_surrogate_missing_dependency_error_is_actionable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = make_sphere_dataset()
    plugin = RandomForestSurrogate()

    real_import = __import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("sklearn"):
            raise ImportError("missing scikit-learn")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError, match="uv sync --extra sklearn"):
        plugin.fit(dataset)


def make_sphere_problem() -> Problem:
    return Problem(
        name="sphere",
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


def make_sphere_dataset() -> Dataset:
    problem = make_sphere_problem()
    records = []
    for x1 in (-2.0, 0.0, 2.0):
        for x2 in (-2.0, 0.0, 2.0):
            solution = Solution(problem=problem, values={"x1": x1, "x2": x2})
            records.append(
                EvaluationRecord(
                    solution=solution,
                    objective_values={"sphere": x1**2 + x2**2},
                    source="example.sphere",
                )
            )
    return Dataset.from_records(records)
