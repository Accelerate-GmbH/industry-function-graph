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
    ("sector", ID_BASE + "sector/"),
    ("func", ID_BASE + "function/"),
    ("cbf", ID_BASE + "cbf/"),
    ("apqc", ID_BASE + "apqc/"),
    ("uc", ID_BASE + "use-case/"),
    ("driver", ID_BASE + "value-driver/"),
    ("mode", ID_BASE + "transformation-mode/"),
    ("stream", ID_BASE + "value-stream/"),
    ("stage", ID_BASE + "value-stream-stage/"),
    ("role", ID_BASE + "trust-role/"),
    ("prior", ID_BASE + "prior-evidence/"),
    ("part", ID_BASE + "participation/"),
    ("state", ID_BASE + "state/"),
    ("cred", ID_BASE + "credential-type/"),
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
    "sector": "sector",
    "function": "func",
    "cbf": "cbf",
    "apqc": "apqc",
    "use-case": "uc",
    "driver": "driver",
    "mode": "mode",
    "stream": "stream",
    "stage": "stage",
    "role": "role",
    "prior-evidence": "prior",
    "participation": "part",
    "state": "state",
    "credential": "cred",
}


def scheme_iri(scheme_id):
    return f"scheme:{scheme_id}"


def concept_ref(kind, ident):
    return f"{PREFIX_OF_KIND[kind]}:{ident}"


# What a party does with a credential. Keyed on the participation, so one party
# holding two roles in a use case keeps its actions apart.
def by_action(model, participation):
    """{predicate: [credential ids]} for one participation.

    Grouped by predicate because a party can verify two credentials. Two pairs
    sharing a predicate serialise differently in Turtle and JSON-LD.
    """
    grouped: dict[str, list[str]] = {}
    for link in model.credentials_of.get(
            (participation["use_case_id"], participation["participation_id"]), []):
        grouped.setdefault(ACTION_PROPERTY[link["action"]], []).append(
            link["credential_type_id"])
    return grouped


# The four stages of the credential lifecycle a participation can cover:
# issued, held, presented, verified.
ACTION_PROPERTY = {
    "issues": "ifm:issuesCredential",
    "holds": "ifm:holdsCredential",
    "presents": "ifm:presentsCredential",
    "verifies": "ifm:verifiesCredential",
}


# Evidence states record possession; outcome states record a business or
# administrative conclusion. Both are ifm:State subclasses, so composition is
# unaffected by which one a state is.
STATE_CLASS = {
    "evidence": "ifm:EvidenceState",
    "outcome": "ifm:OutcomeState",
}


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

    heading = "Layer 1 - Sectors (ISIC Rev. 5)"
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

    heading = "Layer 2a - CBF categories (mapping target)"
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

    heading = "Layer 2b - APQC PCF categories (mapping target)"
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

    heading = "Layer 2c - Operational business functions (+ alignments)"
    kind_of_scheme = {"cbf": "cbf", "apqc-pcf": "apqc"}
    for function_id, row in model.functions.items():
        matches = {}
        notes = []
        statuses: set[str] = set()
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
                      [Lit(s, datatype=None, lang=None) for s in sorted(statuses)]))
        pairs.append(("skos:editorialNote", notes))
        blocks.append((heading, Ref(concept_ref("function", function_id)), pairs))

    heading = "Layer 4 - Credential types"
    for cred_id, row in model.credential_types.items():
        blocks.append((heading, Ref(concept_ref("credential", cred_id)), [
            ("a", [Ref("ifm:CredentialType"), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-credential-types"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-credential-types"))),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:definition", L(row["definition"])),
            ("ifm:evidences", R(concept_ref("state", row["evidences_state"]))
             if row["evidences_state"] else []),
            ("ifm:credentialFormat", L(row["format"], lang=None)),
            ("ifm:semanticModel", L(row["semantic_model"], lang=None)),
            ("ifm:trustFramework", L(row["trust_framework"], lang=None)),
            ("ifm:protocolProfile", L(row["protocol_profile"], lang=None)),
            ("ifm:codeStatus", L(row["code_status"], lang=None)),
        ]))

    heading = "Layer 3c - States: the interface that makes use cases composable"
    for state_id, row in model.states.items():
        blocks.append((heading, Ref(concept_ref("state", state_id)), [
            ("a", [Ref(STATE_CLASS[row["kind"]]), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-states"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-states"))),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:definition", L(row["definition"])),
        ]))

    heading = "Layer 3b - Trust roles and the mechanisms a credential displaces"
    for role_id, row in model.trust_roles.items():
        blocks.append((heading, Ref(concept_ref("role", role_id)), [
            ("a", [Ref("ifm:TrustRole"), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-trust-roles"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-trust-roles"))),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:definition", L(row["definition"])),
        ]))
    for mechanism_id, row in model.prior_evidence.items():
        blocks.append((heading, Ref(concept_ref("prior-evidence", mechanism_id)), [
            ("a", [Ref("ifm:PriorEvidenceMechanism"), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-prior-evidence"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-prior-evidence"))),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:definition", L(row["definition"])),
        ]))
    for row in model.participants:
        ident = f"{row['use_case_id']}-{row['participation_id']}"
        blocks.append((heading, Ref(concept_ref("participation", ident)), [
            ("a", R("ifm:Participation")),
            ("ifm:inUseCase", R(concept_ref("use-case", row["use_case_id"]))),
            ("ifm:trustRole", R(concept_ref("role", row["role_id"]))),
            ("ifm:party", L(row["party"])),
            ("ifm:bearsCost", [Lit("true" if row["bears_cost"] == "yes" else "false",
                                   datatype="xsd:boolean")]),
            ("ifm:gainsValue", L(row["gains_value"], lang=None)),
            ("skos:scopeNote", L(row["note"])),
        ] + [
            (prop, [Ref(concept_ref("credential", cred)) for cred in creds])
            for prop, creds in sorted(by_action(model, row).items())
        ]))

    heading = "Layer 3a - Value drivers and transformation modes"
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

    heading = "Layer 2d - Value streams (ordered compositions of functions)"
    for stream_id, row in model.value_streams.items():
        stages = model.stages_of[stream_id]
        blocks.append((heading, Ref(concept_ref("stream", stream_id)), [
            ("a", [Ref("ifm:ValueStream"), Ref("skos:Concept")]),
            ("skos:inScheme", R(scheme_iri("ifm-value-streams"))),
            ("skos:topConceptOf", R(scheme_iri("ifm-value-streams"))),
            ("skos:prefLabel", L(row["pref_label_en"])),
            ("skos:altLabel", [Lit(alt.strip()) for alt in row["also_known_as"].split(";")
                               if alt.strip()]),
            ("skos:definition", L(row["definition"])),
            ("ifm:codeStatus", L(row["code_status"], lang=None)),
            ("ifm:hasStage", [Ref(concept_ref("stage", f"{stream_id}-{int(st['position']):02d}"))
                              for st in stages]),
        ]))
        for stage in stages:
            position = int(stage["position"])
            blocks.append((heading, Ref(concept_ref(
                "stage", f"{stream_id}-{position:02d}")), [
                ("a", R("ifm:ValueStreamStage")),
                ("ifm:inValueStream", R(concept_ref("stream", stream_id))),
                ("ifm:position", [Lit(position, datatype="xsd:integer")]),
                ("rdfs:label", L(stage["stage_label"])),
                ("ifm:stageFunction", R(concept_ref("function", stage["function_id"]))),
                ("skos:scopeNote", L(stage["note"])),
            ]))

    heading = "Layer 3 - Use cases (sector x function intersection nodes)"
    for uc_id, row in model.use_cases.items():
        primary = model.primary_function(uc_id)
        supporting = [r["function_id"] for r in model.functions_of[uc_id]
                      if r["role"] != "primary"]
        documentation = model.documentation_iri(uc_id)
        deployment = row["deployment_evidence"].strip()
        blocks.append((heading, Ref(concept_ref("use-case", uc_id)), [
            # Not a schema:Action: these are reusable use-case definitions, not
            # occurrences of an action performed by an agent at a time.
            ("a", R("ifm:UseCase")),
            ("rdfs:label", L(row["name"])),
            ("dct:description", L(row["description"])),
            ("ifm:appliesToSector", [Ref(concept_ref("sector", s))
                                     for s in model.sectors_of[uc_id]]),
            ("ifm:primaryFunction", R(concept_ref("function", primary)) if primary else []),
            ("ifm:executesFunction", [Ref(concept_ref("function", f)) for f in supporting]),
            ("ifm:sectionScope", R(f"ifm:{model.scope_of(uc_id, 'section')}")),
            ("ifm:divisionScope", R(f"ifm:{model.scope_of(uc_id, 'division')}")),
            ("ifm:classScope", R(f"ifm:{model.scope_of(uc_id, 'class')}")),
            ("ifm:participation", [Ref(concept_ref(
                "participation", f"{uc_id}-{p['participation_id']}"))
                for p in model.participants_of[uc_id]]),
            ("ifm:reducesRelianceOn", [Ref(concept_ref("prior-evidence", e))
                                       for e in model.prior_evidence_of[uc_id]]),
            ("ifm:precondition", [Ref(concept_ref("state", st))
                                  for st in model.pre_of[uc_id]]),
            ("ifm:postcondition", [Ref(concept_ref("state", st))
                                   for st in model.post_of[uc_id]]),
            ("ifm:enables", [Ref(concept_ref("use-case", other))
                             for other in model.enables(uc_id)]),
            ("ifm:requiresUseCase", [Ref(concept_ref("use-case", r))
                                     for r in model.requires_of[uc_id]]),
            ("ifm:costValueAsymmetry", [Lit(
                "true" if model.is_asymmetric(uc_id) else "false",
                datatype="xsd:boolean")]),
            ("ifm:valueDriver", [Ref(concept_ref("driver", d))
                                 for d in model.value_drivers_of[uc_id]]),
            ("ifm:valueStream", [Ref(concept_ref("stream", vs))
                                 for vs in model.streams_of[uc_id]]),
            ("ifm:transformationMode", R(concept_ref("mode", row["transformation_mode"]))),
            ("ifm:changeMode", R(f"ifm:{(model.change_mode_of(uc_id) or '').capitalize()}")),
            ("ifm:maturity", R(f"ifm:{row['maturity']}")),
            ("ifm:documentedBy", R(f"<{documentation}>") if documentation else []),
            ("ifm:deploymentEvidence", R(f"<{deployment}>") if deployment else []),
        ]))

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

    lines += ["", "## Use cases", ""]
    for uc_id, row in model.use_cases.items():
        sector_labels = ", ".join(
            f"{model.sectors[s]['notation']} {model.label('sector', s)}"
            for s in model.sectors_of[uc_id])
        primary = model.primary_function(uc_id)
        lines.append(f"### {row['name']}")
        lines.append("")
        lines.append(f"{row['description']}")
        lines.append("")
        lines.append(f"- Sectors: {sector_labels}")
        lines.append(f"- Primary function: {model.label('function', primary)}")
        supporting = [model.label('function', r["function_id"])
                      for r in model.functions_of[uc_id] if r["role"] != "primary"]
        if supporting:
            lines.append(f"- Supporting functions: {', '.join(supporting)}")
        lines.append(f"- Scope: {scope_phrase(model, uc_id)}"
                     f" · Maturity: {row['maturity'].lower()}")
        documentation = model.documentation_iri(uc_id)
        if documentation:
            lines.append(f"- Worked flow: [{row['documented_by']}]({documentation})")
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

    cards = []
    for uc_id, row in model.use_cases.items():
        primary = model.primary_function(uc_id)
        supporting = [model.label("function", r["function_id"])
                      for r in model.functions_of[uc_id] if r["role"] != "primary"]
        sector_list = ", ".join(
            f'<span class="code">{esc(model.sectors[s]["notation"])}</span> '
            f'{esc(model.label("sector", s))}' for s in model.sectors_of[uc_id])
        documentation = model.documentation_iri(uc_id)
        link = (f'<div class="flow-link"><a href="{esc(documentation)}">Worked flow &rarr;</a></div>'
                if documentation else
                '<div class="flow-link"><span class="status">Not yet modelled</span></div>')
        scope = scope_phrase(model, uc_id)
        mode = model.modes[row["transformation_mode"]]
        change = model.change_mode_of(uc_id)
        drivers = ", ".join(esc(model.label("driver", d))
                            for d in model.value_drivers_of[uc_id])
        requires = ", ".join(esc(model.label("state", st))
                             for st in model.pre_of[uc_id]) or "&mdash; nothing"
        establishes = ", ".join(esc(model.label("state", st))
                                for st in model.post_of[uc_id])
        streams = ", ".join(esc(model.label("stream", vs))
                            for vs in model.streams_of[uc_id])
        stream_line = (f'\n          <p class="meta"><strong>Value stream:</strong> '
                       f'{streams}</p>') if streams else ""
        payers = ", ".join(esc(p["party"]) for p in model.bears_cost_without_value(uc_id))
        asym_line = (f'\n          <p class="meta asym"><strong>Recorded as bearing cost '
                     f'without direct value:</strong> {payers}</p>') if payers else ""
        cards.append(f"""      <div class="flow" id="{esc(uc_id)}">
        <div class="flow-tag">{esc(scope)} &middot; {esc(row['maturity'])}
          &middot; <span class="mode mode-{esc(change)}">{esc(mode['pref_label_en'])}</span></div>
        <div class="flow-body">
          <h3>{esc(row['name'])}</h3>
          <p>{esc(row['description'])}</p>
          <p class="meta"><strong>Sectors:</strong> {sector_list}</p>
          <p class="meta"><strong>Primary function:</strong> {esc(model.label('function', primary))}</p>
          <p class="meta"><strong>Supporting:</strong> {esc(', '.join(supporting)) or '&mdash;'}</p>
          <p class="meta"><strong>Why it pays:</strong> {drivers}</p>
          <p class="meta"><strong>Needs:</strong> {requires}</p>
          <p class="meta"><strong>Leaves:</strong> {establishes}</p>{stream_line}{asym_line}
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

    # roots: nothing here produces what they need, so the chain starts at them
    unmet = set(model.unproduced_states())
    roots = [uc for uc in model.use_cases
             if not model.pre_of[uc] or set(model.pre_of[uc]) <= unmet]

    def chain_items(uc_id, seen):
        if uc_id in seen:
            return ""
        seen = seen | {uc_id}
        children = "".join(chain_items(nxt, seen) for nxt in model.enables(uc_id))
        inner = f"<ul>{children}</ul>" if children else ""
        name = esc(model.use_cases[uc_id]["name"])
        return (f'<li><a href="#{esc(uc_id)}">{name}</a>'
                f'<span class="muted"> leaves '
                f'{esc(", ".join(model.label("state", s) for s in model.post_of[uc_id]))}'
                f'</span>{inner}</li>')

    chain_html = "\n".join(f"      {chain_items(r, frozenset())}" for r in roots)
    unmet_html = ", ".join(f"<code>{esc(s)}</code>" for s in sorted(unmet)) or "none"

    streams_html = "\n".join(
        '      <div><h3>' + esc(row["pref_label_en"]) + '</h3><ol class="stages">'
        + "".join(
            f'<li>{esc(stage["stage_label"])}'
            f'<span class="muted"> &middot; {esc(model.label("function", stage["function_id"]))}'
            f'</span></li>'
            for stage in model.stages_of[stream_id])
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
      A use case declares what must already be true to run and what is true once it
      has. The arrows below are computed from those interfaces; change a postcondition
      and the chain changes with it.
    </p>
    <ul class="chain">
{chain_html}
    </ul>
    <p class="legend">
      <strong>Unmet preconditions:</strong> {unmet_html} &mdash; required by a use case
      here and left behind by none. Each marks a flow that is outside this repository
      or not yet written down.
    </p>
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
    <h2>Why these are worth doing</h2>
    <p class="prose">
      Sector and function say where a use case sits. Neither says why applying a
      verifiable credential there is worth doing, or how far it reorganises the
      process. Those are separate axes: the same function in the same sector can sit
      at either end of both. Both vocabularies are this repository's editorial
      classifications, not external standards.
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
    <h2>Use cases</h2>
    <div class="flows">
{chr(10).join(cards)}
    </div>
  </section>

  <section>
    <h2>The graph itself</h2>
    <p class="prose">
      This page is generated from the same data as the machine-readable graph:
      SKOS concept schemes for the sector, function, state, role and credential
      layers, and <code>ifm:UseCase</code> nodes linking them. A use case is a
      reusable definition rather than a record of something performed, which is why
      it is not a <code>schema:Action</code>. Load
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

OUTPUTS = {
    "ifm-graph.ttl": build_turtle,
    "ifm-graph.jsonld": build_jsonld,
    "matrix.md": build_matrix_md,
    "index.html": build_html,
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
