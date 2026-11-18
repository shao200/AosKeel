# AOS Specification — English Overview (non-normative companion)

> **Status: informational navigation aid, NOT the specification.** The only normative
> text is the frozen Chinese canonical [`aos-spec.md`](aos-spec.md) (sha256 `48df813a…`,
> registered as `AOS-ART-002`, spec v2.1.0). This file is deliberately **outside** the hash coverage
> set (`tools/hash_spec.py:CANONICAL_FILES`) and outside the declaration digest domain
> (`spec/**/*.yaml`). If anything here conflicts with the canonical text, the Chinese
> canonical wins. Clause identifiers are preserved verbatim; no clause is translated.

## Why this file exists, and what it refuses to do

The canonical specification is a frozen Chinese text. Its clause IDs
(`AX-1..5`, `KS-1.1..8.5`, `P-1..17`, `INV-1..13`, `BOOT-0..4`, `GOV-1..6`,
`VER-1..33`, `T01..T26`, accidents `A..R`) are the continuity contract; the prose is
normative and must not drift. A full English translation would create a second
source of truth with no mechanism to keep it byte-identical to the frozen text.
This overview therefore gives English readers a **map**, not a substitute: enough
structure to navigate the canonical clauses and the source, without pretending to
reproduce their legal force.

## The clause map

| Prefix | Count | What it governs | Where |
|---|---|---|---|
| AX | 5 | Core axioms; highest authority on conflict | §2 |
| KS | 30 | Kernel semantics the runtime/registration must implement | §3 |
| P | 17 | Design patterns, each justified by the accident it prevents | §4 |
| INV | 13 | Global invariants — **supreme adjudicator** of any conflict | §5 |
| BOOT | 5 | Boot sequence; first four steps are preconditions | §6 |
| GOV | 6 | Governance and SpecChange (social contract, version channel) | §7 |
| VER | 33 | Verification matrix — executable checkpoints for MUST duties | §8 |
| T | 26 | Canonical glossary; variant terms are banned in normative clauses | §1.1 |
| A–R | 18 | Accident categories; GOV-4 proposals must cite the accident prevented | App. B.2 |

Three precedence rules recur throughout: (1) an implementation conflicting with an axiom
yields to the axiom; (2) tension between clauses is adjudicated by INV; (3) VER
checkpoints are mandatory and may not be bypassed.

## The mental model (see the README diagram)

The architecture is an **inductive view** of the clauses, not a new normative layer:

- **Descriptive layer** — `ObjectType / Property / LinkType` (the TBox analogy) states
  what is true. `ActionType` is the element that turns a descriptive ontology into a
  **governable** one: it compiles "who may change what, under what conditions, with
  what audit" into an executable contract.
- **Governance plane** — GOV-1..6 plus the capability list cross-cut every layer and
  act as a startup condition (`declared == registered`).
- **Instance layer** — the append-only 8-field event log is the sole authoritative
  fact; projections are read-only and rebuildable.
- **Observation layer** — the physically separated session stream may never stand in
  as authority (KS-2.2).

A four-element tuple (`ObjectType / Property / LinkType / ActionType`, T01) plus four
constructs (`ContextType / AggregateType / Mapping / ProcessType`, T02) is the
ontology's unit of expression.

## What AOS deliberately is not

AosKeel is a governable ontology scaffold — not a DL reasoner, planner, or triple
store. Description logics / OWL, action formalisms (PDDL, situation/event calculus),
and deontic logic are teaching analogies and lineage, not runtime mechanisms. OWL keeps
no counterpart for `ActionType`, the capability list, the observation layer, or the
genesis window; see [`guide/06-formal-semantics.md`](guide/06-formal-semantics.md) for the
exact translation limits, and [`WHITEPAPER.md`](WHITEPAPER.md) §1–2 for the five-layer
standard model and the ten disciplines.

## How to actually use the specification

1. Read the clause you need **in the Chinese canonical** — clause IDs are stable
   anchors across versions.
2. Cross-check behavior in the source (`src/kernel`, `src/interpreter`) and the
   executable gates (`aos verify`, `aos cq`, `aos test`).
3. For the derivation chain behind every clause, read
   [`guide/02-architecture.md`](guide/02-architecture.md).

Machine-checkable entry points: `aos verify` (structural fingerprint + canonical hash
+ declaration digest + registration), `aos cq` (executable competency questions),
`aos test` (wired suites). A passing local test run is not a substitute for system-wide
consistency; authority remains the canonical text and its registered hashes.
