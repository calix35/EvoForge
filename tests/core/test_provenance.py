"""Provenance availability, privacy, installed layouts, and persistence."""

import hashlib
import json
import subprocess
from importlib.metadata import Distribution, PackageNotFoundError
from pathlib import Path

import pytest

from evoforge import __version__
from evoforge.adapters.examples import register_builtin_example_plugins
from evoforge.config import load_experiment_config
from evoforge.core import Experiment, provenance


def config():
    return load_experiment_config("examples/sphere_random_search.yaml")


def collect():
    registry = register_builtin_example_plugins()
    return provenance.collect_provenance(
        config(),
        {
            "optimizer": registry.get("example.random_search"),
            "simulator": registry.get("example.sphere"),
        },
        {},
        (),
    )


def test_metadata_in_current_git_checkout():
    data = collect()
    root = Path(__file__).resolve().parents[2]
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    assert data["git"]["revision"] == revision
    assert type(data["git"]["dirty"]) is bool
    assert (
        data["uv_lock_sha256"]
        == hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()
    )
    assert data["evoforge_version"] == __version__
    assert data["python"]["version"]
    assert data["system"]["os"]
    assert data["system"]["architecture"]
    assert data["distributions"]["evoforge"] == __version__
    optimizer = data["plugins"][0]
    assert optimizer["plugin_id"] == "example.random_search"
    assert optimizer["class"].endswith(".ExampleRandomSearchOptimizer")
    assert optimizer["distributions"] == [{"name": "evoforge", "version": __version__}]


def test_outside_git_and_without_lockfile(tmp_path, monkeypatch):
    monkeypatch.setattr(provenance, "_source_root", lambda: tmp_path)
    data = collect()
    assert data["git"] == {"revision": None, "dirty": None}
    assert data["uv_lock_sha256"] is None
    assert data["python"]["version"]


def test_unborn_git_revision_and_privacy(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    (tmp_path / "private-file-name.txt").write_text("private-file-contents")
    monkeypatch.setenv("EVOFORGE_TEST_SECRET", "private-environment-value")
    monkeypatch.setattr(provenance, "_source_root", lambda: tmp_path)
    data = collect()
    assert data["git"] == {"revision": None, "dirty": True}
    text = json.dumps(data)
    assert "private-file" not in text
    assert "private-environment-value" not in text
    assert "EVOFORGE_TEST_SECRET" not in text


def test_git_from_parent_project_not_misattributed(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    child = tmp_path / "other_project"
    child.mkdir()
    monkeypatch.setattr(provenance, "_source_root", lambda: child)
    assert collect()["git"] == {"revision": None, "dirty": None}


def test_source_root_requires_evoforge_src_layout(tmp_path, monkeypatch):
    module = tmp_path / "src/evoforge/core/provenance.py"
    monkeypatch.setattr(provenance, "__file__", str(module))
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "evoforge"\n')
    assert provenance._source_root() == tmp_path
    project.write_text('[project]\nname = "another-project"\n')
    assert provenance._source_root() is None


def test_installed_distribution_without_repository(tmp_path, monkeypatch):
    info = tmp_path / "evoforge-9.8.7.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Name: evoforge\nVersion: 9.8.7\n")
    installed = Distribution.at(info)

    def version(name):
        if name == "evoforge":
            return installed.version
        raise PackageNotFoundError(name)

    monkeypatch.setattr(
        provenance,
        "__file__",
        str(tmp_path / "site-packages/evoforge/core/provenance.py"),
    )
    monkeypatch.setattr(provenance.distribution_metadata, "version", version)
    monkeypatch.setattr(
        provenance.distribution_metadata, "distributions", lambda: [installed]
    )
    # Even though cwd is a checkout, installed code must not borrow its Git/lock.
    data = collect()
    assert data["evoforge_version"] == "9.8.7"
    assert data["distributions"] == {"evoforge": "9.8.7"}
    assert data["git"] == {"revision": None, "dirty": None}
    assert data["uv_lock_sha256"] is None


def test_unknown_plugin_distribution_not_invented(monkeypatch):
    class LocalPlugin:
        pass

    monkeypatch.setattr(provenance, "_package_owners", lambda: {})
    data = provenance._plugin("optimizer", LocalPlugin(), "local.optimizer")
    assert data["distributions"] is None
    assert data["class"].endswith("LocalPlugin")


def test_plugin_distribution_mapping_and_unavailable_version(monkeypatch):
    class External:
        pass

    External.__module__ = "external_plugins.optimizer"
    monkeypatch.setattr(
        provenance, "_package_owners", lambda: {"external_plugins": ["custom-plugin"]}
    )

    def unavailable(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(provenance.distribution_metadata, "version", unavailable)
    assert provenance._plugin("optimizer", External(), "custom")["distributions"] == [
        {"name": "custom-plugin", "version": None}
    ]
    assert collect()["evoforge_version"] is None


def test_metadata_errors_do_not_abort_experiment(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("private error path must not be serialized")

    monkeypatch.setattr(provenance.platform, "machine", fail)
    monkeypatch.setattr(provenance, "_versions", fail)
    monkeypatch.setattr(provenance, "_lock_hash", fail)
    monkeypatch.setattr(provenance.subprocess, "check_output", fail)
    cfg = config()
    cfg.outputs.directory = str(tmp_path)
    result = Experiment(cfg, register_builtin_example_plugins()).run()
    stored = json.loads((tmp_path / "metadata.json").read_text())
    data = stored["provenance"]
    assert data["system"]["architecture"] is None
    assert data["distributions"] is None
    assert data["uv_lock_sha256"] is None
    assert data["git"] == {"revision": None, "dirty": None}
    assert "private error path" not in json.dumps(stored)
    assert result.status.value == "completed"


def test_configured_experiment_seed_is_not_assumed_used_by_optimizer(tmp_path):
    cfg = config()
    cfg.outputs.directory = str(tmp_path)
    cfg.experiment.seed = 91
    cfg.optimizer.parameters["seed"] = 7
    result = Experiment(cfg, register_builtin_example_plugins()).run()
    seeds = result.reproducibility_metadata["provenance"]["seeds"]
    assert seeds["configured"]["experiment"] == 91
    assert seeds["configured"]["optimizer"]["seed"] == 7
    assert seeds["effective"]["optimizer"] == 7
    assert seeds["effective"]["initial_design"] is None


def test_unreported_seed_remains_unavailable(tmp_path):
    cfg = config()
    cfg.outputs.directory = str(tmp_path)
    cfg.optimizer.parameters.pop("seed")
    result = Experiment(cfg, register_builtin_example_plugins()).run()
    assert (
        result.reproducibility_metadata["provenance"]["seeds"]["effective"]["optimizer"]
        is None
    )


def test_unusable_seed_reports_are_not_serialized():
    cfg = config()
    plugin = type("ExternalPlugin", (), {})()
    plugin.last_run_metadata = {"optimizer_seed": "private-value-not-a-seed"}
    data = provenance.collect_provenance(cfg, {"optimizer": plugin}, {}, ())
    assert data["seeds"]["effective"]["optimizer"] is None
    assert "private-value-not-a-seed" not in json.dumps(data)


def test_malformed_source_project_is_unavailable_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setattr(
        provenance, "__file__", str(tmp_path / "src/evoforge/core/provenance.py")
    )
    (tmp_path / "pyproject.toml").write_text("[not-valid-toml")
    data = collect()
    assert data["uv_lock_sha256"] is None
    assert data["git"] == {"revision": None, "dirty": None}
    assert data["python"]["version"]


@pytest.mark.parametrize(
    "example", ["sphere_pymoo_ga", "sphere_surrogate", "zdt1_nsga2"]
)
def test_real_runtime_provenance_persisted_for_each_workflow(tmp_path, example):
    pytest.importorskip("pymoo")
    from evoforge.adapters.pymoo import register_pymoo_plugins

    registry = register_pymoo_plugins(register_builtin_example_plugins())
    if example == "sphere_surrogate":
        pytest.importorskip("sklearn")
        from evoforge.adapters.sklearn import register_sklearn_plugins

        register_sklearn_plugins(registry)
    cfg = load_experiment_config(f"examples/{example}.yaml")
    cfg.outputs.directory = str(tmp_path)
    result = Experiment(cfg, registry).run()
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata == result.reproducibility_metadata
    data = metadata["provenance"]
    assert data["distributions"]["pymoo"]
    assert data["evoforge_version"] == __version__
    assert len(data["uv_lock_sha256"]) == 64
    assert all(plugin["class"].startswith("evoforge.") for plugin in data["plugins"])
    if example == "sphere_surrogate":
        assert data["seeds"]["effective"]["initial_design"] == 42
        assert data["seeds"]["effective"]["surrogate_random_state"] == 42
        assert data["seeds"]["effective"]["optimizer_searches"] == [
            {"iteration": item["iteration"], "seed": item["optimizer_seed"]}
            for item in metadata["iterations"]
        ]
        assert {p["role"] for p in data["plugins"]} == {
            "optimizer",
            "simulator",
            "surrogate",
        }
    else:
        assert data["seeds"]["effective"]["optimizer"] == 42


def test_generated_surrogate_seed_reported_separately(tmp_path):
    pytest.importorskip("pymoo")
    pytest.importorskip("sklearn")
    from evoforge.adapters.pymoo import register_pymoo_plugins
    from evoforge.adapters.sklearn import register_sklearn_plugins

    cfg = load_experiment_config("examples/sphere_surrogate.yaml")
    cfg.experiment.seed = None
    cfg.outputs.directory = str(tmp_path)
    registry = register_sklearn_plugins(
        register_pymoo_plugins(register_builtin_example_plugins())
    )
    result = Experiment(cfg, registry).run()
    seeds = result.reproducibility_metadata["provenance"]["seeds"]
    assert seeds["configured"]["experiment"] is None
    assert type(seeds["effective"]["initial_design"]) is int


def test_aquacrop_climate_provenance_preserved_in_metadata(tmp_path):
    pytest.importorskip("aquacrop")
    pytest.importorskip("pymoo")
    from evoforge.adapters.aquacrop import register_aquacrop_plugins
    from evoforge.adapters.pymoo import register_pymoo_plugins

    cfg = load_experiment_config("examples/aquacrop_irrigation_ga.yaml")
    cfg.outputs.directory = str(tmp_path)
    result = Experiment(cfg, register_aquacrop_plugins(register_pymoo_plugins())).run()
    data = json.loads((tmp_path / "metadata.json").read_text())["provenance"]
    assert data["climate"] == [
        {
            "weather": result.records[0].metadata["weather"],
            "aquacrop_version": "3.1.0",
        }
    ]
