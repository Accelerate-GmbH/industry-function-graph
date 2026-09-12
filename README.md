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
