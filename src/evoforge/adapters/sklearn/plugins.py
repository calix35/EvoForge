"""scikit-learn surrogate adapter plugins."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evoforge.config import SurrogateConfig
from evoforge.domain import Dataset, EvaluationRecord, Solution


class RandomForestSurrogate:
    """Single-objective surrogate model backed by scikit-learn random forests."""

    plugin_id = "sklearn.random_forest"

    def __init__(self) -> None:
        self.n_estimators = 100
        self.random_state: int | None = None
        self.objective_name: str | None = None
        self._model: object | None = None
        self._feature_names: tuple[str, ...] | None = None
        self._training_records = 0

    def configure(self, config: object) -> None:
        surrogate_config = _require_surrogate_config(config)
        parameters = surrogate_config.parameters
        self.n_estimators = int(parameters.get("n_estimators", self.n_estimators))
        self.random_state = _optional_int(parameters.get("random_state"))
        self.objective_name = parameters.get("objective", self.objective_name)
        self._validate_parameters()

    def fit(self, dataset: Dataset) -> None:
        """Fit the surrogate from EvoForge evaluation records."""

        RandomForestRegressor = _load_random_forest_regressor()
        feature_names = _infer_feature_names(dataset)
        objective_name = self.objective_name or _infer_objective_name(dataset)
        x_train = _feature_matrix(dataset, feature_names)
        y_train = _target_vector(dataset, objective_name)

        model = RandomForestRegressor(
            n_estimators=self.n_estimators,
            random_state=self.random_state,
        )
        model.fit(x_train, y_train)

        self._model = model
        self._feature_names = feature_names
        self.objective_name = objective_name
        self._training_records = len(dataset)

    def predict(self, solution: Solution) -> EvaluationRecord:
        """Predict an EvoForge evaluation record for a solution."""

        if self._model is None or self._feature_names is None:
            msg = "sklearn.random_forest must be fitted before prediction."
            raise RuntimeError(msg)
        if self.objective_name is None:
            msg = "sklearn.random_forest has no configured objective name."
            raise RuntimeError(msg)

        x_value = [_solution_features(solution, self._feature_names)]
        prediction = float(self._model.predict(x_value)[0])
        return EvaluationRecord(
            solution=solution,
            objective_values={self.objective_name: prediction},
            source=self.plugin_id,
            metadata={
                "surrogate_model": "RandomForestRegressor",
                "training_records": self._training_records,
                "feature_names": list(self._feature_names),
                "prediction_type": "surrogate",
            },
        )

    def save(self, path: str | Path) -> Path:
        """Persist the fitted surrogate state with joblib."""

        if self._model is None or self._feature_names is None:
            msg = "sklearn.random_forest must be fitted before it can be saved."
            raise RuntimeError(msg)

        joblib = _load_joblib()
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self._model,
                "feature_names": self._feature_names,
                "objective_name": self.objective_name,
                "training_records": self._training_records,
                "n_estimators": self.n_estimators,
                "random_state": self.random_state,
            },
            output_path,
        )
        return output_path

    def load(self, path: str | Path) -> None:
        """Load a previously persisted surrogate state."""

        joblib = _load_joblib()
        state = joblib.load(Path(path))
        self._model = state["model"]
        self._feature_names = tuple(state["feature_names"])
        self.objective_name = state["objective_name"]
        self._training_records = int(state["training_records"])
        self.n_estimators = int(state["n_estimators"])
        self.random_state = _optional_int(state["random_state"])

    def _validate_parameters(self) -> None:
        if self.n_estimators < 1:
            msg = "sklearn.random_forest n_estimators must be at least 1."
            raise ValueError(msg)


def _require_surrogate_config(config: object) -> SurrogateConfig:
    if not isinstance(config, SurrogateConfig):
        msg = "Expected SurrogateConfig."
        raise TypeError(msg)
    return config


def _infer_feature_names(dataset: Dataset) -> tuple[str, ...]:
    if len(dataset) == 0:
        msg = "sklearn.random_forest requires at least one evaluation record."
        raise ValueError(msg)

    first_solution = dataset.records[0].solution
    if first_solution.problem is not None:
        return first_solution.problem.variable_names

    return tuple(sorted(first_solution.values))


def _infer_objective_name(dataset: Dataset) -> str:
    if len(dataset) == 0:
        msg = "sklearn.random_forest requires at least one evaluation record."
        raise ValueError(msg)
    return next(iter(dataset.records[0].objective_values))


def _feature_matrix(
    dataset: Dataset,
    feature_names: tuple[str, ...],
) -> list[list[float]]:
    return [
        _solution_features(record.solution, feature_names)
        for record in dataset.records
    ]


def _target_vector(dataset: Dataset, objective_name: str) -> list[float]:
    values: list[float] = []
    for record in dataset.records:
        if objective_name not in record.objective_values:
            msg = (
                "All records used by sklearn.random_forest must contain objective "
                f"{objective_name!r}."
            )
            raise ValueError(msg)
        values.append(float(record.objective_values[objective_name]))
    return values


def _solution_features(
    solution: Solution,
    feature_names: tuple[str, ...],
) -> list[float]:
    values: list[float] = []
    for name in feature_names:
        if name not in solution.values:
            msg = f"Solution is missing feature {name!r}."
            raise ValueError(msg)
        values.append(_numeric_feature(solution.values[name], name))
    return values


def _numeric_feature(value: Any, name: str) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    msg = (
        "sklearn.random_forest currently supports numeric solution values only. "
        f"Feature {name!r} has value {value!r}."
    )
    raise ValueError(msg)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _load_random_forest_regressor() -> Any:
    try:
        from sklearn.ensemble import RandomForestRegressor
    except ImportError as error:
        msg = (
            "The optional 'scikit-learn' dependency is required to use plugin "
            "'sklearn.random_forest'. Install it with 'uv sync --extra sklearn'."
        )
        raise RuntimeError(msg) from error
    return RandomForestRegressor


def _load_joblib() -> Any:
    try:
        import joblib
    except ImportError as error:
        msg = (
            "The optional 'joblib' dependency is required to persist plugin "
            "'sklearn.random_forest'. Install it with 'uv sync --extra sklearn'."
        )
        raise RuntimeError(msg) from error
    return joblib
