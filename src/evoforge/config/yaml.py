"""YAML loading helpers for EvoForge experiment configuration."""

from pathlib import Path
from typing import Any

import yaml

from evoforge.config.models import ExperimentConfig


def load_experiment_config(path: str | Path) -> ExperimentConfig:
    """Load and validate an EvoForge experiment configuration YAML file."""

    with Path(path).open(encoding="utf-8") as config_file:
        data: Any = yaml.safe_load(config_file)

    if data is None:
        data = {}

    return ExperimentConfig.model_validate(data)

