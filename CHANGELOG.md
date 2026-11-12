# Changelog

## 0.2.0

- Add sequential single-objective surrogate-assisted execution and separate
  prediction artifacts, with strict real-call and prediction budgets.
- Add optional AquaCrop-OSPy irrigation simulation and direct/assisted examples.
- Add optional NSGA-II, ZDT1, and observed non-dominated artifact export.
- Record best-effort environment, plugin, source, input, and seed provenance.
- Add basic/full CI environments, coverage reports, and documentation deployment.
- Add local sequential scaling measurement and documented execution limits.

### Compatibility Notes

- Experiment boundaries now expose contextual configuration, execution, and
  output errors. Original exceptions are available through `__cause__`.
- Direct optimizers must use the supplied evaluator's `evaluate(solution)`
  interface rather than depend on a simulator's concrete class or identity.
- Invalid real records and predictions presented as real evaluations are rejected.
- Enabled surrogate configurations require explicit workflow budgets.
- No automatic migration, checkpoint/resume, or indefinite 0.x compatibility
  guarantee is provided. Preserve previous environments and configurations.
