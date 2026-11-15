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
3. **Submit**: `Kernel.submit()` runs capability check → structural validation → conditional evaluation → append. A version conflict reruns the *entire* evaluation, not just the append.
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
params = {"contract_id": "C-1", "status": "pending", "amount": 500000}

ev = kernel.submit("ApproveContract", dict(params), "contract_steward")
print(ev.event_type, ev.stream_id)     # ApproveContract@1 domain:ContractAggregate

try:
    kernel.submit("ApproveContract", dict(params, status="void"), "contract_steward")
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
| 05 | [Reference](docs/guide/05-reference.md) | 11 commands, file map, T01–T26, VER-1..33 wiring, exceptions, FAQ |
| 06 | [Formal semantics](docs/guide/06-formal-semantics.md) | Description logic, open vs closed world, engineering method, OWL↔AOS translation limits |
| 07 | [Kernel walkthrough](docs/guide/07-kernel-walkthrough.md) | Executable Python: rejection paths, full re-evaluation, projections, decision audit |
| — | [Visual overview](docs/guide/index.html) | HTML concept map: generic concept → AOS clause → code artifact |

---

## 7. Command cheat sheet

| Command | Purpose |
|---|---|
| `aos init <dir>` | Instantiate a template copy with version lock |
| `aos verify` | Three chained gates |
| `aos register <version>` | GOV-2.3 artifact registration (idempotent for the same hash) |
| `aos bootstrap --stage N [--dry-run]` | BOOT-0..3; stage 1 requires a real external appointment reference |
| `aos test [--suite S]` | Run suites wired in `config/verification.yaml` |
| `aos spec fingerprint` | Standalone structural-layer check |
| `aos spec version <v> --proposal-ref ...` | GOV-3 version channel (append-only) |
| `aos generate [--force]` | Declarations → code skeleton; hand edits block silent overwrite |
| `aos draft <file> [--name N]` | Requirements DSL → compiler-gated draft |
| `aos draft promote <f> --proposal-ref ...` | Promote a draft to canonical (single writer) |
| `aos release` | Fail-closed release gate → `dist/RELEASE-MANIFEST.json` |

---

## 8. Honest boundaries (read before adopting)

- **No proof of compliance.** `mandatory` clauses require human execution on a running system, with evidence, judge and signer. The template never marks them passed for you.
- **No manufactured legitimacy.** Stewards and founding appointments are world events; the template records them, never synthesizes them (GOV-1).
- **Source-tree delivery.** The wheel does not carry `docs/spec/config` and the startup self-check refuses it. Wheel-installability is an open P2 item.
- **In-memory event store.** `EventStore` is a dict: no persistence across process restarts. Production instances must supply their own durable, append-only store.
- **Structural fingerprint is weak by design.** It checks clause counts and anchors; the cryptographic hash layer is the strong guarantee.
- **Chinese frozen canon.** `aos-spec.md` and the other canonical documents are frozen Chinese text and are not translated; only the READMEs are bilingual.

Full detail: [docs/README.md](docs/README.md) · [简体中文](docs/README.zh-CN.md) · [Positioning](docs/POSITIONING.md) · [Runbook](docs/RUNBOOK.md) · [Canonical specification](docs/aos-spec.md).
