# AosKeel — Documentation index / 文档索引

> **This file is an index, not a copy of any README.** The English first-screen README lives
> at the repository root ([README.md](../README.md)); its Chinese counterpart is
> [README.zh-CN.md](README.zh-CN.md). The two are **language editions of one page**:
> §1–§9 are mirrored section by section (same facts, numbers and boundaries), and the
> Chinese edition carries an additional full source-tree map in Appendix A. Keeping
> exactly one English first-screen source prevents duplicate drift; the Chinese edition
> is kept in lockstep by the section skeleton and by
> [`tests/conformance/test_doc_consistency.py`](../tests/conformance/test_doc_consistency.py).

<a id="language--authority"></a>
<a id="语言与效力矩阵"></a>

## 语言与效力矩阵 / Language and authority

| Document | Language | Status | In hash domain | Counterpart |
|---|---|---|---|---|
| [README.md](../README.md) | English | informative first screen, §§1–9 | no | [README.zh-CN.md](README.zh-CN.md) — mirrored §§1–9 |
| [README.zh-CN.md](README.zh-CN.md) | 简体中文 | informative full edition + Appendix A | no | [README.md](../README.md) |
| [aos-spec.md](aos-spec.md) | 简体中文 | **normative canonical**, v2.1.1, frozen (informative appendices R/S) | **yes** (`AOS-ART-003`, `18868adf…`) | [English overview](aos-spec.en-overview.md) — map only, non-normative |
| [SPEC-FINGERPRINT.md](SPEC-FINGERPRINT.md) | 简体中文 | **normative**, clause fingerprint list (GOV-2.4) | **yes** | none |
| [ARTIFACT-REGISTRY.md](ARTIFACT-REGISTRY.md) | 简体中文 | append-only registry (GOV-2.3) | no (registry itself) | none |
| `spec/**/*.yaml` | YAML | declarative business-semantics source | **yes** (declaration digest `91ffe5a1…`) | n/a |
| [aos-spec.en-overview.md](aos-spec.en-overview.md) | English | **non-normative navigation aid**; translates no clause | no | [aos-spec.md](aos-spec.md) — canonical |
| [STRATEGY.md](STRATEGY.md) / [STRATEGY.en.md](STRATEGY.en.md) | 中文 / English | strategy paper, mirrored paragraph by paragraph | no | each other |
| [WHITEPAPER.md](WHITEPAPER.md) | 简体中文 | technical whitepaper (five-layer model, ten disciplines) | no | summarised in both README §8 |
| [POSITIONING.md](POSITIONING.md) | 简体中文 | methodology / factory / ontology gap map | no | summarised in both README headers |
| [RUNBOOK.md](RUNBOOK.md) | 简体中文 | BOOT-2/3 workflow scaffold, GOV-3 channels | no | none |
| [REVIEW-ontology-peer-review.md](REVIEW-ontology-peer-review.md) | 简体中文 | historical peer-review record (author-local, not copied into instances) | no | none |
| [adr/ADR-001-dual-distribution.md](adr/ADR-001-dual-distribution.md) | 简体中文 | Accepted architecture decision (kernel wheel + template sdist) | no | none |
| [adr/ADR-002-canonical-appendices-rs.md](adr/ADR-002-canonical-appendices-rs.md) | 简体中文 | Accepted GOV-3 decision (canonical informative appendices R/S, v2.1.0) | no | none |
| [adr/ADR-003-appendix-errata-v211.md](adr/ADR-003-appendix-errata-v211.md) | 简体中文 | Accepted GOV-3 errata decision (appendix R/S content, v2.1.1) | no | none |
| [guide/](guide/README.md) | 简体中文 | nine-part **informative** guide (copied into every instance) | no | clause IDs stay verbatim in English prose |
| [guide/index.html](guide/index.html) | mixed | visual concept map, informative | no | none |
| [samples/llm/README.md](samples/llm/README.md) | 简体中文 | offline LLM-in-the-loop worked example | no | none |
| [packages/kernel/README.md](../packages/kernel/README.md) / [packages/template/README.md](../packages/template/README.md) | 简体中文 | distribution-artifact boundaries (ADR-001) | no | none |
| [tests/README.md](../tests/README.md) | 简体中文 | test organisation and contracts | no | none |
| `docs/DOMAIN-MANUAL.md`, `docs/TEMPLATE-LOCK.md` | 简体中文 | **generated inside an instance** by `aos init`; derived views | no | n/a |

**Authority rule:** the frozen Chinese canonical (`aos-spec.md`) plus its fingerprint list
are the only normative prose. English material never overrides them; the English overview
is a map, not a translation. The guide, whitepaper, strategy papers and READMEs are
informative — they explain, they do not create clauses. Conflicts are adjudicated by INV.

**Two different "sources of truth"**: `docs/aos-spec.md` is the source for *normative
clauses*; `spec/` is the source for *business-semantics declarations* and is itself
compiled input, not specification text. Do not describe `spec/` as the canonical spec.

## Index / 索引

| You want… | Go to |
|---|---|
| English overview, commands, migration pipeline, boundaries | [README.md](../README.md) |
| 简体中文完整版（含附录 A 模板树） | [README.zh-CN.md](README.zh-CN.md) |
| Canonical specification (frozen Chinese) | [aos-spec.md](aos-spec.md) |
| English clause map (non-normative) | [aos-spec.en-overview.md](aos-spec.en-overview.md) |
| Clause fingerprint list (GOV-2.4) | [SPEC-FINGERPRINT.md](SPEC-FINGERPRINT.md) |
| Artifact registry (append-only, GOV-2.3) | [ARTIFACT-REGISTRY.md](ARTIFACT-REGISTRY.md) |
| Ontology-driven architecture whitepaper (五图理论 + 十条纪律) | [WHITEPAPER.md](WHITEPAPER.md) |
| Positioning: methodology / factory / ontology gap map | [POSITIONING.md](POSITIONING.md) |
| Strategic vision, bilingual | [STRATEGY.md](STRATEGY.md) · [STRATEGY.en.md](STRATEGY.en.md) |
| BOOT-2/3 workflow scaffold (GOV-3 channels) | [RUNBOOK.md](RUNBOOK.md) |
| Historical peer review (author-local) | [REVIEW-ontology-peer-review.md](REVIEW-ontology-peer-review.md) |
| Architecture decisions | [adr/ADR-001-dual-distribution.md](adr/ADR-001-dual-distribution.md) · [adr/ADR-002-canonical-appendices-rs.md](adr/ADR-002-canonical-appendices-rs.md) · [adr/ADR-003-appendix-errata-v211.md](adr/ADR-003-appendix-errata-v211.md) |
| Nine-part guide (Chinese, copied into every instance) | [guide/README.md](guide/README.md) |
| Visual concept map | [guide/index.html](guide/index.html) |
| LLM-in-the-loop offline example / requirements DSL sample | [samples/llm/README.md](samples/llm/README.md) · [samples/requirements-sample.txt](samples/requirements-sample.txt) |
| Distribution artifacts (ADR-001) | [packages/kernel/README.md](../packages/kernel/README.md) · [packages/template/README.md](../packages/template/README.md) |
| Test organisation and wiring contracts | [tests/README.md](../tests/README.md) |
| Wiring source of truth (VER-1..33 + INTEGRITY paths) | [config/verification.yaml](../config/verification.yaml) |

## Maintaining the two language editions / 双语维护约定

1. **Numbers are derived, never hand-copied.** [`tools/doc_metrics.py`](../tools/doc_metrics.py)
   derives the CLI command count from `src/cli/main.py` dispatch branches and the wiring
   count from `config/verification.yaml`. Current authoritative values:
   `CLI 26 命令面（21 顶层 + 5 子命令）` and
   `60 条布线（可执行 60 / 缺失 0 / 〔强〕未布线 1）`, plus 28 INTEGRITY regression guards.
   `tests/conformance/test_doc_consistency.py` locks the strings that consume them.
   Test-suite size is quoted as **73 test files / 379 `def test_` functions**; pytest
   collects 393 cases after parametrisation. Both numbers are correct — different units,
   so do not "correct" one into the other.
2. **Changing a fact changes both editions.** Any edit to §§1–9 of one README must be
   mirrored in the other in the same commit. This is now a machine check, not just a
   review convention: `test_readme_section_skeleton_is_mirrored` in
   `tests/conformance/test_doc_consistency.py` locks the 11 top-level slots
   (§§1–9 + Appendix A) in both editions, and
   `test_readme_editions_cross_link_and_mirror_shared_facts` locks the cross-links
   and the shared dual-distribution subsection. Execution-boundary disclosures are
   locked by `test_declaration_execution_boundaries_disclosed`.
3. **Run the guards after editing docs**: `python -m pytest -q tests/conformance/test_doc_consistency.py`
   and `aos verify`. Editing any document outside `aos-spec.md` / `SPEC-FINGERPRINT.md`
   does not change the canonical hash; changing either of those requires the GOV-3
   version channel and a proposal reference.
4. **Version numbers**: software `0.3.0` · canonical spec `v2.1.1` (informative appendices R/S; semantic delta zero) · whitepaper/strategy
   documents `v1.0`. Do not conflate them.
