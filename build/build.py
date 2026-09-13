#!/usr/bin/env python3
"""Generate the Industry-Function Mapping knowledge graph and its matrix views.

    python3 build/build.py            # write generated/
    python3 build/build.py --check    # fail if generated/ is stale (used in CI)

Inputs are the CSVs in data/; nothing in generated/ should ever be hand-edited.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model import BASE, GENERATED_DIR, ID_BASE, ONT, SCHEMES, Model  # noqa: E402

MASTHEAD_SCRIPT = '''<script>
/* Shared DIDAS masthead controls — colour theme, layout width and text size.
   The same three the glossary carries, reading and writing the same
   localStorage keys. All four DIDAS sites are served from
   didas-swiss.github.io, so a preference set on any one of them is the
   preference on all of them. Keep this block identical across the sites. */
(function () {
  var root = document.documentElement;
  var KEY = {
    theme: 'theme',                        /* 'light' | 'dark' | 'auto'        */
    width: 'container_width_preference',   /* 'container' | 'container-fluid'  */
    font: 'font_size_preference'           /* a root font size, in px          */
  };
  var WIDE = 'container-fluid';
  var FONT = { base: 16, min: 13, max: 22, step: 1 };

  function read(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }
  function write(key, value) {
    /* Private browsing and blocked site data both throw here; the controls
       still work for the session, they just do not persist. */
    try { window.localStorage.setItem(key, value); } catch (e) { /* ignore */ }
  }

  function theme() {
    var v = read(KEY.theme);
    return v === 'light' || v === 'dark' ? v : 'auto';
  }
  function width() { return read(KEY.width) === WIDE ? WIDE : 'container'; }
  function font() {
    var v = parseFloat(read(KEY.font));
    return v >= FONT.min && v <= FONT.max ? v : FONT.base;
  }

  function apply() {
    var t = theme();
    /* No attribute means follow the operating system, which is what the
       prefers-color-scheme block in the stylesheet keys off. */
    if (t === 'auto') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', t);
    root.setAttribute('data-width', width() === WIDE ? 'wide' : 'narrow');
    root.style.fontSize = font() + 'px';
  }

  function sync() {
    var t = theme();
    var wide = width() === WIDE;
    document.querySelectorAll('[data-theme-value]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-theme-value') === t));
    });
    document.querySelectorAll('[data-width-value]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(wide));
    });
  }

  function wire() {
    document.querySelectorAll('[data-theme-value]').forEach(function (b) {
      b.addEventListener('click', function () {
        write(KEY.theme, b.getAttribute('data-theme-value'));
        apply();
        sync();
      });
    });
    document.querySelectorAll('[data-width-value]').forEach(function (b) {
      b.addEventListener('click', function () {
        write(KEY.width, width() === WIDE ? 'container' : WIDE);
        apply();
        sync();
      });
    });
    document.querySelectorAll('[data-font-step]').forEach(function (b) {
      b.addEventListener('click', function () {
        var next = font() + FONT.step * Number(b.getAttribute('data-font-step'));
        write(KEY.font, String(Math.min(FONT.max, Math.max(FONT.min, next))));
        apply();
      });
    });
    sync();
  }

  apply();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire, { once: true });
  } else {
    wire();
  }
})();
</script>'''

XSD_IRI = "http://www.w3.org/2001/XMLSchema#"

PREFIXES = [
    ("ifm", ONT),
    ("scheme", ID_BASE + "scheme/"),
    # Classification
    ("sector", ID_BASE + "sector/"),
    ("func", ID_BASE + "function/"),
    ("cbf", ID_BASE + "cbf/"),
    ("apqc", ID_BASE + "apqc/"),
    ("stream", ID_BASE + "value-stream/"),
    ("stage", ID_BASE + "value-stream-stage/"),
    ("uc", ID_BASE + "use-case/"),
    # Interface
    ("cond", ID_BASE + "condition/"),
    ("req", ID_BASE + "requirement/"),
    ("prov", ID_BASE + "provision/"),
    ("srole", ID_BASE + "subject-role/"),
    # Realisation
    ("flow", ID_BASE + "flow/"),
    ("part", ID_BASE + "participation/"),
    ("cred", ID_BASE + "credential-type/"),
    ("role", ID_BASE + "trust-role/"),
    # Decision support
    ("driver", ID_BASE + "value-driver/"),
    ("mode", ID_BASE + "transformation-mode/"),
    ("prior", ID_BASE + "prior-evidence/"),
    ("skos", "http://www.w3.org/2004/02/skos/core#"),
    ("dct", "http://purl.org/dc/terms/"),
    ("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
    ("owl", "http://www.w3.org/2002/07/owl#"),
    ("xsd", "http://www.w3.org/2001/XMLSchema#"),
]


# --------------------------------------------------------------------------
# One graph, two serialisations
#
# The blocks below are the single source of truth for both ifm-graph.ttl and
# ifm-graph.jsonld, so the two files can never drift apart. A block is
# (subject, [(predicate, [object, ...]), ...]); objects are Ref or Lit.
# --------------------------------------------------------------------------

class Ref(str):
    """A prefixed name (sector:ISIC-C) or an absolute IRI (<https://...>)."""


class Lit:
    def __init__(self, value, lang="en", datatype=None):
        self.value = str(value)
        # A datatype and a language tag are mutually exclusive in RDF.
        self.lang = None if datatype else lang
        self.datatype = datatype

    def turtle(self):
        text = (self.value.replace("\\", "\\\\").replace('"', '\\"')
                .replace("\n", "\\n").replace("\r", ""))
        if self.datatype:
            return f'"{text}"^^{self.datatype}'
        return f'"{text}"@{self.lang}' if self.lang else f'"{text}"'


def L(value, lang="en"):
    return [Lit(value, lang)] if value else []


def R(ref):
    return [Ref(ref)] if ref else []


# Turtle prefixed names cannot contain "/", so each layer gets its own prefix
# rather than one namespace with slash-separated local names.
PREFIX_OF_KIND = {
    # Classification
    "sector": "sector",
    "function": "func",
    "cbf": "cbf",
    "apqc": "apqc",
    "stream": "stream",
    "stage": "stage",
    "use-case": "uc",
    # Interface
    "condition": "cond",
    "requirement": "req",
    "provision": "prov",
    "subject-role": "srole",
    # Realisation
    "flow": "flow",
    "participation": "part",
    "credential": "cred",
    "role": "role",
    # Decision support
    "driver": "driver",
    "mode": "mode",
    "prior-evidence": "prior",
}


def scheme_iri(scheme_id):
    return f"scheme:{scheme_id}"


def concept_ref(kind, ident):
    return f"{PREFIX_OF_KIND[kind]}:{ident}"


# The four stages of the credential lifecycle a participation can cover.
ACTION_PROPERTY = {
    "issues": "ifm:issuesCredential",
    "holds": "ifm:holdsCredential",
    "presents": "ifm:presentsCredential",
    "verifies": "ifm:verifiesCredential",
}

# Evidence, fact, outcome and relationship conditions are all ifm:Condition
# subclasses, so composition is unaffected by which one a condition is. The
# distinction records what a condition asserts: holding evidence is not the
# same as a relying party having established something on it.
CONDITION_CLASS = {
    "evidence": "ifm:EvidenceCondition",
    "fact": "ifm:FactCondition",
    "outcome": "ifm:OutcomeCondition",
    "relationship": "ifm:RelationshipCondition",
}


def by_action(model, flow_id, participation_id):
    """{predicate: [credential ids]} for one participation.

    Grouped by predicate because a party can verify two credentials. Two pairs
    sharing a predicate serialise differently in Turtle and JSON-LD.
    """
    grouped: dict[str, list[str]] = {}
    for link in model.credentials_of.get((flow_id, participation_id), []):
        grouped.setdefault(ACTION_PROPERTY[link["action"]], []).append(
            link["credential_type_id"])
    return grouped


def interface_point(model, kind, ident, row, blocks, heading, is_provision):
    """Emit one reified ifm:Requirement or ifm:Provision.

    Reified rather than a bare condition link so an interface point can also
    carry the subject role, a specific evidence type and context constraints -
    none of them mandatory.
    """
    pairs = [
        ("a", R("ifm:Provision" if is_provision else "ifm:Requirement")),
        ("ifm:condition", R(concept_ref("condition", row["condition_id"]))),
        ("ifm:subjectRole", R(concept_ref("subject-role", row["subject_role"]))
         if row.get("subject_role", "").strip() else []),
        ("ifm:evidenceType", R(concept_ref("credential", row["evidence_type"]))
         if row.get("evidence_type", "").strip() else []),
        ("ifm:contextConstraint", L(row.get("context", "").strip(), lang=None)),
        ("skos:scopeNote", L(row.get("note", ""))),
    ]
    if is_provision:
        pairs.insert(2, ("ifm:principalOutcome",
                         [Lit("true", datatype="xsd:boolean")]
                         if row.get("principal") == "yes" else []))
    blocks.append((heading, Ref(concept_ref(kind, ident)), pairs))


def graph_blocks(model):
    """Yield (heading, subject, pairs) for every node in the graph."""
    blocks = []

    blocks.append(("Concept schemes", Ref(f"<{BASE}>"), [
        ("a", R("owl:Ontology")),
        ("owl:imports", R(f"<{BASE}ontology>")),
        ("dct:title", L("Industry-Function Mapping graph")),
        ("dct:creator", L("Daniel Saeuberli", lang=None)),
        ("dct:license", R("<https://creativecommons.org/licenses/by/4.0/>")),
    ]))
    for scheme_id, meta in SCHEMES.items():
        blocks.append(("Concept schemes", Ref(scheme_iri(scheme_id)), [
            ("a", R("skos:ConceptScheme")),
            ("dct:title", L(meta["title"])),
            ("dct:description", L(meta["description"])),
            ("ifm:schemeVersion", L(meta["version"], lang=None)
             if meta.get("version") else []),
            ("dct:source", R(f"<{meta['source']}>")),
        ]))

    # ---------------------------------------------------------------
    heading = "Classification - Sectors (ISIC Rev. 5)"
    for sector_id, row in model.sectors.items():
        narrower = [Ref(concept_ref("sector", other_id))
                    for other_id, other in model.sectors.items()
                    if other["broader"] == sector_id]
        blocks.append((heading, Ref(concept_ref("sector", sector_id)), [
            ("a", [Ref("ifm:Sector"), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("isic-rev5"))),
            ("skos:topConceptOf", R(scheme_iri("isic-rev5")) if not row["broader"] else []),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:notation", L(row["notation"], lang=None)),
            ("skos:broader", R(concept_ref("sector", row["broader"])) if row["broader"] else []),
            ("skos:narrower", narrower),
            ("ifm:naceRev21Code", L(row["nace_rev21"], lang=None)),
            ("ifm:codeStatus", L(row["code_status"], lang=None)),
            ("skos:scopeNote", L(row["note"])),
        ]))

    heading = "Classification - CBF categories (mapping target)"
    for cbf_id, row in model.cbf.items():
        blocks.append((heading, Ref(concept_ref("cbf", cbf_id)), [
            ("a", R("skos:Concept")),
            ("skos:inScheme", R(scheme_iri("cbf"))),
            ("skos:topConceptOf", R(scheme_iri("cbf")) if not row["broader"] else []),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:broader", R(concept_ref("cbf", row["broader"])) if row["broader"] else []),
            ("skos:definition", L(row["definition"])),
            ("ifm:codeStatus", L(row["code_status"], lang=None)),
        ]))

    heading = "Classification - APQC PCF categories (mapping target)"
    for apqc_id, row in model.apqc.items():
        blocks.append((heading, Ref(concept_ref("apqc", apqc_id)), [
            ("a", R("skos:Concept")),
            ("skos:inScheme", R(scheme_iri("apqc-pcf"))),
            ("skos:topConceptOf", R(scheme_iri("apqc-pcf"))),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:notation", L(row["notation"], lang=None)),
            ("ifm:codeStatus", L(row["code_status"], lang=None)),
            ("skos:scopeNote", L(row["note"])),
        ]))

    heading = "Classification - Business functions (+ alignments)"
    kind_of_scheme = {"cbf": "cbf", "apqc-pcf": "apqc"}
    for function_id, row in model.functions.items():
        matches, notes, statuses = {}, [], set()
        for alignment in model.alignments:
            if alignment["function_id"] != function_id:
                continue
            ref = Ref(concept_ref(kind_of_scheme[alignment["target_scheme"]],
                                  alignment["target_id"]))
            matches.setdefault(f"skos:{alignment['match_type']}", []).append(ref)
            notes += L(alignment["note"])
            statuses.add(alignment["mapping_status"])
        narrower = [Ref(concept_ref("function", other_id))
                    for other_id, other in model.functions.items()
                    if other["broader"] == function_id]
        pairs = [
            ("a", [Ref("ifm:BusinessFunction"), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-functions"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-functions")) if not row["broader"] else []),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:altLabel", [Lit(alt.strip()) for alt in row["also_known_as"].split(";")
                               if alt.strip()]),
            ("skos:definition", L(row["definition"])),
            ("skos:broader", R(concept_ref("function", row["broader"])) if row["broader"] else []),
            ("skos:narrower", narrower),
        ]
        for match_type in ("skos:exactMatch", "skos:closeMatch", "skos:broadMatch",
                           "skos:narrowMatch", "skos:relatedMatch"):
            pairs.append((match_type, matches.get(match_type, [])))
        pairs.append(("ifm:mappingStatus",
                      [Lit(s, lang=None) for s in sorted(statuses)]))
        pairs.append(("skos:editorialNote", notes))
        blocks.append((heading, Ref(concept_ref("function", function_id)), pairs))

    # ---------------------------------------------------------------
    heading = "Interface - Conditions (the subsumption lattice)"
    for condition_id, row in model.conditions.items():
        narrower = [Ref(concept_ref("condition", other_id))
                    for other_id, other in model.conditions.items()
                    if other["broader"] == condition_id]
        blocks.append((heading, Ref(concept_ref("condition", condition_id)), [
            ("a", [Ref(CONDITION_CLASS[row["kind"]]), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-conditions"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-conditions")) if not row["broader"] else []),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:definition", L(row["definition"])),
            ("skos:broader", R(concept_ref("condition", row["broader"]))
             if row["broader"] else []),
            ("skos:narrower", narrower),
            ("ifm:substantiatedBy", [Ref(concept_ref("credential", c))
                                     for c in model.substantiated_by.get(condition_id, [])]),
        ]))

    heading = "Interface - Subject roles"
    for role_id, row in model.subject_roles.items():
        blocks.append((heading, Ref(concept_ref("subject-role", role_id)), [
            ("a", [Ref("ifm:SubjectRole"), Ref("skos:Concept")]),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:definition", L(row["definition"])),
        ]))

    heading = "Interface - Requirements and provisions"
    for row in model.uc_requires:
        interface_point(model, "requirement",
                        f"{row['use_case_id']}-{row['requirement_id']}", row,
                        blocks, heading, is_provision=False)
    for row in model.uc_provides:
        interface_point(model, "provision",
                        f"{row['use_case_id']}-{row['provision_id']}", row,
                        blocks, heading, is_provision=True)
    for row in model.stage_requires:
        interface_point(model, "requirement",
                        f"stage-{row['value_stream_id']}-{row['stage_id']}-{row['condition_id']}",
                        row, blocks, heading, is_provision=False)
    for row in model.stage_provides:
        interface_point(model, "provision",
                        f"stage-{row['value_stream_id']}-{row['stage_id']}-{row['condition_id']}",
                        row, blocks, heading, is_provision=True)
    for row in model.stream_requires:
        interface_point(model, "requirement",
                        f"stream-{row['value_stream_id']}-{row['condition_id']}",
                        row, blocks, heading, is_provision=False)
    for row in model.stream_provides:
        interface_point(model, "provision",
                        f"stream-{row['value_stream_id']}-{row['condition_id']}",
                        row, blocks, heading, is_provision=True)

    # ---------------------------------------------------------------
    heading = "Classification - Value streams as composition templates"
    for stream_id, row in model.value_streams.items():
        stages = model.stages_of[stream_id]
        blocks.append((heading, Ref(concept_ref("stream", stream_id)), [
            ("a", [Ref("ifm:ValueStream"), Ref("ifm:ComposableElement"),
                   Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-value-streams"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-value-streams"))),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:altLabel", [Lit(alt.strip()) for alt in row["also_known_as"].split(";")
                               if alt.strip()]),
            ("skos:definition", L(row["definition"])),
            ("ifm:codeStatus", L(row["code_status"], lang=None)),
            ("ifm:hasStage", [Ref(concept_ref("stage", f"{stream_id}-{st['stage_id']}"))
                              for st in stages]),
            ("ifm:requires", [Ref(concept_ref(
                "requirement", f"stream-{stream_id}-{r['condition_id']}"))
                for r in model.stream_requires if r["value_stream_id"] == stream_id]),
            ("ifm:provides", [Ref(concept_ref(
                "provision", f"stream-{stream_id}-{r['condition_id']}"))
                for r in model.stream_provides if r["value_stream_id"] == stream_id]),
        ]))
        for stage in stages:
            stage_id = stage["stage_id"]
            realised = [uc for uc, pairs in model.stages_realised_by.items()
                        if (stream_id, stage_id) in pairs]
            blocks.append((heading, Ref(concept_ref(
                "stage", f"{stream_id}-{stage_id}")), [
                ("a", [Ref("ifm:ValueStreamStage"), Ref("ifm:ComposableElement")]),
                ("ifm:inValueStream", R(concept_ref("stream", stream_id))),
                ("ifm:position", [Lit(int(stage["position"]), datatype="xsd:integer")]),
                ("rdfs:label", L(stage["stage_label"])),
                ("ifm:stageFunction", R(concept_ref("function", stage["function_id"]))),
                ("ifm:requires", [Ref(concept_ref(
                    "requirement", f"stage-{stream_id}-{stage_id}-{r['condition_id']}"))
                    for r in model.stage_requires
                    if r["value_stream_id"] == stream_id and r["stage_id"] == stage_id]),
                ("ifm:provides", [Ref(concept_ref(
                    "provision", f"stage-{stream_id}-{stage_id}-{r['condition_id']}"))
                    for r in model.stage_provides
                    if r["value_stream_id"] == stream_id and r["stage_id"] == stage_id]),
                ("ifm:realisedBy", [Ref(concept_ref("use-case", uc)) for uc in realised]),
                ("skos:scopeNote", L(stage["note"])),
            ]))

    # ---------------------------------------------------------------
    heading = "Use case patterns (classification + interface)"
    for uc_id, row in model.use_cases.items():
        primary = model.primary_function(uc_id)
        supporting = [r["function_id"] for r in model.functions_of[uc_id]
                      if r["role"] != "primary"]
        blocks.append((heading, Ref(concept_ref("use-case", uc_id)), [
            ("a", [Ref("ifm:UseCasePattern"), Ref("ifm:ComposableElement")]),
            ("rdfs:label", L(row["name"])),
            ("dct:description", L(row["description"])),
            # -- classification
            ("ifm:appliesToSector", [Ref(concept_ref("sector", s))
                                     for s in model.sectors_of[uc_id]]),
            ("ifm:primaryFunction", R(concept_ref("function", primary)) if primary else []),
            ("ifm:executesFunction", [Ref(concept_ref("function", f)) for f in supporting]),
            ("ifm:realisesStage", [Ref(concept_ref("stage", f"{vs}-{st}"))
                                   for vs, st in model.stages_realised_by[uc_id]]),
            ("ifm:sectionScope", R(f"ifm:{model.scope_of(uc_id, 'section')}")),
            ("ifm:divisionScope", R(f"ifm:{model.scope_of(uc_id, 'division')}")),
            ("ifm:classScope", R(f"ifm:{model.scope_of(uc_id, 'class')}")),
            # -- interface
            ("ifm:requires", [Ref(concept_ref("requirement", f"{uc_id}-{r['requirement_id']}"))
                              for r in model.requires_of[uc_id]]),
            ("ifm:provides", [Ref(concept_ref("provision", f"{uc_id}-{p['provision_id']}"))
                              for p in model.provides_of[uc_id]]),
            ("ifm:enables", [Ref(concept_ref("use-case", other))
                             for other in model.enables(uc_id)]),
            ("ifm:requiresUseCase", [Ref(concept_ref("use-case", r))
                                     for r in model.depends_on[uc_id]]),
            # -- realisation
            ("ifm:realisedBy", [Ref(concept_ref("flow", f))
                                for f in model.flows_of_use_case(uc_id)]),
            # -- decision support
            ("ifm:valueDriver", [Ref(concept_ref("driver", d))
                                 for d in model.value_drivers_of[uc_id]]),
            ("ifm:reducesRelianceOn", [Ref(concept_ref("prior-evidence", e))
                                       for e in model.prior_evidence_of[uc_id]]),
            ("ifm:transformationMode", R(concept_ref("mode", row["transformation_mode"]))),
            ("ifm:changeMode", R(f"ifm:{(model.change_mode_of(uc_id) or '').capitalize()}")),
            ("skos:scopeNote", L(row["note"])),
        ]))

    # ---------------------------------------------------------------
    heading = "Realisation - Flows (real implementations)"
    for flow_id, row in model.flows.items():
        documentation = model.documentation_iri(flow_id)
        deployment = row["deployment_evidence"].strip()
        blocks.append((heading, Ref(concept_ref("flow", flow_id)), [
            ("a", R("ifm:Flow")),
            ("rdfs:label", L(row["name"])),
            ("dct:description", L(row["description"])),
            ("ifm:realisesUseCase", [Ref(concept_ref("use-case", uc))
                                     for uc in model.realises_of[flow_id]]),
            ("ifm:sectorContext", R(concept_ref("sector", row["sector_id"]))
             if row["sector_id"].strip() else []),
            ("ifm:jurisdiction", L(row["jurisdiction"], lang=None)),
            ("ifm:governanceReference", L(row["governance_ref"])),
            ("ifm:participation", [Ref(concept_ref(
                "participation", f"{flow_id}-{p['participation_id']}"))
                for p in model.participants_of[flow_id]]),
            ("ifm:costValueAsymmetry", [Lit(
                "true" if model.is_asymmetric(flow_id) else "false",
                datatype="xsd:boolean")]),
            ("ifm:maturity", R(f"ifm:{row['maturity']}")),
            ("ifm:documentedBy", R(f"<{documentation}>") if documentation else []),
            ("ifm:deploymentEvidence", R(f"<{deployment}>") if deployment else []),
            ("skos:scopeNote", L(row["note"])),
        ]))
    for row in model.flow_participants:
        ident = f"{row['flow_id']}-{row['participation_id']}"
        blocks.append((heading, Ref(concept_ref("participation", ident)), [
            ("a", R("ifm:Participation")),
            ("ifm:inFlow", R(concept_ref("flow", row["flow_id"]))),
            ("ifm:trustRole", R(concept_ref("role", row["role_id"]))),
            ("ifm:party", L(row["party"])),
            ("ifm:bearsCost", [Lit("true" if row["bears_cost"] == "yes" else "false",
                                   datatype="xsd:boolean")]),
            ("ifm:gainsValue", L(row["gains_value"], lang=None)),
            ("skos:scopeNote", L(row["note"])),
        ] + [
            (prop, [Ref(concept_ref("credential", cred)) for cred in creds])
            for prop, creds in sorted(
                by_action(model, row["flow_id"], row["participation_id"]).items())
        ]))

    heading = "Realisation - Credential types and trust roles"
    for cred_id, row in model.credential_types.items():
        blocks.append((heading, Ref(concept_ref("credential", cred_id)), [
            ("a", [Ref("ifm:CredentialType"), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-credential-types"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-credential-types"))),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:definition", L(row["definition"])),
            ("ifm:substantiates", [Ref(concept_ref("condition", link["condition_id"]))
                                   for link in model.substantiates.get(cred_id, [])]),
            ("ifm:credentialFormat", L(row["format"], lang=None)),
            ("ifm:semanticModel", L(row["semantic_model"], lang=None)),
            ("ifm:trustFramework", L(row["trust_framework"], lang=None)),
            ("ifm:protocolProfile", L(row["protocol_profile"], lang=None)),
            ("ifm:codeStatus", L(row["code_status"], lang=None)),
        ]))
    for role_id, row in model.trust_roles.items():
        blocks.append((heading, Ref(concept_ref("role", role_id)), [
            ("a", [Ref("ifm:TrustRole"), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-trust-roles"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-trust-roles"))),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:definition", L(row["definition"])),
        ]))

    # ---------------------------------------------------------------
    heading = "Decision support - drivers, modes, prior evidence"
    for driver_id, row in model.value_drivers.items():
        blocks.append((heading, Ref(concept_ref("driver", driver_id)), [
            ("a", [Ref("ifm:ValueDriver"), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-value-drivers"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-value-drivers"))),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:definition", L(row["definition"])),
        ]))
    for mode_id, row in model.modes.items():
        blocks.append((heading, Ref(concept_ref("mode", mode_id)), [
            ("a", [Ref("ifm:TransformationMode"), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-transformation-modes"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-transformation-modes"))),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:definition", L(row["definition"])),
            ("ifm:changeMode", R(f"ifm:{row['change_mode'].capitalize()}")),
        ]))
    for mechanism_id, row in model.prior_evidence.items():
        blocks.append((heading, Ref(concept_ref("prior-evidence", mechanism_id)), [
            ("a", [Ref("ifm:PriorEvidenceMechanism"), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-prior-evidence"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-prior-evidence"))),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:definition", L(row["definition"])),
        ]))

    # Derived satisfaction edges, the machine-readable form of "these two
    # compose". Emitted last because they are computed from everything above.
    heading = "Derived - which provisions satisfy which requirements"
    for uc_id in model.use_cases:
        for provision in model.provides_of[uc_id]:
            met = []
            for other in model.use_cases:
                if other == uc_id:
                    continue
                for requirement in model.requires_of[other]:
                    if model.satisfies(provision, requirement):
                        met.append(Ref(concept_ref(
                            "requirement", f"{other}-{requirement['requirement_id']}")))
            if met:
                blocks.append((heading, Ref(concept_ref(
                    "provision", f"{uc_id}-{provision['provision_id']}")),
                    [("ifm:satisfies", met)]))

    return blocks


def build_turtle(model):
    blocks = graph_blocks(model)
    out = [
        "# Industry-Function Mapping - generated knowledge graph.",
        "# DO NOT EDIT: regenerate with `python3 build/build.py` from data/*.csv.",
        f"# {len(model.use_cases)} use cases, {len(model.sectors)} sector concepts, "
        f"{len(model.functions)} function concepts.",
        "# SPDX-License-Identifier: CC-BY-4.0",
        "",
    ]
    out += [f"@prefix {prefix}: <{uri}> ." for prefix, uri in PREFIXES]
    out.append("")

    current_heading = None
    for heading, subject, pairs in blocks:
        if heading != current_heading:
            current_heading = heading
            out += ["#" * 70, f"# {heading}", "#" * 70, ""]
        kept = [(predicate, objects) for predicate, objects in pairs if objects]
        lines = [str(subject)]
        for index, (predicate, objects) in enumerate(kept):
            rendered = ", ".join(o if isinstance(o, Ref) else o.turtle() for o in objects)
            terminator = " ;" if index < len(kept) - 1 else " ."
            lines.append(f"    {predicate} {rendered}{terminator}")
        out.append("\n".join(lines))
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def build_jsonld(model):
    """Expanded-by-prefix JSON-LD: same triples as the Turtle, key for key."""
    context = {prefix: uri for prefix, uri in PREFIXES}
    context["@vocab"] = ONT

    nodes = []
    for _heading, subject, pairs in graph_blocks(model):
        subject_id = str(subject)
        if subject_id.startswith("<"):
            subject_id = subject_id[1:-1]
        node = {"@id": subject_id}
        for predicate, objects in pairs:
            if not objects:
                continue
            key = "@type" if predicate == "a" else predicate
            values = []
            for obj in objects:
                if isinstance(obj, Ref):
                    ref = str(obj)
                    ref = ref[1:-1] if ref.startswith("<") else ref
                    values.append(ref if key == "@type" else {"@id": ref})
                elif obj.datatype:
                    values.append({"@value": obj.value,
                                   "@type": XSD_IRI + obj.datatype.split(":", 1)[1]})
                elif obj.lang:
                    values.append({"@value": obj.value, "@language": obj.lang})
                else:
                    values.append({"@value": obj.value})
            node[key] = values[0] if len(values) == 1 and key != "@type" else values
        nodes.append(node)

    return json.dumps({"@context": context, "@graph": nodes}, indent=2,
                      ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------
# Matrix views
# --------------------------------------------------------------------------

def scope_phrase(model, uc_id):
    """Reach at all three ISIC levels, as one readable phrase.

    Reported per level because "cross-sector" in ordinary usage and "more than
    one ISIC section" are different claims. Only the finest level that is still
    single is named, since cross at one level implies cross at every coarser one.
    """
    words = {"CrossSection": "cross-section", "SingleSection": "single section",
             "CrossDivision": "cross-division", "SingleDivision": "single division",
             "CrossClass": "cross-class", "SingleClass": "single class"}
    return " · ".join(words[model.scope_of(uc_id, level)]
                      for level in ("section", "division", "class"))


def matrix_rows(model):
    sections = model.used_sections()
    functions = model.used_functions()
    grid = {}
    for section in sections:
        for function in functions:
            primary = model.cell(section, function, role="primary")
            supporting = [uc for uc in model.cell(section, function) if uc not in primary]
            grid[(section, function)] = (primary, supporting)
    return sections, functions, grid


def build_matrix_md(model):
    sections, functions, grid = matrix_rows(model)
    lines = [
        "<!-- DO NOT EDIT: generated by build/build.py -->",
        "# Sector x function matrix",
        "",
        "Rows are ISIC Rev. 5 sections, columns are business functions. "
        "`#` marks a use case where the function is the primary one, "
        "`.` marks a supporting function.",
        "",
    ]
    header = "| Sector | " + " | ".join(
        f"{model.label('function', f)}" for f in functions) + " |"
    lines.append(header)
    lines.append("|---|" + "---|" * len(functions))
    for section in sections:
        cells = []
        for function in functions:
            primary, supporting = grid[(section, function)]
            cells.append(("#" * len(primary)) + ("." * len(supporting)) or "")
        lines.append(f"| **{model.sectors[section]['notation']}** "
                     f"{model.label('sector', section)} | " + " | ".join(cells) + " |")

    lines += ["", "## Functions reused across sections", "",
              "Keeping functions independent of sectors makes this visible: "
              "a function that appears in more than one section is a candidate "
              "for one shared pattern instead of several sector-specific ones.", ""]
    for function in functions:
        touched = [s for s in sections if model.cell(s, function)]
        if len(touched) > 1:
            codes = ", ".join(model.sectors[s]["notation"] for s in touched)
            lines.append(f"- **{model.label('function', function)}** — "
                         f"{len(touched)} sections ({codes})")

    def interface_line(rows, key):
        out = []
        for row in rows:
            text = model.label("condition", row["condition_id"])
            extras = []
            if row.get("subject_role", "").strip():
                extras.append(model.label("subject-role", row["subject_role"]).lower())
            if row.get("evidence_type", "").strip():
                extras.append("as " + model.label("credential", row["evidence_type"]))
            if row.get("context", "").strip():
                extras.append(row["context"].strip())
            if extras:
                text += f" ({', '.join(extras)})"
            if key == "provision" and row.get("principal") == "yes":
                text = f"**{text}**"
            out.append(text)
        return ", ".join(out) or "—"

    lines += ["", "## Use case patterns", "",
              "Each pattern carries a classification and an interface. The interface "
              "is what composes: a pattern providing a condition narrower than what "
              "another requires is recognised as feeding it. The principal outcome is "
              "in bold.", ""]
    for uc_id, row in model.use_cases.items():
        sector_labels = ", ".join(
            f"{model.sectors[s]['notation']} {model.label('sector', s)}"
            for s in model.sectors_of[uc_id])
        primary = model.primary_function(uc_id)
        lines.append(f"### {row['name']}")
        lines.append("")
        lines.append(f"{row['description']}")
        lines.append("")
        lines.append(f"- Requires: {interface_line(model.requires_of[uc_id], 'requirement')}")
        lines.append(f"- Provides: {interface_line(model.provides_of[uc_id], 'provision')}")
        enabled = model.enables(uc_id)
        if enabled:
            lines.append(f"- Enables: {', '.join(model.label('use-case', e) for e in enabled)}")
        lines.append(f"- Primary function: {model.label('function', primary)}")
        supporting = [model.label('function', r["function_id"])
                      for r in model.functions_of[uc_id] if r["role"] != "primary"]
        if supporting:
            lines.append(f"- Supporting functions: {', '.join(supporting)}")
        lines.append(f"- Applies in: {sector_labels} · {scope_phrase(model, uc_id)}")
        stages = model.stages_realised_by[uc_id]
        if stages:
            lines.append("- Realises stage: " + ", ".join(
                f"{model.label('stream', vs)} — {model.stage_index[(vs, st)]['stage_label']}"
                for vs, st in stages))
        flows = model.flows_of_use_case(uc_id)
        if flows:
            lines.append("- Realised by: " + ", ".join(
                f"{model.label('flow', f)}" for f in flows))
        else:
            lines.append("- Realised by: no flow yet")
        lines.append("")

    lines += ["", "## Flows (real implementations)", "",
              "A flow is an actual implementation in an actual sector and "
              "jurisdiction. Several flows may realise one pattern, and one flow may "
              "realise several patterns in sequence.", ""]
    for flow_id, row in model.flows.items():
        lines.append(f"### {row['name']}")
        lines.append("")
        lines.append(f"{row['description']}")
        lines.append("")
        realises = " → ".join(model.label("use-case", uc)
                              for uc in model.realises_of[flow_id])
        lines.append(f"- Realises: {realises}")
        context = []
        if row["sector_id"].strip():
            context.append(f"{model.sectors[row['sector_id']]['notation']} "
                           f"{model.label('sector', row['sector_id'])}")
        if row["jurisdiction"].strip():
            context.append(row["jurisdiction"].strip())
        lines.append(f"- Context: {' · '.join(context) or 'sector-neutral'}")
        lines.append(f"- Maturity: {row['maturity'].lower()}")
        credentials = sorted({link["credential_type_id"]
                              for (f, _p), links in model.credentials_of.items()
                              if f == flow_id for link in links})
        if credentials:
            lines.append("- Credentials: " + ", ".join(
                model.label("credential", c) for c in credentials))
        documentation = model.documentation_iri(flow_id)
        if documentation:
            lines.append(f"- Worked flow: [{documentation}]({documentation})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_html(model):
    sections, functions, grid = matrix_rows(model)
    esc = html.escape

    head = []
    for function in functions:
        head.append(f'<th class="fn"><span>{esc(model.label("function", function))}</span></th>')

    body = []
    for section in sections:
        cells = []
        for function in functions:
            primary, supporting = grid[(section, function)]
            if not primary and not supporting:
                cells.append('<td class="empty"></td>')
                continue
            marks = []
            for uc in primary:
                marks.append(f'<a class="dot primary" href="#{esc(uc)}" '
                             f'title="{esc(model.use_cases[uc]["name"])} (primary)">&#9679;</a>')
            for uc in supporting:
                marks.append(f'<a class="dot support" href="#{esc(uc)}" '
                             f'title="{esc(model.use_cases[uc]["name"])} (supporting)">&#9675;</a>')
            cells.append('<td>' + "".join(marks) + '</td>')
        label = esc(model.label("sector", section))
        code = esc(model.sectors[section]["notation"])
        body.append(f'<tr><th class="sector" scope="row"><span class="code">{code}</span> '
                    f'{label}</th>' + "".join(cells) + "</tr>")

    def iface(rows, principal=False):
        """One interface point per line, with whatever dimensions it states."""
        out = []
        for row in rows:
            text = esc(model.label("condition", row["condition_id"]))
            extras = []
            if row.get("subject_role", "").strip() and row["subject_role"] != "subject":
                extras.append(esc(model.label("subject-role", row["subject_role"]).lower()))
            if row.get("evidence_type", "").strip():
                extras.append("as " + esc(model.label("credential", row["evidence_type"])))
            if row.get("context", "").strip():
                extras.append(esc(row["context"].strip()))
            if extras:
                text += f' <span class="muted">({", ".join(extras)})</span>'
            if principal and row.get("principal") == "yes":
                text = f"<strong>{text}</strong>"
            out.append(text)
        return ", ".join(out) or "&mdash; nothing"

    cards = []
    for uc_id, row in model.use_cases.items():
        primary = model.primary_function(uc_id)
        supporting = [model.label("function", r["function_id"])
                      for r in model.functions_of[uc_id] if r["role"] != "primary"]
        sector_list = ", ".join(
            f'<span class="code">{esc(model.sectors[s]["notation"])}</span> '
            f'{esc(model.label("sector", s))}' for s in model.sectors_of[uc_id])
        flows = model.flows_of_use_case(uc_id)
        if flows:
            link = ('<div class="flow-link">Realised by ' + ", ".join(
                (f'<a href="{esc(model.documentation_iri(f))}">'
                 f'{esc(model.label("flow", f))} &rarr;</a>'
                 if model.documentation_iri(f) else esc(model.label("flow", f)))
                for f in flows) + '</div>')
        else:
            link = ('<div class="flow-link"><span class="status">'
                    'No implementation yet</span></div>')
        scope = scope_phrase(model, uc_id)
        mode = model.modes[row["transformation_mode"]]
        change = model.change_mode_of(uc_id)
        requires = iface(model.requires_of[uc_id])
        provides = iface(model.provides_of[uc_id], principal=True)
        enabled = ", ".join(f'<a href="#{esc(e)}">{esc(model.label("use-case", e))}</a>'
                            for e in model.enables(uc_id))
        enables_line = (f'\n          <p class="meta"><strong>Enables:</strong> '
                        f'{enabled}</p>') if enabled else ""
        stages = model.stages_realised_by[uc_id]
        stage_line = (f'\n          <p class="meta"><strong>Value stream stage:</strong> '
                      + ", ".join(
                          f'{esc(model.label("stream", vs))} &mdash; '
                          f'{esc(model.stage_index[(vs, st)]["stage_label"])}'
                          for vs, st in stages) + '</p>') if stages else ""
        cards.append(f"""      <div class="flow" id="{esc(uc_id)}">
        <div class="flow-tag">{esc(scope)}
          &middot; <span class="mode mode-{esc(change)}">{esc(mode['pref_label_en'])}</span></div>
        <div class="flow-body">
          <h3>{esc(row['name'])}</h3>
          <p>{esc(row['description'])}</p>
          <p class="meta"><strong>Requires:</strong> {requires}</p>
          <p class="meta"><strong>Provides:</strong> {provides}</p>{enables_line}
          <p class="meta"><strong>Primary function:</strong> {esc(model.label('function', primary))}</p>
          <p class="meta"><strong>Supporting:</strong> {esc(', '.join(supporting)) or '&mdash;'}</p>
          <p class="meta"><strong>Applies in:</strong> {sector_list}</p>{stage_line}
        </div>
{link}
      </div>""")

    flow_cards = []
    for flow_id, row in model.flows.items():
        realises = " &rarr; ".join(
            f'<a href="#{esc(uc)}">{esc(model.label("use-case", uc))}</a>'
            for uc in model.realises_of[flow_id])
        context = []
        if row["sector_id"].strip():
            context.append(f'<span class="code">{esc(model.sectors[row["sector_id"]]["notation"])}'
                           f'</span> {esc(model.label("sector", row["sector_id"]))}')
        if row["jurisdiction"].strip():
            context.append(esc(row["jurisdiction"].strip()))
        credentials = sorted({link["credential_type_id"]
                              for (f, _pt), links in model.credentials_of.items()
                              if f == flow_id for link in links})
        cred_line = (f'\n          <p class="meta"><strong>Credentials:</strong> '
                     + ", ".join(esc(model.label("credential", c)) for c in credentials)
                     + '</p>') if credentials else ""
        payers = ", ".join(esc(p["party"]) for p in model.bears_cost_without_value(flow_id))
        asym_line = (f'\n          <p class="meta asym"><strong>Recorded as bearing cost '
                     f'without direct value:</strong> {payers}</p>') if payers else ""
        documentation = model.documentation_iri(flow_id)
        link = (f'<div class="flow-link"><a href="{esc(documentation)}">Worked flow &rarr;</a></div>'
                if documentation else
                '<div class="flow-link"><span class="status">Not yet documented</span></div>')
        flow_cards.append(f"""      <div class="flow" id="{esc(flow_id)}">
        <div class="flow-tag">{esc(" &middot; ".join(context)) or "sector-neutral"}
          &middot; {esc(row['maturity'])}</div>
        <div class="flow-body">
          <h3>{esc(row['name'])}</h3>
          <p>{esc(row['description'])}</p>
          <p class="meta"><strong>Realises:</strong> {realises}</p>{cred_line}{asym_line}
        </div>
{link}
      </div>""")

    driver_counts = {d: 0 for d in model.value_drivers}
    for uc_id in model.use_cases:
        for d in model.value_drivers_of[uc_id]:
            driver_counts[d] += 1
    driver_tally = "\n".join(
        f'          <li><span class="n">{count}</span> '
        f'{esc(model.label("driver", key))}</li>'
        for key, count in sorted(driver_counts.items(), key=lambda kv: -kv[1]))

    mode_counts = {m: 0 for m in model.modes}
    for uc_id, row in model.use_cases.items():
        mode_counts[row["transformation_mode"]] += 1
    mode_tally = "\n".join(
        f'          <li><span class="n">{mode_counts[key]}</span> '
        f'<span class="mode mode-{esc(row["change_mode"])}">'
        f'{esc(row["pref_label_en"])}</span> '
        f'<span class="muted">&mdash; {esc(row["change_mode"])}</span></li>'
        for key, row in model.modes.items())

    # Roots: nothing here satisfies what they need, so a chain starts at them.
    unmet_pairs = model.unmet_requirements()
    unmet_ids = {uc for uc, _requirement in unmet_pairs}
    roots = [uc for uc in model.use_cases
             if not model.requires_of[uc] or uc in unmet_ids]

    def chain_items(uc_id, seen):
        if uc_id in seen:
            return ""
        seen = seen | {uc_id}
        children = "".join(chain_items(nxt, seen) for nxt in model.enables(uc_id))
        inner = f"<ul>{children}</ul>" if children else ""
        name = esc(model.label("use-case", uc_id))
        principal = model.principal_outcome(uc_id)
        return (f'<li><a href="#{esc(uc_id)}">{name}</a>'
                f'<span class="muted"> provides '
                f'{esc(model.label("condition", principal) if principal else "nothing")}'
                f'</span>{inner}</li>')

    chain_html = "\n".join(f"      {chain_items(r, frozenset())}" for r in roots)
    unmet_html = ", ".join(
        f'<code>{esc(r["condition_id"])}</code>'
        for uc, requirement_id in unmet_pairs
        for r in model.requires_of[uc]
        if r["requirement_id"] == requirement_id) or "none"

    def stage_line(stream_id, stage):
        """A stage, its function, its interface and whatever realises it."""
        stage_id = stage["stage_id"]
        wants = [r["condition_id"] for r in model.stage_requires
                 if r["value_stream_id"] == stream_id and r["stage_id"] == stage_id]
        gives = [r["condition_id"] for r in model.stage_provides
                 if r["value_stream_id"] == stream_id and r["stage_id"] == stage_id]
        realised = [uc for uc, pairs in model.stages_realised_by.items()
                    if (stream_id, stage_id) in pairs]
        bits = [f'<span class="muted"> &middot; '
                f'{esc(model.label("function", stage["function_id"]))}</span>']
        if wants:
            bits.append(f'<span class="muted"> &middot; needs '
                        f'{esc(", ".join(model.label("condition", c) for c in wants))}</span>')
        if gives:
            bits.append(f'<span class="muted"> &middot; gives '
                        f'{esc(", ".join(model.label("condition", c) for c in gives))}</span>')
        if realised:
            bits.append(" &middot; " + ", ".join(
                f'<a href="#{esc(uc)}">{esc(model.label("use-case", uc))}</a>'
                for uc in realised))
        else:
            bits.append('<span class="muted"> &middot; no use case yet</span>')
        return f'<li>{esc(stage["stage_label"])}' + "".join(bits) + '</li>'

    def stream_interface(stream_id):
        wants = [r["condition_id"] for r in model.stream_requires
                 if r["value_stream_id"] == stream_id]
        gives = [r["condition_id"] for r in model.stream_provides
                 if r["value_stream_id"] == stream_id]
        if not wants and not gives:
            return ""
        return ('<p class="meta"><strong>Stream interface:</strong> '
                + esc(", ".join(model.label("condition", c) for c in wants) or "nothing")
                + ' &rarr; '
                + esc(", ".join(model.label("condition", c) for c in gives) or "nothing")
                + '</p>')

    streams_html = "\n".join(
        '      <div><h3>' + esc(row["pref_label_en"]) + '</h3>'
        + stream_interface(stream_id)
        + '<ol class="stages">'
        + "".join(stage_line(stream_id, stage) for stage in model.stages_of[stream_id])
        + '</ol></div>'
        for stream_id, row in model.value_streams.items())

    reused = []
    for function in functions:
        touched = [s for s in sections if model.cell(s, function)]
        if len(touched) > 1:
            codes = " ".join(f'<span class="code">{esc(model.sectors[s]["notation"])}</span>'
                             for s in touched)
            reused.append(f"<li><strong>{esc(model.label('function', function))}</strong> "
                          f"&mdash; {codes}</li>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Industry &amp; function mapping</title>
<meta name="description" content="Which use cases sit at which intersection of economic sector (ISIC Rev. 5) and business function.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
  /* Self-contained on purpose: this page is published straight out of
     generated/ with no other assets to deploy alongside it.

     The complete light palette lives on bare :root. The dark blocks below
     redefine only the tokens, so every rule in this file is written once. */
  :root {{
    --accent: #c61623; --ink: #212934; --body: #4a5261;
    --line: #e4e8ec; --bg-soft: #f8f9fb; --paper: #ffffff; --wash: #f1f3f6;
    --dot-support: #9aa3b0;

    /* The masthead's width control switches this. */
    --wrap-max: 1040px;
  }}
  :root[data-width="wide"] {{ --wrap-max: 1440px; }}

  /* Three theme states, the same pattern on every DIDAS site: no data-theme
     follows the operating system, data-theme="light" and "dark" override it. */
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --accent: #ff6b73; --ink: #e6eaef; --body: #a6b0bd;
      --line: #2a313b; --bg-soft: #171c22; --paper: #11151a; --wash: #1b2128;
      --dot-support: #6d7886;
    }}
  }}
  :root[data-theme="dark"] {{
    --accent: #ff6b73; --ink: #e6eaef; --body: #a6b0bd;
    --line: #2a313b; --bg-soft: #171c22; --paper: #11151a; --wash: #1b2128;
    --dot-support: #6d7886;
  }}

  * {{ box-sizing: border-box; }}
  /* The masthead's text-size control sets this in px; everything typographic
     on this page is in rem so that it follows. */
  html {{ font-size: 16px; }}
  body {{ margin: 0; background: var(--paper); color: var(--ink); line-height: 1.6;
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  a:focus-visible, button:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
  code {{ font-size: 0.92em; background: var(--bg-soft); padding: 1px 4px;
    border-radius: 3px; }}
  .wrap {{ max-width: var(--wrap-max); margin: 0 auto; padding: 0 24px; }}

  /* =====================================================================
     Shared DIDAS masthead
     The same header across the DIDAS sites: the identity line from the
     digital-health_swiyu showcase, in the bar geometry and hairline rule of
     the Trust Flow landing page. Only the four --mh-* values below differ
     between sites; everything after them is identical everywhere, so a
     change to the design can be copied across without rereading each site's
     stylesheet.
     ===================================================================== */
  .site-masthead {{
    --mh-rule:  var(--line);
    --mh-ink:   var(--body);
    --mh-hover: var(--accent);
    --mh-wash:  var(--wash);
    --mh-width: var(--wrap-max);   /* this page's own content width, so the
                                      bar lines up with the matrix below it */

    border-bottom: 1px solid var(--mh-rule);
  }}
  .site-masthead .bar {{
    max-width: var(--mh-width);
    margin-inline: auto;
    padding-inline: 24px;
    padding-block: 22px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px 24px;
  }}
  .site-masthead .id {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px 12px;
  }}
  .site-masthead .didas {{ display: inline-flex; align-items: center; line-height: 0; }}
  .site-masthead .didas img {{ height: 20px; width: auto; display: block; }}
  .site-masthead .eyebrow {{
    margin: 0;
    font-family: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--mh-ink);
  }}
  .site-masthead .repolink {{
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-family: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.72rem;
    letter-spacing: 0.06em;
    color: var(--mh-ink);
    text-decoration: none;
    white-space: nowrap;
  }}
  .site-masthead .repolink svg {{ flex: none; }}
  .site-masthead .repolink span {{
    border-bottom: 1px solid var(--mh-rule);
    padding-bottom: 2px;
  }}
  .site-masthead .repolink:hover {{ color: var(--mh-hover); }}
  .site-masthead .repolink:hover span {{ border-bottom-color: currentColor; }}
  /* The same controls the glossary carries — colour theme, layout width and text
     size — reading and writing the same localStorage keys. All four DIDAS sites
     are served from one origin, so a preference set on any of them is the
     preference on all of them. */
  .site-masthead .tools {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px 14px;
  }}
  .site-masthead .seg {{
    display: inline-flex;
    align-items: stretch;
    border: 1px solid var(--mh-rule);
    border-radius: 4px;
    overflow: hidden;
  }}
  .site-masthead button {{
    appearance: none;
    -webkit-appearance: none;
    background: none;
    border: 0;
    margin: 0;
    padding: 5px 8px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--mh-ink);
    cursor: pointer;
    font: inherit;
    line-height: 0;
  }}
  .site-masthead .seg button + button {{ border-left: 1px solid var(--mh-rule); }}
  .site-masthead button:hover {{ color: var(--mh-hover); }}
  .site-masthead button[aria-pressed="true"] {{
    color: var(--mh-hover);
    background: var(--mh-wash);
  }}
  .site-masthead button svg {{ width: 14px; height: 14px; display: block; }}
  .site-masthead .seg.text button {{
    font-family: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    line-height: 1;
    padding-block: 4px;
  }}
  .site-masthead .seg.text button:first-child {{ font-size: 0.62rem; }}
  .site-masthead .seg.text button:last-child  {{ font-size: 0.88rem; }}
  /* The width control shows the action it would take, so it swaps icon rather
     than carrying the pressed background the theme buttons use. */
  .site-masthead button[data-width-value] .w-contract {{ display: none; }}
  .site-masthead button[data-width-value][aria-pressed="true"] {{ background: none; }}
  .site-masthead button[data-width-value][aria-pressed="true"] .w-expand {{ display: none; }}
  .site-masthead button[data-width-value][aria-pressed="true"] .w-contract {{ display: block; }}
  /* === end shared DIDAS masthead ==================================== */
  section {{ padding: 36px 0; border-top: 1px solid var(--line); }}
  section.hero {{ border-top: none; padding-bottom: 8px; }}
  h1 {{ font-size: 2.125rem; line-height: 1.2; margin: 8px 0 16px; }}
  h2 {{ font-size: 0.8125rem; text-transform: uppercase; letter-spacing: .08em;
    color: var(--body); margin: 0 0 18px; }}
  h3 {{ font-size: 1rem; margin: 0 0 8px; }}
  .eyebrow {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: .08em;
    color: var(--accent); font-weight: 600; }}
  .lede {{ font-size: 1rem; color: var(--body); max-width: 680px; }}
  .prose {{ color: var(--body); font-size: 0.9062rem; max-width: 680px; }}
  .matrix-scroll {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; }}
  table.matrix {{ border-collapse: collapse; font-size: 0.8125rem; min-width: 100%; }}
  table.matrix th, table.matrix td {{ border-bottom: 1px solid var(--line); padding: 8px 10px; }}
  table.matrix th.fn {{ vertical-align: bottom; text-align: left; font-weight: 600;
    white-space: nowrap; font-size: 0.75rem; color: var(--body); }}
  table.matrix th.fn span {{ display: block; writing-mode: vertical-rl;
    transform: rotate(180deg); height: 11.5625rem; }}
  table.matrix th.sector {{ text-align: left; font-weight: 500; max-width: 260px;
    position: sticky; left: 0; background: var(--paper); border-right: 1px solid var(--line);
    line-height: 1.35; }}
  table.matrix td {{ text-align: center; vertical-align: middle; }}
  table.matrix td.empty {{ background: var(--bg-soft); }}
  .code {{ display: inline-block; min-width: 20px; padding: 0 5px; margin-right: 4px;
    border: 1px solid var(--line); border-radius: 3px; font-size: 0.6875rem;
    color: var(--body); background: var(--bg-soft); }}
  .dot {{ text-decoration: none; font-size: 0.8125rem; padding: 0 1px; }}
  .dot.primary {{ color: var(--accent); }}
  .dot.support {{ color: var(--dot-support); }}
  .legend {{ font-size: 0.8125rem; color: var(--body); margin-top: 12px; }}
  .meta {{ font-size: 0.8125rem; color: var(--body); margin: 4px 0; }}
  .axes {{ display: grid; gap: 24px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
  .axes h3 {{ font-size: 0.8125rem; text-transform: uppercase; letter-spacing: .06em;
    color: var(--body); }}
  ul.tally {{ list-style: none; padding: 0; margin: 0; font-size: 0.875rem; }}
  ul.tally li {{ padding: 5px 0; border-bottom: 1px solid var(--line); }}
  ul.tally .n {{ display: inline-block; min-width: 26px; font-weight: 600; }}
  .muted {{ color: var(--body); font-size: 0.75rem; }}
  .mode {{ font-weight: 600; }}
  .mode-change {{ color: var(--accent); }}
  .meta.asym {{ color: var(--accent); }}
  ul.chain {{ font-size: 0.875rem; }}
  ul.chain ul {{ margin: 4px 0; }}
  ul.chain li {{ padding: 2px 0; }}
  ol.stages {{ font-size: 0.8125rem; color: var(--body); padding-left: 20px; margin: 0; }}
  ol.stages li {{ padding: 2px 0; }}
  .flows {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }}
  .flow {{ border: 1px solid var(--line); border-radius: 6px; display: flex;
    flex-direction: column; scroll-margin-top: 20px; }}
  .flow-tag {{ font-size: 0.6875rem; text-transform: uppercase; letter-spacing: .06em;
    color: var(--body); padding: 10px 16px; border-bottom: 1px solid var(--line);
    background: var(--bg-soft); }}
  .flow-body {{ padding: 16px; flex: 1; }}
  .flow-body p {{ font-size: 0.875rem; color: var(--body); margin-top: 0; }}
  .flow-link {{ padding: 12px 16px; border-top: 1px solid var(--line); font-size: 0.875rem; }}
  .status {{ font-size: 0.75rem; color: var(--body); }}
  footer.site {{ border-top: 1px solid var(--line); margin-top: 40px; }}
  footer.site .wrap {{ display: flex; flex-wrap: wrap; gap: 10px 24px;
    justify-content: space-between; padding-top: 20px; padding-bottom: 40px;
    font-size: 0.7812rem; color: var(--body); }}
  @media (max-width: 620px) {{
    h1 {{ font-size: 1.6875rem; }}
    table.matrix th.sector {{ max-width: 160px; }}
  }}
</style>
</head>
<body>

<!-- Shared DIDAS masthead. Keep the markup identical across the DIDAS sites;
     only the eyebrow text and the repository URL differ. -->
<header class="site-masthead">
  <div class="bar">
    <div class="id">
      <a class="didas" href="https://www.didas.swiss" target="_blank" rel="noopener">
        <img src="https://www.didas.swiss/wp-content/uploads/2021/02/logo.png" alt="DIDAS">
      </a>
      <p class="eyebrow">Industry &amp; function mapping · knowledge graph</p>
    </div>
    <div class="tools">
      <div class="seg" role="group" aria-label="Colour theme">
        <button type="button" data-theme-value="light" aria-pressed="false" title="Light" aria-label="Light theme"><svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path fill="currentColor" d="M8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM8 0a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 0zm0 13a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-1 0v-2A.5.5 0 0 1 8 13zm8-5a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2a.5.5 0 0 1 .5.5zM3 8a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1 0-1h2A.5.5 0 0 1 3 8zm10.657-5.657a.5.5 0 0 1 0 .707l-1.414 1.415a.5.5 0 1 1-.707-.708l1.414-1.414a.5.5 0 0 1 .707 0zm-9.193 9.193a.5.5 0 0 1 0 .707L3.05 13.657a.5.5 0 0 1-.707-.707l1.414-1.414a.5.5 0 0 1 .707 0zm9.193 2.121a.5.5 0 0 1-.707 0l-1.414-1.414a.5.5 0 0 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .707zM4.464 4.465a.5.5 0 0 1-.707 0L2.343 3.05a.5.5 0 1 1 .707-.707l1.414 1.414a.5.5 0 0 1 0 .708z"/></svg></button>
        <button type="button" data-theme-value="dark" aria-pressed="false" title="Dark" aria-label="Dark theme"><svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path fill="currentColor" d="M6 .278a.768.768 0 0 1 .08.858 7.208 7.208 0 0 0-.878 3.46c0 4.021 3.278 7.277 7.318 7.277.527 0 1.04-.055 1.533-.16a.787.787 0 0 1 .81.316.733.733 0 0 1-.031.893A8.349 8.349 0 0 1 8.344 16C3.734 16 0 12.286 0 7.71 0 4.266 2.114 1.312 5.124.06A.752.752 0 0 1 6 .278z"/><path fill="currentColor" d="M10.794 3.148a.217.217 0 0 1 .412 0l.387 1.162c.173.518.579.924 1.097 1.097l1.162.387a.217.217 0 0 1 0 .412l-1.162.387a1.734 1.734 0 0 0-1.097 1.097l-.387 1.162a.217.217 0 0 1-.412 0l-.387-1.162A1.734 1.734 0 0 0 9.31 6.593l-1.162-.387a.217.217 0 0 1 0-.412l1.162-.387a1.734 1.734 0 0 0 1.097-1.097l.387-1.162zM13.863.099a.145.145 0 0 1 .274 0l.258.774c.115.346.386.617.732.732l.774.258a.145.145 0 0 1 0 .274l-.774.258a1.156 1.156 0 0 0-.732.732l-.258.774a.145.145 0 0 1-.274 0l-.258-.774a1.156 1.156 0 0 0-.732-.732l-.774-.258a.145.145 0 0 1 0-.274l.774-.258c.346-.115.617-.386.732-.732L13.863.1z"/></svg></button>
        <button type="button" data-theme-value="auto" aria-pressed="true" title="Match the system" aria-label="Match the system theme"><svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path fill="currentColor" d="M8 15A7 7 0 1 0 8 1v14zm0 1A8 8 0 1 1 8 0a8 8 0 0 1 0 16z"/></svg></button>
      </div>
      <div class="seg" role="group" aria-label="Layout width">
        <button type="button" data-width-value="container-fluid" aria-pressed="false" title="Toggle wide or narrow layout" aria-label="Toggle wide or narrow layout"><svg class="w-expand" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path fill="currentColor" fill-rule="evenodd" d="M5.828 10.172a.5.5 0 0 0-.707 0l-4.096 4.096V11.5a.5.5 0 0 0-1 0v3.975a.5.5 0 0 0 .5.5H4.5a.5.5 0 0 0 0-1H1.732l4.096-4.096a.5.5 0 0 0 0-.707m4.344-4.344a.5.5 0 0 0 .707 0l4.096-4.096V4.5a.5.5 0 1 0 1 0V.525a.5.5 0 0 0-.5-.5H11.5a.5.5 0 0 0 0 1h2.768l-4.096 4.096a.5.5 0 0 0 0 .707"/></svg><svg class="w-contract" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path fill="currentColor" fill-rule="evenodd" d="M.172 15.828a.5.5 0 0 0 .707 0l4.096-4.096V14.5a.5.5 0 1 0 1 0v-3.975a.5.5 0 0 0-.5-.5H1.5a.5.5 0 0 0 0 1h2.768L.172 15.121a.5.5 0 0 0 0 .707M15.828.172a.5.5 0 0 0-.707 0l-4.096 4.096V1.5a.5.5 0 1 0-1 0v3.975a.5.5 0 0 0 .5.5H14.5a.5.5 0 0 0 0-1h-2.768L15.828.879a.5.5 0 0 0 0-.707"/></svg></button>
      </div>
      <div class="seg text" role="group" aria-label="Text size">
        <button type="button" data-font-step="-1" title="Decrease text size" aria-label="Decrease text size">A</button>
        <button type="button" data-font-step="1" title="Increase text size" aria-label="Increase text size">A</button>
      </div>
      <a class="repolink" href="https://github.com/DIDAS-swiss/industry-function-graph" target="_blank" rel="noopener">
        <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true" focusable="false"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg>
        <span>Source on GitHub</span>
      </a>
    </div>
  </div>
</header>

{MASTHEAD_SCRIPT}

<div class="wrap">

  <section class="hero" style="border-top:none;">
    <span class="eyebrow">Knowledge graph</span>
    <h1>Which function, in which sector</h1>
    <p class="lede">
      Every use case in this graph sits at an intersection: an economic sector
      (ISIC Rev. 5) and a business function that is defined independently of it.
      Read the matrix down a column to find the same function recurring across
      sectors &mdash; those are the places where one pattern can serve many industries.
    </p>
  </section>

  <section>
    <h2>Sector &times; function</h2>
    <div class="matrix-scroll">
      <table class="matrix">
        <thead><tr><th class="sector">ISIC Rev. 5 section</th>{''.join(head)}</tr></thead>
        <tbody>
{chr(10).join(body)}
        </tbody>
      </table>
    </div>
    <p class="legend">
      <span class="dot primary">&#9679;</span> primary function of a use case &nbsp;&middot;&nbsp;
      <span class="dot support">&#9675;</span> supporting function. Follow a marker to the use case.
    </p>
  </section>

  <section>
    <h2>Functions that recur across sectors</h2>
    <ul>
{chr(10).join(reused)}
    </ul>
  </section>

  <section>
    <h2>What plugs into what</h2>
    <p class="prose">
      Each use case declares the conditions it requires and the conditions it
      provides. The arrows below are computed from those interfaces, through the
      condition hierarchy: a use case providing something <em>narrower</em> than what
      another asks for still counts as feeding it, which is what lets an alternative
      upstream flow serve the same downstream need. Nothing here is a list of
      hand-drawn dependencies.
    </p>
    <ul class="chain">
{chain_html}
    </ul>
    <p class="legend">
      <strong>Unmet requirements:</strong> {unmet_html} &mdash; required by a use case
      here and provided by none. Each marks a flow that is outside this repository
      or not yet written down.
    </p>
  </section>

  <section>
    <h2>Use case patterns</h2>
    <p class="prose">
      The canonical unit: one primary business function, a set of required
      conditions and one principal outcome, shown in bold. A pattern is a reusable
      definition, not an implementation &mdash; the implementations are below.
    </p>
    <div class="flows">
{chr(10).join(cards)}
    </div>
  </section>

  <section>
    <h2>Flows &mdash; real implementations</h2>
    <p class="prose">
      An actual trust flow, in an actual sector and jurisdiction, naming the
      credentials it uses. Several flows may realise one pattern &mdash; the same age
      check in retail and in hospitality, the same qualification issuance for a
      Matur&auml;t and a vocational certificate &mdash; and one flow may realise several
      patterns in sequence. Keeping flows out of the taxonomy is the point: the
      ecosystem adds implementations continuously, and each should find a place among
      the existing patterns rather than becoming another one.
    </p>
    <div class="flows">
{chr(10).join(flow_cards)}
    </div>
  </section>

  <section>
    <h2>Value streams</h2>
    <p class="prose">
      Where the work sits end to end. The concept follows ArchiMate's
      <em>Value Stream</em> element. The catalogue and the stage decomposition below
      are this repository's editorial models rather than extracts from a standard,
      since no openly licensed catalogue exists: each is one modelled sequence, not
      the universal one. Stage numbers are a reading order, not an execution order.
    </p>
    <div class="axes">
{streams_html}
    </div>
  </section>

  <section>
    <h2>Decision support</h2>
    <p class="prose">
      Secondary by design. None of this takes part in classification or in
      composition; it is here to help prioritise work, and both vocabularies are
      this repository's editorial classifications rather than external standards.
    </p>
    <div class="axes">
      <div>
        <h3>Value drivers</h3>
        <ul class="tally">
{driver_tally}
        </ul>
      </div>
      <div>
        <h3>How far the process changes</h3>
        <ul class="tally">
{mode_tally}
        </ul>
      </div>
    </div>
  </section>

  <section>
    <h2>The graph itself</h2>
    <p class="prose">
      This page is generated from the same data as the machine-readable graph:
      SKOS concept schemes for the sector, function, condition, role and credential
      vocabularies; <code>ifm:UseCasePattern</code> nodes carrying a classification
      and an interface of <code>ifm:requires</code> and <code>ifm:provides</code>; and
      <code>ifm:Flow</code> nodes recording what actually implements them. Load
      <a href="ifm-graph.ttl">ifm-graph.ttl</a> or
      <a href="ifm-graph.jsonld">ifm-graph.jsonld</a> into any triple store, or read the
      <a href="https://github.com/DIDAS-swiss/industry-function-graph">source data and build script</a>.
    </p>
  </section>

</div>

<footer class="site">
  <div class="wrap">
    <span>industry-function-graph</span>
    <span>Generated from <code>data/</code> &mdash; do not edit by hand</span>
    <span><a href="https://github.com/DIDAS-swiss/industry-function-graph">Source on GitHub</a></span>
  </div>
</footer>

</body>
</html>
"""


# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Composition report
#
# Worked compositions, the gaps and the overlap candidates, regenerated with
# everything else so it cannot drift from the data. Everything in it is
# derived: no file in data/ records which use case enables which, which
# requirement has no supplier, or which two use cases overlap.
# --------------------------------------------------------------------------

WORKED_COMPOSITIONS = [
    ("Electronic identity to an open banking relationship, and its refresh",
     "eid-held", "kyc-attestation-current",
     "The chain the ecosystem is actually built on. Note that nothing in it "
     "names a credential: each step asks for a condition, and the e-ID happens "
     "to be what substantiates the first one."),
    ("Education qualification to university admission",
     "secondary-education-credential-held", "tertiary-enrolment-established",
     "Admission asks for a verified qualification, not for a Maturitätszeugnis, "
     "so any flow that can establish the qualification serves it."),
    ("Education qualification to employment",
     "secondary-education-credential-held", "employment-relationship-open",
     "The same two upstream patterns feed a different downstream one. Neither "
     "the issuance nor the verification pattern knows or cares which."),
    ("Electronic identity to a proven age threshold",
     "eid-held", "age-attribute-proven",
     "One step: age verification is not identity verification, and the "
     "interface says so - it consumes identity evidence and provides an "
     "attribute, never an identity."),
]


def build_composition_report(model):
    lines = [
        "<!-- DO NOT EDIT: generated by build/build.py -->",
        "# Composition report",
        "",
        "Everything below is derived from the interfaces in `data/`. Nothing here "
        "is maintained by hand: no file records which use case enables which, "
        "which requirement has no supplier, or which two use cases overlap.",
        "",
        "Regenerate with `python3 build/build.py`; `build/queries.py` answers the "
        "same questions interactively.",
        "",
        "## Worked compositions",
        "",
        "A chain is reported only if every step earns its place - drop any one of "
        "them and the goal is no longer reachable.",
        "",
    ]
    for title, start, goal, note in WORKED_COMPOSITIONS:
        lines += [f"### {title}", "", note, ""]
        paths = model.composition_paths(start, goal)
        if not paths:
            lines += [f"No path from `{start}` to `{goal}`.", ""]
            continue
        for path in paths:
            steps = [f"**{model.label('condition', start)}**"]
            for uc_id in path:
                steps.append(f"`{uc_id}`")
            steps.append(f"**{model.label('condition', goal)}**")
            lines.append(" → ".join(steps))
            lines.append("")
            for uc_id in path:
                requires = ", ".join(
                    model.label("condition", r["condition_id"])
                    for r in model.requires_of[uc_id]) or "nothing"
                principal = model.principal_outcome(uc_id)
                lines.append(f"- `{uc_id}` — needs {requires}; provides "
                             f"{model.label('condition', principal) if principal else '—'}")
            lines.append("")

    lines += [
        "## Alternative evidence for one requirement",
        "",
        "The test of whether conditions and credentials are really separate: can "
        "a second credential satisfy an existing requirement without any "
        "canonical use case changing?",
        "",
    ]
    for condition_id in sorted(
            {r["condition_id"] for uc in model.use_cases
             for r in model.requires_of[uc]}):
        credentials = model.credentials_for_condition(condition_id)
        if len(credentials) < 2:
            continue
        askers = sorted({uc for uc in model.use_cases
                         for r in model.requires_of[uc]
                         if r["condition_id"] == condition_id})
        lines += [
            f"**{model.label('condition', condition_id)}** is required by "
            + ", ".join(f"`{uc}`" for uc in askers) + ".",
            "",
            "It can be substantiated by:",
            "",
        ]
        for cred in credentials:
            issuing = sorted({flow for flow in model.flows
                              if cred in model.credential_actions(flow, "issues")})
            lines.append(f"- **{model.label('credential', cred)}** — issued by "
                         + (", ".join(f"`{f}`" for f in issuing) or "no flow here"))
        lines += ["",
                  "No use case pattern names either credential, so a third one can "
                  "be added to `data/credential-conditions.csv` and every use case "
                  "requiring this condition accepts it immediately.",
                  ""]

    lines += ["## Overlapping use case patterns", "",
              "Candidates for editorial review, not decisions. Two patterns are "
              "reported when they share a primary function and their interfaces "
              "relate. Nothing is merged automatically: a shared shape may still "
              "be genuinely different work.", ""]
    overlaps = model.overlaps()
    if not overlaps:
        lines += ["None detected.", ""]
    else:
        lines += ["| Relation | Pattern | Pattern | Shared primary function |",
                  "|---|---|---|---|"]
        for verdict, first, second in overlaps:
            lines.append(f"| {verdict} | `{first}` | `{second}` | "
                         f"{model.label('function', model.primary_function(first))} |")
        lines.append("")
        for verdict, first, second in overlaps:
            lines += [
                f"**`{first}` ~ `{second}`** ({verdict})", "",
                f"- `{first}` needs "
                + (", ".join(model.label("condition", r["condition_id"])
                             for r in model.requires_of[first]) or "nothing")
                + "; provides "
                + (", ".join(model.label("condition", p["condition_id"])
                             for p in model.provides_of[first]) or "nothing"),
                f"- `{second}` needs "
                + (", ".join(model.label("condition", r["condition_id"])
                             for r in model.requires_of[second]) or "nothing")
                + "; provides "
                + (", ".join(model.label("condition", p["condition_id"])
                             for p in model.provides_of[second]) or "nothing"),
                "",
            ]

    lines += ["## Gaps", "",
              "Where the classification and the ecosystem do not yet meet.", ""]

    unmet = model.unmet_requirements()
    lines += ["### Requirements with no upstream provider", ""]
    if not unmet:
        lines += ["None: every requirement is satisfied by some use case here.", ""]
    else:
        for uc_id, requirement_id in unmet:
            requirement = next(r for r in model.requires_of[uc_id]
                               if r["requirement_id"] == requirement_id)
            lines.append(f"- `{uc_id}` requires "
                         f"**{model.label('condition', requirement['condition_id'])}** "
                         f"— no use case here provides it")
        lines.append("")

    lines += ["### Principal outcomes with no downstream consumer", ""]
    ends = []
    for uc_id, provision_id in model.unconsumed_provisions():
        provision = next(p for p in model.provides_of[uc_id]
                         if p["provision_id"] == provision_id)
        if provision.get("principal") == "yes":
            ends.append((uc_id, provision["condition_id"]))
    if not ends:
        lines += ["None.", ""]
    else:
        lines += ["Either genuine ends of a chain, or downstream use cases nobody "
                  "has written down.", ""]
        for uc_id, condition_id in ends:
            lines.append(f"- `{uc_id}` provides "
                         f"**{model.label('condition', condition_id)}**")
        lines.append("")

    lines += ["### Use case patterns with no implementation", ""]
    unrealised = model.unrealised_use_cases()
    if not unrealised:
        lines += ["None: every pattern has at least one flow.", ""]
    else:
        for uc_id in unrealised:
            lines.append(f"- `{uc_id}`")
        lines.append("")

    lines += ["### Value stream stages with no use case", ""]
    unrealised_stages = model.unrealised_stages()
    if not unrealised_stages:
        lines += ["None.", ""]
    else:
        lines += [f"{len(unrealised_stages)} of {len(model.stage_index)} stages. "
                  "The graph covers a slice of each stream, and the stages below "
                  "mark where a use case could be added without inventing a new "
                  "classification.", ""]
        current = None
        for stream_id, stage_id in unrealised_stages:
            if stream_id != current:
                current = stream_id
                lines.append(f"**{model.label('stream', stream_id)}**")
                lines.append("")
            lines.append(f"- {model.stage_index[(stream_id, stage_id)]['stage_label']} "
                         f"(`{stage_id}`)")
        lines.append("")

    lines += ["### Credentials issued here but verified by no flow here", ""]
    orphaned = sorted(model.issued_credentials() - model.consumed_credentials())
    if not orphaned:
        lines += ["None.", ""]
    else:
        for cred in orphaned:
            lines.append(f"- **{model.label('credential', cred)}**")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


OUTPUTS = {
    "ifm-graph.ttl": build_turtle,
    "ifm-graph.jsonld": build_jsonld,
    "matrix.md": build_matrix_md,
    "index.html": build_html,
    "composition-report.md": build_composition_report,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify generated/ matches data/ instead of writing")
    args = parser.parse_args()

    model = Model()
    os.makedirs(GENERATED_DIR, exist_ok=True)
    stale = []
    for name, builder in OUTPUTS.items():
        content = builder(model)
        path = os.path.join(GENERATED_DIR, name)
        if args.check:
            current = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            if current != content:
                stale.append(name)
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"wrote generated/{name} ({len(content):,} bytes)")

    if args.check:
        if stale:
            print("stale generated files: " + ", ".join(stale), file=sys.stderr)
            print("run: python3 build/build.py", file=sys.stderr)
            return 1
        print("generated/ is up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
