"""Single-season irrigation simulations using the optional AquaCrop-OSPy API."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from importlib.metadata import version
from math import isfinite
from numbers import Real
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evoforge.config import SimulatorConfig
from evoforge.domain import (
    EvaluationRecord,
    ObjectiveDirection,
    Solution,
    VariableType,
)

_VARIABLE_NAMES = ("smt1", "smt2", "smt3", "smt4")
_YIELD = "Dry yield (tonne/ha)"
_IRRIGATION = "Seasonal irrigation (mm)"


class _Scenario(BaseModel):
    """Adapter-local scenario validation; no scientific dependencies."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    crop: str = Field(min_length=1)
    soil: str = Field(min_length=1)
    sim_start_time: date
    sim_end_time: date
    planting_date: str
    initial_water_pct: float = Field(ge=0, le=100)
    max_irr_season: float = Field(ge=0)
    weather_file: str = Field(default="champion_climate.txt", min_length=1)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.sim_start_time >= self.sim_end_time:
            raise ValueError("sim_start_time must precede sim_end_time.")
        if self.sim_start_time.year != self.sim_end_time.year:
            raise ValueError("aquacrop.irrigation supports one calendar-year season.")
        try:
            planting = datetime.strptime(
                f"{self.sim_start_time.year}/{self.planting_date}", "%Y/%m/%d"
            ).date()
        except ValueError as error:
            raise ValueError("planting_date must be a valid MM/DD date.") from error
        if not self.sim_start_time <= planting <= self.sim_end_time:
            raise ValueError("planting_date must fall within the simulation dates.")
        return self


class AquaCropIrrigationSimulator:
    """Evaluate four soil-moisture thresholds with fresh per-candidate state."""

    plugin_id = "aquacrop.irrigation"

    def __init__(self) -> None:
        self._scenario: _Scenario | None = None

    def configure(self, config: object) -> None:
        if not isinstance(config, SimulatorConfig):
            raise TypeError("Expected SimulatorConfig.")
        self._scenario = _Scenario.model_validate(config.parameters)

    def evaluate(self, solution: Solution) -> EvaluationRecord:
        started = perf_counter()
        if self._scenario is None:
            raise RuntimeError(
                "aquacrop.irrigation must be configured before evaluation."
            )
        smts = _validate_solution(solution)
        scenario = self._scenario
        api = _load_aquacrop()
        bundled = scenario.weather_file == "champion_climate.txt"
        weather_path = (
            Path(
                api.get_filepath("champion_climate.txt")
                if bundled
                else scenario.weather_file
            )
            .expanduser()
            .resolve()
        )
        if not weather_path.is_file():
            raise ValueError(f"AquaCrop weather file does not exist: {weather_path}")
        digest = hashlib.sha256(weather_path.read_bytes()).hexdigest()
        try:
            weather = api.prepare_weather(str(weather_path))
            _validate_weather(weather, scenario)
        except Exception as error:
            raise ValueError(
                f"Invalid AquaCrop weather file {weather_path}: {error}"
            ) from error

        # AquaCrop mutates its inputs; never retain these objects between candidates.
        model = api.AquaCropModel(
            sim_start_time=scenario.sim_start_time.strftime("%Y/%m/%d"),
            sim_end_time=scenario.sim_end_time.strftime("%Y/%m/%d"),
            weather_df=weather,
            soil=api.Soil(scenario.soil),
            crop=api.Crop(scenario.crop, planting_date=scenario.planting_date),
            initial_water_content=api.InitialWaterContent(
                wc_type="Pct", value=[scenario.initial_water_pct]
            ),
            irrigation_management=api.IrrigationManagement(
                irrigation_method=1, SMT=smts, MaxIrrSeason=scenario.max_irr_season
            ),
        )
        model.run_model(till_termination=True)
        results = model.get_simulation_results()
        dry_yield, irrigation = _read_results(results)
        return EvaluationRecord(
            solution=solution,
            objective_values={"dry_yield": dry_yield},
            source=self.plugin_id,
            metadata={
                "evaluation_kind": "real",
                "dry_yield_unit": "tonne/ha",
                "seasonal_irrigation_mm": irrigation,
                "scenario": scenario.model_dump(mode="json"),
                "soil_moisture_targets_pct_taw": dict(
                    zip(_VARIABLE_NAMES, smts, strict=True)
                ),
                "weather": {
                    "path": str(weather_path),
                    "provenance": "aquacrop_bundled" if bundled else "local_file",
                    "sha256": digest,
                },
                "aquacrop_version": api.version,
                "elapsed_seconds": perf_counter() - started,
            },
        )


def _validate_solution(solution: Solution) -> list[float]:
    if set(solution.values) != set(_VARIABLE_NAMES):
        raise ValueError("aquacrop.irrigation requires exactly smt1, smt2, smt3, smt4.")
    problem = solution.problem
    if problem is None:
        raise ValueError("aquacrop.irrigation requires a solution linked to a problem.")
    if (
        len(problem.objectives) != 1
        or problem.objectives[0].name != "dry_yield"
        or problem.objectives[0].direction is not ObjectiveDirection.MAXIMIZE
        or problem.constraints
    ):
        raise ValueError(
            "aquacrop.irrigation requires dry_yield to maximize, no constraints."
        )
    for variable in problem.variables:
        if (
            variable.type is not VariableType.CONTINUOUS
            or variable.bounds is None
            or not all(isfinite(v) for v in variable.bounds)
            or not 0 <= variable.bounds[0] < variable.bounds[1] <= 100
        ):
            raise ValueError("SMT variables require continuous bounds within [0, 100].")
    smts = []
    for name in _VARIABLE_NAMES:
        value = solution.values[name]
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("SMT values must be finite numbers within [0, 100].")
        if not isfinite(value) or not 0 <= value <= 100:
            raise ValueError("SMT values must be finite numbers within [0, 100].")
        bounds = next(v.bounds for v in problem.variables if v.name == name)
        if not bounds[0] <= value <= bounds[1]:
            raise ValueError(f"SMT value {name} is outside its declared bounds.")
        smts.append(float(value))
    return smts


def _validate_weather(weather: Any, scenario: _Scenario) -> None:
    columns = {"Date", "MinTemp", "MaxTemp", "Precipitation", "ReferenceET"}
    if not columns.issubset(weather.columns):
        raise ValueError("Missing required weather columns.")
    dates = list(weather["Date"].dt.date)
    if len(dates) != len(set(dates)) or dates != sorted(dates):
        raise ValueError("Weather dates must be unique and sorted.")
    required_days = (scenario.sim_end_time - scenario.sim_start_time).days + 1
    expected = {
        scenario.sim_start_time + timedelta(days=i) for i in range(required_days)
    }
    if not expected.issubset(dates):
        raise ValueError("Weather coverage must include every simulation day.")
    for column in columns - {"Date"}:
        if not all(isfinite(float(v)) for v in weather[column]):
            raise ValueError(f"Weather column {column} contains nonfinite values.")


def _read_results(results: Any) -> tuple[float, float]:
    if results is None or isinstance(results, bool) or len(results) == 0:
        raise ValueError("AquaCrop returned empty or unfinished simulation results.")
    if len(results) != 1:
        raise ValueError("aquacrop.irrigation requires exactly one season of results.")
    if not {_YIELD, _IRRIGATION}.issubset(results.columns):
        raise ValueError("AquaCrop results are missing yield or irrigation columns.")
    row = results.iloc[0]
    values = (float(row[_YIELD]), float(row[_IRRIGATION]))
    if not all(isfinite(value) for value in values):
        raise ValueError("AquaCrop results contain nonfinite yield or irrigation.")
    return values


def _load_aquacrop() -> SimpleNamespace:
    try:
        from aquacrop import (
            AquaCropModel,
            Crop,
            InitialWaterContent,
            IrrigationManagement,
            Soil,
        )
        from aquacrop.utils import get_filepath, prepare_weather
    except ImportError as error:
        raise RuntimeError(
            "Plugin 'aquacrop.irrigation' requires AquaCrop-OSPy 3.1.0. "
            "Install it with 'uv sync --python 3.12 --extra aquacrop'."
        ) from error
    return SimpleNamespace(
        AquaCropModel=AquaCropModel,
        Crop=Crop,
        InitialWaterContent=InitialWaterContent,
        IrrigationManagement=IrrigationManagement,
        Soil=Soil,
        get_filepath=get_filepath,
        prepare_weather=prepare_weather,
        version=version("aquacrop"),
    )
