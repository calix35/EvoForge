"""Reproducible, budget-checked direct versus surrogate AquaCrop pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import platform
import subprocess
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from importlib.metadata import distributions
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Any

from evoforge.config import ExperimentConfig, load_experiment_config
from evoforge.core import Experiment
from evoforge.data import OutputManager
from evoforge.domain import EvaluationRecord, EvaluationStatus
from evoforge.errors import _ControlFlowSignal

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class PilotSettings:
    seeds: tuple[int, ...] = tuple(range(10))
    real_budget: int = 60
    pop_size: int = 20
    initial_size: int = 20
    candidates_per_update: int = 4
    search_budget: int = 200
    n_estimators: int = 100

    def validate(self) -> None:
        if not self.seeds or len(set(self.seeds)) != len(self.seeds):
            raise ValueError("Seeds must be nonempty and unique.")
        if any(seed < 0 or seed >= 2**32 for seed in self.seeds):
            raise ValueError("Seeds must be in [0, 2**32).")
        if self.pop_size < 2 or self.real_budget < self.pop_size:
            raise ValueError("Require pop_size >= 2 and real_budget >= pop_size.")
        if self.real_budget % self.pop_size:
            raise ValueError(
                "real_budget must be a multiple of pop_size for direct GA."
            )
        if not 2 <= self.initial_size < self.real_budget:
            raise ValueError("Require 2 <= initial_size < real_budget.")
        if (
            not 1
            <= self.candidates_per_update
            <= min(self.search_budget, self.real_budget - self.initial_size)
        ):
            raise ValueError(
                "Incompatible candidates_per_update and surrogate budgets."
            )
        if self.n_estimators < 1:
            raise ValueError("n_estimators must be positive.")


class _RealBudgetReached(_ControlFlowSignal):
    pass


class _CountedSimulator:
    """Count attempted real calls, including errors, before invoking the simulator."""

    plugin_id = "aquacrop.irrigation"

    def __init__(self, simulator, budget: int):
        self.simulator = simulator
        self.budget = budget
        self.calls = 0
        self.blocked_calls = 0
        self.records: list[EvaluationRecord] = []

    def configure(self, config):
        self.simulator.configure(config)

    def evaluate(self, solution):
        if self.calls >= self.budget:
            self.blocked_calls += 1
            raise _RealBudgetReached("Real simulator budget exhausted.")
        self.calls += 1
        started = perf_counter()
        try:
            record = self.simulator.evaluate(solution)
            if (
                record.solution.values != solution.values
                or set(record.objective_values) != {"dry_yield"}
                or not all(isfinite(v) for v in record.objective_values.values())
            ):
                raise ValueError("Invalid real simulator record.")
        except Exception as error:
            self.records.append(
                EvaluationRecord(
                    solution,
                    {"dry_yield": 0.0},
                    status=EvaluationStatus.FAILED,
                    source=self.plugin_id,
                    metadata={
                        "evaluation_kind": "real",
                        "call_index": self.calls,
                        "elapsed_seconds": perf_counter() - started,
                        "error": f"{type(error).__name__}: {error}",
                    },
                )
            )
            raise
        record = replace(
            record,
            metadata={
                **record.metadata,
                "evaluation_kind": "real",
                "call_index": self.calls,
                "elapsed_seconds": perf_counter() - started,
            },
        )
        self.records.append(record)
        return record


def build_config(settings: PilotSettings, seed: int, method: str, output: Path):
    """Derive effective configs without editing the small executable examples."""
    data = load_experiment_config(
        ROOT / "examples/aquacrop_irrigation_ga.yaml"
    ).model_dump(mode="json")
    data["experiment"].update(name=f"aquacrop_pilot_{method}_{seed}", seed=seed)
    data["optimizer"]["parameters"].update(
        pop_size=settings.pop_size,
        n_evaluations=settings.real_budget,
        seed=seed,
        verbose=False,
    )
    data["outputs"]["directory"] = str(output)
    if method == "surrogate":
        data["optimizer"]["parameters"]["n_evaluations"] = settings.search_budget
        data["surrogate"] = {
            "enabled": True,
            "plugin": "sklearn.random_forest",
            "parameters": {"n_estimators": settings.n_estimators, "random_state": seed},
            "workflow": {
                "initial_size": settings.initial_size,
                "real_budget": settings.real_budget,
                "search_budget": settings.search_budget,
                "candidates_per_update": settings.candidates_per_update,
            },
        }
    return ExperimentConfig.model_validate(data)


def _plugins():
    from evoforge.adapters.aquacrop.plugins import AquaCropIrrigationSimulator
    from evoforge.adapters.pymoo import register_pymoo_plugins
    from evoforge.adapters.sklearn import register_sklearn_plugins

    return (
        register_sklearn_plugins(register_pymoo_plugins()),
        AquaCropIrrigationSimulator(),
    )


def _environment() -> dict[str, Any]:
    started = perf_counter()
    # Import entry points once, without making untimed simulator or model-fit calls.
    for module in (
        "aquacrop",
        "aquacrop.utils",
        "sklearn.ensemble",
        "pymoo.algorithms.soo.nonconvex.ga",
        "pymoo.optimize",
        "pymoo.termination",
    ):
        importlib.import_module(module)
    import_seconds = perf_counter() - started
    weather = Path(
        importlib.import_module("aquacrop.utils").get_filepath("champion_climate.txt")
    ).resolve()

    def git(*args):
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True)

    status = git("status", "--porcelain=v1", "--untracked-files=all")
    diff = git(
        "diff", "HEAD", "--", "src", "scripts", "examples", "pyproject.toml", "uv.lock"
    )
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "versions": dict(
            sorted((dist.metadata["Name"], dist.version) for dist in distributions())
        ),
        "git": {
            "revision": git("rev-parse", "HEAD").strip(),
            "dirty": bool(status),
            "status_porcelain": status,
            "tracked_diff": diff,
            "tracked_diff_sha256": hashlib.sha256(diff.encode()).hexdigest(),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "weather": {
            "path": str(weather),
            "provenance": "aquacrop_bundled",
            "sha256": hashlib.sha256(weather.read_bytes()).hexdigest(),
        },
        "startup_import_seconds": import_seconds,
        "timing_policy": (
            "Per-run wall time includes plugin construction, configuration, "
            "simulation, "
            "fitting, prediction search, and Experiment output persistence. Excludes "
            "initial entry-point imports, config derivation, provenance collection, "
            "and final pilot summary persistence. No simulator/fit warm-up; remaining "
            "first-use lazy imports/caches may affect timed runs."
        ),
    }


def _snapshot_sources(output: Path) -> dict[str, str]:
    """Archive the effective local implementation, including untracked adapters."""
    files = [ROOT / "pyproject.toml", ROOT / "uv.lock"]
    for folder, pattern in (
        ("src", "*.py"),
        ("scripts", "*.py"),
        ("examples", "*.yaml"),
    ):
        files.extend(sorted((ROOT / folder).rglob(pattern)))
    hashes = {}
    for source in files:
        relative = source.relative_to(ROOT)
        data = source.read_bytes()
        destination = output / "source_snapshot" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        hashes[str(relative)] = hashlib.sha256(data).hexdigest()
    return hashes


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _trajectory(records):
    best = None
    points = []
    for call, record in enumerate(records, 1):
        if record.status is EvaluationStatus.SUCCESS and isfinite(
            record.objective_values["dry_yield"]
        ):
            if (
                best is None
                or record.objective_values["dry_yield"]
                > (best.objective_values["dry_yield"])
            ):
                best = record
        points.append(
            {
                "real_calls": call,
                "best_dry_yield_t_ha": best.objective_values["dry_yield"]
                if best
                else None,
                "best_irrigation_mm": (
                    best.metadata.get("seasonal_irrigation_mm") if best else None
                ),
            }
        )
    return best, points


def _run_one(settings, config, method, seed, order, environment, plugin_factory):
    output = Path(config.outputs.directory)
    output.mkdir(parents=True, exist_ok=False)
    monitor = None
    result = None
    error = None
    reason = "real_budget_exhausted"
    status = "completed"
    started_at = datetime.now(UTC).isoformat()
    started = perf_counter()
    try:
        registry, simulator = plugin_factory()
        monitor = _CountedSimulator(simulator, settings.real_budget)
        registry.register(monitor)
        result = Experiment(config, registry).run()
        status = result.status.value
        reason = result.reproducibility_metadata.get("termination_reason", reason)
    except _RealBudgetReached:
        reason = "real_budget_guard"
    except Exception as exc:
        status = "failed"
        reason = "execution_error"
        error = f"{type(exc).__name__}: {exc}"
    elapsed = perf_counter() - started
    records = tuple(monitor.records) if monitor else ()
    calls = monitor.calls if monitor else 0
    if result is not None:
        error = result.reproducibility_metadata.get("error")
        if len(result.records) != calls:
            status, reason = "failed", "call_count_mismatch"
        else:
            records = result.records
    if calls != settings.real_budget and status == "completed":
        status = "incomplete"
        if reason == "real_budget_exhausted":
            reason = "optimizer_stopped_early"
    if calls > settings.real_budget:
        raise AssertionError("Simulator budget guard failed.")
    hashes = {
        r.metadata.get("weather", {}).get("sha256")
        for r in records
        if r.status is EvaluationStatus.SUCCESS
    }
    if hashes and hashes != {environment["weather"]["sha256"]}:
        status, reason = "failed", "weather_hash_mismatch"
    best, trajectory = _trajectory(records)
    failures = sum(r.status is not EvaluationStatus.SUCCESS for r in records)
    summary = {
        "seed": seed,
        "method": method,
        "execution_order": order,
        "status": status,
        "termination_reason": reason,
        "best_dry_yield_t_ha": best.objective_values["dry_yield"] if best else None,
        "best_irrigation_mm": best.metadata.get("seasonal_irrigation_mm")
        if best
        else None,
        "real_calls": calls,
        "failures": failures,
        "budget_complete": calls == settings.real_budget,
        "prediction_calls": (
            result.reproducibility_metadata.get("prediction_calls", 0) if result else 0
        ),
        "elapsed_seconds": elapsed,
        "output_directory": str(output),
        "error": error,
    }
    metadata = dict(result.reproducibility_metadata) if result else {}
    metadata["pilot"] = {
        **environment,
        **summary,
        "settings": asdict(settings),
        "started_at": started_at,
        "error": error,
        "blocked_simulator_calls": monitor.blocked_calls if monitor else 0,
    }
    OutputManager(output).save_run_outputs(
        config, metadata, records, result.predictions if result else ()
    )
    serialized = (
        json.loads((output / "evaluation_records.json").read_text()) if records else []
    )
    _write_json(
        output / "failures.json", [r for r in serialized if r["status"] != "success"]
    )
    _write_json(output / "trajectory.json", trajectory)
    if trajectory:
        _write_csv(output / "trajectory.csv", trajectory)
    _write_json(output / "run_summary.json", summary)
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for name in ("failures.json", "trajectory.json", "run_summary.json"):
        manifest["artifacts"].append({"name": name, "path": name, "kind": "pilot"})
    if trajectory:
        manifest["artifacts"].append(
            {"name": "trajectory.csv", "path": "trajectory.csv", "kind": "pilot"}
        )
    _write_json(manifest_path, manifest)
    return summary


def run_pilot(
    settings: PilotSettings, output: Path, *, plugin_factory=_plugins, environment=None
) -> list[dict]:
    """Run paired methods in alternating order; refuse to overwrite an earlier pilot."""
    settings.validate()
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Pilot directory already exists: {output}")
    environment = _environment() if environment is None else environment
    jobs = []
    for index, seed in enumerate(settings.seeds):
        methods = ("direct", "surrogate") if index % 2 == 0 else ("surrogate", "direct")
        for method in methods:
            destination = output / f"seed_{seed:04d}" / method
            jobs.append(
                (seed, method, build_config(settings, seed, method, destination))
            )
    output.mkdir(parents=True, exist_ok=False)
    environment = {**environment, "source_sha256": _snapshot_sources(output)}
    _write_json(
        output / "pilot.json",
        {
            "settings": asdict(settings),
            "environment": environment,
            "execution_order": [{"seed": s, "method": m} for s, m, _ in jobs],
        },
    )
    summaries = []
    for order, (seed, method, config) in enumerate(jobs):
        summaries.append(
            _run_one(settings, config, method, seed, order, environment, plugin_factory)
        )
        _write_json(output / "summary.json", summaries)
        _write_csv(output / "summary.csv", summaries)
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/aquacrop_pilot"))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    for name in (
        "real_budget",
        "pop_size",
        "initial_size",
        "candidates_per_update",
        "search_budget",
        "n_estimators",
    ):
        parser.add_argument(
            "--" + name.replace("_", "-"),
            type=int,
            default=getattr(PilotSettings(), name),
        )
    args = vars(parser.parse_args())
    output = args.pop("output")
    args["seeds"] = tuple(args["seeds"])
    try:
        rows = run_pilot(PilotSettings(**args), output)
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        parser.exit(1, f"Pilot error: {error}\n")
    for row in rows:
        print(
            f"{row['method']} seed={row['seed']}: {row['status']}, "
            f"real_calls={row['real_calls']}, failures={row['failures']}"
        )
    return 0 if all(row["status"] == "completed" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
