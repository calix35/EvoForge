"""Typer-based command-line interface for EvoForge."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml
from pydantic import ValidationError

from evoforge.adapters.examples import register_builtin_example_plugins
from evoforge.core import Experiment
from evoforge.errors import ConfigurationError, EvoForgeError
from evoforge.plugins import PluginRegistry

app = typer.Typer(help="EvoForge command-line interface.", no_args_is_help=True)
_plugin_registry: PluginRegistry | None = None


@app.callback()
def cli() -> None:
    """EvoForge command-line interface."""


@app.command()
def run(config_path: Path) -> None:
    """Run an EvoForge experiment from a YAML configuration file."""

    try:
        registry = (
            _plugin_registry
            if _plugin_registry is not None
            else _default_plugin_registry()
        )
        experiment = Experiment.from_config(config_path, registry=registry)
        result = experiment.run()
    except EvoForgeError as error:
        prefix = ""
        if isinstance(error, ConfigurationError):
            if error.stage == "load_config" and isinstance(
                error.__cause__, FileNotFoundError
            ):
                prefix = f"Configuration file not found: {config_path}. "
            elif error.stage == "load_config" and isinstance(
                error.__cause__, yaml.YAMLError
            ):
                prefix = "Invalid YAML in configuration file: "
            elif isinstance(error.__cause__, ValidationError):
                prefix = "Configuration validation failed: "
            elif error.stage == "lookup":
                prefix = "Plugin lookup failed: "
        typer.secho(prefix + str(error), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    except (ValueError, RuntimeError, OSError) as error:
        typer.secho(
            f"Execution failed ({type(error).__name__}): {error}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from None

    typer.echo(
        "Experiment "
        f"{result.experiment_id} finished with status {result.status.value}. "
        f"Output directory: {result.output_directory}"
    )
    if result.status.value == "failed":
        typer.echo(str(result.reproducibility_metadata.get("termination_reason")))
        if "error" in result.reproducibility_metadata:
            typer.echo(result.reproducibility_metadata["error"], err=True)
        raise typer.Exit(code=1)


def main() -> None:
    """Run the EvoForge CLI application."""

    app()


def _default_plugin_registry() -> PluginRegistry:
    from evoforge.adapters.aquacrop import register_aquacrop_plugins
    from evoforge.adapters.sklearn import register_sklearn_plugins

    registry = register_builtin_example_plugins()
    register_sklearn_plugins(registry)
    register_aquacrop_plugins(registry)
    try:
        from evoforge.adapters.pymoo import register_pymoo_plugins
    except ImportError:
        return registry

    return register_pymoo_plugins(registry)
