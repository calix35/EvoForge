# Scaling and Execution Limits

The current runtime is sequential. It accumulates evaluation records in memory
and serializes complete JSON artifacts after execution. The assisted workflow
also retains predictions and retrains from successful real records. These choices
are appropriate to the demonstrated small experiments, but memory, serialization,
model fitting and prediction storage become relevant as budgets grow.

## Local Measurement

Run an isolated-process measurement with the locked base environment:

```bash
uv sync --locked --python 3.12
uv run --locked --no-sync python scripts/measure_scaling.py \
  --output results/scaling
```

The default runs 100, 1,000, 10,000 and 100,000 Sphere evaluations, each with three
seeds (0, 1, 2), using built-in random search. Each run starts a fresh process.
It measures wall time around experiment construction, execution, provenance
collection, and artifact persistence; interpreter startup, imports, configuration
loading, and final measurement-summary writing are excluded. It reports whole
process peak resident memory (RSS), including imported modules, not just memory
allocated by EvoForge. macOS reports RSS in bytes and Linux in KiB; the script
normalizes both to MiB. Other platforms are not supported by this measurement.

The generated CSV/JSON contains individual runs; summary values are medians of
the three repeats. Artifact bytes cover the runtime's generated files, excluding
the measurement summary. Existing output roots are rejected to prevent overwrite.
Use `--counts` and `--seeds` to choose other budgets or repeats.

This measures record accumulation and export using a cheap analytic evaluator.
It is not an optimizer benchmark, an external-simulator throughput result, a
surrogate training scalability test, or proof of asymptotic behavior. Small-run
timings can be dominated by fixed overhead and system noise. Reaching the largest
tested budget is not a general capacity guarantee; hardware, record size, input
dimension, model and prediction budgets all affect practical limits.

## Recorded Local Observation

A macOS/ARM64 run with Python 3.12.13 and EvoForge 0.2.0 produced the following
medians of three fresh-process repetitions per budget. The two-variable Sphere
evaluator is inexpensive; these measurements mainly exercise accumulation and
JSON output, not simulation cost.

| Evaluations | Wall time (s) | Peak process RSS (MiB) | Runtime artifacts (bytes) |
| ---: | ---: | ---: | ---: |
| 100 | 0.078 | 36.42 | 47,168 |
| 1,000 | 0.078 | 39.66 | 418,640 |
| 10,000 | 0.224 | 78.16 | 4,133,092 |
| 100,000 | 1.737 | 444.23 | 41,278,442 |

All twelve runs returned the requested number of records. Time, memory, and
artifact size depend on the environment and are not capacity guarantees. At
100,000 records the observed process memory was already about 444 MiB, supporting
the need to consider record/prediction storage when selecting budgets. The
measurement does not evaluate large input dimensions, surrogate retraining,
parallel throughput, or long-running simulations. Raw measurements are generated
locally under the chosen output directory and are not bundled with the package.

## Unsupported Execution Capabilities

- Parallel/distributed evaluation and resource scheduling are not implemented.
- The runtime does not stream records to disk or provide a disk-backed dataset.
- Long-running simulator processes have no generic timeout, cancellation,
  automatic retry or recovery policy.
- Checkpoint/resume and atomic output transactions are not implemented.
- Direct exceptions do not guarantee persisted partial results; see [errors](errors.md).
- The current assisted workflow does not incrementally fit or bound an archive
  independently of its configured evaluation and prediction budgets.

For expensive or long-running external evaluations, choose small validation
budgets first and retain original inputs and environment records. A larger
simulation cost does not by itself establish speedup from surrogate assistance.
