"""Public plugin contracts and registry for EvoForge."""

from evoforge.plugins.contracts import (
    AnalysisPlugin,
    OptimizerPlugin,
    Plugin,
    ReportPlugin,
    SimulatorPlugin,
    SurrogatePlugin,
    VisualizationPlugin,
)
from evoforge.plugins.registry import (
    DuplicatePluginError,
    MissingPluginError,
    PluginRegistry,
)

__all__ = [
    "AnalysisPlugin",
    "DuplicatePluginError",
    "MissingPluginError",
    "OptimizerPlugin",
    "Plugin",
    "PluginRegistry",
    "ReportPlugin",
    "SimulatorPlugin",
    "SurrogatePlugin",
    "VisualizationPlugin",
]
