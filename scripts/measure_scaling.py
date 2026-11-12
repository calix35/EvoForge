"""Measure local sequential record/export scaling in isolated processes."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import resource
import subprocess
import sys
from pathlib import Path
from statistics import median
from time import perf_counter

from evoforge.adapters.examples import register_builtin_example_plugins
from evoforge.config import load_experiment_config
from evoforge.core import Experiment

ROOT = Path(__file__).resolve().parents[1]


def measure(count: int, seed: int, output: Path) -> dict:
    """Time execution and persistence; report whole-process peak RSS."""
    config = load_experiment_config(ROOT / "examples/sphere_random_search.yaml")
    config.experiment.name = f"scaling_{count}_{seed}"
    config.experiment.seed = seed
    config.optimizer.parameters.update(iterations=count, seed=seed)
    config.outputs.directory = str(output)
    started = perf_counter()
    result = Experiment(config, register_builtin_example_plugins()).run()
    elapsed = perf_counter() - started
    if len(result.records) != count:
        raise RuntimeError("Unexpected evaluation count.")
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports KiB. Other OSes are outside this script.
    rss_bytes = rss if sys.platform == "darwin" else rss * 1024
    return {
        "evaluations": count,
        "seed": seed,
        "elapsed_seconds": elapsed,
        "peak_process_rss_mib": rss_bytes / 1024**2,
        "artifact_bytes": sum(p.stat().st_size for p in output.iterdir()),
        "records": len(result.records),
        "status": result.status.value,
        "python": platform.python_version(),
        "platform": platform.platform(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--counts", type=int, nargs="+", default=[100, 1000, 10000, 100000]
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if sys.platform not in {"darwin", "linux"}:
        parser.error("Peak RSS measurement supports macOS and Linux only.")
    if any(n < 1 for n in args.counts):
        parser.error("Evaluation counts must be positive.")
    if args.output.exists():
        parser.error("Output already exists; choose a new path.")
    if args.worker:
        row = measure(args.counts[0], args.seeds[0], args.output)
        print(json.dumps(row))
        return
    args.output.mkdir(parents=True)
    rows = []
    for count in args.counts:
        for seed in args.seeds:
            output = args.output / f"n_{count}_seed_{seed}"
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker",
                 "--output", str(output), "--counts", str(count),
                 "--seeds", str(seed)],
                check=True, capture_output=True, text=True,
            )
            rows.append(json.loads(completed.stdout))
            (args.output / "measurements.json").write_text(
                json.dumps(rows, indent=2) + "\n", encoding="utf-8"
            )
    with (args.output / "measurements.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = []
    for count in args.counts:
        selected = [r for r in rows if r["evaluations"] == count]
        summary.append({
            "evaluations": count,
            "repetitions": len(selected),
            **{key: median(r[key] for r in selected) for key in (
                "elapsed_seconds", "peak_process_rss_mib", "artifact_bytes"
            )},
        })
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
