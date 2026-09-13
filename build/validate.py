#!/usr/bin/env python3
"""Integrity checks for the Industry-Function Mapping data.

    python3 build/validate.py

Catches the mistakes a growing mapping actually makes: a use case pointing at a
sector code that was renamed, two primary functions, an ISIC class filed under
the wrong division, a documentation link to a directory that has since moved.

Exits non-zero on any error. Warnings never fail the build.
"""

# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model import Model  # noqa: E402

# Division and class ids deliberately omit the section letter: letters move
# between ISIC revisions (finance K->L, education P->Q, health Q->R from Rev. 4
# to Rev. 5) while the numbers hold, so an id keyed on the letter would have to
# be rewritten every revision.
SECTOR_ID = re.compile(r"^ISIC-([A-V]|\d{2}|\d{4})$")
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CODE_STATUS = {"verified", "provisional"}
# The concept's own provenance and the confidence of a mapping onto it are
# separate questions: a mapping onto a verified concept can still be editorial.
MAPPING_STATUS = {"editorial", "verified"}
MATURITY = {"Exploratory", "Modelled", "Live"}
CHANGE_MODE = {"run", "change"}
BEARS_COST = {"yes", "no"}
STATE_KIND = {"evidence", "outcome"}

# The credential lifecycle, and which trust role may perform each stage. A role
# never borrows another role's action: where one organisation issues and also
# verifies, that is two participations, not one participation with two verbs.
CREDENTIAL_ACTIONS = {"issues", "holds", "presents", "verifies"}
ACTIONS_BY_ROLE = {
    "issuer": {"issues"},
    "holder": {"holds", "presents"},
    "verifier": {"verifies"},
    # A relying party acts on the outcome of verification rather than on the
    # credential; a trust anchor publishes the information verification rests on.
    "relying-party": set(),
    "trust-anchor": set(),
}
GAINS_VALUE = {"direct", "indirect", "none"}
MATCH_TYPES = {"exactMatch", "closeMatch", "broadMatch", "narrowMatch", "relatedMatch"}
DOC_URL = re.compile(r"^https://\S+$")

errors: list[str] = []
warnings: list[str] = []


def error(message):
    errors.append(message)


def warn(message):
    warnings.append(message)


def check_sectors(model):
    for sector_id, row in model.sectors.items():
        where = f"sectors.csv[{sector_id}]"
        if not SECTOR_ID.match(sector_id):
            error(f"{where}: id must look like ISIC-C, ISIC-C-30 or ISIC-C-3030")
        if row["code_status"] not in CODE_STATUS:
            error(f"{where}: code_status {row['code_status']!r} not in {sorted(CODE_STATUS)}")

        level, notation, broader = row["level"], row["notation"], row["broader"]
        if broader and broader not in model.sectors:
            error(f"{where}: broader {broader!r} does not exist")
            continue

        if level == "section":
            if not re.fullmatch(r"[A-V]", notation):
                error(f"{where}: a section notation must be one letter A-V, got {notation!r}")
            if broader:
                error(f"{where}: a section must not have a broader concept")
            if row["nace_rev21"] != notation:
                error(f"{where}: NACE Rev. 2.1 and ISIC Rev. 5 are identical at section "
                      f"level, expected nace_rev21={notation!r}")
        elif level == "division":
            if not re.fullmatch(r"\d{2}", notation):
                error(f"{where}: a division notation must be two digits, got {notation!r}")
            if not broader or model.sectors[broader]["level"] != "section":
                error(f"{where}: a division must sit directly under a section")
            if row["nace_rev21"] and row["nace_rev21"] != notation:
                error(f"{where}: NACE Rev. 2.1 and ISIC Rev. 5 are identical at division "
                      f"level, expected nace_rev21={notation!r} or empty")
        elif level == "class":
            if not re.fullmatch(r"\d{4}", notation):
                error(f"{where}: a class notation must be four digits, got {notation!r}")
            if not broader or model.sectors[broader]["level"] != "division":
                error(f"{where}: a class must sit directly under a division")
            elif not notation.startswith(model.sectors[broader]["notation"]):
                error(f"{where}: class {notation} is not inside division "
                      f"{model.sectors[broader]['notation']}")
            if row["nace_rev21"]:
                error(f"{where}: ISIC and NACE diverge below division level; "
                      f"nace_rev21 must be empty at class level")
        else:
            error(f"{where}: unknown level {level!r}")

        if model.section_of(sector_id) is None:
            error(f"{where}: does not resolve to an ISIC section (broken or cyclic broader)")


def check_functions(model):
    aligned = {a["function_id"] for a in model.alignments}
    for function_id, row in model.functions.items():
        where = f"functions.csv[{function_id}]"
        if not SLUG.match(function_id):
            error(f"{where}: id must be a lower-case slug")
        if not row["definition"].strip():
            error(f"{where}: a function without a definition cannot be mapped consistently")
        if row["broader"] and row["broader"] not in model.functions:
            error(f"{where}: broader {row['broader']!r} does not exist")
        if function_id not in aligned:
            warn(f"{where}: no alignment to CBF or APQC PCF — the function is an island")

    for cbf_id, row in model.cbf.items():
        if row["broader"] and row["broader"] not in model.cbf:
            error(f"cbf.csv[{cbf_id}]: broader {row['broader']!r} does not exist")
        if row["code_status"] not in CODE_STATUS:
            error(f"cbf.csv[{cbf_id}]: bad code_status {row['code_status']!r}")


def check_alignments(model):
    targets = {"cbf": model.cbf, "apqc-pcf": model.apqc}
    seen = set()
    for index, row in enumerate(model.alignments, start=2):
        where = f"function-alignments.csv:{index}"
        if row["function_id"] not in model.functions:
            error(f"{where}: unknown function {row['function_id']!r}")
        if row["target_scheme"] not in targets:
            error(f"{where}: unknown target_scheme {row['target_scheme']!r}")
        elif row["target_id"] not in targets[row["target_scheme"]]:
            error(f"{where}: {row['target_id']!r} is not in scheme {row['target_scheme']}")
        if row["match_type"] not in MATCH_TYPES:
            error(f"{where}: match_type {row['match_type']!r} is not a SKOS mapping relation")
        if row["mapping_status"] not in MAPPING_STATUS:
            error(f"{where}: mapping_status {row['mapping_status']!r} not in "
                  f"{sorted(MAPPING_STATUS)}")
        # CBF's core/support split is relative to the enterprise, not to the
        # activity, so a context-free hierarchical mapping onto it would bake one
        # enterprise's viewpoint into the vocabulary.
        if (row["target_id"] in {"CBF-CORE", "CBF-SUP"}
                and row["match_type"] in {"broadMatch", "narrowMatch"}):
            error(f"{where}: {row['target_id']} is enterprise-relative; a hierarchical "
                  f"mapping onto it asserts a core/support classification that the "
                  f"function itself does not carry. Use closeMatch or relatedMatch, "
                  f"with the reasoning in `note`")
        if row["match_type"] != "relatedMatch" and not row["note"].strip():
            error(f"{where}: a {row['match_type']} needs a note saying why the two "
                  f"concepts are that close")
        key = (row["function_id"], row["target_scheme"], row["target_id"])
        if key in seen:
            error(f"{where}: duplicate alignment {key}")
        seen.add(key)


def check_axes(model):
    """The two axes layered on the use case: why, and how far."""
    for driver_id, row in model.value_drivers.items():
        if not SLUG.match(driver_id):
            error(f"value-drivers.csv[{driver_id}]: id must be a lower-case slug")
        if not row["definition"].strip():
            error(f"value-drivers.csv[{driver_id}]: a driver needs a definition, or "
                  f"two people will apply it differently")
    for mode_id, row in model.modes.items():
        if not SLUG.match(mode_id):
            error(f"transformation-modes.csv[{mode_id}]: id must be a lower-case slug")
        if row["change_mode"] not in CHANGE_MODE:
            error(f"transformation-modes.csv[{mode_id}]: change_mode "
                  f"{row['change_mode']!r} not in {sorted(CHANGE_MODE)}")

    for index, row in enumerate(model.uc_value_drivers, start=2):
        where = f"use-case-value-drivers.csv:{index}"
        if row["use_case_id"] not in model.use_cases:
            error(f"{where}: unknown use case {row['use_case_id']!r}")
        if row["value_driver_id"] not in model.value_drivers:
            error(f"{where}: unknown value driver {row['value_driver_id']!r}")

    used = {r["value_driver_id"] for r in model.uc_value_drivers}
    unused = [d for d in model.value_drivers if d not in used]
    if unused:
        warn(f"{len(unused)} of {len(model.value_drivers)} value drivers are not yet "
             f"claimed by a use case: {', '.join(unused)}")
    for mode_id in model.modes:
        if not any(uc["transformation_mode"] == mode_id for uc in model.use_cases.values()):
            warn(f"transformation-modes.csv[{mode_id}]: no use case is classified here")


def check_value_streams(model):
    for stream_id, row in model.value_streams.items():
        where = f"value-streams.csv[{stream_id}]"
        if not SLUG.match(stream_id):
            error(f"{where}: id must be a lower-case slug")
        if not row["definition"].strip():
            error(f"{where}: a stream needs a definition saying what it covers")
        if row["code_status"] not in CODE_STATUS:
            error(f"{where}: bad code_status {row['code_status']!r}")

        stages = model.stages_of.get(stream_id, [])
        if not stages:
            error(f"{where}: no stages. A value stream is defined by its sequence")
            continue
        positions = [int(st["position"]) for st in stages]
        if positions != list(range(1, len(positions) + 1)):
            error(f"{where}: stage positions must run 1..n with no gaps, got {positions}")
        seen: set[str] = set()
        for stage in stages:
            stage_where = f"{where} stage {stage['position']}"
            if stage["function_id"] not in model.functions:
                error(f"{stage_where}: unknown function {stage['function_id']!r}")
            if not stage["stage_label"].strip():
                error(f"{stage_where}: needs a label saying what happens there")
            if stage["function_id"] in seen:
                warn(f"{stage_where}: {stage['function_id']} appears twice in this stream")
            seen.add(stage["function_id"])

    for index, row in enumerate(model.uc_value_streams, start=2):
        where = f"use-case-value-streams.csv:{index}"
        if row["use_case_id"] not in model.use_cases:
            error(f"{where}: unknown use case {row['use_case_id']!r}")
        if row["value_stream_id"] not in model.value_streams:
            error(f"{where}: unknown value stream {row['value_stream_id']!r}")

    placed = {r["value_stream_id"] for r in model.uc_value_streams}
    empty = [v for v in model.value_streams if v not in placed]
    if empty:
        warn(f"{len(empty)} of {len(model.value_streams)} value streams have no use case "
             f"in them yet: {', '.join(empty)}")


def check_states(model):
    for state_id, row in model.states.items():
        if not SLUG.match(state_id):
            error(f"states.csv[{state_id}]: id must be a lower-case slug")
        if not row["definition"].strip():
            error(f"states.csv[{state_id}]: needs a definition. Without one there is "
                  f"no way to tell whether the state holds")
        if row["kind"] not in STATE_KIND:
            error(f"states.csv[{state_id}]: kind {row['kind']!r} not in "
                  f"{sorted(STATE_KIND)}. An evidence state records possession; an "
                  f"outcome state records a business or administrative conclusion")

    for table, name in ((model.preconditions, "use-case-preconditions.csv"),
                        (model.postconditions, "use-case-postconditions.csv")):
        for index, row in enumerate(table, start=2):
            where = f"{name}:{index}"
            if row["use_case_id"] not in model.use_cases:
                error(f"{where}: unknown use case {row['use_case_id']!r}")
            if row["state_id"] not in model.states:
                error(f"{where}: unknown state {row['state_id']!r}")

    for uc_id in model.use_cases:
        if not model.post_of.get(uc_id):
            error(f"use-cases.csv[{uc_id}]: no postcondition. Nothing can follow a use "
                  f"case that leaves no state behind")
        overlap = set(model.pre_of.get(uc_id, [])) & set(model.post_of.get(uc_id, []))
        if overlap:
            warn(f"use-cases.csv[{uc_id}]: {', '.join(sorted(overlap))} is both a pre- "
                 f"and a postcondition. Deliberate for a refresh, a mistake otherwise")

    # An asserted dependency has to be justified by the interfaces, or one of
    # the two is wrong and it is worth knowing which.
    for index, row in enumerate(model.dependencies, start=2):
        a, b = row["use_case_id"], row["requires_use_case_id"]
        if a in model.use_cases and b in model.use_cases:
            if not (set(model.post_of.get(b, [])) & set(model.pre_of.get(a, []))):
                error(f"use-case-dependencies.csv:{index}: {a} is declared to require "
                      f"{b}, but nothing {b} leaves true is anything {a} needs. Either "
                      f"the dependency is wrong or the states are")

    unproduced = model.unproduced_states()
    if unproduced:
        warn(f"{len(unproduced)} state(s) are required by a use case here and left "
             f"behind by none: {', '.join(unproduced)}. Each marks a flow that is "
             f"outside this repository or not yet written down")

    for group in model.overlaps():
        warn(f"same interface, so possibly one use case rather than "
             f"{len(group)}: {', '.join(group)}")


def check_trust_roles(model):
    for table, name in ((model.trust_roles, "trust-roles.csv"),
                        (model.prior_evidence, "prior-evidence.csv")):
        for key, row in table.items():
            if not SLUG.match(key):
                error(f"{name}[{key}]: id must be a lower-case slug")
            if not row["definition"].strip():
                error(f"{name}[{key}]: needs a definition")

    for role_id in model.trust_roles:
        if role_id not in ACTIONS_BY_ROLE:
            error(f"trust-roles.csv[{role_id}]: no credential actions are declared for "
                  f"this role in build/validate.py. Add it to ACTIONS_BY_ROLE, with an "
                  f"empty set if the role handles no credential itself")

    for index, row in enumerate(model.participants, start=2):
        where = f"use-case-participants.csv:{index}"
        if row["use_case_id"] not in model.use_cases:
            error(f"{where}: unknown use case {row['use_case_id']!r}")
        if not SLUG.match(row["participation_id"]):
            error(f"{where}: participation_id must be a lower-case slug")
        if row["role_id"] not in model.trust_roles:
            error(f"{where}: unknown trust role {row['role_id']!r}")
        if not row["party"].strip():
            error(f"{where}: `party` is required - name the kind of organisation")
        if row["bears_cost"] not in BEARS_COST:
            error(f"{where}: bears_cost {row['bears_cost']!r} not in {sorted(BEARS_COST)}")
        if row["gains_value"] not in GAINS_VALUE:
            error(f"{where}: gains_value {row['gains_value']!r} not in {sorted(GAINS_VALUE)}")

    # A participation is identified within its use case, not by its role, so
    # that one party in two capacities is two participations rather than one
    # participation borrowing a second role's actions.
    seen = set()
    for row in model.participants:
        key = (row["use_case_id"], row["participation_id"])
        if key in seen:
            error(f"use-case-participants.csv: {row['use_case_id']} uses the "
                  f"participation id {row['participation_id']!r} twice")
        seen.add(key)

    for index, row in enumerate(model.uc_prior_evidence, start=2):
        where = f"use-case-prior-evidence.csv:{index}"
        if row["use_case_id"] not in model.use_cases:
            error(f"{where}: unknown use case {row['use_case_id']!r}")
        if row["mechanism_id"] not in model.prior_evidence:
            error(f"{where}: unknown prior evidence mechanism {row['mechanism_id']!r}")


def check_credentials(model):
    for cred_id, row in model.credential_types.items():
        where = f"credential-types.csv[{cred_id}]"
        if not SLUG.match(cred_id):
            error(f"{where}: id must be a lower-case slug")
        if not row["definition"].strip():
            error(f"{where}: needs a definition")
        if row["code_status"] not in CODE_STATUS:
            error(f"{where}: bad code_status {row['code_status']!r}")
        if not row["format"].strip():
            error(f"{where}: `format` is required - a credential with no format cannot "
                  f"be implemented")
        state = row["evidences_state"]
        if state and state not in model.states:
            error(f"{where}: evidences_state {state!r} is not in states.csv")

    claimed = {}
    for cred_id, row in model.credential_types.items():
        state = row["evidences_state"]
        if state:
            claimed.setdefault(state, []).append(cred_id)
    for state, creds in claimed.items():
        if len(creds) > 1:
            warn(f"states.csv[{state}]: evidenced by {len(creds)} credential types "
                 f"({', '.join(creds)}). Two credentials for one state means either the "
                 f"state is too coarse or one of them is redundant")

    role_of = {(p["use_case_id"], p["participation_id"]): p["role_id"]
               for p in model.participants}
    for index, row in enumerate(model.participation_credentials, start=2):
        where = f"participation-credentials.csv:{index}"
        if row["credential_type_id"] not in model.credential_types:
            error(f"{where}: unknown credential type {row['credential_type_id']!r}")
        if row["action"] not in CREDENTIAL_ACTIONS:
            error(f"{where}: action {row['action']!r} not in {sorted(CREDENTIAL_ACTIONS)}")
            continue
        key = (row["use_case_id"], row["participation_id"])
        role = role_of.get(key)
        if role is None:
            error(f"{where}: {row['use_case_id']} has no participation "
                  f"{row['participation_id']!r} to attach a credential to")
            continue
        # The heart of the trust-role model: a role performs its own action and
        # no other. One party acting in two roles is two participations.
        allowed = ACTIONS_BY_ROLE.get(role, set())
        if row["action"] not in allowed:
            expected = (f"only {' and '.join(sorted(allowed))}" if allowed
                        else "no credential action at all")
            error(f"{where}: the {role} participation {row['participation_id']!r} is "
                  f"recorded as {row['action']!r}, but a {role} performs {expected}. If "
                  f"one party acts in two roles here, give it a second participation in "
                  f"use-case-participants.csv rather than letting one role borrow "
                  f"another's action")

    check_credential_lifecycle(model)
    check_credential_supply(model)


def check_credential_lifecycle(model):
    """Issued, held, presented, verified - and no half of a pair on its own.

    A use case may cover any part of the lifecycle. What it may not do is record
    one side of an exchange without the other: a credential verified inside a use
    case has to have been presented inside it, and one issued has to land with a
    holder.
    """
    for uc_id in model.use_cases:
        where = f"use-cases.csv[{uc_id}]"
        issued = model.credential_actions(uc_id, "issues")
        held = model.credential_actions(uc_id, "holds")
        presented = model.credential_actions(uc_id, "presents")
        verified = model.credential_actions(uc_id, "verifies")

        for cred in sorted(verified - presented):
            error(f"{where}: {cred} is verified here but never presented. Record the "
                  f"holder's presentation, or move the verification to the use case "
                  f"where the presentation happens")
        for cred in sorted(presented - verified):
            error(f"{where}: {cred} is presented here but nobody verifies it. A "
                  f"presentation with no verifier is not an exchange")
        for cred in sorted(issued - held):
            error(f"{where}: {cred} is issued here but no holder takes possession of "
                  f"it. Record the holder's `holds`, or the credential goes nowhere")
        for cred in sorted(held - issued):
            error(f"{where}: {cred} is held here but nothing issues it. `holds` marks "
                  f"the use case where possession begins; a credential obtained "
                  f"elsewhere and used here records `presents` alone")
        # Issuing the evidence for a state the same use case demands first is a
        # lifecycle contradiction: the issuing step is a separate use case.
        for state in model.pre_of.get(uc_id, []):
            cred = model.credential_for_state(state)
            if cred and cred in issued:
                error(f"{where}: requires {state} as a precondition and also issues "
                      f"{cred}, the credential that evidences it. The issuing step "
                      f"belongs in its own use case")


def check_credential_supply(model):
    """Credentials nothing issues, and preconditions nobody checks."""
    issued_anywhere = {link["credential_type_id"]
                       for links in model.credentials_of.values()
                       for link in links if link["action"] == "issues"}
    referenced = {link["credential_type_id"]
                  for links in model.credentials_of.values() for link in links}

    unused = [c for c in model.credential_types if c not in referenced]
    if unused:
        warn(f"{len(unused)} credential type(s) no participation handles at all: "
             f"{', '.join(unused)}. Either a use case is missing or the credential may "
             f"have been added speculatively")
    unissued = [c for c in model.credential_types
                if c in referenced and c not in issued_anywhere]
    if unissued:
        warn(f"{len(unissued)} credential type(s) are presented or verified here but "
             f"issued by no use case in this graph: {', '.join(unissued)}. Each marks an "
             f"issuing flow that is outside the repository or not yet written down")

    # If a use case needs a state, somebody in it should be checking the
    # credential that evidences that state.
    for uc_id in model.use_cases:
        verified = model.credential_actions(uc_id, "verifies")
        for state in model.pre_of.get(uc_id, []):
            cred = model.credential_for_state(state)
            if cred and cred not in verified:
                warn(f"use-cases.csv[{uc_id}]: requires {state}, evidenced by {cred}, "
                     f"but no verifier in this use case checks it")


def check_dependencies(model):
    for index, row in enumerate(model.dependencies, start=2):
        where = f"use-case-dependencies.csv:{index}"
        for field in ("use_case_id", "requires_use_case_id"):
            if row[field] not in model.use_cases:
                error(f"{where}: unknown use case {row[field]!r}")
        if row["use_case_id"] == row["requires_use_case_id"]:
            error(f"{where}: a use case cannot require itself")

    # A dependency cycle means no valid order to build things in, which is the
    # whole point of recording dependencies.
    colour: dict[str, int] = {}

    def visit(node, trail):
        if colour.get(node) == 1:
            error(f"use-case-dependencies.csv: dependency cycle "
                  f"{' -> '.join(trail + [node])}")
            return
        if colour.get(node) == 2:
            return
        colour[node] = 1
        for nxt in model.requires_of.get(node, []):
            if nxt in model.use_cases:
                visit(nxt, trail + [node])
        colour[node] = 2

    for uc_id in model.use_cases:
        visit(uc_id, [])


def check_use_cases(model):
    for uc_id, row in model.use_cases.items():
        where = f"use-cases.csv[{uc_id}]"
        if not SLUG.match(uc_id):
            error(f"{where}: id must be a lower-case slug")
        mode = row["transformation_mode"]
        if mode not in model.modes:
            error(f"{where}: transformation_mode {mode!r} is not in "
                  f"transformation-modes.csv")
        drivers = model.value_drivers_of.get(uc_id, [])
        if not drivers:
            error(f"{where}: no value driver. Record at least one reason applying a "
                  f"credential here is worth doing")
        if len(drivers) != len(set(drivers)):
            error(f"{where}: the same value driver is listed twice")

        # A use case may cover only part of the credential lifecycle, so an
        # issuance-only or a verification-only one is legitimate. What it may not
        # be is a use case in which no credential changes hands at all.
        roles = {p["role_id"] for p in model.participants_of.get(uc_id, [])}
        if not roles & {"issuer", "verifier"}:
            error(f"{where}: neither an issuer nor a verifier. A use case in this graph "
                  f"has to cover at least one end of a credential exchange")
        if "holder" not in roles:
            warn(f"{where}: no holder named. Check whether this is an "
                 f"organisation-to-organisation exchange or an omission")

        # Friction reduction is easy to claim without evidence. Naming the
        # mechanism the use case reduces reliance on makes the claim checkable.
        if "friction-reduction" in drivers and not model.prior_evidence_of.get(uc_id):
            error(f"{where}: claims friction-reduction but names no mechanism it "
                  f"reduces reliance on. Add a row to use-case-prior-evidence.csv or "
                  f"drop the driver")

        if row["maturity"] not in MATURITY:
            error(f"{where}: maturity {row['maturity']!r} not in {sorted(MATURITY)}")
        deployment = row["deployment_evidence"].strip()
        if deployment and not DOC_URL.match(deployment):
            error(f"{where}: deployment_evidence must be an absolute https URL, "
                  f"got {deployment!r}")
        if row["maturity"] == "Live" and not deployment:
            error(f"{where}: maturity Live claims a production deployment. Record the "
                  f"evidence for it in deployment_evidence, or use Modelled")
        if deployment and row["maturity"] != "Live":
            warn(f"{where}: carries deployment evidence but is not marked Live")

        sectors = model.sectors_of.get(uc_id, [])
        if not sectors:
            error(f"{where}: no sector — a use case that sits in no sector is not a use case")
        if len(sectors) != len(set(sectors)):
            error(f"{where}: the same sector is listed twice")

        functions = [r["function_id"] for r in model.functions_of.get(uc_id, [])]
        if len(functions) != len(set(functions)):
            error(f"{where}: the same function is listed twice")
        primaries = [r for r in model.functions_of.get(uc_id, []) if r["role"] == "primary"]
        if len(primaries) != 1:
            error(f"{where}: expected exactly one primary function, found {len(primaries)}")
        for link in model.functions_of.get(uc_id, []):
            if link["role"] not in {"primary", "supporting"}:
                error(f"{where}: role {link['role']!r} must be primary or supporting")

        documented = row["documented_by"].strip()
        if documented:
            # The worked flows live in other repositories, so this checks the shape
            # of the link, not that it resolves — no network call in CI.
            if not DOC_URL.match(documented):
                error(f"{where}: documented_by must be an absolute https URL, "
                      f"got {documented!r}")
            if row["maturity"] == "Exploratory":
                warn(f"{where}: has a worked flow but is still marked Exploratory")
        elif row["maturity"] != "Exploratory":
            error(f"{where}: maturity {row['maturity']} claims a worked flow, "
                  f"but documented_by is empty")


def check_links(model):
    for index, row in enumerate(model.uc_sectors, start=2):
        where = f"use-case-sectors.csv:{index}"
        if row["use_case_id"] not in model.use_cases:
            error(f"{where}: unknown use case {row['use_case_id']!r}")
        if row["sector_id"] not in model.sectors:
            error(f"{where}: unknown sector {row['sector_id']!r}")
    for index, row in enumerate(model.uc_functions, start=2):
        where = f"use-case-functions.csv:{index}"
        if row["use_case_id"] not in model.use_cases:
            error(f"{where}: unknown use case {row['use_case_id']!r}")
        if row["function_id"] not in model.functions:
            error(f"{where}: unknown function {row['function_id']!r}")

    # The vocabulary is deliberately wider than the seeded use cases, so unused
    # functions are expected. Report them once as coverage, not one line each.
    used_functions = {r["function_id"] for r in model.uc_functions}
    unused = [f for f in model.functions if f not in used_functions]
    if unused:
        warn(f"{len(unused)} of {len(model.functions)} functions are not yet exercised "
             f"by a use case: {', '.join(unused)}")


def check_generated(model):
    """Fail if generated/ no longer matches data/.

    build.py --check does the same thing in CI. Having it here too means a local
    validate run cannot pass while the published graph still describes the
    previous data.
    """
    import build as build_module

    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    stale, missing = [], []
    for name, builder in build_module.OUTPUTS.items():
        path = os.path.join(root, "generated", name)
        if not os.path.exists(path):
            missing.append(name)
            continue
        with open(path, encoding="utf-8") as fh:
            if fh.read() != builder(model):
                stale.append(name)
    for name in missing:
        error(f"generated/{name}: missing — run python3 build/build.py")
    for name in stale:
        error(f"generated/{name}: does not match data/ — run python3 build/build.py")


def check_rdf():
    """Parse the generated graph if rdflib is installed; skip cleanly if not."""
    try:
        from rdflib import Graph
    except ImportError:
        warn("rdflib not installed — skipped parsing the generated RDF "
             "(pip install rdflib to enable)")
        return
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    graphs = {}
    for name, fmt in (("ontology/ifm.ttl", "turtle"),
                      ("ontology/ifm-shapes.ttl", "turtle"),
                      ("generated/ifm-graph.ttl", "turtle"),
                      ("generated/ifm-graph.jsonld", "json-ld")):
        path = os.path.join(root, name)
        if not os.path.exists(path):
            warn(f"{name}: missing — run build/build.py")
            continue
        try:
            graphs[name] = Graph().parse(path, format=fmt)
        except Exception as exc:  # noqa: BLE001 - report any parse failure verbatim
            error(f"{name}: does not parse as {fmt}: {exc}")
    ttl = graphs.get("generated/ifm-graph.ttl")
    jsonld = graphs.get("generated/ifm-graph.jsonld")
    if ttl is not None and jsonld is not None and not ttl.isomorphic(jsonld):
        error("generated/ifm-graph.ttl and ifm-graph.jsonld are not the same graph")
    if ttl is not None and graphs.get("ontology/ifm-shapes.ttl") is not None:
        check_shacl(root)


def check_shacl(root):
    """Run the SHACL shapes over the generated graph, if pyshacl is installed.

    The Python checks above remain the build authority: they see the CSVs and can
    say which row is wrong. The shapes exist so that a consumer who has only the
    RDF can check the same structural constraints without this repository.
    """
    try:
        from pyshacl import validate as shacl_validate
    except ImportError:
        warn("pyshacl not installed — skipped SHACL validation of the generated RDF "
             "(pip install pyshacl to enable)")
        return
    conforms, _results_graph, results_text = shacl_validate(
        os.path.join(root, "generated", "ifm-graph.ttl"),
        shacl_graph=os.path.join(root, "ontology", "ifm-shapes.ttl"),
        ont_graph=os.path.join(root, "ontology", "ifm.ttl"),
        data_graph_format="turtle", shacl_graph_format="turtle",
        ont_graph_format="turtle", advanced=True, inference="none")
    if not conforms:
        error("generated/ifm-graph.ttl does not satisfy ontology/ifm-shapes.ttl:\n"
              + results_text.strip())


def main():
    model = Model()
    check_sectors(model)
    check_functions(model)
    check_alignments(model)
    check_axes(model)
    check_value_streams(model)
    check_states(model)
    check_trust_roles(model)
    check_dependencies(model)
    check_credentials(model)
    check_use_cases(model)
    check_links(model)
    check_generated(model)
    check_rdf()

    for message in warnings:
        print(f"warning: {message}")
    for message in errors:
        print(f"error: {message}", file=sys.stderr)

    counts = (f"{len(model.use_cases)} use cases, {len(model.sectors)} sectors, "
              f"{len(model.functions)} functions, {len(model.alignments)} alignments, "
              f"{len(model.value_drivers)} value drivers, "
              f"{len(model.value_streams)} value streams, "
              f"{len(model.participants)} participations, "
              f"{len(model.states)} states, "
              f"{len(model.credential_types)} credential types")
    if errors:
        print(f"\nFAILED: {len(errors)} error(s) in {counts}", file=sys.stderr)
        return 1
    print(f"OK: {counts}, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
