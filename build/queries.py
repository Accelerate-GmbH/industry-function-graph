#!/usr/bin/env python3
"""The fourteen questions the graph exists to answer.

    python3 build/queries.py            # answer all fourteen
    python3 build/queries.py --check    # fail if any cannot be answered
    python3 build/queries.py 5 7 9      # answer a selection

These are acceptance tests for the model, not documentation examples. Each one
runs against the same data the graph is generated from, and `--check` fails if a
query returns nothing where it must return something - which is how a refactor
that quietly breaks composability gets caught.

Every answer here is derived. Nothing in data/ records which use case enables
which, which requirement has no supplier, or which two use cases overlap.
"""

# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model import Model  # noqa: E402

QUERIES = []


def query(number, question, must_answer=True):
    """Register a query. `must_answer` marks the ones --check treats as required."""
    def decorate(fn):
        QUERIES.append((number, question, fn, must_answer))
        return fn
    return decorate


def _iface(model, rows, principal=False):
    out = []
    for row in rows:
        text = model.label("condition", row["condition_id"])
        if principal and row.get("principal") == "yes":
            text += " (principal)"
        if row.get("evidence_type", "").strip():
            text += f" [as {model.label('credential', row['evidence_type'])}]"
        out.append(text)
    return ", ".join(out) or "nothing"


# ======================================================================
# 1-2  Classification: where does a use case belong?
# ======================================================================

@query(1, "Which use cases perform function X in sector Y?")
def q1(model):
    out = []
    for function_id in ("identity-proofing", "relationship-onboarding"):
        for section in model.used_sections():
            hits = model.cell(section, function_id, role="primary")
            for uc in hits:
                out.append(f"{model.label('function', function_id)} in "
                           f"{model.sectors[section]['notation']} "
                           f"{model.label('sector', section)}: "
                           f"{model.label('use-case', uc)}")
    return out


@query(2, "Which use cases realise stage Z of value stream V?")
def q2(model):
    out = []
    for (stream_id, stage_id), stage in model.stage_index.items():
        realised = [uc for uc, pairs in model.stages_realised_by.items()
                    if (stream_id, stage_id) in pairs]
        if realised:
            out.append(f"{model.label('stream', stream_id)} / {stage['stage_label']}: "
                       + ", ".join(model.label("use-case", uc) for uc in realised))
    return out


# ======================================================================
# 3-6  Interface and composition
# ======================================================================

@query(3, "What does use case A require?")
def q3(model):
    return [f"{model.label('use-case', uc)}: {_iface(model, model.requires_of[uc])}"
            for uc in model.use_cases]


@query(4, "What does use case A provide?")
def q4(model):
    return [f"{model.label('use-case', uc)}: "
            f"{_iface(model, model.provides_of[uc], principal=True)}"
            for uc in model.use_cases]


@query(5, "Which existing use cases can satisfy A's requirements?")
def q5(model):
    out = []
    for uc in model.use_cases:
        for requirement_id, matches in model.suppliers_for(uc).items():
            if matches:
                out.append(f"{model.label('use-case', uc)} needs {requirement_id!r} — "
                           + ", ".join(sorted({model.label("use-case", other)
                                               for other, _p in matches})))
    return out


@query(6, "Which use cases can consume A's outputs?")
def q6(model):
    out = []
    for uc in model.use_cases:
        for provision_id, matches in model.consumers_of(uc).items():
            if matches:
                out.append(f"{model.label('use-case', uc)} provides {provision_id!r} — "
                           + ", ".join(sorted({model.label("use-case", other)
                                               for other, _r in matches})))
    return out


# ======================================================================
# 7-9  Gaps and overlaps
# ======================================================================

@query(7, "Which requirements currently have no upstream provider?", must_answer=False)
def q7(model):
    out = []
    for uc, requirement_id in model.unmet_requirements():
        requirement = next(r for r in model.requires_of[uc]
                           if r["requirement_id"] == requirement_id)
        out.append(f"{model.label('use-case', uc)} needs "
                   f"{model.label('condition', requirement['condition_id'])} — "
                   f"no use case here provides it")
    return out


@query(8, "Which outputs currently have no downstream consumer?", must_answer=False)
def q8(model):
    out = []
    for uc, provision_id in model.unconsumed_provisions():
        provision = next(p for p in model.provides_of[uc]
                         if p["provision_id"] == provision_id)
        mark = " (principal)" if provision.get("principal") == "yes" else ""
        out.append(f"{model.label('use-case', uc)} provides "
                   f"{model.label('condition', provision['condition_id'])}{mark} — "
                   f"nothing here consumes it")
    return out


@query(9, "Which use cases appear to overlap semantically?", must_answer=False)
def q9(model):
    return [f"{verdict}: {model.label('use-case', first)} ~ "
            f"{model.label('use-case', second)} "
            f"(both {model.label('function', model.primary_function(first))})"
            for verdict, first, second in model.overlaps()]


# ======================================================================
# 10-13  Realisation
# ======================================================================

@query(10, "Which real implementation flows realise a canonical use case?")
def q10(model):
    out = []
    for uc in model.use_cases:
        flows = model.flows_of_use_case(uc)
        out.append(f"{model.label('use-case', uc)}: "
                   + (", ".join(model.label("flow", f) for f in flows)
                      or "no implementation yet"))
    return out


@query(11, "Which credential/evidence types can satisfy a particular input requirement?")
def q11(model):
    out = []
    seen = set()
    for uc in model.use_cases:
        for requirement in model.requires_of[uc]:
            condition = requirement["condition_id"]
            if condition in seen:
                continue
            seen.add(condition)
            credentials = model.credentials_for_condition(condition)
            if credentials:
                out.append(f"{model.label('condition', condition)}: "
                           + ", ".join(model.label("credential", c) for c in credentials))
    return out


@query(12, "Which value-stream stages currently have no use case implementation?",
       must_answer=False)
def q12(model):
    return [f"{model.label('stream', stream_id)} / "
            f"{model.stage_index[(stream_id, stage_id)]['stage_label']}"
            for stream_id, stage_id in model.unrealised_stages()]


@query(13, "Which credentials are produced but currently have no consuming flow?",
       must_answer=False)
def q13(model):
    issued = model.issued_credentials()
    consumed = model.consumed_credentials()
    return [f"{model.label('credential', c)} — issued, never verified here"
            for c in sorted(issued - consumed)]


# ======================================================================
# 14  End-to-end composition
# ======================================================================

@query(14, "Which composition paths connect a given starting condition to a desired outcome?")
def q14(model):
    goals = [
        ("eid-held", "customer-relationship-open"),
        ("eid-held", "kyc-attestation-current"),
        ("secondary-education-credential-held", "tertiary-enrolment-established"),
        ("secondary-education-credential-held", "employment-relationship-open"),
        ("eid-held", "age-threshold-established"),
    ]
    out = []
    for start, goal in goals:
        for path in model.composition_paths(start, goal):
            out.append(f"{model.label('condition', start)} → "
                       + " → ".join(model.label("use-case", uc) for uc in path)
                       + f" → {model.label('condition', goal)}")
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv
    wanted = {int(a) for a in args} if args else None

    model = Model()
    failures = []
    for number, question, fn, must_answer in QUERIES:
        if wanted and number not in wanted:
            continue
        answers = fn(model)
        if not check:
            print(f"\n{number:>2}. {question}")
            if answers:
                for line in answers:
                    print(f"      {line}")
            else:
                print("      (nothing)")
        if must_answer and not answers:
            failures.append(f"query {number} ({question}) returned nothing, but the "
                            f"model must be able to answer it")

    if check:
        for failure in failures:
            print(f"error: {failure}", file=sys.stderr)
        if failures:
            print(f"\nFAILED: {len(failures)} of {len(QUERIES)} acceptance queries",
                  file=sys.stderr)
            return 1
        print(f"OK: all {len(QUERIES)} acceptance queries answerable")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
