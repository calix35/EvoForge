"""Optional pymoo adapter registration for EvoForge."""

from __future__ import annotations

from evoforge.plugins import PluginRegistry


def register_pymoo_plugins(registry: PluginRegistry | None = None) -> PluginRegistry:
    """Register optional pymoo plugins into a plugin registry."""

    from evoforge.adapters.pymoo.plugins import PymooGAOptimizer

    plugin_registry = registry if registry is not None else PluginRegistry()
    plugin_registry.register(PymooGAOptimizer())
    return plugin_registry


__all__ = ["register_pymoo_plugins"]

