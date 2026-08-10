#!/usr/bin/env python3
"""
List every paper with a ready-to-paste string for `selected:` in overrides.yaml.

    make papers          # or: python3 scripts/papers.py

Choosing what the homepage features should not mean hunting through DBLP and
copying a title exactly. This prints the shortest fragment that identifies each
paper unambiguously, marks the ones currently selected, and can be filtered:

    python3 scripts/papers.py llm      # only papers matching "llm"
"""

import json
import re
import sys
from pathlib import Path

PUBS = Path(__file__).resolve().parent.parent / "data" / "publications.json"


def norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def shortest_unique(title: str, others: list[str]) -> str:
    """Fewest leading words that no other title contains."""
    words = title.split()
    for n in range(2, len(words) + 1):
        frag = " ".join(words[:n])
        if not any(norm(frag) in norm(o) for o in others):
            return frag
    return title


def main() -> int:
    if not PUBS.exists():
        print("Run `make pubs` first.")
        return 1

    data = json.loads(PUBS.read_text())
    pubs = data["publications"]
    needle = " ".join(sys.argv[1:]).lower()

    print(f"\n{len(pubs)} papers · ★ = currently on the homepage")
    print("Paste the quoted string under `selected:` in data/overrides.yaml\n")

    shown = 0
    for pub in pubs:
        blob = (pub["title"] + " " + (pub.get("venue_short") or "") + " " +
                " ".join(a["name"] for a in pub["authors"])).lower()
        if needle and needle not in blob:
            continue
        shown += 1
        others = [p["title"] for p in pubs if p is not pub]
        frag = shortest_unique(pub["title"], others)
        star = "★" if pub.get("selected") else " "
        venue = (pub.get("venue_short") or "")[:9]
        print(f' {star} {pub["year"]}  {venue:<9}  "{frag}"')
        if frag.lower() != pub["title"].lower():
            print(f"              {pub['title'][:72]}")

    if needle and not shown:
        print(f"  nothing matched {needle!r}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
