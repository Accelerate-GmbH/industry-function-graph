# industry-function-graph

A knowledge graph that answers one question: **which business function, in which
economic sector, does a given use case serve?**

The point of building it this way is reuse. "Identity proofing" is the same
function whether a bank, a hospital or an employer performs it — only the
regulation around it differs. If the function layer is kept independent of the
sector layer, a pattern worked out once in banking is visibly reusable in
education, and the matrix shows you where.

**👉 Live matrix: https://didas-swiss.github.io/industry-function-graph/**

The graph is published at the same place the concepts are named, so the IRIs and
the download are the same URLs:
[Turtle](https://didas-swiss.github.io/industry-function-graph/ifm-graph.ttl) ·
[JSON-LD](https://didas-swiss.github.io/industry-function-graph/ifm-graph.jsonld) ·
[ontology](https://didas-swiss.github.io/industry-function-graph/ontology)

```bash
curl -sO https://didas-swiss.github.io/industry-function-graph/ifm-graph.ttl
```

The same files are committed under [`generated/`](./generated) and
[`ontology/`](./ontology) if you would rather read them in the repository.

## The four layers

```
  [ 1. SECTOR ]                          [ 2. FUNCTION ]
  ISIC Rev. 5 (NACE Rev. 2.1 at         IFM function scheme,
  section and division level)            mapped to UN CBF / APQC PCF
        ^                                       ^
        | ifm:appliesToSector                   | ifm:executesFunction
        +-------------------+-------------------+
                            |
                   [ 3. USE CASE ]
                   schema:Action — the intersection node
                            |
                            v
                   [ 4. CREDENTIAL ]  ← deferred, see below
```

Nothing in the model is invented where a standard exists:

| Layer | Standard | How it is used here |
|---|---|---|
| 1 · Sector | ISIC Rev. 5, NACE Rev. 2.1 | `skos:ConceptScheme` with the official code in `skos:notation`. All 22 ISIC sections, plus the divisions and classes the use cases actually reach. |
| 2 · Function | UNECE/Eurostat CBF, APQC PCF | A local function scheme mapped onto both with SKOS mapping relations. |
| 3 · Use case | `schema:Action` | The bridge: each use case links ≥1 sector and exactly one primary function. |
| 2d · Value stream | ArchiMate `Value Stream` | An ordered composition of functions delivering an outcome — procure to pay, order to cash. Catalogue is our own; no openly licensed one exists. |
| 3c · Interface | own vocabulary | Pre- and postconditions over a shared state vocabulary. Composition, gaps and duplicates are **derived** from these. |
| 3b · Who and what for | own vocabularies | Trust roles with who bears cost and who gains value, what evidence the credential replaces, and which use cases must work first. |
| 3a · Why and how far | own vocabularies | Value drivers (what it removes, prevents or makes possible) and one transformation mode (how far the process changes). |
| 4 · Credential | W3C VCDM 2.0, EBSI, DCC/ELM, UN/CEFACT | **Not implemented yet** — see [Layer 4](#layer-4--deferred). |

## Layout

```
industry-function-graph/
├── data/           the source of truth — CSV, hand-edited, reviewable in a diff
├── ontology/
│   └── ifm.ttl     the vocabulary (hand-written, stable)
├── build/
│   ├── model.py    loads data/ and derives what can be derived
│   ├── build.py    data/ → generated/
│   └── validate.py integrity checks, run in CI
└── generated/      DO NOT EDIT — rebuilt from data/
    ├── ifm-graph.ttl      the graph, Turtle
    ├── ifm-graph.jsonld   the same graph, JSON-LD
    ├── matrix.md          the sector × function matrix, Markdown
    └── index.html         the same matrix, browsable, self-contained
```

## Rebuilding

No dependencies beyond Python 3:

```bash
python3 build/validate.py      # integrity checks (exit 1 on error)
python3 build/build.py         # regenerate generated/
python3 build/build.py --check # fail if generated/ is stale — this is what CI runs
```

`validate.py` additionally parses the generated RDF and checks that the Turtle
and the JSON-LD are the same graph, *if* `rdflib` is installed (`pip install
rdflib`). Without it that one check is skipped with a warning; everything else
still runs.

## The namespace

Concepts are minted under
`https://didas-swiss.github.io/industry-function-graph/`, the GitHub Pages
URL of this repository. Pages is enabled, so the matrix, the graph and the
ontology are all fetchable there; the individual concept IRIs
(`…/id/sector/ISIC-C`) are identifiers rather than dereferenceable documents,
which is fine for a vocabulary this size but is the thing a `w3id.org` redirect
would fix if these IRIs ever need to outlive this repository.

The namespace is a single constant, `BASE` in `build/model.py` — change it and
rebuild to move the vocabulary elsewhere. Nothing else hard-codes it.

## Identifiers, and why they drop the section letter

A division or class is `ISIC-64`, `ISIC-6419` — not `ISIC-L-64`. Section letters
move between revisions while the numbers hold. Between ISIC Rev. 4 and Rev. 5,
finance went K → L, education P → Q, human health Q → R, and old section J
("Information and communication") split, with the IT half becoming Rev. 5 K.
Every division and class number involved stayed put. An identifier keyed on the
letter would have to be rewritten at every revision, taking every concept IRI
with it.

Two classes *were* renumbered in Rev. 5 and are worth knowing about, because
anything mapped under Rev. 4 will be wrong:

| Rev. 4 | Rev. 5 | |
|---|---|---|
| 8521 General secondary education | **8531** General secondary education | group 852 → 853 |
| 8530 Higher education | **8540** Tertiary education | renamed as well as renumbered |

### Cross-check against NOGA 2025

The sector layer was checked against the NOGA 2025 subset codified in the
[DIDAS Trust Flow Diagram Repository](https://github.com/DIDAS-swiss/Trust-Flow-Diagram-Repository),
which classifies its flows by NOGA. Comparing the two:

- **22 of 22** section letters present in both, structurally identical
- **23 of 23** NOGA divisions sit under the same section in ISIC Rev. 5 — zero mismatches
- 3 section titles differ in spelling only ("organisations"/"organizations",
  "Telecommunication"/"Telecommunications", one `and` for a `;`)

That is the evidence behind the NACE Rev. 2.1 codes recorded here: NOGA 2025 is
the Swiss implementation of NACE Rev. 2.1, and it matches ISIC Rev. 5 at section
and division level, so NACE does too. It also means the **division number is a
usable join key** between this graph and any NOGA-classified sector — which is
the point of
[Trust-Flow-Diagram-Repository#12](https://github.com/DIDAS-swiss/Trust-Flow-Diagram-Repository/issues/12).

The three divisions absent from that NOGA subset (30, 56, 62) carry no NACE code
and say so in their `note`.

## Adding a use case

Edit CSVs, never `generated/`:

1. `data/use-cases.csv` — one row: id, name, description, maturity
   (`Exploratory` / `Modelled` / `Live`), and `documented_by`, an absolute URL
   to wherever the use case is worked out in detail (empty if nowhere yet).
2. `data/use-case-sectors.csv` — one row per sector. **Use the most specific
   ISIC concept that is actually warranted.** A use case that genuinely spans a
   whole section links to the section; it does not pick an arbitrary class
   inside it. If the sector you need is missing, add it to `data/sectors.csv`
   together with its parents.
3. `data/use-case-functions.csv` — one row per function, exactly one with
   `role=primary`. Reuse an existing function if one fits; a function that
   exists only to describe a single use case is a sign the function layer is
   drifting into the use case layer.
4. Run `validate.py`, then `build.py`, and commit `data/` and `generated/`
   together.

Cross-sector vs. sector-specific is **derived**, not typed in: a use case that
reaches more than one ISIC section is cross-sector. Same for the narrower/
broader inverses and the matrix itself. Anything derivable is derived, so it
cannot fall out of sync.

### The seeded use cases

The 11 use cases currently in `data/` are a worked seed, not a claim to
completeness. Six of them are Swiss e-ID trust flows documented in the
[DIDAS Trust Flow Diagram Repository](https://github.com/DIDAS-swiss/Trust-Flow-Diagram-Repository)
(banking KYC and re-identification, education credential issuance and
university immatriculation); the other five — age verification at the point of
sale, employee identity proofing, aerospace supplier onboarding, patient
identification, e-government service access — are scoped but not yet worked
out anywhere, and are marked `Exploratory`. Replace or extend them freely;
the sector and function layers do not depend on them.

## Querying

The graph is plain SKOS + schema.org, so any triple store works —
Apache Jena, GraphDB, or Neo4j with neosemantics (`n10s.rdf.import.fetch`).

Which functions recur across sectors (the reuse candidates):

```sparql
PREFIX ifm:  <https://didas-swiss.github.io/industry-function-graph/ontology#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?function (COUNT(DISTINCT ?section) AS ?sections)
WHERE {
  ?useCase a ifm:UseCase ;
           ifm:executesFunction ?f ;
           ifm:appliesToSector ?sector .
  ?f skos:prefLabel ?function .
  ?sector skos:broader* ?section .
  ?section skos:topConceptOf ?scheme .
}
GROUP BY ?function
HAVING (COUNT(DISTINCT ?section) > 1)
ORDER BY DESC(?sections)
```

Everything in a sector, including its sub-classes, via `skos:broader*`:

```sparql
SELECT DISTINCT ?name WHERE {
  ?useCase a ifm:UseCase ; schema:name ?name ; ifm:appliesToSector ?sector .
  ?sector skos:broader* ?section .
  ?section skos:notation "K" .
}
```

## Provenance and honesty

The blueprint this follows sketches notations like `UN_CBF_F4`. Those are not
reproduced here, because they could not be checked against an official
publication — and a plausible-looking wrong code is worse than no code. Every
concept therefore carries `ifm:codeStatus`:

| Data | `codeStatus` | Basis |
|---|---|---|
| ISIC Rev. 5 sections, divisions, classes | `verified` | Codes and titles taken from the official ISIC Rev. 5 structure file published by the UN Statistics Division. |
| NACE Rev. 2.1 codes | — | Recorded as `ifm:naceRev21Code` literals at **section and division level only**, where NACE is identical to ISIC — and only for divisions the cross-check below covers. Deliberately not asserted at class level, where the two diverge. |
| CBF categories | `provisional` | Category labels following the UNECE/Eurostat Classification of Business Functions. No notations are asserted. Replace with an official extract before relying on them. |
| APQC PCF categories | `provisional` | Only the cross-industry categories an alignment actually references. The framework is published by APQC and is not redistributed here; get the full version from [apqc.org](https://www.apqc.org/process-frameworks). |
| Function alignments | `provisional` | Editorial judgement, recorded row by row in `data/function-alignments.csv` with the reasoning. |

Two modelling decisions follow from this:

**The function scheme is its own scheme, not a fork of CBF.** Use cases point at
`ifm-functions` concepts; those concepts point at CBF and APQC with
`skos:broadMatch` / `skos:relatedMatch`. Correcting an alignment — or swapping
CBF for something else entirely — then touches one row of one CSV and no use
case at all.

**CBF's core/support split is not used as a hierarchy.** In CBF, whether an
activity is a *core* or a *support* function depends on the enterprise, not on
the activity: issuing certificates is the core function of a certification body
and a support function of a manufacturer. Hanging our functions under
`CBF-CORE` or `CBF-SUP` as `skos:broader` would bake one enterprise's viewpoint
into the vocabulary, so the relation used is `skos:broadMatch` between schemes
instead.

## Value streams

A function says what kind of work something is. It does not say where that work
sits in an end-to-end sequence — and "supplier qualification" only means
something once you know it is the front of procure-to-pay.

The concept follows [ArchiMate's Value Stream
element](https://pubs.opengroup.org/architecture/archimate32-doc/) — *a sequence
of activities that create an overall result for a customer, stakeholder or end
user*, the **what** rather than the **how**. ArchiMate is an open standard for
expressing a value stream. There is **no openly licensed catalogue** of them:
APQC publishes end-to-end process maps, including for procure-to-pay, under its
own terms, and the SAP naming is proprietary. So the catalogue here is this
repository's own, marked `provisional` like every other unverified vocabulary.

Streams **compose** functions, they do not contain them. One function appears in
several streams, so this is not a hierarchy over the function layer. Stages are
reified rather than listed, so each carries a position and its own label:

```
procure-to-pay
  1  Source and qualify                              sourcing-and-procurement
  2  Establish the supplier is a real legal entity   identity-proofing
  3  Assess counterparty and financial risk          credit-and-risk-assessment
  4  Check accreditations and audit reports          audit-and-assurance
  5  Check conformity of what will be supplied       product-compliance
  6  Agree and sign                                  contracting-and-signing
  7  Establish provenance through delivery           supply-chain-traceability
  8  Clear the border                                customs-and-trade-facilitation
  9  Goods receipt against specification             quality-assurance
 10  Invoice and payment                             invoicing-and-settlement
 11  Substantiate the tax position                   tax-administration
 12  Retain the audit trail                          records-management
```

`ifm:position` is ordering only — real stages overlap, and the sequence is a
reading aid rather than a claim about execution.

### On "finance" and "manufacturing"

People reach for department names when asked which function a use case serves.
Neither is a function here: **manufacturing** is a *sector* (ISIC section C), and
**finance** is either a sector (section L) or, as work, the three stages above
marked finance — credit and risk assessment, invoicing and settlement, tax
administration. The value stream is what makes that legible: it shows where the
finance-side and the production-side stages fall inside one sequence, which is
the thing a department name is reaching for.

## Why, and how far: the axes on top

Sector and function say *where* a use case sits. They say nothing about why a
verifiable credential is worth applying there, or whether it improves a process
that already exists or replaces it — and those are the questions someone
deciding what to build actually asks. The same function in the same sector can
be a paper substitution in one instance and a new business model in another.

**Value drivers** — what it removes, prevents or makes possible. Several per use
case, unranked:

| Driver | |
|---|---|
| `friction-reduction` | steps, waiting, re-keying or intermediaries removed from an exchange that already happens |
| `fraud-prevention` | forgery, impersonation and misrepresentation made impractical rather than merely detectable afterwards |
| `compliance-assurance` | evidence a supervisor will accept, produced as a by-product of the work rather than as an exercise |
| `data-quality` | transcription, reconciliation and staleness errors removed |
| `data-minimisation` | proving what the counterparty is entitled to know without disclosing the rest — often what makes an exchange permissible at all |
| `reach-and-inclusion` | counterparties served who could not be before: remote, cross-border, or with no prior relationship |
| `new-revenue` | a chargeable service, market or pricing model that verifiable data is a precondition for |

**Transformation mode** — how far the process changes. Exactly one per use case,
and the pair of them splits into *run* and *change*:

| Mode | | |
|---|---|---|
| `digitise` | **run** | the process keeps its shape; a paper artefact becomes a credential |
| `optimise` | **run** | steps, hand-offs or waiting removed, but recognisably the same process |
| `redesign` | **change** | reorganised around verifiable data; roles and sequence change, and the old process is not recoverable from the new one |
| `enable` | **change** | the activity was not viable before, because the trust it needs could not be established at acceptable cost |

`ifm:changeMode` is derived from the mode, never typed in.

The distinction earns its place because the two halves are justified
differently: *run* is a business case — count the steps removed — while *change*
is a strategy, and can look like a poor business case right up until it works.
Collapsing them is how digitisation programmes end up paving the cowpath: a PDF
becomes a credential, every signature stays where it was, and nobody asks
whether the process should exist.

It is also a coverage check on the repository. Of the eleven seeded use cases,
**none** is classified `enable`, and `new-revenue` is claimed by none of them —
every one improves or reorganises something organisations already do. That is a
fair reflection of where Swiss e-ID practice currently is, and the graph says so
out loud rather than implying a breadth it does not have.

## Composability: the point of the classification

A use case is not a leaf in a taxonomy. It is a **component with two ends** —
what must already be true for it to run, and what is true once it has. Type both
ends against a shared state vocabulary and composition stops being drawn by hand
and starts being computed: **B follows A exactly when something A leaves true is
something B needs.**

```
education-maturitaetszeugnis-issuance
    → education-university-immatriculation   via secondary-education-credential-held
    → employment-identity-proofing           via secondary-education-credential-held

banking-kyc-onboarding
    → banking-re-kyc                         via customer-relationship-open
    → banking-reidentification-…             via customer-relationship-open
    → banking-age-of-majority-…              via customer-relationship-open
```

Those arrows are `ifm:enables`, and nobody typed them. Change a postcondition and
the chain changes with it. `ifm:requiresUseCase` survives for dependencies a
modeller knows and the interfaces do not yet say, but it is **checked against
them**: assert that A requires B and the validator insists something B leaves
true is something A needs, or one of the two is wrong.

Three things fall out that a taxonomy alone cannot give you.

**The chain** — above.

**The gaps.** A state everything needs and nothing here produces is an open
socket: either a use case nobody has written down, or a dependency on something
outside the repository. Today there are two:

`eid-held` was the first one found — needed by nine of twelve use cases and
produced by none of them. It is now `eid-issuance`, the root the whole chain
hangs from:

```
eid-issuance
  → banking-kyc-onboarding                    via eid-held
      → banking-re-kyc                        via customer-relationship-open
      → banking-reidentification-…            via customer-relationship-open
      → banking-age-of-majority-…             via customer-relationship-open
  → education-maturitaetszeugnis-issuance     via eid-held
      → education-university-immatriculation  via secondary-education-credential-held
      → employment-identity-proofing          via secondary-education-credential-held
  → egov-service-access, healthcare-patient-identification,
    retail-hospitality-age-verification       via eid-held
```

It is also the only use case classified `enable` and the clearest asymmetry in
the graph: the issuer bears the cost of the credential every other use case
depends on, while the value lands on the parties verifying it.

One socket remains — `supplier-accreditation-held`, needed by supplier
qualification and produced by nothing here. That is a real gap: accreditation
bodies issuing verifiable certificates is a use case nobody in this repository
has written down.

**The duplicates.** Two use cases with the same precondition set, postcondition
set and primary function are, on the evidence, one use case. The check caught a
pair written separately here — `aerospace-supplier-onboarding` and
`pharma-supplier-qualification` had identical interfaces and differed only by
sector — and they have since been collapsed into one `supplier-qualification`
that both sectors instantiate. The sector-specific detail that mattered (GMP for
pharmaceuticals, quality accreditation for aerospace) survives as a note on the
issuing participation, which is where it belonged.

That is the minimal-overlap goal working as a check rather than an aspiration,
and the first thing it did was find a duplicate in its own author's data.

### Why states are coarse

An interface with one implementor is not an interface. States are deliberately
blunt — `secondary-education-credential-held`, not
`gymnasiale-maturitaet-2026-held` — because the point is that flows nobody has
written yet should plug into the same sockets. As the ecosystem iterates and new
credentials arrive, they fall into place by matching states, not by being added
to a list.

## Who pays, who benefits

The reason credential ecosystems stall is almost never technical. It is that the
party who must invest in issuing is not the party who gets the value from
verifying. A graph that cannot express that cannot answer the first question
anyone actually has: **who has to move first, and what is in it for them?**

So each use case records its participations — a party, a trust role, whether it
bears material cost, and whether it gains direct, indirect or no value.
`ifm:costValueAsymmetry` is derived from those, never typed in.

On the twelve seeded use cases, **nine are asymmetric**:

| | |
|---|---|
| Self-funding — issuer gains directly | `banking-kyc-onboarding`, `banking-re-kyc`, `egov-service-access` |
| Someone must move for another's benefit | the other nine |

The pattern is worth staring at. The three that fund themselves are the three
where **the issuer and the verifier are the same party or the same institution**:
a bank issuing a KYC attestation it will re-verify, and a state issuing the
credential its own services accept. Everywhere else — a school issuing for a
university's benefit, the federal e-ID issuer bearing cost so a merchant can
check an age — somebody has to be persuaded, funded or obliged.

That is a prediction the graph makes and can be checked against reality: the
self-funding cases should be the ones already running. It is also the argument
for where public funding or regulation does most good, and it fell out of the
model rather than being asserted.

## What the credential replaces

`friction-reduction` is the easiest driver to claim and the easiest to claim
emptily. Every use case that claims it must name what goes away — a paper
document, an uncheckable PDF, a phone call to the issuer, an in-person visit, a
notarised copy, a registry lookup, a self-declaration nobody checks. The
validator fails a use case that claims the driver and names nothing, because a
business case starts with the thing being removed.

## What must work first

`ifm:requiresUseCase` records dependencies between use cases, and the validator
rejects cycles. There is nothing to present until somebody issues, so these edges
are the sequencing plan: university immatriculation cannot work before schools
issue, and employment qualification checks depend on awarding institutions doing
the same.

## What belongs in the function layer

The first draft of this vocabulary read like a list of electronic-identity use
cases — proofing, onboarding, access. That is too narrow, and narrowing it that
way quietly answers a question it should leave open.

A verifiable credential is a container for **any** signed, structured,
machine-checkable claim. Identity is the most familiar payload, not the only
valuable one: a test certificate, a customs declaration, a product conformity
statement, an emissions figure, a consent record and an invoice are all
structured assertions whose value comes from being checkable without calling the
issuer. The function axis should therefore cover the business functions where a
checkable claim removes a phone call, a PDF or a trusted intermediary — not the
functions where identity happens to be the subject.

So the vocabulary deliberately spans more than it currently uses. It is wider
than the seeded use cases, and `validate.py` reports the unexercised ones as
coverage rather than as a problem.

Two rules keep it from sprawling:

- **A function is work, not a credential type.** "Diploma" is a credential;
  "certification and attestation" is the function that issues one. If a proposed
  entry names a document, it is in the wrong layer.
- **A function is sector-independent.** If it cannot be stated without naming an
  industry, it belongs in a use case instead.

Three entries are close together and worth telling apart: **quality assurance**
is checking your own output before it ships, **audit and assurance** is someone
independent checking it afterwards, and **certification and attestation** is
issuing the statement that results.

## Layer 4 — deferred

The verifiable credential layer is intentionally left out for now. When it is
added, nothing in layers 1–3 has to change; the extension point is:

- a `ifm:CredentialSchema` class for W3C VCDM 2.0 credential types, in its own
  file under `data/`;
- an `ifm:requiresCredential` property from `ifm:UseCase` to it — the use case
  node is already the right place to hang it, because what a credential has to
  prove is a property of the *use case*, not of the sector or the function;
- ecosystem-specific schema anchors alongside it (EBSI conformance frameworks
  for cross-sector governance, DCC/ELM for education and labour, UN/CEFACT or
  GS1 for supply chain and trade), mapped the same way the function alignments
  are — as mapping relations with a recorded `codeStatus`, not as a fork.

## Licence

| What | Licence |
|---|---|
| The content — the mapping data in [`data/`](./data), the ontology in [`ontology/`](./ontology), everything generated from them in [`generated/`](./generated), and the prose in this README and `NOTICE.md` | [CC BY 4.0](./LICENSE-CONTENT) |
| The software — the build and validation scripts in [`build/`](./build) and the workflows in `.github/workflows/` | [MIT](./LICENSE) |

The data files are content rather than software: they are a vocabulary and a set
of editorial mappings, and the creative work in them is the mapping itself.

Reuse the mapping freely, including commercially and in modified form, as long
as you attribute:

> industry-function-graph, Daniel Saeuberli, https://github.com/DIDAS-swiss/industry-function-graph

The classifications this maps onto (ISIC, NACE, CBF, APQC PCF) are published by
their respective organisations under their own terms and are **not** covered by
that grant — see [`NOTICE.md`](./NOTICE.md). Concepts marked
`ifm:codeStatus "provisional"` have not been checked against an official
publication.
