"""Built-in example plugins for EvoForge."""

from evoforge.adapters.examples.plugins import (
    ExampleRandomSearchOptimizer,
    ExampleSphereSimulator,
    register_builtin_example_plugins,
)

__all__ = [
    "ExampleRandomSearchOptimizer",
    "ExampleSphereSimulator",
    "register_builtin_example_plugins",
]

