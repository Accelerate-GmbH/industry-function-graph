"""Load the Industry-Function Mapping CSVs into a plain-Python model.

No third-party dependencies on purpose: the CSVs are the source of truth and
anyone with a Python 3 interpreter must be able to rebuild the graph.
"""

# SPDX-License-Identifier: MIT

from __future__ import annotations

import csv
import os

# The namespace every concept is minted under. Change this one constant (and
# rebuild) to move the vocabulary to another domain — nothing else hard-codes it.
# It matches the GitHub Pages URL of this repository, so the IRIs resolve to the
# generated matrix once Pages is enabled.
BASE = "https://didas-swiss.github.io/industry-function-graph/"
ID_BASE = BASE + "id/"
ONT = BASE + "ontology#"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
GENERATED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "generated")

SCHEMES = {
    "isic-rev5": {
        "title": "ISIC Rev. 5 (sectors used by this repository)",
        "description": "Local SKOS rendering of the International Standard Industrial "
                       "Classification of All Economic Activities, Revision 5. All 22 "
                       "sections, plus the divisions and classes the mapped use cases "
                       "actually reach. ISIC is the primary scheme here. It agrees with "
                       "NOGA 2025 at section and division level: checked against the NOGA "
                       "subset codified in the DIDAS Trust Flow Diagram Repository, all 22 "
                       "section letters and all 23 of its divisions agree, with three "
                       "section titles differing in spelling only. A division number is "
                       "therefore a usable join key between this graph and a "
                       "NOGA-classified sector. The agreement does not extend below "
                       "division level.",
        "version": "Rev. 5",
        "source": "https://unstats.un.org/unsd/classifications/Econ/isic",
    },
    "cbf": {
        "title": "Classification of Business Functions (categories)",
        "description": "Business function categories following the UNECE/Eurostat "
                       "Classification of Business Functions. Labels are seeded here and "
                       "carry codeStatus 'provisional' until checked against the official "
                       "publication; no notations are invented. Core and support in CBF "
                       "are relative to the enterprise, so no IFM function is hung under "
                       "either as a broader concept.",
        "version": "edition not confirmed; check against the UN Manual on the "
                   "Classification of Business Functions",
        "source": "https://unstats.un.org/unsd/classifications/Econ/Download/"
                  "Manual_on_the_Classification_of_Business_Functions_WEB_2024-08-19.pdf",
    },
    "apqc-pcf": {
        "title": "APQC Process Classification Framework (referenced categories)",
        "description": "Only the cross-industry PCF categories an alignment actually "
                       "references. The framework itself is published by APQC and is not "
                       "redistributed here. The labels carried here follow the "
                       "13-category cross-industry structure.",
        "version": "Cross-Industry, 13-category structure; the point release these "
                   "labels were seeded from has not been confirmed against the APQC "
                   "publication",
        "source": "https://www.apqc.org/process-frameworks",
    },
    "ifm-value-drivers": {
        "title": "Value drivers",
        "description": "Why applying a verifiable credential to a function is worth "
                       "doing: what it removes, prevents or makes possible. A use case "
                       "usually has several.",
        "source": BASE,
    },
    "ifm-transformation-modes": {
        "title": "Transformation modes",
        "description": "How far the process changes. The first two are run - improving "
                       "a process that already exists. The last two are change - "
                       "reorganising it, or doing something that was not viable before. "
                       "A use case has exactly one.",
        "source": BASE,
    },
    "ifm-credential-types": {
        "title": "Credential types",
        "description": "What is actually issued as a separate artefact, held, presented "
                       "and verified. A credential type provides evidence for a state, "
                       "which connects this layer to the rest; the evidence may support "
                       "the state without being equivalent to it. A claim inside another "
                       "credential, a derived attribute or a business conclusion is not a "
                       "credential type.",
        "source": "https://www.w3.org/TR/vc-data-model-2.0/",
    },
    "ifm-conditions": {
        "title": "Conditions",
        "description": "What is true, or what a party holds, before and after a "
                       "composable element runs. Conditions are the interface that "
                       "makes use cases compose: one element's provision satisfies "
                       "another's requirement, so the chain is computed rather than "
                       "maintained. They form a subsumption lattice through "
                       "skos:broader, so an interface can be written at the level of "
                       "generality it actually needs. Evidence conditions record that "
                       "evidence is available; fact, outcome and relationship "
                       "conditions record what a relying party established on it.",
        "source": BASE,
    },
    "ifm-trust-roles": {
        "title": "Trust roles",
        "description": "Who does what in a credential exchange: issuer, holder, "
                       "verifier, relying party, trust anchor. Verifier and relying party "
                       "are separate roles that often belong to the same organisation. "
                       "Recorded per use case together with who bears the cost and who "
                       "gains the value, which are often different parties.",
        "source": BASE,
    },
    "ifm-prior-evidence": {
        "title": "Prior evidence mechanisms",
        "description": "How the same assurance is obtained today without a verifiable "
                       "credential: a paper document, a PDF, a phone call, a register "
                       "lookup, an in-person visit. Naming the mechanism is how a "
                       "friction-reduction claim becomes checkable. The entries describe "
                       "mechanisms; they do not rank them.",
        "source": BASE,
    },
    "ifm-value-streams": {
        "title": "Value streams",
        "description": "End-to-end sequences of functions that produce an outcome for "
                       "a customer or the organisation. The concept follows ArchiMate's "
                       "Value Stream element, which describes the value created rather "
                       "than the steps taken. The catalogue and the stage decomposition "
                       "are this repository's editorial models, because no openly "
                       "licensed catalogue exists; each is one modelled sequence rather "
                       "than the universal one. A function appears in several streams.",
        "source": "https://pubs.opengroup.org/architecture/archimate32-doc/",
    },
    "ifm-functions": {
        "title": "IFM operational business functions",
        "description": "The function vocabulary this repository actually maps use cases "
                       "onto. Deliberately its own scheme rather than a fork of CBF or "
                       "APQC PCF: the alignment to those is recorded as SKOS mapping "
                       "relations, so the external classifications can be swapped or "
                       "corrected without touching any use case.",
        "source": BASE,
    },
}




def _read(name):
    with open(os.path.join(DATA_DIR, name), newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _group(rows, key):
    out = {}
    for row in rows:
        out.setdefault(row[key], []).append(row)
    return out


class Model:
    """The three layers of the model, loaded and cross-indexed.

    Classification  - where a use case belongs: sector, function, value stream.
    Interface       - what can connect to it: required and provided conditions.
    Realisation     - how it is implemented: flows, credentials, participants.

    The layers are kept apart on purpose. A classification link never implies
    that two use cases compose, and a credential identifier is never the thing
    that joins them: composition runs through conditions, and a credential is
    one way of substantiating a condition.
    """

    def __init__(self):
        # -- classification ---------------------------------------------
        self.sectors = {r["id"]: r for r in _read("sectors.csv")}
        self.cbf = {r["id"]: r for r in _read("cbf.csv")}
        self.apqc = {r["id"]: r for r in _read("apqc-pcf.csv")}
        self.functions = {r["id"]: r for r in _read("functions.csv")}
        self.alignments = _read("function-alignments.csv")
        self.value_streams = {r["id"]: r for r in _read("value-streams.csv")}
        self.use_cases = {r["id"]: r for r in _read("use-cases.csv")}
        self.uc_sectors = _read("use-case-sectors.csv")
        self.uc_functions = _read("use-case-functions.csv")
        self.uc_stages = _read("use-case-stages.csv")

        self.stream_stages = sorted(_read("value-stream-stages.csv"),
                                    key=lambda r: (r["value_stream_id"], int(r["position"])))
        self.stages_of = {vs: [] for vs in self.value_streams}
        for row in self.stream_stages:
            self.stages_of.setdefault(row["value_stream_id"], []).append(row)
        self.stage_index = {(r["value_stream_id"], r["stage_id"]): r
                            for r in self.stream_stages}

        # -- interface --------------------------------------------------
        self.conditions = {r["id"]: r for r in _read("conditions.csv")}
        self.subject_roles = {r["id"]: r for r in _read("subject-roles.csv")}
        self.uc_requires = _read("use-case-requires.csv")
        self.uc_provides = _read("use-case-provides.csv")
        self.stage_requires = _read("value-stream-stage-requires.csv")
        self.stage_provides = _read("value-stream-stage-provides.csv")
        self.stream_requires = _read("value-stream-requires.csv")
        self.stream_provides = _read("value-stream-provides.csv")

        self.requires_of = {uc: [] for uc in self.use_cases}
        for row in self.uc_requires:
            self.requires_of.setdefault(row["use_case_id"], []).append(row)
        self.provides_of = {uc: [] for uc in self.use_cases}
        for row in self.uc_provides:
            self.provides_of.setdefault(row["use_case_id"], []).append(row)

        # -- realisation ------------------------------------------------
        self.credential_types = {r["id"]: r for r in _read("credential-types.csv")}
        self.credential_conditions = _read("credential-conditions.csv")
        self.trust_roles = {r["id"]: r for r in _read("trust-roles.csv")}
        self.prior_evidence = {r["id"]: r for r in _read("prior-evidence.csv")}
        self.flows = {r["id"]: r for r in _read("flows.csv")}
        self.flow_realises = sorted(_read("flow-realises.csv"),
                                    key=lambda r: (r["flow_id"], int(r["step"])))
        self.flow_participants = _read("flow-participants.csv")
        self.flow_credentials = _read("flow-credentials.csv")

        self.realises_of = {f: [] for f in self.flows}
        for row in self.flow_realises:
            self.realises_of.setdefault(row["flow_id"], []).append(row["use_case_id"])
        self.realised_by = {uc: [] for uc in self.use_cases}
        for row in self.flow_realises:
            self.realised_by.setdefault(row["use_case_id"], []).append(row["flow_id"])

        self.participants_of = {f: [] for f in self.flows}
        for row in self.flow_participants:
            self.participants_of.setdefault(row["flow_id"], []).append(row)
        # Keyed on the participation, not the role: one flow can hold two
        # participations with the same trust role - one party in two
        # capacities, or two parties in the same capacity.
        self.credentials_of = {}
        for row in self.flow_credentials:
            self.credentials_of.setdefault(
                (row["flow_id"], row["participation_id"]), []).append(row)
        self.substantiated_by = {}
        for row in self.credential_conditions:
            self.substantiated_by.setdefault(row["condition_id"], []).append(
                row["credential_type_id"])
        self.substantiates = _group(self.credential_conditions, "credential_type_id")

        # -- decision-support metadata ----------------------------------
        self.value_drivers = {r["id"]: r for r in _read("value-drivers.csv")}
        self.modes = {r["id"]: r for r in _read("transformation-modes.csv")}
        self.uc_value_drivers = _read("use-case-value-drivers.csv")
        self.uc_prior_evidence = _read("use-case-prior-evidence.csv")
        self.dependencies = _read("use-case-dependencies.csv")

        self.value_drivers_of = {uc: [] for uc in self.use_cases}
        for row in self.uc_value_drivers:
            self.value_drivers_of.setdefault(row["use_case_id"], []).append(
                row["value_driver_id"])
        self.prior_evidence_of = {uc: [] for uc in self.use_cases}
        for row in self.uc_prior_evidence:
            self.prior_evidence_of.setdefault(row["use_case_id"], []).append(
                row["mechanism_id"])
        self.depends_on = {uc: [] for uc in self.use_cases}
        for row in self.dependencies:
            self.depends_on.setdefault(row["use_case_id"], []).append(
                row["requires_use_case_id"])

        self.sectors_of = {uc: [] for uc in self.use_cases}
        for row in self.uc_sectors:
            self.sectors_of.setdefault(row["use_case_id"], []).append(row["sector_id"])
        self.functions_of = {uc: [] for uc in self.use_cases}
        for row in self.uc_functions:
            self.functions_of.setdefault(row["use_case_id"], []).append(row)
        self.stages_realised_by = {uc: [] for uc in self.use_cases}
        for row in self.uc_stages:
            self.stages_realised_by.setdefault(row["use_case_id"], []).append(
                (row["value_stream_id"], row["stage_id"]))

    # ==================================================================
    # Conditions: the subsumption lattice composition rests on
    # ==================================================================

    def condition_ancestors(self, condition_id):
        """A condition and every condition it is narrower than.

        Walking up is what lets a use case providing a specific condition
        satisfy another that asks for a general one: an upper-secondary
        qualification is education qualification evidence, so a flow issuing
        one can feed a flow that asks only for the latter.
        """
        seen, out, current = set(), [], condition_id
        while current and current not in seen:
            seen.add(current)
            out.append(current)
            row = self.conditions.get(current)
            if row is None:
                return out
            current = row["broader"] or None
        return out

    def condition_descendants(self, condition_id):
        """A condition and every condition narrower than it."""
        out = {condition_id}
        changed = True
        while changed:
            changed = False
            for cid, row in self.conditions.items():
                if row["broader"] in out and cid not in out:
                    out.add(cid)
                    changed = True
        return out

    def condition_satisfies(self, provided_id, required_id):
        """Does providing `provided_id` satisfy a requirement for `required_id`?

        True when they are the same condition, or when the provided one is
        narrower. Never the other way round: providing "identity evidence is
        available" does not satisfy a requirement for the state e-ID
        specifically.
        """
        return required_id in self.condition_ancestors(provided_id)

    def satisfies(self, provision, requirement):
        """Does one provision satisfy one requirement, across every dimension?

        Condition compatibility is the core test. The other dimensions narrow
        it, and each is checked only when the requirement states it, so an
        interface stays as loose as its author left it.
        """
        if not self.condition_satisfies(provision["condition_id"],
                                        requirement["condition_id"]):
            return False
        # Subject role: a requirement about an organisation is not met by a
        # provision about a natural person.
        wanted_role = requirement.get("subject_role", "").strip()
        given_role = provision.get("subject_role", "").strip()
        if wanted_role and given_role and wanted_role != given_role:
            return False
        # Evidence type: only where the requirement names one. A requirement
        # that names no credential accepts any evidence for the condition.
        wanted_evidence = requirement.get("evidence_type", "").strip()
        if wanted_evidence:
            given_evidence = provision.get("evidence_type", "").strip()
            if given_evidence and given_evidence != wanted_evidence:
                return False
            if not given_evidence:
                # The provision names no credential, so it can still satisfy
                # the requirement if the condition it provides is one the
                # wanted credential substantiates.
                if provision["condition_id"] not in self.substantiated_by.get(
                        wanted_evidence, []) and wanted_evidence not in [
                        c for c in self.substantiated_by
                        if provision["condition_id"] in
                        self.substantiated_by.get(c, [])]:
                    return False
        return self.context_compatible(provision.get("context", ""),
                                       requirement.get("context", ""))

    @staticmethod
    def parse_context(text):
        """`key=value; key=value` into a dict. Empty means "no constraint"."""
        out = {}
        for clause in (text or "").split(";"):
            clause = clause.strip()
            if not clause or "=" not in clause:
                continue
            key, value = clause.split("=", 1)
            out[key.strip()] = value.strip()
        return out

    def context_compatible(self, provided, required):
        """Every constraint the requirement states must be met by the provision.

        A requirement that states nothing is met by anything, and a provision
        that states nothing is assumed to be unconstrained. That is the loosest
        reading, and it is the right default while the context vocabulary is
        still small: the shape is here so jurisdiction, assurance level or
        governing authority can be added without changing the interface model.
        """
        wanted = self.parse_context(required)
        if not wanted:
            return True
        given = self.parse_context(provided)
        for key, value in wanted.items():
            if key in given and given[key] != value:
                return False
        return True

    # ==================================================================
    # Composition
    # ==================================================================

    def suppliers_for(self, uc_id):
        """{requirement_id: [(supplier use case, its provision), ...]}.

        Query 5: which existing use cases can satisfy A's requirements.
        """
        out = {}
        for requirement in self.requires_of.get(uc_id, []):
            matches = []
            for other in self.use_cases:
                if other == uc_id:
                    continue
                for provision in self.provides_of.get(other, []):
                    if self.satisfies(provision, requirement):
                        matches.append((other, provision))
            out[requirement["requirement_id"]] = matches
        return out

    def consumers_of(self, uc_id):
        """{provision_id: [(consumer use case, its requirement), ...]}.

        Query 6: which use cases can consume A's outputs.
        """
        out = {}
        for provision in self.provides_of.get(uc_id, []):
            matches = []
            for other in self.use_cases:
                if other == uc_id:
                    continue
                for requirement in self.requires_of.get(other, []):
                    if self.satisfies(provision, requirement):
                        matches.append((other, requirement))
            out[provision["provision_id"]] = matches
        return out

    def enables(self, uc_id):
        """Use cases that can start because this one finished. Derived.

        The composition edge of the graph. It runs on condition compatibility,
        so an upstream use case that provides something narrower than what a
        downstream one asks for is still recognised as feeding it.
        """
        out = set()
        for matches in self.consumers_of(uc_id).values():
            out.update(other for other, _requirement in matches)
        return sorted(out)

    def unmet_requirements(self):
        """Requirements no use case here can satisfy. Query 7."""
        out = []
        for uc_id in self.use_cases:
            for requirement_id, matches in self.suppliers_for(uc_id).items():
                if not matches:
                    out.append((uc_id, requirement_id))
        return sorted(out)

    def unconsumed_provisions(self):
        """Outputs no use case here consumes. Query 8."""
        out = []
        for uc_id in self.use_cases:
            for provision_id, matches in self.consumers_of(uc_id).items():
                if not matches:
                    out.append((uc_id, provision_id))
        return sorted(out)

    def composition_paths(self, start_condition, goal_condition, limit=12):
        """Chains of use cases leading from a condition to a wanted one. Query 14.

        Breadth-first over the conditions true so far: a use case can run once
        every one of its requirements is satisfied by something already true,
        and running it adds what it provides.
        """
        start = frozenset(self.condition_ancestors(start_condition))
        queue, paths, seen = [(start, [])], [], {start}
        while queue:
            held, chain = queue.pop(0)
            if goal_condition in held:
                if self._minimal(start, chain, goal_condition):
                    paths.append(chain)
                    if len(paths) >= limit:
                        break
                continue
            for uc_id in self.use_cases:
                if uc_id in chain:
                    continue
                if not self.runnable(uc_id, held):
                    continue
                gained = set(held)
                for provision in self.provides_of.get(uc_id, []):
                    gained.update(self.condition_ancestors(provision["condition_id"]))
                gained = frozenset(gained)
                if gained in seen:
                    continue
                seen.add(gained)
                queue.append((gained, chain + [uc_id]))
        return paths

    def _minimal(self, start, chain, goal_condition):
        """Does every step in the chain earn its place?

        Breadth-first search finds the shortest chain first but then keeps
        finding longer ones that reach the goal with a detour bolted on. A
        chain is reported only if dropping any one of its steps breaks it.
        """
        for index in range(len(chain)):
            shorter = chain[:index] + chain[index + 1:]
            held = set(start)
            for uc_id in shorter:
                if not self.runnable(uc_id, held):
                    break
                for provision in self.provides_of.get(uc_id, []):
                    held.update(self.condition_ancestors(provision["condition_id"]))
            else:
                if goal_condition in held:
                    return False
        return True

    def runnable(self, uc_id, held_conditions):
        """Is every requirement of this use case met by the conditions held?"""
        for requirement in self.requires_of.get(uc_id, []):
            wanted = requirement["condition_id"]
            if not any(wanted in self.condition_ancestors(c) for c in held_conditions):
                return False
        return True

    # ==================================================================
    # Interface comparison and overlap
    # ==================================================================

    def principal_outcome(self, uc_id):
        for provision in self.provides_of.get(uc_id, []):
            if provision.get("principal") == "yes":
                return provision["condition_id"]
        return None

    def primary_function(self, uc_id):
        for row in self.functions_of.get(uc_id, []):
            if row["role"] == "primary":
                return row["function_id"]
        return None

    def _condition_set(self, rows):
        return frozenset(r["condition_id"] for r in rows)

    def _relation(self, left, right):
        """How two condition sets relate, read through the subsumption lattice."""
        if left == right:
            return "same"
        left_covers_right = all(
            any(self.condition_satisfies(a, b) for a in left) for b in right)
        right_covers_left = all(
            any(self.condition_satisfies(b, a) for b in right) for a in left)
        if left_covers_right and right_covers_left:
            return "same"
        if left_covers_right:
            return "narrower"
        if right_covers_left:
            return "broader"
        if left & right:
            return "partial"
        return "distinct"

    def compare(self, first, second):
        """Classify how two use cases relate. Query 9.

        Reported for editorial review, never acted on: two use cases with the
        same shape may still be genuinely different work.
        """
        if self.primary_function(first) != self.primary_function(second):
            return "distinct"
        requires = self._relation(self._condition_set(self.requires_of.get(first, [])),
                                  self._condition_set(self.requires_of.get(second, [])))
        provides = self._relation(self._condition_set(self.provides_of.get(first, [])),
                                  self._condition_set(self.provides_of.get(second, [])))
        if requires == "same" and provides == "same":
            return "duplicate"
        if requires in {"same", "narrower"} and provides in {"same", "narrower"}:
            return "specialisation"
        if requires in {"same", "broader"} and provides in {"same", "broader"}:
            return "generalisation"
        # Only when neither end relates at all are they plainly different work.
        # Two use cases under one primary function that share an entry condition
        # but diverge afterwards are a candidate worth a human look: the
        # divergence may be a real distinction or an accident of drafting.
        if requires == "distinct" and provides == "distinct":
            return "distinct"
        return "overlap"

    def overlaps(self):
        """Candidate overlaps, most similar first. Never merged automatically."""
        rank = {"duplicate": 0, "specialisation": 1, "generalisation": 2, "overlap": 3}
        out = []
        ids = list(self.use_cases)
        for i, first in enumerate(ids):
            for second in ids[i + 1:]:
                verdict = self.compare(first, second)
                if verdict != "distinct":
                    out.append((verdict, first, second))
        return sorted(out, key=lambda row: (rank[row[0]], row[1], row[2]))

    # ==================================================================
    # Classification derivations
    # ==================================================================

    def section_of(self, sector_id):
        """Walk skos:broader up to the ISIC section a sector sits under."""
        seen = set()
        current = sector_id
        while current and current not in seen:
            seen.add(current)
            row = self.sectors.get(current)
            if row is None:
                return None
            if row["level"] == "section":
                return current
            current = row["broader"] or None
        return None

    def sections_of_use_case(self, uc_id):
        out = []
        for sector_id in self.sectors_of.get(uc_id, []):
            section = self.section_of(sector_id)
            if section and section not in out:
                out.append(section)
        return sorted(out, key=lambda s: self.sectors[s]["notation"])

    def divisions_of_use_case(self, uc_id):
        """(divisions reached, spans a whole section).

        A class contributes its parent division. A link to a whole section
        reaches every division under it, which the second element records
        because the set of those divisions is not enumerated here.
        """
        divisions, whole_section = [], False
        for sector_id in self.sectors_of.get(uc_id, []):
            row = self.sectors.get(sector_id)
            if row is None:
                continue
            if row["level"] == "section":
                whole_section = True
            elif row["level"] == "division":
                divisions.append(sector_id)
            elif row["level"] == "class" and row["broader"]:
                divisions.append(row["broader"])
        return sorted(set(divisions)), whole_section

    def classes_of_use_case(self, uc_id):
        """(classes reached, spans a whole section or division)."""
        classes, whole = [], False
        for sector_id in self.sectors_of.get(uc_id, []):
            row = self.sectors.get(sector_id)
            if row is None:
                continue
            if row["level"] == "class":
                classes.append(sector_id)
            else:
                whole = True
        return sorted(set(classes)), whole

    def scope_of(self, uc_id, level):
        """Cross or single at one ISIC level.

        Derived per level rather than as one flag. "Cross-sector" in ordinary
        usage and "more than one ISIC section" are different claims: banking and
        insurance are different industries inside section L, and a use case
        covering both is single-section but cross-division.
        """
        if level == "section":
            wide = len(self.sections_of_use_case(uc_id)) > 1
            return "CrossSection" if wide else "SingleSection"
        if level == "division":
            divisions, whole_section = self.divisions_of_use_case(uc_id)
            wide = whole_section or len(divisions) > 1
            return "CrossDivision" if wide else "SingleDivision"
        if level == "class":
            classes, whole = self.classes_of_use_case(uc_id)
            wide = whole or len(classes) > 1
            return "CrossClass" if wide else "SingleClass"
        raise ValueError(f"unknown classification level {level!r}")

    def change_mode_of(self, uc_id):
        """run or change - derived from the transformation mode, not typed in."""
        mode = self.modes.get(self.use_cases[uc_id]["transformation_mode"])
        return mode["change_mode"] if mode else None

    # ==================================================================
    # Realisation queries
    # ==================================================================

    def credentials_for_condition(self, condition_id):
        """Credential types that can substantiate a condition. Query 11.

        Includes credentials recorded against a narrower condition: a
        credential proving an upper-secondary qualification is acceptable
        evidence wherever education qualification evidence is asked for.
        """
        out = set()
        for narrower in self.condition_descendants(condition_id):
            out.update(self.substantiated_by.get(narrower, []))
        return sorted(out)

    def credential_actions(self, flow_id, action):
        """Credential types on which some participation performs `action`."""
        return {link["credential_type_id"]
                for (flow, _part), links in self.credentials_of.items()
                if flow == flow_id
                for link in links if link["action"] == action}

    def issued_credentials(self):
        return {c for f in self.flows for c in self.credential_actions(f, "issues")}

    def consumed_credentials(self):
        return {c for f in self.flows for c in self.credential_actions(f, "verifies")}

    def unrealised_use_cases(self):
        """Canonical use cases no flow implements. Query 10, inverted."""
        return sorted(uc for uc in self.use_cases if not self.realised_by.get(uc))

    def unrealised_stages(self):
        """Value stream stages no use case realises. Query 12."""
        claimed = {pair for pairs in self.stages_realised_by.values() for pair in pairs}
        return sorted(key for key in self.stage_index if key not in claimed)

    def flows_of_use_case(self, uc_id):
        """Real implementations realising a canonical use case. Query 10."""
        return sorted(self.realised_by.get(uc_id, []))

    def bears_cost_without_value(self, flow_id):
        """Participants who pay for a flow without getting direct value back."""
        return [p for p in self.participants_of.get(flow_id, [])
                if p["bears_cost"] == "yes" and p["gains_value"] != "direct"]

    def is_asymmetric(self, flow_id):
        """True when at least one participation bears cost without direct value.

        Derived from two editorial yes/no judgements. An indicator of where
        funding or coordination may be needed, not an economic result.
        """
        return bool(self.bears_cost_without_value(flow_id))

    def documentation_iri(self, flow_id):
        """Absolute URL of the worked flow, wherever it happens to be published."""
        return self.flows[flow_id]["documented_by"].strip() or None

    def sectors_of_use_case_via_flows(self, uc_id):
        """Sector contexts the flows realising this use case actually run in."""
        out = []
        for flow_id in self.realised_by.get(uc_id, []):
            sector = self.flows[flow_id]["sector_id"].strip()
            if sector and sector not in out:
                out.append(sector)
        return out

    # ==================================================================
    # Convenience
    # ==================================================================

    def used_sections(self):
        used = {s for uc in self.use_cases for s in self.sections_of_use_case(uc)}
        return sorted(used, key=lambda s: self.sectors[s]["notation"])

    def used_functions(self):
        used = {r["function_id"] for r in self.uc_functions}
        return [f for f in self.functions if f in used]

    def cell(self, section_id, function_id, role=None):
        """Use cases sitting at the intersection of a section and a function.

        Query 1, in the form the matrix needs it.
        """
        out = []
        for uc in self.use_cases:
            if section_id not in self.sections_of_use_case(uc):
                continue
            for row in self.functions_of.get(uc, []):
                if row["function_id"] == function_id and (role is None or row["role"] == role):
                    out.append(uc)
                    break
        return out

    def label(self, kind, ident):
        table = {"sector": self.sectors, "function": self.functions,
                 "cbf": self.cbf, "apqc-pcf": self.apqc,
                 "driver": self.value_drivers, "mode": self.modes,
                 "stream": self.value_streams, "role": self.trust_roles,
                 "prior-evidence": self.prior_evidence, "condition": self.conditions,
                 "credential": self.credential_types, "use-case": self.use_cases,
                 "flow": self.flows, "subject-role": self.subject_roles}[kind]
        row = table.get(ident, {})
        return row.get("pref_label_en") or row.get("name") or ident
