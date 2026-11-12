# AquaCrop Irrigation Adapter

`aquacrop.irrigation` is an optional, single-season `SimulatorPlugin` backed by
**AquaCrop-OSPy 3.1.0**. The core, configuration models, domain objects, and
plugin contracts do not import AquaCrop. The CLI registers the adapter explicitly;
the external library is loaded only when evaluating a candidate.

## Installation and Examples

The initial validation environment uses Python 3.12.13. Install the pinned
dependency and both optimization extras:

```bash
uv sync --python 3.12 --extra pymoo --extra sklearn --extra aquacrop
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop evoforge run examples/aquacrop_irrigation_ga.yaml
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop evoforge run examples/aquacrop_irrigation_surrogate.yaml
```

Both examples use Maize, ClayLoam, May 1 through October 31, 2018, initial
water content of 70% total available water (TAW), and `MaxIrrSeason=300` mm.
The direct GA demonstration uses a population of four and four requested
evaluations. The surrogate demonstration uses three initial real calls, a strict
total of five real calls, eight predictions per search, and one real candidate
per update. Seeds are explicitly set to 42. Output directories are respectively
`results/aquacrop_irrigation_ga/` and `results/aquacrop_irrigation_surrogate/`.

The surrogate workflow separates unvalidated predictions from real observations
and selects its best result only from successful real calls. The direct pymoo
adapter retains its existing population-based evaluation termination semantics;
its general `n_evaluations` setting is not a strict simulator-call cap.

These small budgets demonstrate execution and provenance. They do not establish
an agronomic optimum, surrogate accuracy, or a speed improvement.

For paired direct/surrogate runs with configurable equal real budgets, see the
[comparison pilot](aquacrop_pilot.md). It preserves these small examples and
adds call accounting, alternating order, provenance, and summary trajectories.

## Inputs and Units

Candidates must link to a problem with exactly four continuous variables named
`smt1`, `smt2`, `smt3`, `smt4`, with finite, nondegenerate bounds within [0, 100].
Their order in the problem is arbitrary: the adapter maps the names to AquaCrop's
four `SMT` entries in that fixed order. They are soil-moisture targets expressed
as percent TAW for the four crop growth stages, not volumetric water content.
The only objective is `dry_yield`, direction `maximize`, measured in tonnes per
hectare. Problem constraints are not supported; the seasonal irrigation limit
is a simulator management parameter rather than an EvoForge constraint.

Scenario fields live under `evaluator.simulator.parameters`:

| Field | Meaning |
| --- | --- |
| `crop` | AquaCrop built-in crop name, e.g. `Maize`. |
| `soil` | AquaCrop built-in soil name, e.g. `ClayLoam`. |
| `sim_start_time` | ISO date, e.g. `"2018-05-01"`. |
| `sim_end_time` | Later ISO date in the same calendar year. |
| `planting_date` | `MM/DD`, inside the simulation interval. |
| `initial_water_pct` | 0-100% TAW, passed to `InitialWaterContent(wc_type="Pct")`. |
| `max_irr_season` | Nonnegative finite seasonal limit in mm, passed as `MaxIrrSeason`. |
| `weather_file` | Local path, or `champion_climate.txt` (default) for bundled data. |

Unknown scenario fields are rejected. Crop and soil names are resolved by
AquaCrop itself. Parameters not exposed here retain AquaCrop 3.1.0 defaults,
including daily irrigation limits and application efficiency.

Every evaluation creates new crop, soil, initial-water, irrigation-management,
weather, and model objects. The adapter calls `run_model(till_termination=True)`
and reads the public `get_simulation_results()` API. It never accesses private
output attributes. Empty/unfinished results, more than one result season,
missing dry-yield or irrigation columns, and nonfinite values raise errors.
The adapter does not convert simulation exceptions into successful records.
The existing surrogate runtime may capture these errors as failed real calls;
such calls consume real budget and cannot train the model or become the best.

## Climate Data and Provenance

`champion_climate.txt` is resolved with AquaCrop's `get_filepath()` from the
installed distribution. In 3.1.0 it covers January 1, 1982 through December 31,
2018. The [upstream irrigation example](https://aquacropos.github.io/aquacrop/notebooks/AquaCrop_OSPy_Notebook_3/)
describes its Champion, Nebraska scenario. No dataset is copied into EvoForge.
Dependency installation may access the package index; simulation execution never
downloads climate files.

An explicit local path uses the same AquaCrop text format: seven whitespace-
separated columns with a header, in the order `Day Month Year MinTemp MaxTemp
Precipitation ReferenceET`. Temperatures are in degrees Celsius; precipitation
and reference evapotranspiration are daily mm. Paths are resolved relative to the
working directory, not relative to the YAML file. Use an absolute path when that
distinction matters. The literal `champion_climate.txt` selects the packaged
resource; use `./champion_climate.txt` to select a local file of the same name.

The adapter uses `prepare_weather()`, which includes AquaCrop's reference-ET
floor of 0.1 mm/day. Parsed dates must be sorted, unique, and cover every day
of the simulation interval. Parsed weather values must be finite. No imputation,
climate generation, or additional calibration is provided. Coverage alone does
not establish physical quality or local representativeness.

Each successful real record includes the resolved weather path, `local_file` or
`aquacrop_bundled` provenance, SHA-256 of the source file bytes, installed AquaCrop
version, scenario parameters, SMT values, elapsed seconds, dry-yield unit, and
`seasonal_irrigation_mm`. Hashes identify inputs; they are not data licenses.

## License and Limitations

EvoForge's MIT license does not replace third-party terms. AquaCrop-OSPy 3.1.0
has inconsistent licensing labels: its [PyPI metadata](https://pypi.org/project/aquacrop/3.1.0/)
classifies it as MIT, while the [LICENSE at tag v3.1.0](https://github.com/aquacropos/aquacrop/blob/v3.1.0/LICENSE)
and the installed distribution's license file contain Apache License 2.0.
Review the shipped notices and clarify upstream terms before redistribution.
The adapter does not assign a separate license to `champion_climate.txt` or to
user-provided climate data; users must verify their provenance and reuse rights.

Only one season within one calendar year is supported. There is no calibration,
multi-season aggregation, salinity/fertility extension, economic objective,
external data service, or custom crop/soil profile interface in this adapter.
The example is a model scenario and has not been validated as field advice.
Repeatability is checked in the pinned environment, not guaranteed across
dependency versions or platforms.

## Verification

```bash
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop pytest
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop ruff check .
uv run --python 3.12 --extra pymoo --extra sklearn --extra aquacrop mkdocs build --strict
```

Unit tests validate scenarios, variables, weather coverage, output shape,
dependency errors, and state isolation using fakes. Real integration tests run
when the optional dependencies are installed; otherwise they skip. They execute
the bundled-data scenario repeatedly, verify local-path provenance, and run both
CLI examples. The core import test blocks any attempt to import AquaCrop.
