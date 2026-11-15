# AosKeel

> **Language / 语言**: **English (default)** · [简体中文](docs/README.zh-CN.md)

A verifiable implementation of the *AOS: Ontology-Based Agent System Development Specification* v2.0.0 — a template that instantiates, from 0 to 1, an ontology-based, governance-built-in enterprise Agent system.

**Full documentation**

- [English (default) — docs/README.md](docs/README.md)
- [简体中文 — docs/README.zh-CN.md](docs/README.zh-CN.md)

Both versions carry identical content. The canonical specification ([docs/aos-spec.md](docs/aos-spec.md)) is a frozen Chinese text; only the README is bilingual. The remaining `docs/` files also remain in Chinese.

**Quick start** (source tree only — see the [engineering boundaries](docs/README.md#runtime-shape-and-engineering-boundaries-read-first-to-avoid-misjudgement))

```powershell
pip install -e .
python -m src.cli.main verify
python -m src.cli.main init my-org-system
```

**What this template does not provide**: proof of compliance. Mandatory clauses require human execution on a running system; legitimacy (steward, founding appointment) is a world event that the template records, never manufactures (GOV-1). See the [honest boundary](docs/README.md#what-this-template-provides--and-what-it-does-not-read-this-first).
