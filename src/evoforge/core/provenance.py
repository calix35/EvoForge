"""Best-effort, local provenance without importing scientific libraries."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import tomllib
from functools import lru_cache
from importlib import metadata as distribution_metadata
from pathlib import Path
from typing import Any

from evoforge.config import ExperimentConfig
from evoforge.domain import EvaluationRecord


def _available(operation):
    try:
        return operation()
    except Exception:
        # Metadata failure must not abort computation or expose exception paths.
        return None


def _source_root() -> Path | None:
    location = Path(__file__).resolve()
    source = location.parent.parent.parent
    if source.name != "src":
        return None
    root = source.parent
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return root if project.get("project", {}).get("name") == "evoforge" else None


def _git(root: Path | None) -> dict[str, Any]:
    result = {"revision": None, "dirty": None}
    if root is None:
        return result

    def command(*args):
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).strip()

    checkout = _available(lambda: command("rev-parse", "--show-toplevel"))
    if checkout is None or Path(checkout).resolve() != root.resolve():
        return result
    result["revision"] = _available(lambda: command("rev-parse", "HEAD"))
    status = _available(
        lambda: command("status", "--porcelain=v1", "--untracked-files=normal")
    )
    result["dirty"] = None if status is None else bool(status)
    return result


def _lock_hash(root: Path | None) -> str | None:
    if root is None:
        return None
    return hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()


def _versions() -> dict[str, str]:
    return dict(
        sorted(
            (dist.metadata["Name"], dist.version)
            for dist in distribution_metadata.distributions()
        )
    )


@lru_cache(maxsize=1)
def _package_owners() -> dict[str, list[str]]:
    return distribution_metadata.packages_distributions()


def _plugin(role: str, plugin: object, plugin_id: str) -> dict[str, Any]:
    cls = type(plugin)
    package = cls.__module__.split(".")[0]
    # Editable installs may not expose top_level.txt. These are our own wrappers,
    # not classes owned by the scientific library they call.
    owners = (
        ["evoforge"]
        if package == "evoforge"
        else ((_available(_package_owners) or {}).get(package, []))
    )
    return {
        "role": role,
        "plugin_id": plugin_id,
        "class": f"{cls.__module__}.{cls.__qualname__}",
        "distributions": [
            {
                "name": name,
                "version": _available(
                    lambda name=name: distribution_metadata.version(name)
                ),
            }
            for name in owners
        ]
        or None,
    }


def _seeds(config: ExperimentConfig, runtime: dict, plugins: dict) -> dict:
    def observed(value):
        return value if type(value) is int else None

    def configured(parameters):
        return {key: observed(parameters.get(key)) for key in ("seed", "random_state")}

    optimizer_report = _available(lambda: plugins["optimizer"].last_run_metadata) or {}
    assisted = config.surrogate.enabled
    return {
        "configured": {
            "experiment": config.experiment.seed,
            "optimizer": configured(config.optimizer.parameters),
            "simulator": configured(config.evaluator.simulator.parameters)
            if config.evaluator.simulator
            else None,
            "surrogate": configured(config.surrogate.parameters) if assisted else None,
        },
        "effective": {
            "initial_design": observed(runtime.get("effective_seed"))
            if assisted
            else None,
            "optimizer": None
            if assisted
            else observed(
                runtime.get("optimizer_seed", optimizer_report.get("optimizer_seed"))
            ),
            "optimizer_searches": [
                {
                    "iteration": item["iteration"],
                    "seed": observed(item["optimizer_seed"]),
                }
                for item in runtime.get("iterations", [])
            ]
            if assisted
            else [],
            "surrogate_random_state": observed(
                runtime.get("surrogate_parameters", {}).get("random_state")
            )
            if assisted
            else None,
            "simulator": None,
        },
    }


def _climate(records: tuple[EvaluationRecord, ...]) -> list[dict] | None:
    unique = {}
    for record in records:
        if "weather" not in record.metadata:
            continue
        # Preserve only adapter-published climate provenance; never read climate
        # contents or arbitrary plugin configuration here.
        entry = {
            "weather": {
                key: record.metadata["weather"].get(key)
                for key in ("path", "provenance", "sha256")
            },
            "aquacrop_version": record.metadata.get("aquacrop_version"),
        }
        unique[json.dumps(entry, sort_keys=True)] = entry
    return list(unique.values()) or None


def collect_provenance(
    config: ExperimentConfig,
    plugins: dict[str, object],
    runtime_metadata: dict[str, Any],
    records: tuple[EvaluationRecord, ...],
) -> dict[str, Any]:
    """Collect observed provenance; absent or inaccessible values are JSON null."""
    root = _available(_source_root)
    ids = {
        "optimizer": config.optimizer.plugin,
        "simulator": config.evaluator.simulator.plugin
        if config.evaluator.simulator
        else None,
        "surrogate": config.surrogate.plugin,
    }
    return {
        "evoforge_version": _available(
            lambda: distribution_metadata.version("evoforge")
        ),
        "python": {
            "version": _available(platform.python_version),
            "implementation": _available(platform.python_implementation),
        },
        "system": {
            "os": _available(platform.system),
            "release": _available(platform.release),
            "architecture": _available(platform.machine),
        },
        "distributions": _available(_versions),
        "plugins": [
            _available(
                lambda role=role, plugin=plugin: _plugin(role, plugin, ids[role])
            )
            for role, plugin in plugins.items()
        ],
        "git": _available(lambda: _git(root)),
        "uv_lock_sha256": _available(lambda: _lock_hash(root)),
        "seeds": _available(lambda: _seeds(config, runtime_metadata, plugins)),
        "climate": _available(lambda: _climate(records)),
    }
