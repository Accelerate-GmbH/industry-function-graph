#!/usr/bin/env python3
"""Integrity checks for the Industry-Function Mapping data.

    python3 build/validate.py

Checks the three layers and, above all, the boundaries between them: that the
classification does not smuggle in composability, that composition runs through
conditions rather than credential identifiers, and that a canonical use case
stays one coherent transformation.

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
# to Rev. 5) while the numbers hold.
SECTOR_ID = re.compile(r"^ISIC-([A-V]|\d{2}|\d{4})$")
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CODE_STATUS = {"verified", "provisional"}
# A concept's own provenance and the confidence of a mapping onto it are
# separate questions: a mapping onto a verified concept can still be editorial.
MAPPING_STATUS = {"editorial", "verified"}
MATURITY = {"Exploratory", "Modelled", "Live"}
CHANGE_MODE = {"run", "change"}
BEARS_COST = {"yes", "no"}
CONDITION_KIND = {"evidence", "fact", "outcome", "relationship"}
PRINCIPAL = {"yes", "no"}

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
# Contextual constraints are open-ended by design, but the keys are not: an
# unrecognised key is a typo that would silently never match anything.
CONTEXT_KEYS = {"jurisdiction", "sector", "actor-type", "governing-authority",
                "assurance", "governance-regime"}
DOC_URL = re.compile(r"^https://\S+$")

errors: list[str] = []
warnings: list[str] = []


def error(message):
    errors.append(message)


def warn(message):
    warnings.append(message)


# ======================================================================
# Classification
# ======================================================================

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
                  f"function itself does not carry. Use closeMatch or relatedMatch")
        if row["match_type"] != "relatedMatch" and not row["note"].strip():
            error(f"{where}: a {row['match_type']} needs a note saying why the two "
                  f"concepts are that close")
        key = (row["function_id"], row["target_scheme"], row["target_id"])
        if key in seen:
            error(f"{where}: duplicate alignment {key}")
        seen.add(key)


# ======================================================================
# Interface
# ======================================================================

def check_conditions(model):
    for condition_id, row in model.conditions.items():
        where = f"conditions.csv[{condition_id}]"
        if not SLUG.match(condition_id):
            error(f"{where}: id must be a lower-case slug")
        if not row["definition"].strip():
            error(f"{where}: needs a definition. Without one there is no way to tell "
                  f"whether the condition holds")
        if row["kind"] not in CONDITION_KIND:
            error(f"{where}: kind {row['kind']!r} not in {sorted(CONDITION_KIND)}")
        broader = row["broader"].strip()
        if broader and broader not in model.conditions:
            error(f"{where}: broader {broader!r} does not exist")
        elif broader and condition_id not in model.condition_ancestors(broader):
            parent = model.conditions[broader]
            if parent["kind"] != row["kind"]:
                error(f"{where}: is {row['kind']} but sits under {broader}, which is "
                      f"{parent['kind']}. Subsumption must not cross the kinds: holding "
                      f"evidence is not the same claim as a relying party having "
                      f"established something on it")
        # A cycle would make condition_ancestors loop, and the whole composition
        # engine runs on that walk.
        if broader and condition_id in model.condition_ancestors(broader):
            error(f"{where}: broader cycle through {broader!r}")

    for role_id, row in model.subject_roles.items():
        if not SLUG.match(role_id):
            error(f"subject-roles.csv[{role_id}]: id must be a lower-case slug")
        if not row["definition"].strip():
            error(f"subject-roles.csv[{role_id}]: needs a definition")

    used = ({r["condition_id"] for r in model.uc_requires}
            | {r["condition_id"] for r in model.uc_provides}
            | {r["condition_id"] for r in model.stage_requires}
            | {r["condition_id"] for r in model.stage_provides}
            | {r["condition_id"] for r in model.stream_requires}
            | {r["condition_id"] for r in model.stream_provides}
            # A condition a credential substantiates is reachable even if no
            # interface names it directly: a requirement for its broader parent
            # finds it through the lattice.
            | {r["condition_id"] for r in model.credential_conditions})
    orphans = [c for c in model.conditions
               if c not in used
               and not any(model.conditions[other]["broader"] == c
                           for other in model.conditions)]
    if orphans:
        warn(f"{len(orphans)} condition(s) appear in no interface and have nothing "
             f"under them: {', '.join(orphans)}. A condition used by nobody connects "
             f"nothing")


def check_interface_rows(model):
    """Every requirement and provision, on every kind of composable element."""
    tables = [
        ("use-case-requires.csv", model.uc_requires, model.use_cases, "use_case_id", False),
        ("use-case-provides.csv", model.uc_provides, model.use_cases, "use_case_id", True),
        ("value-stream-stage-requires.csv", model.stage_requires, None, None, False),
        ("value-stream-stage-provides.csv", model.stage_provides, None, None, True),
        ("value-stream-requires.csv", model.stream_requires, model.value_streams,
         "value_stream_id", False),
        ("value-stream-provides.csv", model.stream_provides, model.value_streams,
         "value_stream_id", True),
    ]
    for name, rows, owners, owner_key, is_provision in tables:
        for index, row in enumerate(rows, start=2):
            where = f"{name}:{index}"
            if owners is not None and row[owner_key] not in owners:
                error(f"{where}: unknown {owner_key} {row[owner_key]!r}")
            if row["condition_id"] not in model.conditions:
                error(f"{where}: unknown condition {row['condition_id']!r}")
            role = row.get("subject_role", "").strip()
            if role and role not in model.subject_roles:
                error(f"{where}: unknown subject_role {role!r}")
            evidence = row.get("evidence_type", "").strip()
            if evidence and evidence not in model.credential_types:
                error(f"{where}: unknown evidence_type {evidence!r}")
            if evidence and not is_provision:
                # Naming a credential in a requirement is what stops an
                # alternative credential from serving the same business need.
                warn(f"{where}: requires a specific credential ({evidence}). Prefer "
                     f"requiring the condition alone, so a second credential can "
                     f"satisfy it without this interface changing")
            for key in model.parse_context(row.get("context", "")):
                if key not in CONTEXT_KEYS:
                    error(f"{where}: unknown context key {key!r}, not in "
                          f"{sorted(CONTEXT_KEYS)}")
            if row.get("context", "").strip() and "=" not in row["context"]:
                error(f"{where}: context must be `key=value` clauses separated by `;`")
            if is_provision and "principal" in row:
                if row["principal"] not in PRINCIPAL:
                    error(f"{where}: principal {row['principal']!r} not in "
                          f"{sorted(PRINCIPAL)}")

    for name, rows in (("value-stream-stage-requires.csv", model.stage_requires),
                       ("value-stream-stage-provides.csv", model.stage_provides)):
        for index, row in enumerate(rows, start=2):
            key = (row["value_stream_id"], row["stage_id"])
            if key not in model.stage_index:
                error(f"{name}:{index}: unknown stage {key}")


def check_use_case_interfaces(model):
    """The atomicity rule, enforced.

    One primary function, one principal outcome, a coherent set of required
    conditions. A use case that fails these is not one transformation, and
    everything downstream - composition, overlap detection, stage realisation -
    reads it as if it were.
    """
    for uc_id, row in model.use_cases.items():
        where = f"use-cases.csv[{uc_id}]"
        if not SLUG.match(uc_id):
            error(f"{where}: id must be a lower-case slug")
        if not row["description"].strip():
            error(f"{where}: needs a description")
        if row["transformation_mode"] not in model.modes:
            error(f"{where}: transformation_mode {row['transformation_mode']!r} is not "
                  f"in transformation-modes.csv")

        primaries = [r for r in model.functions_of.get(uc_id, []) if r["role"] == "primary"]
        if len(primaries) != 1:
            error(f"{where}: expected exactly one primary function, found "
                  f"{len(primaries)}")
        functions = [r["function_id"] for r in model.functions_of.get(uc_id, [])]
        if len(functions) != len(set(functions)):
            error(f"{where}: the same function is listed twice")
        for link in model.functions_of.get(uc_id, []):
            if link["role"] not in {"primary", "supporting"}:
                error(f"{where}: role {link['role']!r} must be primary or supporting")
            if link["function_id"] not in model.functions:
                error(f"{where}: unknown function {link['function_id']!r}")

        provisions = model.provides_of.get(uc_id, [])
        if not provisions:
            error(f"{where}: provides nothing. Nothing can follow a use case that "
                  f"leaves no condition behind")
        principals = [p for p in provisions if p.get("principal") == "yes"]
        if len(principals) != 1:
            error(f"{where}: expected exactly one principal outcome, found "
                  f"{len(principals)}. A use case that has several is doing several "
                  f"transformations: split it, and compose the parts in a flow")

        ids = [p["provision_id"] for p in provisions]
        if len(ids) != len(set(ids)):
            error(f"{where}: the same provision_id is used twice")
        ids = [r["requirement_id"] for r in model.requires_of.get(uc_id, [])]
        if len(ids) != len(set(ids)):
            error(f"{where}: the same requirement_id is used twice")

        # A use case that provides what it also requires is not a
        # transformation; it is a no-op or a mis-modelled refresh.
        required = {r["condition_id"] for r in model.requires_of.get(uc_id, [])}
        provided = {p["condition_id"] for p in provisions}
        for condition in sorted(required & provided):
            warn(f"{where}: both requires and provides {condition}. Deliberate for a "
                 f"refresh, a mistake otherwise")

        sectors = model.sectors_of.get(uc_id, [])
        if not sectors:
            error(f"{where}: no sector — a use case that applies nowhere is not a use case")
        if len(sectors) != len(set(sectors)):
            error(f"{where}: the same sector is listed twice")
        for sector in sectors:
            if sector not in model.sectors:
                error(f"{where}: unknown sector {sector!r}")

        drivers = model.value_drivers_of.get(uc_id, [])
        if not drivers:
            error(f"{where}: no value driver. Record at least one reason applying a "
                  f"credential here is worth doing")
        if len(drivers) != len(set(drivers)):
            error(f"{where}: the same value driver is listed twice")
        for driver in drivers:
            if driver not in model.value_drivers:
                error(f"{where}: unknown value driver {driver!r}")
        if "friction-reduction" in drivers and not model.prior_evidence_of.get(uc_id):
            error(f"{where}: claims friction-reduction but names no mechanism it "
                  f"reduces reliance on")

    for index, row in enumerate(model.uc_prior_evidence, start=2):
        where = f"use-case-prior-evidence.csv:{index}"
        if row["use_case_id"] not in model.use_cases:
            error(f"{where}: unknown use case {row['use_case_id']!r}")
        if row["mechanism_id"] not in model.prior_evidence:
            error(f"{where}: unknown prior evidence mechanism {row['mechanism_id']!r}")


def check_named_dependencies(model):
    """`requiresUseCase` is exceptional, and the validator says so.

    A named dependency composes with exactly one upstream use case and silently
    excludes every alternative route to the same condition. Where the dependency
    is already expressible as a condition, it should be.
    """
    for index, row in enumerate(model.dependencies, start=2):
        where = f"use-case-dependencies.csv:{index}"
        first, second = row["use_case_id"], row["requires_use_case_id"]
        for field, value in (("use_case_id", first), ("requires_use_case_id", second)):
            if value not in model.use_cases:
                error(f"{where}: unknown use case {value!r} in {field}")
        if first == second:
            error(f"{where}: a use case cannot require itself")
        if first in model.use_cases and second in model.use_cases:
            # `first requires second` means second must run first, so the
            # question is whether second already enables first through the
            # interfaces - not the other way round.
            if first in model.enables(second):
                error(f"{where}: {first} already composes onto {second} through the "
                      f"interface, so the named dependency adds nothing and narrows "
                      f"the graph to one upstream route. Remove it")
            else:
                warn(f"{where}: named dependency {first} -> {second}. Prefer stating "
                     f"the condition {first} actually needs, so an alternative "
                     f"upstream flow can satisfy it")

    colour: dict[str, int] = {}

    def visit(node, trail):
        if colour.get(node) == 1:
            error(f"use-case-dependencies.csv: dependency cycle "
                  f"{' -> '.join(trail + [node])}")
            return
        if colour.get(node) == 2:
            return
        colour[node] = 1
        for nxt in model.depends_on.get(node, []):
            if nxt in model.use_cases:
                visit(nxt, trail + [node])
        colour[node] = 2

    for uc_id in model.use_cases:
        visit(uc_id, [])


# ======================================================================
# Value streams as composition templates
# ======================================================================

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
        seen_stage, seen_function = set(), set()
        for stage in stages:
            stage_where = f"{where} stage {stage['stage_id']}"
            if not SLUG.match(stage["stage_id"]):
                error(f"{stage_where}: stage_id must be a lower-case slug")
            if stage["stage_id"] in seen_stage:
                error(f"{stage_where}: stage_id used twice in this stream")
            seen_stage.add(stage["stage_id"])
            if stage["function_id"] not in model.functions:
                error(f"{stage_where}: unknown function {stage['function_id']!r}")
            if not stage["stage_label"].strip():
                error(f"{stage_where}: needs a label saying what happens there")
            if stage["function_id"] in seen_function:
                warn(f"{stage_where}: {stage['function_id']} appears twice in this stream")
            seen_function.add(stage["function_id"])

    for index, row in enumerate(model.uc_stages, start=2):
        where = f"use-case-stages.csv:{index}"
        if row["use_case_id"] not in model.use_cases:
            error(f"{where}: unknown use case {row['use_case_id']!r}")
            continue
        key = (row["value_stream_id"], row["stage_id"])
        if key not in model.stage_index:
            error(f"{where}: unknown stage {key}")
            continue
        # A use case realises a stage only if it does that stage's work. The
        # function is the check the classification can actually make.
        stage = model.stage_index[key]
        uc_functions = {r["function_id"] for r in model.functions_of[row["use_case_id"]]}
        if stage["function_id"] not in uc_functions:
            error(f"{where}: {row['use_case_id']} realises a stage whose function is "
                  f"{stage['function_id']}, but does not list that function at all")
        # And its interface must not contradict the stage's.
        stage_provides = {r["condition_id"] for r in model.stage_provides
                          if (r["value_stream_id"], r["stage_id"]) == key}
        uc_provides = {p["condition_id"] for p in model.provides_of[row["use_case_id"]]}
        for condition in sorted(stage_provides):
            if not any(model.condition_satisfies(p, condition) for p in uc_provides):
                warn(f"{where}: the stage provides {condition}, which "
                     f"{row['use_case_id']} does not provide or narrow. Either the "
                     f"stage interface or the use case interface is wrong")

    unrealised = model.unrealised_stages()
    if unrealised:
        warn(f"{len(unrealised)} of {len(model.stage_index)} value stream stages have "
             f"no use case realising them: "
             f"{', '.join(f'{vs}/{st}' for vs, st in unrealised[:8])}"
             f"{' …' if len(unrealised) > 8 else ''}")


# ======================================================================
# Realisation
# ======================================================================

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
            error(f"trust-roles.csv[{role_id}]: no credential actions declared for this "
                  f"role in build/validate.py. Add it to ACTIONS_BY_ROLE, with an empty "
                  f"set if the role handles no credential itself")


def check_flows(model):
    for flow_id, row in model.flows.items():
        where = f"flows.csv[{flow_id}]"
        if not SLUG.match(flow_id):
            error(f"{where}: id must be a lower-case slug")
        if not row["description"].strip():
            error(f"{where}: needs a description")
        sector = row["sector_id"].strip()
        if sector and sector not in model.sectors:
            error(f"{where}: unknown sector {sector!r}")
        if row["maturity"] not in MATURITY:
            error(f"{where}: maturity {row['maturity']!r} not in {sorted(MATURITY)}")
        documented = row["documented_by"].strip()
        if documented and not DOC_URL.match(documented):
            error(f"{where}: documented_by must be an absolute https URL, got "
                  f"{documented!r}")
        if row["maturity"] == "Modelled" and not documented:
            error(f"{where}: maturity Modelled claims a worked flow, but documented_by "
                  f"is empty")
        deployment = row["deployment_evidence"].strip()
        if deployment and not DOC_URL.match(deployment):
            error(f"{where}: deployment_evidence must be an absolute https URL")
        if row["maturity"] == "Live" and not deployment:
            error(f"{where}: maturity Live claims a production deployment. Record the "
                  f"evidence in deployment_evidence, or use Modelled")
        if deployment and row["maturity"] != "Live":
            warn(f"{where}: carries deployment evidence but is not marked Live")
        if row["jurisdiction"].strip() and not re.fullmatch(
                r"[A-Z]{2}", row["jurisdiction"].strip()):
            error(f"{where}: jurisdiction must be an ISO 3166 alpha-2 code")
        if not model.realises_of.get(flow_id):
            error(f"{where}: realises no use case. A flow that implements no canonical "
                  f"pattern either needs one, or is not a flow")

    seen = set()
    for index, row in enumerate(model.flow_realises, start=2):
        where = f"flow-realises.csv:{index}"
        if row["flow_id"] not in model.flows:
            error(f"{where}: unknown flow {row['flow_id']!r}")
        if row["use_case_id"] not in model.use_cases:
            error(f"{where}: unknown use case {row['use_case_id']!r}")
        key = (row["flow_id"], row["step"])
        if key in seen:
            error(f"{where}: {row['flow_id']} uses step {row['step']} twice")
        seen.add(key)

    for flow_id in model.flows:
        steps = [int(r["step"]) for r in model.flow_realises if r["flow_id"] == flow_id]
        if sorted(steps) != list(range(1, len(steps) + 1)):
            error(f"flows.csv[{flow_id}]: realisation steps must run 1..n with no "
                  f"gaps, got {sorted(steps)}")

    # A flow composing several patterns must be a chain the interfaces allow.
    for flow_id in model.flows:
        chain = model.realises_of[flow_id]
        held: set[str] = set()
        for position, uc_id in enumerate(chain, start=1):
            if uc_id not in model.use_cases:
                continue
            if position > 1 and not model.runnable(uc_id, held):
                missing = [r["condition_id"] for r in model.requires_of[uc_id]
                           if not any(r["condition_id"] in model.condition_ancestors(c)
                                      for c in held)]
                warn(f"flows.csv[{flow_id}]: step {position} is {uc_id}, but nothing "
                     f"earlier in the flow provides {', '.join(missing)}. Either the "
                     f"flow relies on a condition established outside it, or the order "
                     f"is wrong")
            for provision in model.provides_of[uc_id]:
                held.update(model.condition_ancestors(provision["condition_id"]))

    unrealised = model.unrealised_use_cases()
    if unrealised:
        warn(f"{len(unrealised)} use case pattern(s) no flow implements: "
             f"{', '.join(unrealised)}. Each is a gap between the classification and "
             f"the ecosystem")


def check_participations(model):
    for index, row in enumerate(model.flow_participants, start=2):
        where = f"flow-participants.csv:{index}"
        if row["flow_id"] not in model.flows:
            error(f"{where}: unknown flow {row['flow_id']!r}")
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

    seen = set()
    for row in model.flow_participants:
        key = (row["flow_id"], row["participation_id"])
        if key in seen:
            error(f"flow-participants.csv: {row['flow_id']} uses the participation id "
                  f"{row['participation_id']!r} twice")
        seen.add(key)

    for flow_id in model.flows:
        roles = {p["role_id"] for p in model.participants_of.get(flow_id, [])}
        if not roles & {"issuer", "verifier"}:
            error(f"flows.csv[{flow_id}]: neither an issuer nor a verifier. A flow has "
                  f"to cover at least one end of a credential exchange")
        if "holder" not in roles:
            warn(f"flows.csv[{flow_id}]: no holder named. Check whether this is an "
                 f"organisation-to-organisation exchange or an omission")


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
        if cred_id not in model.substantiates:
            warn(f"{where}: substantiates no condition, so nothing can ask for it as "
                 f"evidence")

    for index, row in enumerate(model.credential_conditions, start=2):
        where = f"credential-conditions.csv:{index}"
        if row["credential_type_id"] not in model.credential_types:
            error(f"{where}: unknown credential type {row['credential_type_id']!r}")
        if row["condition_id"] not in model.conditions:
            error(f"{where}: unknown condition {row['condition_id']!r}")
        elif model.conditions[row["condition_id"]]["kind"] != "evidence":
            error(f"{where}: {row['condition_id']} is a "
                  f"{model.conditions[row['condition_id']]['kind']} condition. A "
                  f"credential is evidence; it cannot by itself substantiate a fact a "
                  f"relying party has to establish, or a business outcome")

    role_of = {(p["flow_id"], p["participation_id"]): p["role_id"]
               for p in model.flow_participants}
    for index, row in enumerate(model.flow_credentials, start=2):
        where = f"flow-credentials.csv:{index}"
        if row["credential_type_id"] not in model.credential_types:
            error(f"{where}: unknown credential type {row['credential_type_id']!r}")
        if row["action"] not in CREDENTIAL_ACTIONS:
            error(f"{where}: action {row['action']!r} not in {sorted(CREDENTIAL_ACTIONS)}")
            continue
        key = (row["flow_id"], row["participation_id"])
        role = role_of.get(key)
        if role is None:
            error(f"{where}: {row['flow_id']} has no participation "
                  f"{row['participation_id']!r} to attach a credential to")
            continue
        allowed = ACTIONS_BY_ROLE.get(role, set())
        if row["action"] not in allowed:
            expected = (f"only {' and '.join(sorted(allowed))}" if allowed
                        else "no credential action at all")
            error(f"{where}: the {role} participation {row['participation_id']!r} is "
                  f"recorded as {row['action']!r}, but a {role} performs {expected}. If "
                  f"one party acts in two roles here, give it a second participation")

    check_credential_lifecycle(model)
    check_credential_supply(model)


def check_credential_lifecycle(model):
    """Issued, held, presented, verified - and no half of a pair on its own."""
    for flow_id in model.flows:
        where = f"flows.csv[{flow_id}]"
        issued = model.credential_actions(flow_id, "issues")
        held = model.credential_actions(flow_id, "holds")
        presented = model.credential_actions(flow_id, "presents")
        verified = model.credential_actions(flow_id, "verifies")

        for cred in sorted(verified - presented):
            error(f"{where}: {cred} is verified here but never presented")
        for cred in sorted(presented - verified):
            error(f"{where}: {cred} is presented here but nobody verifies it. A "
                  f"presentation with no verifier is not an exchange")
        for cred in sorted(issued - held):
            error(f"{where}: {cred} is issued here but no holder takes possession of it")
        for cred in sorted(held - issued):
            error(f"{where}: {cred} is held here but nothing issues it. `holds` marks "
                  f"the flow where possession begins; a credential obtained elsewhere "
                  f"and used here records `presents` alone")


def check_credential_supply(model):
    """Credentials nothing issues, and requirements nobody's evidence can meet."""
    issued = model.issued_credentials()
    consumed = model.consumed_credentials()
    referenced = {link["credential_type_id"]
                  for links in model.credentials_of.values() for link in links}

    unused = [c for c in model.credential_types if c not in referenced]
    if unused:
        warn(f"{len(unused)} credential type(s) no flow handles at all: "
             f"{', '.join(unused)}")
    unissued = [c for c in sorted(referenced - issued)]
    if unissued:
        warn(f"{len(unissued)} credential type(s) are presented or verified but issued "
             f"by no flow here: {', '.join(unissued)}. Each marks an issuing flow "
             f"outside the repository or not yet written down")
    unconsumed = [c for c in sorted(issued - consumed)]
    if unconsumed:
        warn(f"{len(unconsumed)} credential type(s) are issued but verified by no flow "
             f"here: {', '.join(unconsumed)}")

    # An evidence condition that nothing can substantiate is a requirement no
    # implementation can meet, however well the interfaces line up.
    for uc_id in model.use_cases:
        for requirement in model.requires_of[uc_id]:
            condition = model.conditions[requirement["condition_id"]]
            if condition["kind"] != "evidence":
                continue
            if not model.credentials_for_condition(requirement["condition_id"]):
                warn(f"use-cases.csv[{uc_id}]: requires evidence condition "
                     f"{requirement['condition_id']}, which no credential type "
                     f"substantiates")


# ======================================================================
# Composition
# ======================================================================

def check_composition(model):
    """The interfaces have to actually compose, and the gaps have to be visible."""
    for uc_id, requirement_id in model.unmet_requirements():
        requirement = next(r for r in model.requires_of[uc_id]
                           if r["requirement_id"] == requirement_id)
        warn(f"use-cases.csv[{uc_id}]: requirement {requirement_id!r} "
             f"({requirement['condition_id']}) is satisfied by no use case here. "
             f"Either an upstream use case is missing, or the condition is "
             f"established outside this graph")

    unconsumed = model.unconsumed_provisions()
    principal_unconsumed = []
    for uc_id, provision_id in unconsumed:
        provision = next(p for p in model.provides_of[uc_id]
                         if p["provision_id"] == provision_id)
        if provision.get("principal") == "yes":
            principal_unconsumed.append(f"{uc_id}/{provision['condition_id']}")
    if principal_unconsumed:
        warn(f"{len(principal_unconsumed)} principal outcome(s) no use case here "
             f"consumes: {', '.join(principal_unconsumed)}. Ends of the chain, or "
             f"downstream use cases nobody has written down")

    for verdict, first, second in model.overlaps():
        message = (f"{first} and {second} share a primary function and their "
                   f"interfaces {verdict}")
        if verdict == "duplicate":
            error(f"use-cases.csv: {message}. Two use cases with the same function and "
                  f"the same interface are one use case")
        else:
            warn(f"use-cases.csv: {message}. Reported for editorial review, not merged")


# ======================================================================
# Generated artefacts and RDF
# ======================================================================

def check_generated(model):
    """Fail if generated/ no longer matches data/."""
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

    The Python checks remain the build authority: they see the CSVs and can say
    which row is wrong. The shapes exist so a consumer with only the RDF can
    check the same structural constraints without this repository.
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
    check_conditions(model)
    check_interface_rows(model)
    check_use_case_interfaces(model)
    check_named_dependencies(model)
    check_value_streams(model)
    check_trust_roles(model)
    check_flows(model)
    check_participations(model)
    check_credentials(model)
    check_composition(model)
    check_generated(model)
    check_rdf()

    for message in warnings:
        print(f"warning: {message}")
    for message in errors:
        print(f"error: {message}", file=sys.stderr)

    counts = (f"{len(model.use_cases)} use case patterns, {len(model.flows)} flows, "
              f"{len(model.conditions)} conditions, "
              f"{len(model.uc_requires)} requirements, "
              f"{len(model.uc_provides)} provisions, "
              f"{len(model.sectors)} sectors, {len(model.functions)} functions, "
              f"{len(model.value_streams)} value streams, "
              f"{len(model.stage_index)} stages, "
              f"{len(model.credential_types)} credential types")
    if errors:
        print(f"\nFAILED: {len(errors)} error(s) in {counts}", file=sys.stderr)
        return 1
    print(f"OK: {counts}, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
