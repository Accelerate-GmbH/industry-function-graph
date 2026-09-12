#!/usr/bin/env python3
"""Compare this graph's use cases with the Trust Flow Diagram Repository.

Both repositories classify the same flows: this one as use cases, that one as
families in sector.yaml files. Without a comparison the two descriptions drift
apart, because nothing in either repository reads the other.

    python3 build/reconcile.py --source ../Trust-Flow-Diagram-Repository

It joins on `documented_by`: a use case pointing at .../banking/KYC%20Credential
belongs to the family in banking/sector.yaml whose `directory` is that name, or
to the sector's only family when the link points at the sector root.

It reports and always exits zero. The two repositories may legitimately
disagree; the point is that someone sees the disagreement.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install pyyaml")

from model import Model  # noqa: E402

MARKER = "Trust-Flow-Diagram-Repository/tree/main/"


def families(root: Path) -> dict[tuple[str, str], dict]:
    """{(sector, family id): family} from every sector.yaml under root."""
    found = {}
    for manifest in sorted(root.glob("*/sector.yaml")):
        data = yaml.safe_load(manifest.read_text()) or {}
        sector = manifest.parent.name
        for family in data.get("families") or []:
            if isinstance(family, dict) and family.get("id"):
                found[(sector, family["id"])] = family
    return found


def locate(use_case, model, by_sector) -> tuple[str, str] | None:
    """Which family a use case's documented_by points at."""
    link = model.documentation_iri(use_case) or ""
    if MARKER not in link:
        return None
    path = unquote(link.split(MARKER, 1)[1]).strip("/").split("/")
    sector = path[0]
    candidates = by_sector.get(sector, [])
    if len(path) > 1:
        for key, family in candidates:
            if str(family.get("directory", "")) == path[1]:
                return key
        return None
    return candidates[0][0] if len(candidates) == 1 else None


def main(argv):
    if len(argv) < 2 or argv[0] != "--source":
        print("Usage: reconcile.py --source <path to Trust-Flow-Diagram-Repository>")
        return 1
    root = Path(argv[1])
    if not root.exists():
        print(f"{root} does not exist")
        return 1

    model = Model()
    fams = families(root)
    by_sector: dict[str, list] = {}
    for key, family in fams.items():
        by_sector.setdefault(key[0], []).append((key, family))

    mapped: dict[tuple[str, str], list[str]] = {}
    unlinked = []
    for use_case in model.use_cases:
        key = locate(use_case, model, by_sector)
        if key is None:
            if model.documentation_iri(use_case):
                unlinked.append(use_case)
        else:
            mapped.setdefault(key, []).append(use_case)

    print(f"{len(model.use_cases)} use cases here, {len(fams)} families there, "
          f"{sum(len(v) for v in mapped.values())} joined\n")

    differences = 0
    for key, family in sorted(fams.items()):
        label = f"{key[0]}/{key[1]}"
        cases = mapped.get(key, [])
        if not cases:
            print(f"  {label}: no use case in the graph documents this family")
            differences += 1
            continue

        block = family.get("states") or {}
        there_pre = set(map(str, block.get("requires") or []))
        there_post = set(map(str, block.get("establishes") or []))
        here_pre = {s for c in cases for s in model.pre_of[c]}
        here_post = {s for c in cases for s in model.post_of[c]}

        fn_there = str((family.get("functions") or {}).get("primary") or "")
        fn_here = {model.primary_function(c) for c in cases}

        notes = []
        if here_pre != there_pre:
            notes.append(f"requires: graph {sorted(here_pre)} vs repo {sorted(there_pre)}")
        if here_post != there_post:
            notes.append(f"establishes: graph {sorted(here_post)} vs repo {sorted(there_post)}")
        if fn_there and fn_there not in fn_here:
            notes.append(f"primary function: graph {sorted(fn_here)} vs repo [{fn_there}]")
        if notes:
            differences += 1
            print(f"  {label}  <- {', '.join(cases)}")
            for note in notes:
                print(f"      {note}")

    for use_case in unlinked:
        print(f"  {use_case}: documented_by points into the repository but at no family")
        differences += 1

    print()
    print(f"{differences} difference(s). This is a report; it does not gate CI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
