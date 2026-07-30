---
title: MVP Release Checklist
version: 0.1.0
status: Draft
project: EvoForge
authors:
  - Alan Diaz Manriquez
language: English
last_updated: 2026-07-30
---

# MVP Release Checklist

## Purpose

This document defines the internal checklist required before treating the current EvoForge MVP as a stable architecture prototype for Product 1.

The checklist is intended to support the transition from framework implementation to the first scientific article.

---

## Scope

This checklist applies to the current MVP architecture prototype only.

It does not represent a public `1.0.0` release and does not include external optimizer adapters, surrogate models, AquaCrop integration, statistical analysis, or visualization workflows.

---

## Release Candidate

Proposed internal version:

```text
0.1.0-mvp
```

Purpose:

```text
First functional architecture prototype for EvoForge.
```

---

## Technical Checklist

- [x] Python package foundation exists.
- [x] `uv` workflow exists.
- [x] Configuration module exists.
- [x] Domain model module exists.
- [x] Plugin contracts and registry exist.
- [x] Minimal experiment runtime exists.
- [x] Local data and output foundation exists.
- [x] CLI foundation exists.
- [x] Built-in example adapter prototype exists.
- [x] End-to-end YAML example exists.
- [x] Tests pass locally.
- [x] Lint checks pass locally.
- [x] Documentation builds locally.
- [x] CI workflow exists.
- [ ] CI has passed on GitHub after the latest push.

---

## Documentation Checklist

- [x] Project vision documented.
- [x] Project principles documented.
- [x] System requirements documented.
- [x] Domain model documented.
- [x] Architecture overview documented.
- [x] API design documented.
- [x] Implementation plan documented.
- [x] MVP architecture review documented.
- [x] Development workflow documented.
- [x] Plugin development guide documented.
- [ ] README reviewed after CI passes.
- [ ] Roadmap reviewed after CI passes.

---

## Reproducibility Checklist

- [x] Example YAML configuration exists.
- [x] Example can be executed through the CLI.
- [x] Configuration artifact is saved.
- [x] Metadata artifact is saved.
- [x] Evaluation records artifact is saved.
- [x] Manifest artifact is saved.
- [ ] Example output has been inspected manually.

---

## Article Readiness Checklist

- [x] Architecture contribution is identifiable.
- [x] Plugin-first decision is documented.
- [x] Configuration-driven reproducibility is documented.
- [x] System context diagram exists.
- [x] Domain model diagram exists.
- [x] Architecture overview diagram exists.
- [ ] Paper outline has been drafted.
- [ ] Target venues have been shortlisted.
- [ ] Related work collection has started.
- [ ] Software repository metadata has been finalized.
- [ ] License decision has been finalized.

---

## Known Limitations

- Plugin discovery is explicit only.
- Example plugins are not production optimizer or simulator integrations.
- No external scientific computing adapters are implemented yet.
- No surrogate-assisted optimization strategy is implemented yet.
- No AquaCrop integration is implemented yet.
- No statistical analysis or visualization workflows are implemented yet.
- No public release tag has been created yet.

---

## Release Decision

Current decision:

```text
Not released yet.
```

Required before internal MVP release:

- CI must pass on GitHub.
- README and roadmap must be reviewed.
- Example output must be manually inspected.
- License decision must be finalized.
- Article outline must be drafted.

---

## References

- `README.md`
- `ROADMAP.md`
- `docs/07_MVP_Architecture_Review.md`
- `docs/08_Development_Workflow.md`
- `docs/09_Plugin_Development_Guide.md`
