"""Standard-library plugin contracts for EvoForge integrations."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from evoforge.domain import Dataset, EvaluationRecord, Problem, Solution


@runtime_checkable
class Plugin(Protocol):
    """Common contract shared by all EvoForge plugins."""

    @property
    def plugin_id(self) -> str:
        """Stable identifier used for explicit plugin registration and lookup."""

    def configure(self, config: object) -> None:
        """Configure the plugin from a validated configuration object."""


@runtime_checkable
class OptimizerPlugin(Plugin, Protocol):
    """Contract for optimizer integrations."""

    def optimize(self, problem: Problem, evaluator: object) -> Any:
        """Optimize a problem using an evaluation provider."""


@runtime_checkable
class SimulatorPlugin(Plugin, Protocol):
    """Contract for simulator integrations."""

    def evaluate(self, solution: Solution) -> EvaluationRecord:
        """Evaluate a solution with a simulator."""


@runtime_checkable
class SurrogatePlugin(Plugin, Protocol):
    """Contract for surrogate model integrations."""

    def fit(self, dataset: Dataset) -> None:
        """Fit a surrogate model from evaluation records."""

    def predict(self, solution: Solution) -> EvaluationRecord:
        """Predict an evaluation record for a solution."""


@runtime_checkable
class AnalysisPlugin(Plugin, Protocol):
    """Contract for statistical analysis integrations."""

    def analyze(self, dataset: Dataset) -> Any:
        """Analyze an evaluation dataset."""


@runtime_checkable
class VisualizationPlugin(Plugin, Protocol):
    """Contract for visualization integrations."""

    def visualize(self, dataset: Dataset) -> Any:
        """Create visualizations from an evaluation dataset."""


@runtime_checkable
class ReportPlugin(Plugin, Protocol):
    """Contract for report generation integrations."""

    def generate(self, dataset: Dataset, artifacts: dict[str, Any]) -> Any:
        """Generate a report from an evaluation dataset and artifacts."""
