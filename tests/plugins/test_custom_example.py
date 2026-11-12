"""Execute the external-registration walkthrough against the released API."""

import runpy
from pathlib import Path

import pytest

from evoforge.adapters.examples import register_builtin_example_plugins
from evoforge.config import ExperimentConfig, SimulatorConfig, load_experiment_config
from evoforge.core import Experiment
from evoforge.errors import ConfigurationError
from evoforge.plugins import PluginRegistry, SimulatorPlugin

EXAMPLE = Path(__file__).resolve().parents[2] / "examples/custom_simulator.py"


def test_user_plugin_registration_and_execution(tmp_path):
    namespace = runpy.run_path(str(EXAMPLE))
    plugin = namespace["ShiftedSphere"]()
    registry = PluginRegistry()
    registry.register(plugin)
    assert registry.get("user.shifted_sphere", SimulatorPlugin) is plugin
    result = namespace["main"](tmp_path)
    assert len(result.records) == 5
    assert all(r.source == "user.shifted_sphere" for r in result.records)
    for record in result.records:
        expected = sum((float(x) - 1) ** 2 for x in record.solution.values.values())
        assert record.objective_values == {"loss": expected}
    assert (tmp_path / "manifest.json").is_file()


def test_user_plugin_rejects_unexpected_configuration():
    plugin = runpy.run_path(str(EXAMPLE))["ShiftedSphere"]()
    with pytest.raises(TypeError):
        plugin.configure(object())
    with pytest.raises(ValueError):
        plugin.configure(SimulatorConfig(plugin=plugin.plugin_id, parameters={"x": 1}))


@pytest.mark.parametrize("mode", ["function", "surrogate", "hybrid"])
def test_reserved_schema_mode_fails_before_optimization(tmp_path, monkeypatch, mode):
    data = load_experiment_config(EXAMPLE.with_name("sphere_random_search.yaml"))
    raw = data.model_dump()
    raw["evaluator"]["type"] = mode
    raw["outputs"]["directory"] = str(tmp_path / "not_created")
    config = ExperimentConfig.model_validate(raw)
    registry = register_builtin_example_plugins()

    def must_not_optimize(*args):
        pytest.fail("Unsupported evaluator reached optimization.")

    monkeypatch.setattr(
        registry.get(config.optimizer.plugin), "optimize", must_not_optimize
    )
    with pytest.raises(ConfigurationError) as caught:
        Experiment(config, registry).run()
    assert isinstance(caught.value.__cause__, NotImplementedError)
    assert not Path(config.outputs.directory).exists()
