# Reproducibility and Validation

Every experiment that reaches output persistence stores a `provenance` section
in `metadata.json` and in `ExperimentResult.reproducibility_metadata`. Existing
metadata keys and evaluation records are retained. Collection is local and
best-effort: unavailable fields are JSON `null`, and metadata lookup failures
do not stop computation. This does not add persistence for direct runtime errors
that already abort before output generation.

See [errors](errors.md) for contextual exception types and precise persistence
boundaries, and [plugin compatibility](plugin_compatibility.md) for preserving
experiments across interface changes in 0.x.

## Recorded Provenance

| Field | Source and meaning |
| --- | --- |
| `evoforge_version` | Installed EvoForge distribution metadata, not a guessed version. |
| `python` | Python version and implementation. |
| `system` | Operating system, release, and architecture; no hostname. |
| `distributions` | Names and versions of installed distributions, not just requested extras. |
| `plugins` | Actual registered plugin class, configured ID, role, and owning distribution/version when resolvable. |
| `git` | Source checkout revision and dirty flag, when available. |
| `uv_lock_sha256` | SHA-256 of the source project's `uv.lock`, when present and readable. |
| `seeds` | Separate configured seeds and effective seeds reported by execution. |
| `climate` | Distinct adapter-published weather provenance and AquaCrop version, when available. |

Plugin class versions describe their owning distribution. For example,
`evoforge.adapters.pymoo.nsga2.PymooNSGA2Optimizer` belongs to EvoForge, not to
pymoo. The installed pymoo version is separately present in `distributions`.
Local/test plugin classes may have no resolvable distribution; the collector
does not substitute an unrelated library's version. Ownership lookup does not
import scientific packages. Package-to-distribution mappings are cached for the
process, assuming an unchanged environment during execution.

Git and lockfile lookup is anchored to EvoForge's source layout and matching
`pyproject.toml`, not the caller's current directory. An installed wheel does not
borrow the caller's Git revision or lockfile. A source tree without Git may still
have a lockfile hash. Missing Git, an unborn revision, unavailable permissions,
malformed project metadata, or an absent lockfile produce unavailable fields.
Installed distribution versions can still be recorded without repository data.

The collector does not read environment variables, credentials, repository
remotes, file contents from Git, diffs, or untracked file names into its output.
Git status is reduced to a boolean. It does not scan unrelated directories or
private manuscript files. Climate paths and hashes already published explicitly
by the AquaCrop adapter are preserved; climate file contents are not duplicated.
The existing validated configuration serialization remains unchanged.

## Configured and Effective Seeds

`seeds.configured` records the experiment seed and integer `seed`/`random_state`
parameters for the selected optimizer, simulator, and enabled surrogate.
Raw configuration is also saved in `config.json`. `seeds.effective` records
observed execution information rather than assuming that configured values
were consumed:

- `initial_design`: the assisted workflow's effective design seed, including a
  generated seed when `experiment.seed` was omitted.
- `optimizer`: the direct optimizer's reported effective seed. NSGA-II reports
  its generated or explicit seed. GA and example random search report their
  explicit RNG seed; an unspecified seed remains unavailable rather than
  inventing the seed of an entropy-initialized RNG.
- `optimizer_searches`: assisted iteration numbers and their derived search seeds.
- `surrogate_random_state`: the value used for assisted model configuration.
- `simulator`: unavailable unless a runtime report is supported; AquaCrop's
  deterministic adapter has no simulator RNG seed.

The experiment seed is not automatically an optimizer seed in direct mode.
Unreported seed values remain `null`, including for third-party plugins that
do not publish execution seed information. The built-in direct optimizers expose
`last_run_metadata` without adding a requirement to the plugin protocols;
structured optimizer results and assisted runtime metadata supply other reports.
Do not interpret unavailable, inactive, or entropy-initialized seeds as evidence
of deterministic execution.

## Reconstructing an Environment

Keep the exact project source, `pyproject.toml`, `uv.lock`, effective config,
and any external data alongside the run artifacts. From that project checkout:

```bash
uv sync --locked --python 3.12
uv run --locked --no-sync evoforge run examples/sphere_random_search.yaml
```

For all current scientific adapters:

```bash
uv sync --locked --python 3.12 --extra pymoo --extra sklearn --extra aquacrop
uv run --locked --no-sync evoforge run examples/aquacrop_irrigation_surrogate.yaml
```

Select only the necessary extras for smaller environments: `pymoo` for NSGA-II,
GA, and ZDT1; `sklearn` for the random forest; `aquacrop` for irrigation simulation.
Use both optimizer/model extras for a surrogate run, adding `aquacrop` when its
simulator is selected. `uv run --no-sync` assumes the preceding sync succeeded.

[`uv sync --locked`](https://docs.astral.sh/uv/concepts/projects/sync/)
refuses to update a missing or stale lockfile. The lock captures dependency
resolution, artifacts, hashes, and platform/Python markers, so the same project
and selected extras can be resolved without a fresh dependency upgrade. The
recorded SHA-256 identifies the lockfile; it does not contain or replace it.

The lock does not pin an operating-system image, CPU, exact Python patch build,
BLAS/native runtime behavior, external datasets, local code changes, or model
calibration. `--python 3.12` selects that minor series; record and retain the
actual patch version as well. Different platforms or Python versions can select
different compatible distributions/wheels from the same lock. Library versions
and data hashes must be checked against the original run. Dirty Git state alone
does not archive local changes. A package installed without its original project
files cannot reconstruct those files from version metadata alone.

Numerical identity across different environments is not promised. Seeds,
dependency locking, and input provenance make differences inspectable; they do
not establish cross-platform equivalence or eliminate algorithm/library changes.

## Automated Validation and Coverage

After syncing the full environment, run:

```bash
uv run --locked --no-sync python -c "from pymoo.algorithms.moo.nsga2 import NSGA2; from sklearn.ensemble import RandomForestRegressor; from aquacrop import AquaCropModel"
uv run --locked --no-sync pytest --cov=src/evoforge --cov-branch \
  --cov-report=term-missing --cov-report=xml:coverage.xml \
  --cov-report=json:coverage.json --cov-report=html
uv run --locked --no-sync ruff check .
uv run --locked --no-sync mkdocs build --strict
```

Coverage measures `src/evoforge`, including source files not executed. Console,
XML, JSON, and `htmlcov/` reports include line and branch information. With branch
measurement enabled, the console's overall percentage combines line/branch
opportunities. Separate line coverage is `covered_lines / num_statements` and
branch coverage is `covered_branches / num_branches` from the JSON totals.
There is no arbitrary coverage threshold. Coverage indicates exercised code,
not a proof of correctness, agronomic validity, or algorithmic performance.
Reports are generated artifacts ignored by Git; CI uploads each environment's
reports separately.

The GitHub Actions matrix validates Python 3.12 on Ubuntu in two configurations:
base dependencies plus development tools, and all three scientific extras.
Both use `uv sync --locked` and `uv run --locked --no-sync`; neither updates the
lock. The full job explicitly imports the real optional APIs before pytest so
missing dependencies cannot be disguised as optional integration-test skips.
Both jobs run coverage, lint, strict documentation, and a lockfile-change check.
This is one OS and one Python minor version, not a compatibility matrix for
every supported platform.

## Test Scope

| Area | What is exercised |
| --- | --- |
| Unit/config/domain/data | YAML validation, domain invariants, registry behavior, serialization, unavailable metadata, Git/source/installed layouts. |
| Plugin contracts | Fake implementations verify contracts, dependency injection, duplicate registration, and lookup errors. |
| Runtime with doubles | Deterministic fake optimizers/simulators/surrogates test budgets, duplicate stops, failures, provenance, and best-real filtering. |
| Real integrations | Actual pymoo GA/NSGA-II and ZDT1, scikit-learn fitting/prediction/persistence, and AquaCrop single-season simulations. |
| CLI | Typer help/error tests with doubles, plus runnable examples using the installed scientific libraries. |
| Regression | Direct, assisted, multiobjective, AquaCrop, and import-isolation paths; metadata persistence for each workflow. |
| Pilot script | Cheap fake-plugin pairs validate accounting, order, summaries, and timing boundaries; tests do not execute the full 20-run pilot. |

Integration tests skip in the base environment when their extras are absent;
those skips must be read alongside the full job's results. Fake-plugin tests do
not validate external numerical algorithms. Real adapter tests use small budgets
and scenarios; they are smoke/integration checks, not benchmarks. Installed-layout
tests use temporary distribution metadata to test repository absence, rather
than claiming all wheel installers and deployment layouts have been validated.
