"""Exercise paired pilot accounting with cheap deterministic fake plugins."""

import csv
import importlib.util
import json
import random
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from evoforge.domain import EvaluationRecord, EvaluationStatus, Solution
from evoforge.plugins import PluginRegistry

spec = importlib.util.spec_from_file_location(
    "aquacrop_pilot",
    Path(__file__).resolve().parents[2] / "scripts/compare_aquacrop.py",
)
pilot = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pilot
spec.loader.exec_module(pilot)
PilotSettings = pilot.PilotSettings
build_config = pilot.build_config
run_pilot = pilot.run_pilot


class FakeOptimizer:
    plugin_id = "pymoo.ga"
    extra_calls = 0

    def configure(self, config):
        self.config = config

    def optimize(self, problem, evaluator):
        rng = random.Random(self.config.parameters["seed"])
        return [
            evaluator.evaluate(
                Solution(
                    {name: rng.uniform(0, 100) for name in problem.variable_names},
                    problem,
                )
            )
            for _ in range(self.config.parameters["n_evaluations"] + self.extra_calls)
        ]


class FakeSurrogate:
    plugin_id = "sklearn.random_forest"

    def configure(self, config):
        self.config = config

    def fit(self, dataset):
        assert all(r.status is EvaluationStatus.SUCCESS for r in dataset.records)
        assert all(r.source == "aquacrop.irrigation" for r in dataset.records)

    def predict(self, solution):
        # Deliberately better than every real yield; must never enter summaries.
        return EvaluationRecord(solution, {"dry_yield": 10000.0}, source=self.plugin_id)


class FakeSimulator:
    plugin_id = "aquacrop.irrigation"

    def __init__(self):
        self.calls = 0
        self.fail = False

    def configure(self, config):
        self.config = config

    def evaluate(self, solution):
        self.calls += 1
        if self.fail:
            raise RuntimeError("real simulation failed")
        return EvaluationRecord(
            solution,
            {"dry_yield": sum(solution.values.values()) / 100},
            source=self.plugin_id,
            metadata={"seasonal_irrigation_mm": 123.0, "weather": {"sha256": "abc"}},
        )


@pytest.fixture
def harness():
    simulators = []

    def factory():
        registry = PluginRegistry()
        registry.register(FakeOptimizer())
        registry.register(FakeSurrogate())
        simulator = FakeSimulator()
        simulators.append(simulator)
        return registry, simulator

    return factory, simulators


def settings():
    return PilotSettings(
        seeds=(0, 1),
        real_budget=4,
        pop_size=2,
        initial_size=2,
        candidates_per_update=1,
        search_budget=3,
        n_estimators=2,
    )


def environment():
    return {
        "python": "3.12-test",
        "versions": {"aquacrop": "fake"},
        "git": {"revision": "test-revision", "dirty": True},
        "weather": {"sha256": "abc"},
        "timing_policy": "test",
    }


def test_defaults_and_effective_configs(tmp_path):
    defaults = PilotSettings()
    defaults.validate()
    assert defaults.seeds == tuple(range(10))
    assert (defaults.real_budget, defaults.pop_size) == (60, 20)
    assert (defaults.initial_size, defaults.candidates_per_update) == (20, 4)
    assert (defaults.search_budget, defaults.n_estimators) == (200, 100)
    for method in ("direct", "surrogate"):
        config = build_config(defaults, 7, method, tmp_path / method)
        assert config.experiment.seed == config.optimizer.parameters["seed"] == 7
        assert config.optimizer.parameters["pop_size"] == 20
        scenario = config.evaluator.simulator.parameters
        assert (scenario["crop"], scenario["soil"]) == ("Maize", "ClayLoam")
        assert (scenario["initial_water_pct"], scenario["max_irr_season"]) == (70, 300)
        assert scenario["sim_start_time"] == "2018-05-01"
        assert config.surrogate.enabled == (method == "surrogate")
        if method == "surrogate":
            assert config.surrogate.parameters["random_state"] == 7


@pytest.mark.parametrize(
    "changes",
    [
        {"real_budget": 5},
        {"real_budget": 1},
        {"pop_size": 1},
        {"initial_size": 4},
        {"initial_size": 1},
        {"search_budget": 0},
        {"candidates_per_update": 3},
        {"n_estimators": 0},
        {"seeds": ()},
        {"seeds": (0, 0)},
        {"seeds": (-1,)},
    ],
)
def test_invalid_settings_reject_before_execution(tmp_path, harness, changes):
    factory, simulators = harness
    with pytest.raises(ValueError):
        run_pilot(
            replace(settings(), **changes),
            tmp_path / "pilot",
            plugin_factory=factory,
            environment=environment(),
        )
    assert not simulators
    assert not (tmp_path / "pilot").exists()


def test_paired_runs_order_artifacts_and_validated_only_summary(tmp_path, harness):
    factory, simulators = harness
    output = tmp_path / "pilot"
    rows = run_pilot(
        settings(), output, plugin_factory=factory, environment=environment()
    )
    assert [(r["seed"], r["method"]) for r in rows] == [
        (0, "direct"),
        (0, "surrogate"),
        (1, "surrogate"),
        (1, "direct"),
    ]
    assert [s.calls for s in simulators] == [4] * 4
    assert len({r["output_directory"] for r in rows}) == 4
    for row in rows:
        assert row["status"] == "completed"
        assert row["real_calls"] == 4
        assert row["budget_complete"] is True
        assert row["failures"] == 0
        assert 0 <= row["best_dry_yield_t_ha"] <= 4
        assert row["best_irrigation_mm"] == 123
        assert row["elapsed_seconds"] >= 0
        directory = Path(row["output_directory"])
        real = json.loads((directory / "evaluation_records.json").read_text())
        trajectory = json.loads((directory / "trajectory.json").read_text())
        assert [p["real_calls"] for p in trajectory] == [1, 2, 3, 4]
        assert [p["best_dry_yield_t_ha"] for p in trajectory] == [
            max(r["objective_values"]["dry_yield"] for r in real[:i])
            for i in range(1, 5)
        ]
        metadata = json.loads((directory / "metadata.json").read_text())["pilot"]
        assert metadata["git"]["revision"] == "test-revision"
        assert metadata["weather"]["sha256"] == "abc"
        assert metadata["settings"]["real_budget"] == 4
        assert "scripts/compare_aquacrop.py" in metadata["source_sha256"]
        predictions = json.loads((directory / "predictions.json").read_text())
        assert len(predictions) == (6 if row["method"] == "surrogate" else 0)
        assert (directory / "failures.json").read_text().strip() == "[]"
    with (output / "summary.csv").open() as stream:
        assert len(list(csv.DictReader(stream))) == 4
    assert json.loads((output / "summary.json").read_text()) == rows
    assert (output / "source_snapshot/src/evoforge/core/experiment.py").exists()
    with pytest.raises(FileExistsError):
        run_pilot(settings(), output, plugin_factory=factory, environment=environment())


def test_hard_guard_blocks_unexpected_optimizer_overshoot(
    tmp_path, harness, monkeypatch
):
    monkeypatch.setattr(FakeOptimizer, "extra_calls", 10)
    factory, simulators = harness
    rows = run_pilot(
        replace(settings(), seeds=(0,)),
        tmp_path / "pilot",
        plugin_factory=factory,
        environment=environment(),
    )
    assert [s.calls for s in simulators] == [4, 4]
    assert rows[0]["status"] == "completed"
    assert rows[0]["termination_reason"] == "real_budget_guard"
    metadata = json.loads(
        (Path(rows[0]["output_directory"]) / "metadata.json").read_text()
    )
    assert metadata["pilot"]["blocked_simulator_calls"] == 1


def test_real_failures_are_saved_and_never_selected(tmp_path, harness):
    factory, _ = harness

    def failing_factory():
        registry, simulator = factory()
        simulator.fail = True
        return registry, simulator

    rows = run_pilot(
        replace(settings(), seeds=(0,)),
        tmp_path / "pilot",
        plugin_factory=failing_factory,
        environment=environment(),
    )
    assert [r["real_calls"] for r in rows] == [1, 2]
    for row in rows:
        assert row["status"] == "failed"
        assert row["failures"] == row["real_calls"]
        assert row["best_dry_yield_t_ha"] is None
        assert row["best_irrigation_mm"] is None
        assert row["budget_complete"] is False
        directory = Path(row["output_directory"])
        failures = json.loads((directory / "failures.json").read_text())
        assert len(failures) == row["failures"]
        assert all(r["status"] == "failed" for r in failures)
        assert all("simulation failed" in r["metadata"]["error"] for r in failures)


def test_short_optimizer_is_not_reported_as_full_budget(tmp_path, harness, monkeypatch):
    monkeypatch.setattr(FakeOptimizer, "extra_calls", -1)
    factory, _ = harness
    rows = run_pilot(
        replace(settings(), seeds=(0,)),
        tmp_path / "pilot",
        plugin_factory=factory,
        environment=environment(),
    )
    assert rows[0]["real_calls"] == 3
    assert rows[0]["status"] == "incomplete"
    assert rows[0]["budget_complete"] is False


def test_weather_mismatch_marks_run_failed(tmp_path, harness):
    factory, _ = harness
    env = environment()
    env["weather"]["sha256"] = "changed"
    rows = run_pilot(
        replace(settings(), seeds=(0,)),
        tmp_path / "pilot",
        plugin_factory=factory,
        environment=env,
    )
    assert all(r["status"] == "failed" for r in rows)
    assert all(r["termination_reason"] == "weather_hash_mismatch" for r in rows)


def test_elapsed_time_includes_training_and_search(tmp_path, harness, monkeypatch):
    class Clock:
        value = 0.0

        def __call__(self):
            return self.value

    clock = Clock()
    optimizer = FakeOptimizer.optimize
    fit = FakeSurrogate.fit

    def search(self, problem, evaluator):
        clock.value += 5.0
        return optimizer(self, problem, evaluator)

    def train(self, dataset):
        clock.value += 7.0
        fit(self, dataset)

    monkeypatch.setattr(pilot, "perf_counter", clock)
    monkeypatch.setattr(FakeOptimizer, "optimize", search)
    monkeypatch.setattr(FakeSurrogate, "fit", train)
    factory, _ = harness
    rows = run_pilot(
        replace(settings(), seeds=(0,)),
        tmp_path / "pilot",
        plugin_factory=factory,
        environment=environment(),
    )
    assert rows[0]["elapsed_seconds"] == 5.0
    assert rows[1]["elapsed_seconds"] == 2 * (7.0 + 5.0)


def test_failed_call_preserves_previous_best_and_trajectory(tmp_path, harness):
    factory, _ = harness

    def factory_with_failure():
        registry, simulator = factory()
        evaluate = simulator.evaluate

        def fail_second(solution):
            if simulator.calls == 1:
                simulator.fail = True
            return evaluate(solution)

        simulator.evaluate = fail_second
        return registry, simulator

    rows = run_pilot(
        replace(settings(), seeds=(0,)),
        tmp_path / "pilot",
        plugin_factory=factory_with_failure,
        environment=environment(),
    )
    for row in rows:
        assert row["real_calls"] == 2
        assert row["failures"] == 1
        assert row["best_dry_yield_t_ha"] is not None
        trajectory = json.loads(
            (Path(row["output_directory"]) / "trajectory.json").read_text()
        )
        assert (
            trajectory[0]["best_dry_yield_t_ha"]
            == trajectory[1]["best_dry_yield_t_ha"]
            == row["best_dry_yield_t_ha"]
        )


def test_seeded_pilot_numeric_traces_are_reproducible(tmp_path, harness):
    factory, _ = harness
    first = run_pilot(
        replace(settings(), seeds=(0,)),
        tmp_path / "one",
        plugin_factory=factory,
        environment=environment(),
    )
    second = run_pilot(
        replace(settings(), seeds=(0,)),
        tmp_path / "two",
        plugin_factory=factory,
        environment=environment(),
    )
    for a, b in zip(first, second, strict=True):
        assert a["best_dry_yield_t_ha"] == b["best_dry_yield_t_ha"]
        for filename in ("evaluation_records.json", "predictions.json"):
            trace_a = json.loads((Path(a["output_directory"]) / filename).read_text())
            trace_b = json.loads((Path(b["output_directory"]) / filename).read_text())
            assert [
                (r["solution"]["values"], r["objective_values"]) for r in trace_a
            ] == [(r["solution"]["values"], r["objective_values"]) for r in trace_b]
