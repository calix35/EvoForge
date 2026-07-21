from typing import Any

import pytest

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
from evoforge.plugins import (
    DuplicatePluginError,
    MissingPluginError,
    OptimizerPlugin,
    PluginRegistry,
    ReportPlugin,
    SimulatorPlugin,
)


class FakeOptimizer:
    plugin_id = "fake.optimizer"

    def configure(self, config: object) -> None:
        self.config = config

    def optimize(self, problem: Problem, evaluator: object) -> dict[str, Any]:
        return {"problem": problem.name, "evaluator": evaluator}


class FakeSimulator:
    plugin_id = "fake.simulator"

    def configure(self, config: object) -> None:
        self.config = config

    def evaluate(self, solution: Solution) -> EvaluationRecord:
        return EvaluationRecord(solution=solution, objective_values={"score": 1.0})


class FakeSurrogate:
    plugin_id = "fake.surrogate"

    def configure(self, config: object) -> None:
        self.config = config

    def fit(self, dataset: Dataset) -> None:
        self.dataset = dataset

    def predict(self, solution: Solution) -> EvaluationRecord:
        return EvaluationRecord(solution=solution, objective_values={"score": 1.0})


class FakeAnalysis:
    plugin_id = "fake.analysis"

    def configure(self, config: object) -> None:
        self.config = config

    def analyze(self, dataset: Dataset) -> dict[str, int]:
        return {"records": len(dataset)}


class FakeVisualization:
    plugin_id = "fake.visualization"

    def configure(self, config: object) -> None:
        self.config = config

    def visualize(self, dataset: Dataset) -> dict[str, int]:
        return {"records": len(dataset)}


class FakeReport:
    plugin_id = "fake.report"

    def configure(self, config: object) -> None:
        self.config = config

    def generate(self, dataset: Dataset, artifacts: dict[str, Any]) -> dict[str, Any]:
        return {"records": len(dataset), "artifacts": sorted(artifacts)}


def make_problem() -> Problem:
    return Problem(
        name="benchmark",
        variables=(
            DecisionVariable(
                name="x",
                type=VariableType.CONTINUOUS,
                bounds=(0.0, 1.0),
            ),
        ),
        objectives=(Objective(name="score", direction=ObjectiveDirection.MINIMIZE),),
    )


def test_registering_a_plugin() -> None:
    registry = PluginRegistry()
    plugin = FakeOptimizer()

    registry.register(plugin)

    assert "fake.optimizer" in registry
    assert len(registry) == 1


def test_looking_up_a_plugin() -> None:
    registry = PluginRegistry()
    plugin = FakeOptimizer()
    registry.register(plugin)

    found = registry.get("fake.optimizer")

    assert found is plugin


def test_duplicate_plugin_id_rejection() -> None:
    registry = PluginRegistry()
    registry.register(FakeOptimizer())

    with pytest.raises(DuplicatePluginError, match="already registered"):
        registry.register(FakeOptimizer())


def test_missing_plugin_lookup() -> None:
    registry = PluginRegistry()

    with pytest.raises(MissingPluginError, match="No plugin registered"):
        registry.get("missing.plugin")


def test_registry_isolation_between_instances() -> None:
    first = PluginRegistry()
    second = PluginRegistry()

    first.register(FakeOptimizer())

    assert "fake.optimizer" in first
    assert "fake.optimizer" not in second


def test_basic_protocol_contract_compatibility_using_fake_plugins() -> None:
    optimizer = FakeOptimizer()
    simulator = FakeSimulator()
    surrogate = FakeSurrogate()
    analysis = FakeAnalysis()
    visualization = FakeVisualization()
    report = FakeReport()

    problem = make_problem()
    solution = Solution(problem=problem, values={"x": 0.5})
    record = simulator.evaluate(solution)
    dataset = Dataset.from_records([record])

    assert isinstance(optimizer, OptimizerPlugin)
    assert isinstance(simulator, SimulatorPlugin)
    assert optimizer.optimize(problem, simulator)["problem"] == "benchmark"
    assert simulator.evaluate(solution).objective_values == {"score": 1.0}
    surrogate.fit(dataset)
    assert surrogate.predict(solution).objective_values == {"score": 1.0}
    assert analysis.analyze(dataset) == {"records": 1}
    assert visualization.visualize(dataset) == {"records": 1}
    assert isinstance(report, ReportPlugin)
    assert report.generate(dataset, {"figure": "plot.png"}) == {
        "artifacts": ["figure"],
        "records": 1,
    }
