"""Optional pymoo adapter registration for EvoForge."""

from __future__ import annotations

from evoforge.plugins import PluginRegistry


def register_pymoo_plugins(registry: PluginRegistry | None = None) -> PluginRegistry:
    """Register optional pymoo plugins into a plugin registry."""

    from evoforge.adapters.pymoo.nsga2 import PymooNSGA2Optimizer
    from evoforge.adapters.pymoo.plugins import PymooGAOptimizer
    from evoforge.adapters.pymoo.zdt1 import ExampleZDT1Simulator

    plugin_registry = registry if registry is not None else PluginRegistry()
    plugin_registry.register(PymooGAOptimizer())
    plugin_registry.register(PymooNSGA2Optimizer())
    plugin_registry.register(ExampleZDT1Simulator())
    return plugin_registry


__all__ = ["register_pymoo_plugins"]
