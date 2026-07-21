"""Explicit plugin registry for EvoForge."""

from __future__ import annotations

from typing import TypeVar

from evoforge.plugins.contracts import Plugin

PluginT = TypeVar("PluginT", bound=Plugin)


class DuplicatePluginError(ValueError):
    """Raised when registering more than one plugin with the same ID."""


class MissingPluginError(KeyError):
    """Raised when a plugin ID is not registered."""


class PluginRegistry:
    """In-memory registry for explicitly registered plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        """Register a plugin by its stable plugin ID."""

        plugin_id = plugin.plugin_id
        if not plugin_id or not plugin_id.strip():
            msg = "Plugin ID must not be empty."
            raise ValueError(msg)
        if plugin_id in self._plugins:
            msg = f"Plugin with ID {plugin_id!r} is already registered."
            raise DuplicatePluginError(msg)
        self._plugins[plugin_id] = plugin

    def get(
        self,
        plugin_id: str,
        plugin_type: type[PluginT] | None = None,
    ) -> Plugin | PluginT:
        """Look up a plugin by ID."""

        try:
            plugin = self._plugins[plugin_id]
        except KeyError as error:
            msg = f"No plugin registered with ID {plugin_id!r}."
            raise MissingPluginError(msg) from error

        if plugin_type is not None and not isinstance(plugin, plugin_type):
            msg = f"Plugin {plugin_id!r} does not implement {plugin_type.__name__}."
            raise TypeError(msg)

        return plugin

    def __contains__(self, plugin_id: str) -> bool:
        return plugin_id in self._plugins

    def __len__(self) -> int:
        return len(self._plugins)
