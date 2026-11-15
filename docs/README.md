# AosKeel — Ontology-Based Agent System Development Template (AOS Template v0.3)

> **Language / 语言**: **English (default)** · [简体中文](README.zh-CN.md)
>
> Both language versions carry identical content; English is the default entry point.
> The canonical specification ([aos-spec.md](aos-spec.md)) is a frozen Chinese text and is not translated here.
> The remaining `docs/` files (POSITIONING / RUNBOOK / SPEC-FINGERPRINT) also remain in Chinese.

**Positioning** — Specification-driven development is the methodology; the AI software factory is the organizational and process vehicle; the ontological architecture is the infrastructure that makes both genuinely *executable* at the semantic level. This project is a complete, verifiable implementation of that infrastructure (clause-by-clause mapping and the full-chain gap map are in [POSITIONING.md](POSITIONING.md)). It is comparable to `npm create vue` or a Visual Studio project template: instantiate, from 0 to 1, an ontology-based, governance-built-in enterprise Agent system.

Canonical specification: *AOS: Ontology-Based Agent System Development Specification* v2.0.0 ([docs/aos-spec.md](aos-spec.md); registry entries in [docs/ARTIFACT-REGISTRY.md](ARTIFACT-REGISTRY.md)).

## What this template provides — and what it does not (read this first)

**Provides**: CI fulfilment of all `auto` VER clauses · the registration-time pipeline (five steps, single writer) · BOOT-sequence scaffolding · six `mandatory` checklists · the three-gate check (structural / cryptographic / registration) · bijection assertions.

**Does not provide**: proof of compliance. A `mandatory` clause can only be marked "passed" through human execution on the running system (checklist records: evidence + judge + signer); proof that the base is immutable = the VER-28 red-team exercise; interpreter purity = correctness of the interpreter implementation; legitimacy (steward, founding appointment) is a world event — this template records it, never manufactures it (GOV-1).

## Quick start (0 → 1)

```powershell
pip install -e .                              # installs pyyaml + pytest; or use python -m src.cli.main
aos init my-org-system                        # instantiate (refuses to overwrite an existing target)
cd my-org-system
aos bootstrap --stage 0                       # BOOT-0: artifact hash registration + first three-gate run
aos verify                                    # three gates: structural (fingerprint) -> cryptographic (hash) -> registration (declared==registered)
python -m pytest -q tests                     # consistency + forbidden bijection + interpreter negative set
aos bootstrap --stage 1 --appointment-ref <external-credential>   # BOOT-1 founding appointment (real credential mandatory)
aos test                                      # grouped execution per config/verification.yaml
# -- full lifecycle: requirements -> artifact --
aos draft requirements.txt --name r1          # requirements DSL -> draft (compiler-gated; nothing written unless all green)
aos draft promote spec/drafts/draft-r1.yaml --proposal-ref SPEC-2026-021   # promote to canonical (governance proposal mandatory)
aos generate                                  # declarations -> code skeleton (hand-edit detection, provenance header)
aos release                                   # release gate (fail-closed) -> dist/RELEASE-MANIFEST.json
```

Subsequent BOOT-2/3 (governance workflow, Identity Context acceptance) and business-model changes (via the GOV-3 version channel, see [docs/RUNBOOK.md](RUNBOOK.md)) belong to instance-side governance work — the template supplies declaration slots, the compiler, the gates and the acceptance checklists; it does not simulate governance (honest boundary; the Makefile never synthesizes founding-appointment credentials). CI gates are in `.github/workflows/ci.yml` (pytest → three gates → release gate).

The `aos` console script and `python -m src.cli.main` are equivalent: both dispatch through `main()` with `argv` defaulting to `sys.argv[1:]`. `pytest` is a declared runtime dependency because `aos test` and `aos release` execute the wired suites; if it is missing, they refuse explicitly with `PYTEST-MISSING` instead of reporting a suite failure.

## Template tree (v0.1 → v0.3)

```
README.md                      Repository entry (English default; points to both full documents)
docs/README.md                 This file (default English: honest boundary + quick start + template tree)
docs/README.zh-CN.md           Simplified Chinese version of this file (identical content)
docs/aos-spec.md               Canonical specification v2.0.0 (frozen)
docs/SPEC-FINGERPRINT.md       Clause fingerprint manifest (second canonical artifact, GOV-2.4)
docs/ARTIFACT-REGISTRY.md      Artifact registry (append-only, GOV-2.3; instances re-register)
docs/POSITIONING.md            Positioning: SDD / AI software factory / ontology — mapping and gap map
docs/RUNBOOK.md                BOOT-2/3 workflow scaffolding (GOV-3 version channel / GOV-2.5 dichotomy / mandatory index)
docs/TEMPLATE-LOCK.md          Written by init: version binding
config/capabilities.yaml       Capability list, three sections (fixed / generated / provenance)
config/verification.yaml       VER-1..33 clause-to-test wiring (load-bearing)
spec/                          Eight declaration kinds (objects/links/actions/contexts/aggregates/mappings/processes/invariants)
src/cli/main.py                Table-driven CLI entry (11 commands, see below; startup self-check refuses a wrongly installed wheel)
src/kernel/registration.py     Registration pipeline (KS-7.2 five steps, P-5 single writer; loads the eight declaration kinds)
src/kernel/sc_compiler.py      Two-phase SC compiler (KS-7.1 / VER-18)
src/kernel/pipeline.py         Kernel submission pipeline (structural -> conditional -> append; full re-evaluation on conflict, VER-2/3)
src/kernel/store.py            Ontological event log (append-only; INV-1 closed write path)
src/kernel/session.py          Session event stream (KS-2.2 physically separated store / VER-4)
src/kernel/genesis.py          Genesis window state machine (KS-8; extinguishing is irreversible)
src/kernel/projection.py       Projections and decision inputs (P-16; rebuildable / sessions excluded)
src/kernel/detector.py         Detector (T25; violations via RaiseInvariantViolation, P-7/INV-10)
src/kernel/upcasting.py        Read-time upcasting (KS-5.2-5.4; no path = read failure, golden-anchored)
src/kernel/merge.py            Identity merge history (P-8; dual-path replay comparison, VER-24)
src/kernel/saga.py             Cross-aggregate orchestration (P-9; compensation is itself an Action, idempotent)
src/kernel/dryrun.py           Dry-run simulator (P-12; repeatable, zero side effects, VER-25)
src/agents/runtime.py          AGENT capability surface (P-10; strict subset of the list, no privileged channel)
src/kernel/governance.py       Governance layer (GOV-4 re-run on effect; failure = block + governance violation object)
src/kernel/errors.py           Typed exceptions (exception types are the runtime form of clauses)
src/interpreter/boolean_profile.py   Boolean-profile restricted interpreter (R10 AST whitelist / VER-8)
src/interpreter/mapping_profile.py   Mapping-profile restricted interpreter (R11 no predicate dispatch / VER-9)
src/interpreter/audit.py       Interpreter audit (KS-3.3 version identity + snapshot hash)
tools/hash_spec.py             Separated hashing (sole cryptographic-layer executor, GOV-2.3)
tools/fingerprint.py           Structural fingerprint check (GOV-2.5 divergence dichotomy)
tools/verify_capability_list.py  VER-27 support (capability list completeness)
tools/wiring.py                Sole reader of verification.yaml (pyyaml; missing path blocks)
tools/codegen.py               Declarations -> code skeleton generator (aos generate; hand-edit detection, provenance header)
tools/release_gate.py          Release gate (aos release; fail-closed, VER-27 prerequisite)
tools/ontology_draft.py        Requirements DSL -> ontology draft (aos draft; compiler-gated, promotion requires a governance proposal)
docs/samples/requirements-sample.txt   Requirements DSL sample (draft entry point)
src/generated/                 Generated artifacts: actions.py (INV-1 wraps submit) + reducers.py (pure functions, drift visible)
tests/negative/test_forbidden.py            forbidden x negative tests (exactly one case per item)
tests/negative/test_forbidden_coverage.py   Bijection assertion (P-10)
tests/conformance/test_declared_registered.py  Continuous declared == registered check (INV-13)
tests/conformance/test_integrity.py        Integrity guards for the v0.3 hardening (wired via integrity_paths, not new VER clauses)
bootstrap/checklists/          _schema + VER-20/24/26/27/28/29 (P-14 evidence records)
```

## CLI commands ×11 and guardrails ×2

| Command | Semantics | Failure behavior |
|---|---|---|
| `init <dir>` | Instantiate + TEMPLATE-LOCK version binding | Target exists → refuse |
| `verify` | Three gates chained | Any failure → exit 1 |
| `register <version>` | GOV-2.3 registration | Same hash is idempotent; drift → refuse (GOV-3) |
| `bootstrap --stage N` | BOOT-0..3; `--dry-run` runs checklists only | Out-of-order stage → refuse; 2/3 are instance-side |
| `test [--suite S]` | Grouped by verification.yaml | Suite failure / missing wiring path → exit 1 |
| `spec fingerprint` | Standalone structural-layer check | Reports missing clauses → exit 1 |
| `spec version <v>` | GOV-3 version channel (append-only) | Missing `--proposal-ref` → refuse |
| `generate [--force]` | Declarations → code skeleton (byte-level zero drift) | Hand-edit drift → refuse silent overwrite |
| `release` | Release gate (fail-closed) | Any failed step → no artifact |
| `draft <file>` | Requirements DSL → draft (compiler-gated) | Not all green → nothing written |
| `draft promote <f>` | Promote draft to canonical (GOV-1 proposal mandatory) | Target exists → refuse; use GOV-3 |

Guardrail 1: `bootstrap --stage 1` requires `--appointment-ref` — refuses to synthesize a founding appointment (GOV-1).
Guardrail 2: an instance carries a specification copy + registry entry ID; copy hash = registry hash, so any change yields FROZEN-TEXT-MUTATED (INV-12).

## Runtime shape and engineering boundaries (read first to avoid misjudgement)

| Boundary | Fact | Cost / instance-side duty |
|---|---|---|
| Delivery shape | The template ships as a **source tree**: `pip install -e .` (then `aos ...`) or `python -m src.cli.main`. The wheel contains no `docs/spec/config`, and the startup self-check explicitly refuses it — **it is not an installable artifact** | Making the wheel installable requires reworking ROOT resolution and data-file packaging (P2, not done in this version) |
| Event store | `EventStore` is an **in-memory** dict; state is lost on process exit, no persistence | Production instances must connect a database and prove append-only semantics and audit durability themselves |
| Structural fingerprint | Checks "clause count + first anchor + last anchor" and **does not verify intermediate clause content**; the strong guarantee comes from the full-text hash of the cryptographic layer (GOV-2.3) | Changing a middle clause while keeping both anchors → structural layer passes, hash layer catches it; this is the trade-off defined by the Appendix F manifest |
| BOOT-2/3 | The template supplies only scaffolding and checklists; `bootstrap --stage 2/3` returns a refusal | Governance workflow and Identity Context acceptance are instance-side world events (GOV-1) |
| `mandatory` clauses | VER-20/24/26/27/28/29 have only checklist/support entries and never enter the auto suites | Human execution + evidence / judge / signer records; the template never pretends they passed |
| Byte exactness | All write points use UTF-8 + LF byte writes; `.gitattributes * -text` forbids newline conversion | If generated artifacts / registry / manifest are switched to CRLF by external tooling, `generate` / `release` refuse on byte-level drift |

The load-bearing wiring file `config/verification.yaml` is parsed through a single point, `tools/wiring.py`, using pyyaml: if a declared `path` does not exist, `aos test` and `aos release` **block** (no silent degradation). The `integrity_paths` section registers only execution paths for regression guard tests and **does not create new VER clauses** (the v2.0.0 frozen clause set remains VER-1..33; neither the fingerprint manifest nor the registry hash was changed).
