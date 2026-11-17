# AosKeel

> **Language / 语言**: **English (default)** · [简体中文](docs/README.zh-CN.md)

**A verifiable, 0→1 scaffold for ontology-based Agent systems — specification-driven, governance-built-in, and machine-checkable.**

AosKeel implements the *AOS: Ontology-Based Agent System Development Specification* v2.0.0. It is closer to `npm create vue` than to a runtime product: you instantiate a source tree, declare your domain, and let the compiler and gates decide whether the system is allowed to start. This page gives you the theory and a working entry point; the [full guide](#6-guided-learning) goes deeper.

---

## 1. Why an LLM needs an ontology

A language model is widely read but structurally naive: it produces plausible text, not constrained assertions. An ontology supplies the missing structure — an explicit, formal definition of the concepts, relations, properties and rules of a domain.

> A database stores `user_id` and `product_id`. An ontology must say what a **User** is, what a **Purchase** means, and that **payment succeeded** is a precondition for **shipping**.

| Failure mode of LLM-only systems | Ontology mechanism | Where AosKeel enforces it |
|---|---|---|
| Confident hallucination | Assertions must be made through declared actions | Unregistered capabilities have no write path (`INV-1`, `INV-13`) |
| Business rules live in prose | Rules compiled into machine-checkable constraints | `submission_criteria` → Check AST + restricted Boolean profile (`KS-7.1`) |
| Semantic drift between spec and code | One semantic source of truth, continuously reconciled | `declared == registered` bijection (`KS-7.2`) |
| "What did it know at the time?" is unanswerable | Every evaluation and change is recorded | Interpreter audit + 8-field events + decision references (`KS-3.3`, `KS-2.5`) |
| Permissions live in the prompt | Capability surface is a strict subset of the list | Rejection before the store is reached (`P-10`, `INV-4`) |

The current wave of interest is driven by two forces: enterprises need **auditable reasoning** from AI, and Palantir-style ontologies demonstrated that explicit object/link/action models can carry serious workloads. AosKeel borrows that engineering shape and adds a governance layer with mechanical checkpoints.

---

## 2. Ontology in three minutes: TBox, ABox, and the AOS increment

```
Knowledge graph = ontology (schema / TBox) + instance data (ABox)
```

- **TBox (terminological box)** — the blueprint: which classes exist (`Patient`, `Order`), which properties describe them, which relations hold (`is-a`, `part-of`), and which axioms must be true ("every order has exactly one customer").
- **ABox (assertion box)** — the building: individuals and facts, traditionally expressed as triples `(subject, predicate, object)`, e.g. `(ZhangSan, takes, Aspirin)`.

| Classical concept | AOS term | Concrete artifact |
|---|---|---|
| Class | `ObjectType` | `spec/ontology/objects/Contract.object.yaml` |
| Data / object property | `Property` | `properties` in the object declaration; `decision_relevant` adds audit semantics |
| Relation | `LinkType` (structural link) | `spec/ontology/links/same_as.link.yaml` — zero business semantics, system-written |
| Axiom / rule | Invariant triple + restricted Boolean function | `spec/invariants/*.yaml`, `src/interpreter/` |
| Individual | State projected from the event log | `src/kernel/projection.py` |
| Triple assertion | **Event with version, actor and time** | `src/kernel/store.py` — 8 fields, append-only |

**The decisive difference.** Classical ontology describes *what is true*. AOS adds a fourth element to the tuple:

```
ObjectType / Property / LinkType / ActionType        ← T01 four-element tuple
ContextType / AggregateType / Mapping / ProcessType  ← T02 four constructs
```

`ActionType` is a declarative state-change contract: parameters, submission criteria, permissions, side effects and audit requirements. With it, the ontology stops being purely descriptive and starts **gating changes to the world** — who may change what, under which conditions, and with what trace. That is the shift from a descriptive ontology to a **governable ontology**. OWL can express "approved contracts are contracts"; it cannot express "only a contract steward may approve, and never above one million".

Two further AOS-specific dimensions have no classical counterpart: an **observation layer** (the session event stream, physically separated from authoritative facts) and **governance as a startup condition** (the capability list must be complete before the kernel starts; legitimacy is recorded, never manufactured).

> TBox/ABox is a **teaching analogy** here. AosKeel does not use RDF triples, SPARQL or a DL reasoner. Facts are immutable events; queries are rebuildable projections. [06 · Formal semantics](docs/guide/06-formal-semantics.md) explains the mapping and its exact limits.

---

## 3. Architecture at a glance

```mermaid
flowchart TB
    GOV["GOV-1..6 · governance cross-cuts every layer<br/>capability list · artifact hash · genesis window · three gates"]
    subgraph DECL["Declaration layer — blueprint / TBox analogue"]
      SPEC["spec/ eight declaration kinds<br/>Object · Link · Action · Context · Aggregate · Invariant · Mapping · Process"]
      CAP["capability list<br/>declared == registered"]
      SPEC -->|"registration pipeline (5 steps, single writer)"| CAP
    end
    subgraph AUTH["Authoritative facts — ABox analogue"]
      LOG["append-only event log<br/>8 fields · optimistic version · no update/delete"]
      PROJ["read-only projections<br/>pure reducers · discard + rebuild"]
      LOG -->|"deterministic replay"| PROJ
    end
    subgraph OBS["Observation — non-authoritative"]
      SESS["session event stream<br/>principal-bound · provenance"]
    end
    CAP -->|"submit: capability → structure → condition → append"| LOG
    SESS -.->|"forbidden as authority (KS-2.2)"| PROJ
    GOV --- SPEC
    GOV --- CAP
    GOV --- LOG
```

Five axioms drive the whole design: **AX-1** events are the source of truth and actions are the only change; **AX-2** probabilistic mechanisms may only propose; **AX-3** three separations (type/instance, declaration/implementation, platform contract/context boundary); **AX-4** closed-loop auditability; **AX-5** schema is data. From these come 30 kernel semantics, 17 patterns, 13 global invariants, a 5-stage boot sequence, 6 governance clauses, and 33 verification points. See [02 · Architecture](docs/guide/02-architecture.md).

---

## 4. A five-step runtime loop

1. **Declare** the domain in `spec/` (eight YAML kinds — never edit generated code as the source of truth).
2. **Register**: the five-step pipeline compiles structural checks and conditions, validates links/contexts, and publishes the capability list. A failure blocks startup.
3. **Submit**: `Kernel.submit()` runs capability + role-evidence check → structural validation → conditional evaluation → append. The appended event carries the action's *declared* state effects (T24 副作用 — status is written by the declaration, never asserted by the caller). Declared roles must be presented (`roles=…`); missing evidence = refused before the store is touched (P-10 / INV-4, fail-closed). A version conflict reruns the *entire* evaluation, not just the append.
4. **Check**: three gates — structural fingerprint → cryptographic hash → `declared == registered`. Any failure exits non-zero.
5. **Release**: a fail-closed gate chains the wired test suites and skeleton byte check; only then is `dist/RELEASE-MANIFEST.json` written.

---

## 5. Smallest runnable example

```powershell
pip install -e .                       # installs pyyaml + pytest (pytest runs aos test / release)
aos verify                             # three gates
aos init my-org-system                 # instantiate the source tree
```

```python
# Run from the template root (or an initialized instance root).
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd())); sys.path.insert(0, str(Path.cwd() / "src"))

from kernel.registration import compile_all
from kernel.store import EventStore
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
from kernel.errors import ConditionalRejected

kernel = Kernel(EventStore(), SessionChannel(), compile_all())

# Entities enter the authoritative projection through a declared action;
# status is written by the action's declared effects (T24), never self-reported.
kernel.submit("RegisterContract", {"contract_id": "C-1", "amount": 500000},
              "alice", roles=("contract_steward",))

ev = kernel.submit("ApproveContract", {"contract_id": "C-1"}, "alice",
                   roles=("contract_steward",))
print(ev.event_type, ev.payload["status"])   # ApproveContract@1 approved

try:
    kernel.submit("ApproveContract", {"contract_id": "C-1"}, "alice",
                  roles=("contract_steward",))
except ConditionalRejected:
    print("refused — no event appended; audit retained")
```

In an initialized instance use `python src/cli/main.py <command>`: the `aos` console script is anchored to the template root. Full step-by-step output, including conflict re-evaluation and projection rebuild, is in [07 · Kernel walkthrough](docs/guide/07-kernel-walkthrough.md).

---

## 6. Guided learning

The guide ships in Chinese to preserve clause-level terminology exactly; it is copied into every instance by `aos init`. English readers can follow the code, tables and clause IDs, or read the two bilingual READMEs above.

| # | Document | What you will learn |
|---|---|---|
| — | [Guide index](docs/guide/README.md) | Reader-specific paths and three honest boundaries |
| 01 | [Foundations](docs/guide/01-foundations.md) | Ontology, TBox/ABox, blueprint/building, Palantir-style comparison, the four-element tuple |
| 02 | [Architecture](docs/guide/02-architecture.md) | AX→KS→P→INV→BOOT→GOV→VER derivation, four event streams, accident-based pattern justification |
| 03 | [Implementation](docs/guide/03-implementation.md) | Registration pipeline, SC compiler, submission pipeline, restricted interpreter, upcasting, gates |
| 04 | [Tutorial](docs/guide/04-tutorial.md) | install → init → BOOT-0 → draft/promote → generate → submit → test/release, with real outputs |
| 05 | [Reference](docs/guide/05-reference.md) | 12 commands, file map, T01–T26, VER-1..33 wiring, exceptions, FAQ |
| 06 | [Formal semantics](docs/guide/06-formal-semantics.md) | Description logic, open vs closed world, engineering method, OWL↔AOS translation limits |
| 07 | [Kernel walkthrough](docs/guide/07-kernel-walkthrough.md) | Executable Python: rejection paths, full re-evaluation, projections, decision audit |
| 08 | [Enterprise app guide](docs/guide/08-enterprise-app-guide.md) | The full build-out: modeling → AI drafting & promotion → generation → external ingestion → agent wiring → release → what you must build yourself |
| 09 | [Structure & trajectory](docs/guide/09-structure-and-trajectory.md) | Project structure map, clause-ID lookup, the standard development trajectory (incl. permission model and stuck-point table) |
| — | [Visual overview](docs/guide/index.html) | HTML concept map: generic concept → AOS clause → code artifact |

---

## 7. Command cheat sheet

| Command | Purpose |
|---|---|
| `aos init <dir> [--depth D] [--cap ID]` | Instantiate + capability profile (dependency-expanded) |
| `aos profile` | Resolve and validate the capability profile |
| `aos verify` | Three chained gates |
| `aos register <version>` | GOV-2.3 artifact registration (idempotent for the same hash) |
| `aos bootstrap --stage N [--dry-run]` | BOOT-0..3; stage 1 requires a real external appointment reference |
| `aos test [--suite S]` | Run suites wired in `config/verification.yaml` |
| `aos spec fingerprint` | Standalone structural-layer check |
| `aos spec version <v> --proposal-ref ...` | GOV-3 version channel (append-only) |
| `aos generate [--force]` | Declarations → code skeleton (governance → CQRS → OAuth 2.1 → frontend guard tables); hand edits block silent overwrite |
| `aos draft <file> [--name N]` | Requirements DSL → compiler-gated draft |
| `aos draft promote <f> --proposal-ref ...` | Promote a draft to canonical (single writer) |
| `aos import-db` | Legacy schema → ontology draft (DDL or sqlite DSN; meta-structure only) |
| `aos import-data` | Legacy rows → genesis-event drafts (each row through the full evaluation chain) |
| `aos extract` | Semantic extraction: source code / docs → ontology draft (same three gates; builtin deterministic rules, pluggable LLM adapter via stdout-YAML contract; candidates never facts) |
| `aos shadow` | Offline dual-run reconciliation: legacy rows ↔ new-system events |
| `aos shadow-online` | Online dual-run reconciliation: consumes deployment-side probe NDJSON (probe contract in tool header; fail-closed on bad lines; probes are instance-side) |
| `aos review` | Read-only adjudication list (anchors / draft candidates / governance audit) |
| `aos release` | Fail-closed release gate → `dist/RELEASE-MANIFEST.json` |
| `tools/console.py` | WEB governance console shell (whitelisted commands via subprocess CLI; signing commands excluded) |

---

## 8. Legacy migration: the strangler pipeline

Old systems enter through the same gates — imported material is always a **draft**, never a fact:

```powershell
aos init <dir> --depth standard        # 1. instantiate + capability breadth
aos import-db --ddl legacy.sql         # 2. structure extraction (schema → ontology draft)
aos review                             # 3. adjudication list (candidates / governance audit)
aos draft promote ... --proposal-ref   # 4. human promotion (GOV-1 proposal mandatory)
aos generate                           # 5. new-system code (governance → CQRS → OAuth 2.1)
aos import-data --dsn ... --map M      # 6. data as genesis events (every row through the evaluation chain)
aos shadow --dsn ... --map M           # 7. offline dual-run: rows ↔ events semantic parity
python tools/console.py                # 8. WEB console shell over the same CLI (whitelist, fail-closed)
```

Data migration is **event replay, not table copy**: each legacy row must pass the new system's full evaluation chain (registration → role evidence → structural → conditional → store); dirty rows are refused, never laundered into the event stream. OAuth 2.1 is not a plugin but a **projection of the governance plane** — token claims are rendered from the duty matrix, and presenting an undeclared role is refused.

The theory behind this — the five-layer model (concept/structure/constraint/behavior/mapping) with the governance plane cross-cutting every layer, and the ten engineering disciplines (deterministic generation with LLM-as-drafter, three-gate drafts, fail-closed everywhere, credentials never on disk) — is in the [whitepaper](docs/WHITEPAPER.md).

---

## 9. Honest boundaries (read before adopting)

- **No proof of compliance.** `mandatory` clauses require human execution on a running system, with evidence, judge and signer. The template never marks them passed for you.
- **No manufactured legitimacy.** Stewards and founding appointments are world events; the template records them, never synthesizes them (GOV-1).
- **Source-tree delivery.** The wheel does not carry `docs/spec/config` and the startup self-check refuses it (verified, INTEGRITY-20) — see the wheel boundary note below.
- **In-memory event store.** `EventStore` is a dict: no persistence across process restarts. `kernel/filestore.py` ships a FileStore **reference implementation** (JSONL append + replay, single-writer process model); durable multi-process storage remains an instance-side duty under the same protocol.
- **wheel is a build artifact, not a deliverable.** `pip wheel .` builds `aos_keel-*.whl` (src/ + tools/ only; the `aos` console script works), but it ships **without** docs/spec/config — running it outside a source tree prints an explicit `REFUSED` (machine-guarded, INTEGRITY-20). The only supported runtime form is the source tree with `pip install -e .`, so the canonical declarations stay versioned next to the code.
- **The console is a shell, and an offline one.** `tools/console.py` drives the CLI via subprocess with a fail-closed command whitelist; governance-signing commands (release/register/bootstrap) are excluded by design, and `aos shadow` is offline reconciliation — online dual-run traffic comparison is a deployment-stage duty.
- **Structural fingerprint is weak by design.** It checks clause counts and anchors; the cryptographic hash layer is the strong guarantee.
- **Chinese frozen canon.** `aos-spec.md` and the other canonical documents are frozen Chinese text and are not translated; only the READMEs are bilingual.

Full detail: [docs/README.md](docs/README.md) · [简体中文](docs/README.zh-CN.md) · [Positioning](docs/POSITIONING.md) · [Runbook](docs/RUNBOOK.md) · [Canonical specification](docs/aos-spec.md).
