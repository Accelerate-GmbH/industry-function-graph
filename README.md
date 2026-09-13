# industry-function-graph

A knowledge graph that answers one question: **which business function, in which
economic sector, does a given use case serve?**

The model is built for reuse. "Identity proofing" is the same function whether a
bank, a hospital or an employer performs it — only the regulation around it
differs. Keeping the function layer independent of the sector layer makes a
pattern worked out once in banking visible as a candidate for education, and the
matrix shows where those overlaps are.

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

## The layers

```
  [ 1. SECTOR ]                          [ 2. FUNCTION ]
  ISIC Rev. 5 (NACE Rev. 2.1 at          IFM function scheme,
  section and division level)            mapped to UN CBF / APQC PCF
        ^                                       ^
        | ifm:appliesToSector                   | ifm:executesFunction
        +-------------------+-------------------+
                            |
                   [ 3. USE CASE ]
                   ifm:UseCase — the intersection node
                            |
                            v
                   [ 4. CREDENTIAL ]
                   credential types, on a participation
```

Established classifications and standards are reused where they fit the model.
Local concepts are introduced explicitly where no suitable reusable vocabulary is
available, and are kept distinct from the external standards rather than folded
into them:

| Layer | Basis | How it is used here |
|---|---|---|
| 1 · Sector | ISIC Rev. 5, NACE Rev. 2.1 | `skos:ConceptScheme` with the official code in `skos:notation`. All 22 ISIC sections, plus the divisions and classes the use cases actually reach. |
| 2 · Function | IFM's own scheme, mapped to UNECE/Eurostat CBF and APQC PCF | A local function scheme related to both with SKOS mapping relations. Not a fork of either. |
| 2d · Value stream | ArchiMate `Value Stream` (concept); catalogue is IFM's own | The concept is ArchiMate's. The catalogue and the stage decomposition are this repository's editorial models — see [Value streams](#value-streams). |
| 3 · Use case | IFM's own class | The bridge: each use case links ≥1 sector and exactly one primary function. |
| 3a · Why and how far | IFM editorial vocabularies | Value drivers (what it reduces, removes or makes possible) and one transformation mode (how far the process is reorganised). |
| 3b · Who | IFM's own vocabularies | Trust roles, with who bears cost and who gains value; the mechanisms the use case reduces reliance on; which use cases must work first. |
| 3c · Interface | IFM's own vocabulary | Pre- and postconditions over a shared state vocabulary. Composition, unmet preconditions and duplicates are **derived** from these. |
| 4 · Credential | SD-JWT VC (swiyu), W3C VCDM (ELM, UN/CEFACT UNTP) | Credential types attached to a participation, each providing evidence for one state — see [Layer 4](#layer-4--credential-types). |

## Layout

```
industry-function-graph/
├── data/           the source of truth — CSV, hand-edited, reviewable in a diff
├── ontology/
│   ├── ifm.ttl          the vocabulary (hand-written, stable)
│   └── ifm-shapes.ttl   SHACL shapes for the principal RDF constraints
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

`validate.py` also checks that `generated/` still matches `data/`, so a local run
cannot pass while the published graph describes the previous data.

Two checks need optional packages and are skipped with a warning when they are
absent. With `rdflib` installed, `validate.py` parses the generated RDF and
checks that the Turtle and the JSON-LD are the same graph. With `pyshacl`
installed as well, it runs [`ontology/ifm-shapes.ttl`](./ontology/ifm-shapes.ttl)
over the generated graph.

```bash
pip install rdflib pyshacl
```

## The namespace

Concepts are minted under
`https://didas-swiss.github.io/industry-function-graph/`, the GitHub Pages
URL of this repository. Pages is enabled, so the matrix, the graph and the
ontology are all fetchable there; the individual concept IRIs
(`…/id/sector/ISIC-C`) are identifiers rather than dereferenceable documents,
which is workable for a vocabulary this size but is the thing a `w3id.org`
redirect would fix if these IRIs ever need to outlive this repository.

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

### ISIC Rev. 5 and NACE Rev. 2.1

NACE Rev. 2.1 is the European classification derived from ISIC Rev. 5. The
relationship this repository relies on is that **sections and divisions are
identical between the two**, and that NACE subdivides ISIC at group and class
level according to European requirements. That is why `ifm:naceRev21Code` is
asserted at section and division level only.

How far that has been verified here is set out under
[Provenance](#provenance). In short: it has **not** been read from the Eurostat
or UNSD publication, because neither is reachable from the environment this
repository is maintained in. What follows is a Swiss compatibility check, which
is corroboration rather than proof of the global relationship.

### Cross-check against NOGA 2025

The sector layer was checked against the NOGA 2025 subset codified in the
[DIDAS Trust Flow Diagram Repository](https://github.com/DIDAS-swiss/Trust-Flow-Diagram-Repository),
which classifies its flows by NOGA. Comparing the two:

- **22 of 22** section letters present in both, structurally identical
- **23 of 23** NOGA divisions sit under the same section in ISIC Rev. 5 — zero mismatches
- 3 section titles differ in spelling only ("organisations"/"organizations",
  "Telecommunication"/"Telecommunications", one `and` for a `;`)

NOGA 2025 is the Swiss implementation of NACE Rev. 2.1, so this is consistent
with NACE and ISIC agreeing at those two levels. It also means the **division
number is a usable join key** between this graph and any NOGA-classified sector,
which is the point of
[Trust-Flow-Diagram-Repository#12](https://github.com/DIDAS-swiss/Trust-Flow-Diagram-Repository/issues/12).

The three divisions absent from that NOGA subset (30, 56, 62) carry no NACE code
and say so in their `note`.

## Adding a use case

Edit CSVs, never `generated/`:

1. `data/use-cases.csv` — one row: id, name, description, transformation mode,
   maturity (`Exploratory` / `Modelled` / `Live`), `documented_by` (an absolute
   URL to wherever the use case is worked out in detail, empty if nowhere yet),
   and `deployment_evidence`, which `Live` requires.
2. `data/use-case-sectors.csv` — one row per sector. **Use the most specific
   ISIC concept that is actually warranted.** A use case that genuinely spans a
   whole section links to the section; it does not pick an arbitrary class
   inside it. If the sector you need is missing, add it to `data/sectors.csv`
   together with its parents.
3. `data/use-case-functions.csv` — one row per function, exactly one with
   `role=primary`. Reuse an existing function if one fits; a function that
   exists only to describe a single use case is a sign the function layer is
   drifting into the use case layer.
4. `data/use-case-participants.csv` — one row per participation, each with a
   `participation_id` unique within the use case. Where one organisation acts in
   two roles, give it **two participations**, not one participation doing two
   jobs.
5. `data/participation-credentials.csv` — what each participation does with which
   credential, keyed on `participation_id`.
6. Run `validate.py`, then `build.py`, and commit `data/` and `generated/`
   together.

### Reach across the classification is derived

A use case's reach is computed from the sectors it links, at each of the three
ISIC levels separately: `ifm:sectionScope`, `ifm:divisionScope` and
`ifm:classScope`. Nothing is typed in.

Three levels rather than one binary, because **"cross-sector" in ordinary usage
and "more than one ISIC section" are different claims**. Banking and insurance
are different industries, and both sit inside ISIC section L. Pharmaceutical and
aerospace manufacturing are different industries, and both sit inside section C.
Two of the use cases here show exactly that shape:

| Use case | Section | Division | Class |
|---|---|---|---|
| `banking-kyc-onboarding` (banking + insurance) | single | **cross** | **cross** |
| `supplier-qualification` (pharma + aerospace) | single | **cross** | **cross** |
| `employment-identity-proofing` (five sections) | **cross** | **cross** | **cross** |

A single "cross-sector" flag would have called the first two sector-specific,
which is the wrong answer to the question people are actually asking. The same
goes for the narrower/broader inverses and the matrix itself: anything derivable
is derived, so it cannot fall out of sync.

### The seeded use cases

The 12 use cases in `data/` are a worked seed, not a claim to completeness. Seven
are Swiss e-ID trust flows documented in the
[DIDAS Trust Flow Diagram Repository](https://github.com/DIDAS-swiss/Trust-Flow-Diagram-Repository)
— e-ID issuance, banking KYC onboarding and re-KYC, two banking
re-identifications, education credential issuance and university immatriculation.
The other five — age verification at the point of sale, employee identity
proofing, supplier qualification, patient identification and e-government service
access — are scoped but not yet worked out anywhere, and are marked
`Exploratory`. Replace or extend them freely; the sector and function layers do
not depend on them.

## Querying

The graph is plain SKOS plus this repository's own vocabulary, so any triple
store works — Apache Jena, GraphDB, or Neo4j with neosemantics
(`n10s.rdf.import.fetch`).

Which functions recur across sections (the reuse candidates):

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
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?name WHERE {
  ?useCase a ifm:UseCase ; rdfs:label ?name ; ifm:appliesToSector ?sector .
  ?sector skos:broader* ?section .
  ?section skos:notation "L" .
}
```

Who bears cost without direct value, and for which credential:

```sparql
SELECT ?useCase ?party ?role WHERE {
  ?useCase ifm:participation ?p .
  ?p ifm:bearsCost true ; ifm:gainsValue ?value ; ifm:party ?party ; ifm:trustRole ?r .
  ?r skos:prefLabel ?role .
  FILTER (?value != "direct")
}
```

## Provenance

The blueprint this follows sketches notations like `UN_CBF_F4`. Those are not
reproduced here, because they could not be checked against an official
publication — and a plausible-looking wrong code is worse than no code.

Two provenance questions are recorded separately, because they are separate
questions:

- **`ifm:codeStatus`** — has *this concept's* notation and label been checked
  against the publication of the classification it comes from? `verified` or
  `provisional`.
- **`ifm:mappingStatus`** — how was a *mapping* between an IFM concept and an
  external one arrived at? `editorial` (a modeller's judgement, with the
  reasoning on the row) or `verified` (taken from a published crosswalk).

A mapping onto a verified concept can still be editorial. Every mapping in
`data/function-alignments.csv` is currently `editorial`; that says nothing about
the CBF or APQC concepts themselves.

| Data | `codeStatus` | Basis |
|---|---|---|
| ISIC Rev. 5 sections, divisions, classes | `verified` | Codes and titles taken from the official ISIC Rev. 5 structure file published by the UN Statistics Division. |
| NACE Rev. 2.1 codes | — | Recorded as `ifm:naceRev21Code` literals at **section and division level only**, where NACE and ISIC are identical, and only for divisions the NOGA cross-check covers. Deliberately not asserted at class level, where the two diverge. |
| CBF categories | `provisional` | Category labels following the UNECE/Eurostat Classification of Business Functions. No notations are asserted. Replace with an official extract before relying on them. |
| APQC PCF categories | `provisional` | Only the cross-industry categories an alignment references, following the 13-category structure. The framework is published by APQC and is not redistributed here; get it from [apqc.org](https://www.apqc.org/process-frameworks). |
| Function alignments | `mappingStatus: editorial` | Recorded row by row in `data/function-alignments.csv` with the reasoning. |
| Credential types | `provisional` | None has been checked against a published schema registry. |

### What could not be verified from here

Three assertions in this repository rest on secondary material, because the
primary publications are not reachable from the environment it is maintained in.
They are listed so that anyone relying on them knows what to re-check:

| Assertion | Status |
|---|---|
| NACE Rev. 2.1 and ISIC Rev. 5 are identical at section and division level, and NACE subdivides ISIC below that | Consistent with the NOGA 2025 cross-check above and with secondary descriptions of Commission Delegated Regulation (EU) 2023/137. **Not** read from the Eurostat or UNSD publication: `ec.europa.eu`, `eur-lex.europa.eu` and `unstats.un.org` are all blocked by the network policy in use. |
| The CBF category labels carried here | Seeded, `provisional`. The publication to check them against is the UN *Manual on the Classification of Business Functions*, which could not be retrieved. |
| The APQC PCF release these category titles come from | The 13-category cross-industry structure is what the labels follow. The point release was **not** confirmed against the APQC publication, so `ifm:schemeVersion` records the structure rather than naming a release. |

Two modelling decisions follow from all of this:

**The function scheme is its own scheme, not a fork of CBF.** Use cases point at
`ifm-functions` concepts; those concepts point at CBF and APQC with SKOS mapping
relations. Correcting an alignment — or swapping CBF for something else entirely
— then touches one row of one CSV and no use case at all.

**CBF's core/support split is not asserted over the function layer.** In CBF,
whether an activity is a *core* or a *support* function depends on the
enterprise, not on the activity: issuing certificates is the core function of a
certification body and a support function of a manufacturer. Encoding that as a
context-free property of an IFM function would bake one enterprise's viewpoint
into the vocabulary. Two things follow:

- No IFM function is hung under `CBF-CORE` or `CBF-SUP` with `skos:broader`, and
  `validate.py` rejects a `broadMatch` or `narrowMatch` onto either.
- The CBF alignments that remain are `skos:relatedMatch` — an association, not a
  subsumption. `certification-and-attestation` previously carried
  `broadMatch CBF-CORE`; it has been removed rather than weakened, and that
  function now has no external alignment at all. `validate.py` reports it as an
  island, which is the honest state of it.

The one exception is `service-delivery → CBF-CORE`, kept as `skos:closeMatch`:
CBF defines the core function as producing the output the enterprise exists to
supply, which is how `service-delivery` is defined. *Whose* output it is still
varies by enterprise; the identity of the activity does not.

## Value streams

A function says what kind of work something is. It does not say where that work
sits in an end-to-end sequence — and "supplier qualification" reads differently
once you know it is positioned at the front of procure-to-pay.

The **concept** follows [ArchiMate's Value Stream
element](https://pubs.opengroup.org/architecture/archimate32-doc/) — *a sequence
of activities that create an overall result for a customer, stakeholder or end
user*, the **what** rather than the **how**. ArchiMate is an open standard for
expressing a value stream.

The **catalogue and the stage decomposition are this repository's editorial
models.** There is no openly licensed catalogue of value streams: APQC publishes
end-to-end process maps, including for procure-to-pay, under its own terms, and
the SAP naming is proprietary. So each entry here is one modelled sequence, not
the universal one for that stream — organisations decompose the same stream
differently, and the twelve stages below are not a claim about how procure-to-pay
must be broken down.

Streams **compose** functions, they do not contain them. One function appears in
several streams, so this is not a hierarchy over the function layer. Stages are
reified rather than listed, so each carries a position and its own label:

```
procure-to-pay (as modelled in this repository)
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

In this repository, supplier qualification is positioned at stage 1 of that
modelled procure-to-pay stream.

`ifm:position` is an **ordering and presentation hint only**. It does not assert
that a stage is mandatory, that it excludes the others in time, that it causally
depends on the one before it, or anything else about process control. Real stages
overlap, repeat and are skipped.

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
verifiable credential is worth applying there, or how far it reorganises the
process — and those are the questions someone deciding what to build asks. The
same function in the same sector can be a paper substitution in one instance and
a new operating model in another.

Both vocabularies below are **IFM editorial classifications**. Neither is taken
from, nor aligned to, an external standard.

**Value drivers** — what applying a credential reduces, removes or makes
possible. Several per use case, unranked:

| Driver | |
|---|---|
| `friction-reduction` | steps, waiting, re-keying or intermediaries removed from an exchange that already happens |
| `fraud-risk-reduction` | selected forms of forgery, tampering, impersonation or misrepresentation reduced through cryptographically verifiable evidence and governed trust relationships |
| `compliance-assurance` | evidence a supervisor will accept, produced as a by-product of the work rather than as a separate exercise |
| `data-quality` | transcription, reconciliation and staleness errors reduced, and machine-verifiable provenance and freshness enabled where the format and the issuer's practice support it |
| `data-minimisation` | disclosure limited to the attributes a defined interaction requires, where the format and the governance model support it |
| `reach-and-inclusion` | counterparties served who could not be before: remote, cross-border, or with no prior relationship |
| `new-revenue` | a chargeable service, market or pricing model that verifiable data is a precondition for |

Two of these are worth stating precisely, because the loose version is a claim
the technology does not support. `fraud-risk-reduction` is about *selected*
forms of fraud: a credential makes forging the evidence hard, and does nothing
about a truthful credential presented for a fraudulent purpose. And
`data-minimisation` limits disclosure to what an interaction requires — *which*
attributes it requires is a governance question, settled by rules and
supervision, not by the credential format.

**Transformation mode** — how far the process is reorganised. Exactly one per
use case, and the four split into *run* and *change*:

| Mode | | |
|---|---|---|
| `digitise` | **run** | the process keeps its shape; a paper artefact becomes a credential |
| `optimise` | **run** | steps, hand-offs or waiting removed, but recognisably the same process |
| `redesign` | **change** | materially reorganised around verifiable data, including changes to roles, sequence or information custody |
| `enable` | **change** | enables an activity or operating model that was previously impractical or uneconomic at the required level of trust |

`ifm:changeMode` is derived from the mode, never typed in.

The two halves are justified differently. *Run* is usually a business case: count
the steps removed. *Change* is a strategic decision, and may show a weak business
case until it works. Treating them alike tends to produce digitisation that
preserves the existing process — the PDF becomes a credential and the hand-offs
stay where they were.

It also measures coverage. `new-revenue` is claimed by no use case here, and only
one is classified `enable` — the rest improve or reorganise something
organisations already do. That reflects where the seeded use cases sit rather
than where the technology can go, and the validator reports it so the graph does
not imply a breadth it lacks.

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

### Evidence states and outcome states

States divide in two, and conflating them was a real defect in an earlier
version of this model:

- **`ifm:EvidenceState`** — a party is in possession of evidence. `eid-held`,
  `secondary-education-credential-held`, `supplier-accreditation-held`.
- **`ifm:OutcomeState`** — a business or administrative conclusion has been
  reached. `customer-relationship-open`, `supplier-qualified`,
  `patient-record-linked`, `service-entitlement-established`.

Holding evidence is not the same as a relying party having accepted it, and the
distinction matters at exactly the point where a credential is proposed as the
answer to a business question. Both kinds compose in the same way — the
distinction is about what a state asserts, not about how it is used — so the
chain above is unaffected.

It does change what belongs in the credential layer. An outcome state does not
need a credential to evidence it: `age-attribute-proven` and
`legal-capacity-established` are conclusions a relying party reaches from
verified attributes, and neither has a credential issued for the purpose. See
[Layer 4](#layer-4--credential-types).

### Three results the taxonomy alone does not give

**The chain** — above.

**Unmet preconditions.** A state that a use case requires and no use case here
leaves behind marks a flow that is outside this repository or has not been
written down. Finding them was how `eid-issuance` got into the graph: `eid-held`
was required by nine of the twelve use cases and produced by none of them.

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

One unmet precondition remains — `supplier-accreditation-held`, required by
supplier qualification and produced by nothing here. Accreditation bodies issuing
verifiable certificates is a flow nobody in this repository has written down, and
the credential layer reports the same gap from the other side:
`quality-accreditation-certificate` is presented and verified here but issued by
no use case.

**Duplicates.** Two use cases with the same precondition set, postcondition set
and primary function are, on the evidence, one use case. The check caught a pair
written separately here — `aerospace-supplier-onboarding` and
`pharma-supplier-qualification` had identical interfaces and differed only by
sector — and they were collapsed into one `supplier-qualification` that both
sectors instantiate. The sector-specific detail that mattered (GMP for
pharmaceuticals, quality accreditations for aerospace) survives as a note on the
verifying participation, which is where it belonged.

Its first run found a duplicate in the data of this repository itself.

### Why states are coarse

States are deliberately blunt — `secondary-education-credential-held` rather than
`gymnasiale-maturitaet-2026-held` — so that flows nobody has written yet can
connect to the same ones. A state used by a single use case connects nothing. As
new credentials arrive, they attach by matching an existing state, without the
vocabulary having to grow each time.

## Cost and value

Credential ecosystems commonly stall for a commercial reason: the party that must
invest in issuing is not the party that gets the value from verifying. Each use
case therefore records its participations — a party, a trust role, whether it
bears material cost, and whether it gains direct, indirect or no value.
`ifm:costValueAsymmetry` is derived from those, never typed in.

**It is an editorial heuristic, not an economic result.** It aggregates two
yes/no editorial judgements, carries no magnitude and no time profile, and
supports no inference about whether a use case will be adopted. What it is good
for is locating the places worth looking at.

On the twelve seeded use cases, three record a participation bearing cost without
direct value:

| Use case | Who, and in what role |
|---|---|
| `eid-issuance` | Federal e-ID issuer (issuer), Federal trust registry (trust anchor) |
| `education-maturitaetszeugnis-issuance` | Upper-secondary school (issuer) |
| `supplier-qualification` | Accreditation body (trust anchor) |

That figure was nine before this model was corrected, and the difference is
instructive. The earlier data recorded the federal e-ID issuer as a
cost-bearing participant in every use case that merely *verifies* an e-ID —
banking re-identification, age verification, patient identification. Its cost is
real, but it is incurred once, in `eid-issuance`, where it is now recorded. The
count was measuring how many use cases depend on the e-ID, not how many face a
funding problem of their own.

What remains is a shape worth noticing: the cost sits with issuers and trust
anchors, and in the two issuance cases the value falls to parties that verify
later. Where issuer and relying party are the same institution — a bank issuing a
KYC attestation it will re-verify, a public administration issuing entitlements
its own services accept — no asymmetry is recorded. Whether any of that predicts
adoption is a question for someone with cost figures, not for this graph.

## What the use case reduces reliance on

`friction-reduction` is the easiest driver to claim and the easiest to claim
emptily. Every use case that claims it must name the mechanism by which the same
assurance is obtained today — a paper document, a PDF, a phone call to the
issuer, an in-person visit, a notarised copy, a register lookup, a self-
declaration. The validator fails a use case that claims the driver and names
nothing, because a business case starts with the thing being displaced.

The relation is `ifm:reducesRelianceOn`, not "replaces", and the distinction is
deliberate. It says the parties need to lean on that mechanism less for the same
assurance. It does **not** say the mechanism leaves the architecture, that it is
inferior, or that it stops being available: a register queried less often is
still a register, and remains the authoritative source of what it holds. The
entries in `data/prior-evidence.csv` describe mechanisms and their properties
rather than ranking them — a signed PDF whose signature the verifier can check is
not the `pdf-attachment` mechanism at all.

## What must work first

`ifm:requiresUseCase` records dependencies between use cases, and the validator
rejects cycles. There is nothing to present until somebody issues, so these edges
are the sequencing information: university immatriculation cannot work before
schools issue, and employment qualification checks depend on awarding
institutions doing the same.

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

A third divergence is new and is this repository's doing: renaming
`customer-onboarding` to `relationship-onboarding` here means the two
repositories now name the same function differently, which `reconcile.py` reports
under the banking family. The rename is deliberate — see
[the rule an entry has to pass](#the-rule-an-entry-has-to-pass) — and the other
repository has not been changed to match.

A family whose flows have different preconditions cannot state one accurate
interface. "Do these flows share an interface?" is therefore a more precise test
of what belongs in a family than "do they share a trigger and a set of actors?"

## What belongs in the function layer

The first draft of this vocabulary covered only electronic-identity use cases —
proofing, onboarding, access. That is too narrow, and it presumes an answer to
the question of where credentials are useful.

A verifiable credential is a container for **any** signed, structured,
machine-checkable claim. Identity is the most familiar payload, and there are
many others: a test certificate, a customs declaration, a product conformity
statement, an emissions figure, a consent record and an invoice are all
structured assertions whose value comes from being checkable without contacting
the issuer. The function axis therefore covers every business function where a
checkable claim can displace a phone call, a PDF or a trusted intermediary.

So the vocabulary deliberately spans more than it currently uses. It is wider
than the seeded use cases, and `validate.py` reports the unexercised ones as
coverage rather than as a problem.

### The rule an entry has to pass

> A `BusinessFunction` is a **reusable category of work performed by an
> organisation**. It must not denote an industry, a department, an actor, a
> technology, a legal obligation or a desired outcome.

An entry that cannot be stated without naming one of those belongs in another
layer: an industry in the sector layer, an actor in a participation, a document
in the credential layer, an outcome in the state vocabulary.

Two entries failed that rule and were renamed:

| Was | Is | Why |
|---|---|---|
| `customer-onboarding` | `relationship-onboarding` | "Customer" is commercial. A university admitting a student and a public body enrolling a resident perform the same work, and neither has a customer. The commercial reading survives as `skos:altLabel` and as the APQC alignment. |
| `customer-service` | `request-and-complaint-handling` | A department name rather than a category of work. |

`regulatory-compliance` was kept but redefined: it now names the record-keeping,
control and reporting **work** that obligations require, rather than the
obligation or the state of being compliant.

Three entries are close together and worth telling apart: **quality assurance**
is checking your own output before it ships, **audit and assurance** is someone
independent checking it afterwards, and **certification and attestation** is
issuing the statement that results.

## Layer 4 — credential types

The blueprint this started from put a `requiresCredential` property on the use
case. That cannot express the ordinary case: inside one use case the school
issues a certificate and checks a different credential. So credentials attach to
a **participation** — to a party in a role — and each participation names what it
handles:

```turtle
part:eid-issuance-issuer
    ifm:trustRole        role:issuer ;
    ifm:party            "Federal e-ID issuer"@en ;
    ifm:issuesCredential cred:eid-credential .
```

### One role, one action

A participation performs only the credential action its trust role performs:

| Role | Credential actions |
|---|---|
| `issuer` | `issues` |
| `holder` | `holds`, `presents` |
| `verifier` | `verifies` |
| `relying-party` | none — it acts on the outcome of verification, not on the credential |
| `trust-anchor` | none — it provides the information verification rests on |

Where one organisation acts in two roles, that is **two participations**, not one
participation borrowing another role's verb. The school that issues a
school-leaving certificate also verifies the graduate's e-ID, and the model
records an issuing participation and a verifying participation, both with the
party "Upper-secondary school". A participation is therefore identified within
its use case (`participation_id`) rather than by its role.

`validate.py` enforces the table above, and
[`ontology/ifm-shapes.ttl`](./ontology/ifm-shapes.ttl) states the same rule in
SHACL so a consumer holding only the RDF can check it.

### Verifier and relying party are different roles

The **verifier** performs the technical checks on a presentation: signature,
issuer authority, status, holder binding, freshness. It establishes whether the
evidence is valid. The **relying party** acts on that outcome to reach a business
or administrative decision.

In every use case seeded here they are the same organisation, and they are still
recorded separately, because they can be separated — a shared verification
service, a verifier operated by a processor — and because they carry different
accountability. Conflating them makes it impossible to say which of the two a
requirement attaches to.

### The lifecycle, and covering only part of it

The four verbs mark the stages a use case covers: **issued → held → presented →
verified**. A use case may cover any subset. `eid-issuance` covers issuance and
the holder taking possession, and nothing else — no presentation and no
verification happen inside it, and modelling them there was a defect this pass
removed. `retail-hospitality-age-verification` covers presentation and
verification only.

`holds` marks the use case in which possession begins, which is the issuing one.
A holder presenting a credential it obtained elsewhere records `presents` alone.
The validator rejects half an exchange in either direction: a credential verified
but never presented, presented but never verified, issued but never held, or held
without being issued.

### What is a credential type, and what is not

A credential type is recorded only where something is **actually issued as a
separate artefact**. A claim inside another credential, a derived attribute or a
business conclusion is not one, and a state needing evidence is not on its own a
reason to invent a credential. Two entries failed that test and were removed:

| Removed | Why |
|---|---|
| `age-attestation` | Its own definition said no separate credential is issued. SD-JWT discloses a claim or withholds it and cannot prove a property of a withheld claim, so there are no predicate proofs in this profile. Over-18 works in swiyu because the electronic identity carries an `age_over_18` claim of its own that the holder discloses in place of the date of birth — a claim in the e-ID, not a credential. The profile treats it that way: `swiss-profile-vc` §3.2.2.2 gives "Accepting a 'over 18' proof for a expired e-ID" as its example of why a credential past its business `expiry_date` may still be worth accepting. |
| `legal-capacity-attestation` | A conclusion a relying party reaches from a verified date of birth, not an artefact anyone issues. The earlier data had the federal e-ID issuer issuing it to a bank's customer, which no party does. |

Both states they pointed at — `age-attribute-proven` and
`legal-capacity-established` — are now outcome states with no credential. Some
states are established without a credential, and the model allows for that.

### Evidence, not equivalence

A credential type **provides evidence for** a state (`ifm:evidences`). It does
not make the state true. Possession is not verification, verification is not
acceptance, and whether a relying party accepts the evidence is a governance
question this graph does not settle. The earlier wording — "holding the
credential satisfies the state" — asserted an equivalence that does not hold, and
it is what let an evidence state and an outcome state be treated alike.

### What is recorded per type

The single `ecosystem` column treated values that are not the same kind of thing
as peers — `swiyu` is a trust framework, `ELM` a semantic model, `UN/CEFACT` an
organisation and its protocol. Those are now separate properties, each recorded
only where it has been established:

| Property | What it says |
|---|---|
| `ifm:credentialFormat` | the wire format or representation — SD-JWT VC, W3C VCDM |
| `ifm:semanticModel` | the schema family that gives the claims their meaning — ELM, a UNTP credential type |
| `ifm:trustFramework` | the governance framework under which issuers are authorised — swiyu, UN/CEFACT's UN Transparency Protocol |
| `ifm:protocolProfile` | the issuance and presentation profile the credential is exchanged under, where an ecosystem names one |

So the electronic identity is `SD-JWT VC` in format, `swiyu` as trust framework,
and `swiss-profile-issuance:1.0.0, swiss-profile-verification:1.0.0` as protocol
profile — with **no semantic model recorded**, because the statute states the
content and this repository has not read a published claim schema. A school
certificate is `W3C VCDM` in format with `ELM` as its semantic model and **no
trust framework**, because none has been chosen. Leaving a property empty is the
point of splitting them.

Where the values come from:

| Value | Basis |
|---|---|
| `SD-JWT VC` + `swiyu` | Read from the profile text. [Swiss Profile VC](https://swiyu-admin-ch.github.io/specifications/swiss-profile-vc/) contains SD-JWT VC Draft 15 over SD-JWT (RFC 9901); [Swiss Profile Issuance](https://swiyu-admin-ch.github.io/specifications/swiss-profile-issuance/) §3.3.1 states that the Credential Format Profiles "ISO mdoc" and "W3C VCDM" are **NOT SUPPORTED**. |
| `W3C VCDM 2.0` + UNTP | The UN Transparency Protocol states that its credentials, the Digital Conformity Credential among them, conform to W3C VCDM v2.0. |
| `W3C VCDM` + `ELM` | The European Learning Model extends the W3C data model. Which version the European Digital Credentials infrastructure requires is **not settled here**, so no version is recorded. |

The `eid-credential` type is the one with a statute behind it: the Swiss E-ID Act
(BGEID) of 20 December 2024, BBl 2025 20, read from the Federal Gazette text. It
governs the federal trust infrastructure and the EID, and the attribute list in
the type's definition is Art. 15 para. 1 verbatim. Nothing in that Act decides
what any other credential type in this file may carry or who may ask for it —
Art. 23's proportionality duty on verifiers binds the EID alone. Where a type
here has a legal basis, it is a different statute and this repository has not
read it.

### Three checks that earn their place

**A precondition nobody checks.** If a use case requires a state, and a credential
type provides evidence for that state, somebody in that use case should be
verifying it. This found four use cases with a recorded precondition and no
corresponding verification.

**A credential nothing issues.** A type presented or verified here but issued by
no use case marks an issuing flow outside the repository or not yet written down.
`quality-accreditation-certificate` is the one that remains, and it agrees with
the unmet precondition `supplier-accreditation-held` — the same gap seen from two
sides.

**A credential no participation handles at all.** A type nothing issues, holds,
presents or verifies has probably been added speculatively. This found
`customer-relationship-attestation`, since removed: inside one bank an open
customer relationship is established from the bank's own records, with no
credential presented.

### What this layer still does not carry

Credential *types* are here. Credential *schemas* are not, and adding them does
not disturb layers 1–3:

- an `ifm:CredentialSchema` class in its own file under `data/`, with the claim
  set each type carries;
- ecosystem-specific schema anchors alongside it (EBSI conformance frameworks
  for cross-sector governance, ELM for education and labour, UN/CEFACT or GS1
  for supply chain and trade), mapped the way the function alignments are — as
  mapping relations with a recorded status, not as a fork.

Until then the format, semantic model and trust framework columns say which
schema family a type should be resolved against, and nothing resolves it.

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
