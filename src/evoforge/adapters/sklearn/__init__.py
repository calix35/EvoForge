"""Optional scikit-learn adapter registration for EvoForge."""

from __future__ import annotations

from evoforge.plugins import PluginRegistry


def register_sklearn_plugins(registry: PluginRegistry | None = None) -> PluginRegistry:
    """Register optional scikit-learn plugins into a plugin registry."""

    from evoforge.adapters.sklearn.plugins import RandomForestSurrogate

    plugin_registry = registry if registry is not None else PluginRegistry()
    plugin_registry.register(RandomForestSurrogate())
    return plugin_registry


__all__ = ["register_sklearn_plugins"]
