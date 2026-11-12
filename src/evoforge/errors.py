"""Contextual runtime errors without dependencies on concrete plugins."""

from contextlib import contextmanager


class EvoForgeError(RuntimeError):
    """An error at an experiment boundary, chained to its original exception."""

    category = "Experiment error"

    def __init__(self, stage: str, plugin_id: str | None, original: Exception):
        self.stage = stage
        self.plugin_id = plugin_id
        self.original_type = type(original).__name__
        plugin = f" plugin={plugin_id!r}" if plugin_id is not None else ""
        super().__init__(
            f"{self.category} at {stage}{plugin} ({self.original_type}): {original}"
        )

    def as_dict(self) -> dict:
        """Serializable context; exception objects stay in memory."""
        return {
            "category": type(self).__name__,
            "stage": self.stage,
            "plugin_id": self.plugin_id,
            "original_type": self.original_type,
            "message": str(self),
        }


class ConfigurationError(EvoForgeError):
    category = "Configuration error"


class PluginExecutionError(EvoForgeError):
    category = "Plugin execution error"


class OutputError(EvoForgeError):
    category = "Output error"


class _ControlFlowSignal(Exception):
    """Internal budget termination, never classified as a plugin failure."""


@contextmanager
def error_context(error_type, stage: str, plugin_id: str | None = None):
    """Keep the innermost context and let interpreter/control signals propagate."""
    try:
        yield
    except (EvoForgeError, _ControlFlowSignal):
        raise
    except Exception as error:
        raise error_type(stage, plugin_id, error) from error


__all__ = ["ConfigurationError", "EvoForgeError", "OutputError", "PluginExecutionError"]
