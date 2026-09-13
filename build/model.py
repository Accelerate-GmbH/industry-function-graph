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
    "ifm-states": {
        "title": "States",
        "description": "What is true, or what a party holds, before and after a use "
                       "case runs. States are the interface that makes use cases "
                       "composable: one use case's postcondition is another's "
                       "precondition, so the chain can be computed from the data. "
                       "Evidence states record possession; outcome states record a "
                       "business or administrative conclusion.",
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


class Model:
    def __init__(self):
        self.sectors = {r["id"]: r for r in _read("sectors.csv")}
        self.cbf = {r["id"]: r for r in _read("cbf.csv")}
        self.apqc = {r["id"]: r for r in _read("apqc-pcf.csv")}
        self.functions = {r["id"]: r for r in _read("functions.csv")}
        self.alignments = _read("function-alignments.csv")
        self.value_drivers = {r["id"]: r for r in _read("value-drivers.csv")}
        self.value_streams = {r["id"]: r for r in _read("value-streams.csv")}
        self.states = {r["id"]: r for r in _read("states.csv")}
        self.credential_types = {r["id"]: r for r in _read("credential-types.csv")}
        self.trust_roles = {r["id"]: r for r in _read("trust-roles.csv")}
        self.prior_evidence = {r["id"]: r for r in _read("prior-evidence.csv")}
        self.stream_stages = sorted(_read("value-stream-functions.csv"),
                                    key=lambda r: (r["value_stream_id"], int(r["position"])))
        self.modes = {r["id"]: r for r in _read("transformation-modes.csv")}
        self.use_cases = {r["id"]: r for r in _read("use-cases.csv")}
        self.uc_sectors = _read("use-case-sectors.csv")
        self.uc_functions = _read("use-case-functions.csv")
        self.uc_value_drivers = _read("use-case-value-drivers.csv")
        self.uc_value_streams = _read("use-case-value-streams.csv")
        self.participation_credentials = _read("participation-credentials.csv")
        # Keyed on the participation, not on the role: one use case can hold two
        # participations with the same trust role - one party in two capacities,
        # or two parties in the same capacity - and each handles its own
        # credentials.
        self.credentials_of = {}
        for row in self.participation_credentials:
            self.credentials_of.setdefault(
                (row["use_case_id"], row["participation_id"]), []).append(row)

        self.preconditions = _read("use-case-preconditions.csv")
        self.postconditions = _read("use-case-postconditions.csv")
        self.participants = _read("use-case-participants.csv")

        self.pre_of = {uc: [] for uc in self.use_cases}
        for row in self.preconditions:
            self.pre_of.setdefault(row["use_case_id"], []).append(row["state_id"])
        self.post_of = {uc: [] for uc in self.use_cases}
        for row in self.postconditions:
            self.post_of.setdefault(row["use_case_id"], []).append(row["state_id"])
        self.uc_prior_evidence = _read("use-case-prior-evidence.csv")
        self.dependencies = _read("use-case-dependencies.csv")

        self.participants_of = {uc: [] for uc in self.use_cases}
        for row in self.participants:
            self.participants_of.setdefault(row["use_case_id"], []).append(row)
        self.prior_evidence_of = {uc: [] for uc in self.use_cases}
        for row in self.uc_prior_evidence:
            self.prior_evidence_of.setdefault(row["use_case_id"], []).append(
                row["mechanism_id"])
        self.requires_of = {uc: [] for uc in self.use_cases}
        for row in self.dependencies:
            self.requires_of.setdefault(row["use_case_id"], []).append(
                row["requires_use_case_id"])

        self.streams_of = {uc: [] for uc in self.use_cases}
        for row in self.uc_value_streams:
            self.streams_of.setdefault(row["use_case_id"], []).append(row["value_stream_id"])
        self.stages_of = {vs: [] for vs in self.value_streams}
        for row in self.stream_stages:
            self.stages_of.setdefault(row["value_stream_id"], []).append(row)

        self.value_drivers_of = {uc: [] for uc in self.use_cases}
        for row in self.uc_value_drivers:
            self.value_drivers_of.setdefault(row["use_case_id"], []).append(
                row["value_driver_id"])

        self.sectors_of = {uc: [] for uc in self.use_cases}
        for row in self.uc_sectors:
            self.sectors_of.setdefault(row["use_case_id"], []).append(row["sector_id"])
        self.functions_of = {uc: [] for uc in self.use_cases}
        for row in self.uc_functions:
            self.functions_of.setdefault(row["use_case_id"], []).append(row)

    # -- derivations ----------------------------------------------------
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

    # -- composition ----------------------------------------------------
    def enables(self, uc_id):
        """Use cases that can start because this one finished.

        Computed from the interfaces: B follows A when something A leaves true
        is something B needs. Typing the ends of each use case is what lets the
        chain be derived instead of maintained by hand.
        """
        produced = set(self.post_of.get(uc_id, []))
        return sorted(other for other in self.use_cases
                      if other != uc_id and produced & set(self.pre_of.get(other, [])))

    def unproduced_states(self):
        """States something needs and nothing here produces.

        Each is a gap: either a use case the ecosystem has not written down
        yet, or a dependency on something outside this graph.
        """
        produced = {s for states in self.post_of.values() for s in states}
        needed = {s for states in self.pre_of.values() for s in states}
        return sorted(needed - produced)

    def credential_for_state(self, state_id):
        """The credential type that provides evidence for a state, if there is one.

        Evidence, not equivalence: a state can also be established without any
        credential, and holding one does not oblige a relying party to accept it.
        """
        for key, row in self.credential_types.items():
            if row["evidences_state"] == state_id:
                return key
        return None

    def credential_actions(self, uc_id, action):
        """Credential types on which some participation performs `action`."""
        return {link["credential_type_id"]
                for (case, _part), links in self.credentials_of.items()
                if case == uc_id
                for link in links if link["action"] == action}

    def interface(self, uc_id):
        """Preconditions, postconditions and primary function, as a comparable key."""
        return (frozenset(self.pre_of.get(uc_id, [])),
                frozenset(self.post_of.get(uc_id, [])),
                self.primary_function(uc_id))

    def overlaps(self):
        """Groups of use cases with the same interface - candidates for merging."""
        groups = {}
        for uc_id in self.use_cases:
            groups.setdefault(self.interface(uc_id), []).append(uc_id)
        return [members for members in groups.values() if len(members) > 1]

    def bears_cost_without_value(self, uc_id):
        """Participants who pay for a use case without getting direct value back.

        Credential ecosystems commonly stall for a commercial reason: the cost
        of issuing falls on one party and the benefit of verifying on another.
        """
        return [p for p in self.participants_of.get(uc_id, [])
                if p["bears_cost"] == "yes" and p["gains_value"] != "direct"]

    def is_asymmetric(self, uc_id):
        """True when at least one participation bears cost without direct value.

        Derived from two editorial yes/no judgements. An indicator of where
        funding or coordination may be needed, not an economic result.
        """
        return bool(self.bears_cost_without_value(uc_id))

    def primary_function(self, uc_id):
        for row in self.functions_of.get(uc_id, []):
            if row["role"] == "primary":
                return row["function_id"]
        return None

    def documentation_iri(self, uc_id):
        """Absolute URL of the worked flow, wherever it happens to be published."""
        return self.use_cases[uc_id]["documented_by"].strip() or None

    # -- convenience ----------------------------------------------------
    def used_sections(self):
        used = {s for uc in self.use_cases for s in self.sections_of_use_case(uc)}
        return sorted(used, key=lambda s: self.sectors[s]["notation"])

    def used_functions(self):
        used = {r["function_id"] for r in self.uc_functions}
        return [f for f in self.functions if f in used]

    def cell(self, section_id, function_id, role=None):
        """Use cases sitting at the intersection of a section and a function."""
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
                 "prior-evidence": self.prior_evidence, "state": self.states,
                 "credential": self.credential_types}[kind]
        row = table.get(ident, {})
        return row.get("pref_label_en", ident)


