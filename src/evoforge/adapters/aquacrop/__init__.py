"""Optional AquaCrop-OSPy adapter registration."""

from evoforge.plugins import PluginRegistry


def register_aquacrop_plugins(
    registry: PluginRegistry | None = None,
) -> PluginRegistry:
    """Register the irrigation simulator without importing AquaCrop."""
    from evoforge.adapters.aquacrop.plugins import AquaCropIrrigationSimulator

    plugin_registry = registry if registry is not None else PluginRegistry()
    plugin_registry.register(AquaCropIrrigationSimulator())
    return plugin_registry


__all__ = ["register_aquacrop_plugins"]
