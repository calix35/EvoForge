"""Adapter validation without scientific dependencies, plus optional real runs."""

import hashlib
import subprocess
import sys
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from evoforge.adapters.aquacrop import register_aquacrop_plugins
from evoforge.adapters.aquacrop.plugins import AquaCropIrrigationSimulator
from evoforge.cli.main import app
from evoforge.config import load_experiment_config
from evoforge.domain import (
    Constraint,
    DecisionVariable,
    EvaluationStatus,
    Objective,
    ObjectiveDirection,
    Problem,
    Solution,
    VariableType,
)
from evoforge.plugins import DuplicatePluginError, PluginRegistry, SimulatorPlugin

YIELD = "Dry yield (tonne/ha)"
IRRIGATION = "Seasonal irrigation (mm)"


def scenario():
    return load_experiment_config(
        "examples/aquacrop_irrigation_ga.yaml"
    ).evaluator.simulator


def solution():
    return Solution(
        values={f"smt{i}": 50.0 for i in range(1, 5)},
        problem=Problem(
            "maize",
            variables=tuple(
                DecisionVariable(f"smt{i}", VariableType.CONTINUOUS, (0, 100))
                for i in range(1, 5)
            ),
            objectives=(Objective("dry_yield", ObjectiveDirection.MAXIMIZE),),
        ),
    )


class Frame:
    def __init__(self, rows, columns=None):
        self.iloc = rows
        self.columns = columns if columns is not None else (rows[0] if rows else [])

    def __len__(self):
        return len(self.iloc)


class Weather(dict):
    @property
    def columns(self):
        return self.keys()


@pytest.fixture
def fake_api(tmp_path, monkeypatch):
    path = tmp_path / "weather.txt"
    path.write_text("synthetic weather fixture\n")
    state = SimpleNamespace(
        models=[],
        weather=[],
        bundled_names=[],
        results=Frame([{YIELD: 12.0, IRRIGATION: 275.0}]),
        error=None,
    )

    def prepare_weather(path):
        dates = [date(2018, 5, 1) + timedelta(days=i) for i in range(184)]
        weather = Weather(
            {
                "Date": SimpleNamespace(dt=SimpleNamespace(date=dates)),
                "MinTemp": [10.0] * 184,
                "MaxTemp": [25.0] * 184,
                "Precipitation": [0.0] * 184,
                "ReferenceET": [3.0] * 184,
            }
        )
        state.weather.append(weather)
        return weather

    def get_filepath(name):
        state.bundled_names.append(name)
        return str(path)

    class Model:
        def __init__(self, **kwargs):
            self.inputs = kwargs
            state.models.append(self)

        def run_model(self, *, till_termination):
            assert till_termination is True
            if state.error:
                raise state.error

        def get_simulation_results(self):
            return state.results

    def entity(*args, **kwargs):
        return SimpleNamespace(args=args, kwargs=kwargs)

    api = SimpleNamespace(
        AquaCropModel=Model,
        Crop=entity,
        Soil=entity,
        InitialWaterContent=entity,
        IrrigationManagement=entity,
        prepare_weather=prepare_weather,
        get_filepath=get_filepath,
        version="3.1.0",
    )
    monkeypatch.setattr(
        "evoforge.adapters.aquacrop.plugins._load_aquacrop", lambda: api
    )
    state.api = api
    state.path = path
    return state


def test_registration_is_explicit_and_isolated():
    reg = PluginRegistry()
    assert register_aquacrop_plugins(reg) is reg
    assert isinstance(reg.get("aquacrop.irrigation"), SimulatorPlugin)
    assert "aquacrop.irrigation" not in PluginRegistry()
    with pytest.raises(DuplicatePluginError):
        register_aquacrop_plugins(reg)


def test_configuration_and_metadata(fake_api):
    plugin = AquaCropIrrigationSimulator()
    plugin.configure(scenario())
    record = plugin.evaluate(solution())
    assert record.objective_values == {"dry_yield": 12.0}
    assert record.status is EvaluationStatus.SUCCESS
    assert record.source == "aquacrop.irrigation"
    assert record.metadata["seasonal_irrigation_mm"] == 275.0
    assert record.metadata["aquacrop_version"] == "3.1.0"
    assert record.metadata["weather"] == {
        "path": str(fake_api.path),
        "provenance": "aquacrop_bundled",
        "sha256": hashlib.sha256(fake_api.path.read_bytes()).hexdigest(),
    }
    inputs = fake_api.models[0].inputs
    assert inputs["irrigation_management"].kwargs == {
        "irrigation_method": 1,
        "SMT": [50.0] * 4,
        "MaxIrrSeason": 300.0,
    }
    assert inputs["initial_water_content"].kwargs == {"wc_type": "Pct", "value": [70.0]}
    assert inputs["crop"].args == ("Maize",)
    assert inputs["soil"].args == ("ClayLoam",)
    assert fake_api.bundled_names == ["champion_climate.txt"]


def test_each_evaluation_has_fresh_mutable_inputs(fake_api):
    plugin = AquaCropIrrigationSimulator()
    plugin.configure(scenario())
    first = plugin.evaluate(solution())
    inputs = fake_api.models[0].inputs
    inputs["irrigation_management"].kwargs["SMT"][0] = -999
    inputs["crop"].kwargs["planting_date"] = "01/01"
    inputs["weather_df"]["MinTemp"][0] = -999
    second = plugin.evaluate(solution())
    fresh = fake_api.models[1].inputs
    for name in (
        "soil",
        "crop",
        "initial_water_content",
        "irrigation_management",
        "weather_df",
    ):
        assert inputs[name] is not fresh[name]
    assert fresh["irrigation_management"].kwargs["SMT"] == [50.0] * 4
    assert fresh["weather_df"]["MinTemp"][0] == 10.0
    assert fresh["crop"].kwargs["planting_date"] == "05/01"
    assert first.objective_values == second.objective_values


@pytest.mark.parametrize(
    "key,value",
    [
        ("initial_water_pct", -1),
        ("initial_water_pct", 101),
        ("max_irr_season", float("inf")),
        ("max_irr_season", -1),
        ("sim_end_time", "2019-10-31"),
        ("sim_end_time", "2018-04-01"),
        ("planting_date", "13/01"),
        ("planting_date", "01/01"),
        ("unknown_parameter", 1),
    ],
)
def test_invalid_scenario(key, value):
    config = scenario()
    config.parameters[key] = value
    with pytest.raises(ValidationError):
        AquaCropIrrigationSimulator().configure(config)


def test_configuration_required():
    with pytest.raises(TypeError, match="SimulatorConfig"):
        AquaCropIrrigationSimulator().configure(object())
    with pytest.raises(RuntimeError, match="configured"):
        AquaCropIrrigationSimulator().evaluate(solution())


@pytest.mark.parametrize("value", [-1, 101, float("nan"), float("inf"), "50", True])
def test_invalid_smt_values(value, fake_api):
    plugin = AquaCropIrrigationSimulator()
    plugin.configure(scenario())
    candidate = solution()
    candidate.values["smt1"] = value
    with pytest.raises(ValueError, match="SMT"):
        plugin.evaluate(candidate)
    assert not fake_api.models


@pytest.mark.parametrize(
    "change", ["names", "type", "bounds", "objective", "direction", "constraints"]
)
def test_invalid_problem(change, fake_api):
    candidate = solution()
    problem = candidate.problem
    if change == "names":
        candidate = Solution({"other": 1.0})
    elif change in {"type", "bounds"}:
        var = problem.variables[0]
        var = replace(
            var,
            **(
                {"type": VariableType.INTEGER}
                if change == "type"
                else {"bounds": (-1, 100)}
            ),
        )
        candidate = replace(
            candidate, problem=replace(problem, variables=(var, *problem.variables[1:]))
        )
    else:
        changes = {
            "objective": {"objectives": (Objective("wrong", "maximize"),)},
            "direction": {"objectives": (Objective("dry_yield", "minimize"),)},
            "constraints": {"constraints": (Constraint("limit"),)},
        }
        candidate = replace(candidate, problem=replace(problem, **changes[change]))
    plugin = AquaCropIrrigationSimulator()
    plugin.configure(scenario())
    with pytest.raises(ValueError):
        plugin.evaluate(candidate)
    assert not fake_api.models


@pytest.mark.parametrize(
    "results",
    [
        None,
        False,
        Frame([]),
        Frame([{YIELD: 1.0}]),
        Frame([{YIELD: 1.0, IRRIGATION: 1.0}] * 2),
        Frame([{YIELD: float("nan"), IRRIGATION: 1.0}]),
        Frame([{YIELD: 1.0, IRRIGATION: float("inf")}]),
    ],
)
def test_bad_results_raise_instead_of_success(fake_api, results):
    fake_api.results = results
    plugin = AquaCropIrrigationSimulator()
    plugin.configure(scenario())
    with pytest.raises(ValueError):
        plugin.evaluate(solution())


def test_simulation_errors_propagate(fake_api):
    fake_api.error = RuntimeError("simulation failed")
    plugin = AquaCropIrrigationSimulator()
    plugin.configure(scenario())
    with pytest.raises(RuntimeError, match="simulation failed"):
        plugin.evaluate(solution())


def test_explicit_local_weather(fake_api):
    cfg = scenario()
    cfg.parameters["weather_file"] = str(fake_api.path)
    plugin = AquaCropIrrigationSimulator()
    plugin.configure(cfg)
    record = plugin.evaluate(solution())
    assert record.metadata["weather"]["provenance"] == "local_file"
    assert not fake_api.bundled_names


@pytest.mark.parametrize(
    "change", ["missing", "gap", "duplicate", "nonfinite", "column"]
)
def test_bad_weather_rejected_before_simulation(fake_api, change):
    cfg = scenario()
    if change == "missing":
        cfg.parameters["weather_file"] = str(fake_api.path.parent / "missing.txt")
    else:
        original = fake_api.api.prepare_weather

        def bad_weather(path):
            weather = original(path)
            if change == "gap":
                weather["Date"].dt.date.pop(10)
            elif change == "duplicate":
                weather["Date"].dt.date[10] = weather["Date"].dt.date[9]
            elif change == "nonfinite":
                weather["MinTemp"][0] = float("nan")
            else:
                del weather["ReferenceET"]
            return weather

        fake_api.api.prepare_weather = bad_weather
    plugin = AquaCropIrrigationSimulator()
    plugin.configure(cfg)
    with pytest.raises(ValueError, match="weather"):
        plugin.evaluate(solution())
    assert not fake_api.models


def test_missing_dependency_has_install_hint(monkeypatch):
    original = __import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] == "aquacrop":
            raise ImportError("missing")
        return original(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded)
    plugin = AquaCropIrrigationSimulator()
    plugin.configure(scenario())
    with pytest.raises(RuntimeError, match="uv sync --python 3.12 --extra aquacrop"):
        plugin.evaluate(solution())


def test_core_and_registration_do_not_import_aquacrop():
    script = """
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] == 'aquacrop':
        raise AssertionError('Unexpected AquaCrop import')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from evoforge.core import Experiment
from evoforge.adapters.aquacrop import register_aquacrop_plugins
register_aquacrop_plugins()
assert 'aquacrop' not in sys.modules
"""
    subprocess.run([sys.executable, "-c", script], check=True)


def test_real_aquacrop_repeatability_and_local_provenance():
    pytest.importorskip("aquacrop")
    from aquacrop.utils import get_filepath

    plugin = AquaCropIrrigationSimulator()
    cfg = scenario()
    cfg.parameters["weather_file"] = get_filepath("champion_climate.txt")
    plugin.configure(cfg)
    first = plugin.evaluate(solution())
    changed = solution()
    changed.values.update({name: 90.0 for name in changed.values})
    plugin.evaluate(changed)
    repeated = plugin.evaluate(solution())
    assert first.objective_values == repeated.objective_values
    assert (
        first.metadata["seasonal_irrigation_mm"]
        == repeated.metadata["seasonal_irrigation_mm"]
    )
    assert 0 < first.objective_values["dry_yield"] < 30
    assert 0 <= first.metadata["seasonal_irrigation_mm"] <= 300
    assert first.metadata["weather"]["provenance"] == "local_file"
    assert len(first.metadata["weather"]["sha256"]) == 64
    assert first.metadata["aquacrop_version"] == "3.1.0"


@pytest.mark.parametrize("name,calls", [("ga", 4), ("surrogate", 5)])
def test_real_cli_examples(name, calls, tmp_path, monkeypatch):
    import json

    pytest.importorskip("aquacrop")
    pytest.importorskip("pymoo")
    if name == "surrogate":
        pytest.importorskip("sklearn")
    example = Path(f"examples/aquacrop_irrigation_{name}.yaml").resolve()
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["run", str(example)])
    assert result.exit_code == 0, result.output
    output = tmp_path / f"results/aquacrop_irrigation_{name}"
    records = json.loads((output / "evaluation_records.json").read_text())
    assert len(records) == calls
    assert all(r["status"] == "success" for r in records)
    assert all(r["source"] == "aquacrop.irrigation" for r in records)
    assert all(0 <= r["metadata"]["seasonal_irrigation_mm"] <= 300 for r in records)
    assert (output / "manifest.json").exists()
    if name == "surrogate":
        metadata = json.loads((output / "metadata.json").read_text())
        assert metadata["simulator_calls"] == calls
        assert metadata["termination_reason"] == "real_budget_exhausted"
        assert metadata["best_real_values"]["dry_yield"] == max(
            r["objective_values"]["dry_yield"] for r in records
        )
        assert (output / "predictions.json").exists()
