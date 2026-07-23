"""Typer-based command-line interface for EvoForge."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml
from pydantic import ValidationError

from evoforge.core import Experiment
from evoforge.plugins import MissingPluginError, PluginRegistry

app = typer.Typer(help="EvoForge command-line interface.", no_args_is_help=True)
_plugin_registry: PluginRegistry | None = None


@app.callback()
def cli() -> None:
    """EvoForge command-line interface."""


@app.command()
def run(config_path: Path) -> None:
    """Run an EvoForge experiment from a YAML configuration file."""

    try:
        experiment = Experiment.from_config(config_path, registry=_plugin_registry)
        result = experiment.run()
    except FileNotFoundError:
        typer.secho(
            f"Configuration file not found: {config_path}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from None
    except yaml.YAMLError as error:
        typer.secho(
            f"Invalid YAML in configuration file: {error}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from None
    except ValidationError as error:
        typer.secho(
            f"Configuration validation failed:\n{error}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from None
    except MissingPluginError as error:
        typer.secho(
            f"Plugin lookup failed: {error}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from None

    typer.echo(
        "Experiment "
        f"{result.experiment_id} finished with status {result.status.value}. "
        f"Output directory: {result.output_directory}"
    )


def main() -> None:
    """Run the EvoForge CLI application."""

    app()
