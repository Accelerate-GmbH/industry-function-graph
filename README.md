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
| 4 · Credential | SD-JWT VC (swiyu), W3C VCDM (ELM, UN/CEFACT) | Credential types hung off the trust roles, each evidencing one state — see [Layer 4](#layer-4--credential-types). |

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
administration. The value stream makes that legible by showing where the
finance-side and the production-side stages fall within one sequence, which is
what a department name is pointing at.

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
| `data-minimisation` | proving what the counterparty is entitled to know without disclosing the rest, which can permit an exchange that full disclosure would not |
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

The two halves are justified differently. *Run* is usually a business case: count
the steps removed. *Change* is a strategic decision, and may show a weak business
case until it works. Treating them alike tends to produce digitisation that
preserves the existing process — the PDF becomes a credential, the signatures stay
where they were, and the question of whether the process should exist never comes
up.

It also measures coverage. `new-revenue` is claimed by no use case here, and only
one is classified `enable` — the rest improve or reorganise something
organisations already do. That reflects where Swiss e-ID practice currently is,
and the validator reports it so the graph does not imply a breadth it lacks.

## Composability: the point of the classification

Each use case is a **component with two ends** — what must already be true for it
to run, and what is true once it has. Both ends are typed against a shared state
vocabulary, so the composition can be computed instead of maintained by hand:
**B follows A when something A leaves true is something B needs.**

```
education-maturitaetszeugnis-issuance
    → education-university-immatriculation   via secondary-education-credential-held
    → employment-identity-proofing           via secondary-education-credential-held

banking-kyc-onboarding
    → banking-re-kyc                         via customer-relationship-open
    → banking-reidentification-…             via customer-relationship-open
    → banking-age-of-majority-…              via customer-relationship-open
```

Those arrows are `ifm:enables`, computed from the interfaces. Change a
postcondition and the chain changes with it. `ifm:requiresUseCase` remains
available for dependencies a modeller knows before the interfaces express them,
and it is **validated against them**: assert that A requires B and the validator
requires that something B leaves true is something A needs.

Three results come from this that the taxonomy alone does not provide.

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

This turns minimal overlap into an automated check. Its first run found a
duplicate in the data of this repository itself.

### Why states are coarse

States are deliberately blunt — `secondary-education-credential-held` rather than
`gymnasiale-maturitaet-2026-held` — so that flows nobody has written yet can
connect to the same ones. A state used by a single use case connects nothing. As
new credentials arrive, they attach by matching an existing state, without the
vocabulary having to grow each time.

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
| One party invests for another's benefit | the other nine |

The three self-funding cases share a property: **the issuer and the verifier are
the same party or the same institution**. A bank issues a KYC attestation it will
later re-verify; the state issues the credential its own services accept. In the
other nine the investing party and the benefiting party differ — a school issues
for a university's benefit, the federal e-ID issuer carries cost so a merchant can
check an age — so those require funding, regulation or negotiation to proceed.

This gives a testable prediction: the self-funding cases should be the ones
already in production. It also indicates where public funding or regulation would
have most effect. Both follow from the participation data rather than from an
assumption written into it.

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

## Reconciling with the Trust Flow Diagram Repository

Both repositories classify the same flows: this one as use cases, the
[Trust Flow Diagram Repository](https://github.com/DIDAS-swiss/Trust-Flow-Diagram-Repository)
as families in `sector.yaml`. Two descriptions of one flow that never meet will
drift apart.

```bash
python3 build/reconcile.py --source ../Trust-Flow-Diagram-Repository
```

It joins on `documented_by` and compares the state interfaces and the primary
function. It reports rather than fails: the two repositories are allowed to
disagree, but not to disagree unnoticed. It needs both checkouts, so it is a
local tool rather than a CI job.

The first run found two disagreements, and both have the same cause:

| Family | Disagreement |
|---|---|
| `banking/kyc-credential` | The graph splits it into onboarding and re-KYC, which have different interfaces. The family declares onboarding's, so `kyc-attestation-current` and the `customer-relationship-open` requirement are missing from it. |
| `education/certificates-and-enrolment` | The graph splits it into issuance and immatriculation. The family declares only `eid-held`, missing immatriculation's need for `secondary-education-credential-held`. |

Both are families bundling two flows with different interfaces. The education one
was already suspected; its own pull request raised the question of splitting it.
The banking one was not, and the comparison is what surfaced it.

A family whose flows have different preconditions cannot state one accurate
interface. "Do these flows share an interface?" is therefore a more precise test
of what belongs in a family than "do they share a trigger and a set of actors?"

## What belongs in the function layer

The first draft of this vocabulary covered only electronic-identity use cases —
proofing, onboarding, access. That is too narrow, and it presumes an answer to the
question of where credentials are useful.

A verifiable credential is a container for **any** signed, structured,
machine-checkable claim. Identity is the most familiar payload, and there are
many others: a test certificate, a customs declaration, a product conformity
statement, an emissions figure, a consent record and an invoice are all
structured assertions whose value comes from being checkable without contacting
the issuer. The function axis therefore covers every business function where a
checkable claim removes a phone call, a PDF or a trusted intermediary.

So the vocabulary deliberately spans more than it currently uses. It is wider
than the seeded use cases, and `validate.py` reports the unexercised ones as
coverage rather than as a problem.

Two rules keep it from sprawling:

- **A function names work; a credential type names a document.** "Diploma" is a
  credential and "certification and attestation" is the function that issues one.
  A proposed entry that names a document belongs in layer 4.
- **A function is sector-independent.** One that cannot be stated without naming
  an industry belongs in a use case instead.

Three entries are close together and worth telling apart: **quality assurance**
is checking your own output before it ships, **audit and assurance** is someone
independent checking it afterwards, and **certification and attestation** is
issuing the statement that results.

## Layer 4 — credential types

The blueprint this started from put a `requiresCredential` property on the use
case. That cannot express the ordinary case: inside one use case the school
issues a certificate and the university checks a different credential. So
credentials attach to a **participation** — to a party in a role — and each
party names what it handles:

```turtle
part:eid-issuance-issuer
    ifm:trustRole     role:issuer ;
    ifm:party         "Federal e-ID issuer"@en ;
    ifm:issuesCredential cred:eid-credential .
```

A party is not limited to one verb. The school that issues a school-leaving
certificate also verifies the graduate's e-ID, and both are recorded on its
participation.

A credential type **evidences a state**, which connects this layer to the rest:
holding the credential is the condition that satisfies the state, and states are
what use cases compose against. Credentials explain an existing composition
without altering it.

Recorded per type: the format, the ecosystem whose schemas apply, and the state
it evidences. The schemas themselves are not copied here; they belong to those
ecosystems. Every type is `provisional` — none has been checked against a
published schema registry.

Where the format and ecosystem values come from:

| Value | Basis |
|---|---|
| `SD-JWT VC` + `swiyu` | Read from the profile text. [Swiss Profile VC](https://swiyu-admin-ch.github.io/specifications/swiss-profile-vc/) contains SD-JWT VC Draft 15 over SD-JWT (RFC 9901); [Swiss Profile Issuance](https://swiyu-admin-ch.github.io/specifications/swiss-profile-issuance/) §3.3.1 states that the Credential Format Profiles "ISO mdoc" and "W3C VCDM" are **NOT SUPPORTED**. |
| `W3C VCDM 2.0` + `UN/CEFACT` | The UN Transparency Protocol states that its credentials, the Digital Conformity Credential among them, conform to W3C VCDM v2.0. |
| `W3C VCDM` + `ELM` | The European Learning Model extends the W3C data model. Which version the European Digital Credentials infrastructure requires is **not settled here**, so no version is recorded. |

The `age-attestation` type is worth reading before reusing it. SD-JWT discloses a
claim or withholds it and cannot prove a property of a withheld claim, so there
are no predicate proofs in this profile. Over-18 works in swiyu because the
electronic identity carries an `age_over_18` claim of its own that the holder can
disclose in place of the date of birth. That is a property of the credential's
claim set, not of the format. The profile itself treats it that way: `swiss-profile-vc`
§3.2.2.2 gives "Accepting a 'over 18' proof for a expired e-ID" as the example of
why a credential past its business `expiry_date` may still be worth accepting.

### Two checks that earn their place

**A state needing a credential nobody verifies.** If a use case requires a state,
and a credential type evidences that state, somebody in that use case should be
checking it. This found four use cases where I had recorded a precondition and
no corresponding verification.

**A credential no participation handles.** A type that nothing issues, presents or
verifies has probably been added speculatively. This found
`customer-relationship-attestation`, since removed: inside one bank an open
customer relationship is established from the bank's own records, with no
credential presented. Some states are established without a credential, and the
model allows for that.

### What this layer still does not carry

Credential *types* are here. Credential *schemas* are not, and adding them does
not disturb layers 1–3:

- an `ifm:CredentialSchema` class in its own file under `data/`, with the claim
  set each type carries;
- ecosystem-specific schema anchors alongside it (EBSI conformance frameworks
  for cross-sector governance, ELM for education and labour, UN/CEFACT or GS1
  for supply chain and trade), mapped the way the function alignments are — as
  mapping relations with a recorded `code_status`, not as a fork.

Until then the `format` and `ecosystem` columns say which schema family a type
should be resolved against, and nothing resolves it.

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
