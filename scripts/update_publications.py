#!/usr/bin/env python3
"""
Rebuild the publication list from DBLP, apply the human overrides, and render it
into both pages: a short "selected" list on the homepage and the complete,
filterable list on publications.html.

Run it locally to preview:      python3 scripts/update_publications.py
The GitHub Action runs it daily and commits whatever changed.

Design notes
------------
DBLP is the single source of truth. It has a stable API, no meaningful rate
limiting, and it indexes every venue that matters here. Nothing is scraped from
Google Scholar: citation counts are deliberately not collected or displayed, so
the build has no fragile dependency on a service that blocks CI IP ranges.

Both lists are rendered as real HTML into the pages rather than fetched by
JavaScript at load time, so they stay indexable and work without JS.
"""

from __future__ import annotations

import html
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OVERRIDES_FILE = DATA / "overrides.yaml"
OUTPUT_JSON = DATA / "publications.json"
OUTPUT_BIB = DATA / "publications.bib"
INDEX_HTML = ROOT / "index.html"
PUBS_HTML = ROOT / "publications.html"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " \
     "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def fetch(url: str, timeout: int = 30, retries: int = 3) -> str | None:
    """GET a URL as text. Returns None instead of raising — every caller has a
    sane fallback, and a hard failure would break the nightly build."""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept-Language": "en-US,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            log(f"attempt {attempt}/{retries} failed for {url}: {exc}")
    return None


def norm_title(title: str) -> str:
    """Normalise a title for matching: lowercase, alphanumerics only. DBLP
    appends a trailing period and varies capitalisation between the preprint
    and camera-ready records, so exact matching is useless."""
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_title(a), norm_title(b)).ratio()


def clean_title(title: str) -> str:
    return title.strip().rstrip(".").strip()


# --------------------------------------------------------------------------
# DBLP
# --------------------------------------------------------------------------

def parse_dblp(pid: str) -> list[dict]:
    """Pull the full DBLP record for a persistent author ID."""
    xml = fetch(f"https://dblp.org/pid/{pid}.xml")
    if not xml:
        log("DBLP unreachable — reusing cached publications")
        return []

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        log(f"DBLP XML malformed: {exc}")
        return []

    pubs = []
    for record in root.iter("r"):
        for node in record:
            title = clean_title("".join(node.find("title").itertext())
                                if node.find("title") is not None else "")
            if not title:
                continue

            journal = node.findtext("journal") or ""
            booktitle = node.findtext("booktitle") or ""
            is_preprint = journal == "CoRR"

            if is_preprint:
                kind = "preprint"
            elif booktitle:
                kind = "conference"
            else:
                kind = "journal"

            ees = [e.text for e in node.findall("ee") if e.text]
            doi = next((re.sub(r"^https?://doi\.org/", "", e)
                        for e in ees if "doi.org" in e and "arXiv" not in e), None)
            arxiv = None
            for e in ees:
                m = re.search(r"arXiv\.(\d{4}\.\d{4,5})", e) or \
                    re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5})", e)
                if m:
                    arxiv = m.group(1)
            if not arxiv and is_preprint:
                m = re.search(r"abs/(\d{4}\.\d{4,5})", node.findtext("volume") or "")
                if m:
                    arxiv = m.group(1)

            # For a CoRR record the "volume" is just the arXiv id (abs/2603.00520),
            # which we have already captured. Leaving it in place would print
            # "arXiv preprint, abs/2603.00520" — and worse, would survive if an
            # override later promotes the preprint to its published venue.
            pubs.append({
                "id": node.get("key", ""),
                "title": title,
                "authors": [re.sub(r"\s+\d{4}$", "", a.text).strip()
                            for a in node.findall("author") if a.text],
                "year": int(node.findtext("year") or 0),
                "type": kind,
                "venue": "arXiv preprint" if is_preprint else (journal or booktitle),
                "venue_short": "arXiv" if is_preprint else (journal or booktitle),
                "volume": None if is_preprint else node.findtext("volume"),
                "number": None if is_preprint else node.findtext("number"),
                "pages": None if is_preprint else node.findtext("pages"),
                "doi": doi,
                "arxiv": arxiv,
                "url": ees[0] if ees else None,
                "source": "dblp",
            })

    log(f"DBLP returned {len(pubs)} records")
    return pubs


def fetch_bibtex(pid: str) -> str | None:
    return fetch(f"https://dblp.org/pid/{pid}.bib?param=1")


def load_cached() -> dict:
    if OUTPUT_JSON.exists():
        try:
            return json.loads(OUTPUT_JSON.read_text())
        except json.JSONDecodeError:
            pass
    return {}


# --------------------------------------------------------------------------
# merge + override
# --------------------------------------------------------------------------

def collapse_preprints(pubs: list[dict], merge_rules: list[dict]) -> list[dict]:
    """Drop an arXiv preprint when its published version is also present,
    carrying the arXiv id onto the published entry."""
    published = [p for p in pubs if p["type"] != "preprint"]
    explicit = {norm_title(r["preprint"]): norm_title(r["published"])
                for r in merge_rules}

    keep, dropped = [], 0
    for pub in pubs:
        if pub["type"] != "preprint":
            keep.append(pub)
            continue

        target = None
        want = explicit.get(norm_title(pub["title"]))
        for cand in published:
            if want and norm_title(cand["title"]) == want:
                target = cand
                break
            if title_similarity(pub["title"], cand["title"]) > 0.85:
                target = cand
                break

        if target:
            target["arxiv"] = target.get("arxiv") or pub.get("arxiv")
            dropped += 1
        else:
            keep.append(pub)

    log(f"collapsed {dropped} preprint(s) into published versions")
    return keep


def apply_overrides(pubs: list[dict], ov: dict) -> list[dict]:
    patches = ov.get("patch") or []
    extras = ov.get("extra") or []
    hidden = {norm_title(h) for h in (ov.get("hide") or [])}
    links = {norm_title(k): v for k, v in (ov.get("links") or {}).items()}
    selected = {norm_title(t) for t in (ov.get("selected") or [])}

    # Extras go in first so patch/merge rules can also target them.
    # A manual entry is authoritative: when DBLP already has something under the
    # same title it is almost always the arXiv preprint of this very paper, so we
    # replace it and inherit its identifiers rather than skipping the extra.
    for e in extras:
        entry = dict(e)
        entry.setdefault("id", "extra/" + norm_title(entry["title"])[:40])
        entry.setdefault("source", "manual")
        entry.setdefault("type", "journal")

        key = norm_title(entry["title"])
        for existing in [p for p in pubs if norm_title(p["title"]) == key]:
            for field in ("arxiv", "doi", "url"):
                if not entry.get(field) and existing.get(field):
                    entry[field] = existing[field]
            pubs.remove(existing)
        pubs.append(entry)
    log(f"added {len(extras)} manual entr(ies)")

    pubs = collapse_preprints(pubs, ov.get("merge") or [])

    applied = 0
    for patch in patches:
        key = norm_title(patch["match"])
        for pub in pubs:
            if norm_title(pub["title"]) == key or \
                    title_similarity(pub["title"], patch["match"]) > 0.9:
                for field, value in patch.items():
                    if field != "match":
                        pub[field] = value
                applied += 1
                break
    log(f"applied {applied}/{len(patches)} patch rule(s)")

    for pub in pubs:
        extra_links = links.get(norm_title(pub["title"]))
        if extra_links:
            pub["links"] = {**pub.get("links", {}), **extra_links}
        # Titles are matched after patching, so a patched title is what to list
        # under `selected:` in overrides.yaml.
        pub["selected"] = norm_title(pub["title"]) in selected

    unmatched = selected - {norm_title(p["title"]) for p in pubs}
    for miss in unmatched:
        log(f"WARNING: selected title matched nothing: {miss[:50]}")

    return [p for p in pubs if norm_title(p["title"]) not in hidden]


def mark_authors(pubs: list[dict], aliases: list[str]) -> None:
    alias_set = {a.lower().replace(" ", "") for a in aliases}
    for pub in pubs:
        equal = {e.lower().replace(" ", "")
                 for e in (pub.get("equal_contrib") or [])}
        marked = []
        for name in pub.get("authors", []):
            flat = name.lower().replace(" ", "")
            marked.append({
                "name": name,
                "is_me": flat in alias_set,
                "equal": flat in equal,
            })
        pub["authors"] = marked


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

TYPE_ORDER = {"journal": 0, "conference": 1, "preprint": 2}


def sort_key(pub: dict):
    return (-int(pub.get("year") or 0),
            TYPE_ORDER.get(pub.get("type"), 3),
            MONTHS.index(pub["month"]) * -1 if pub.get("month") in MONTHS else 0,
            pub.get("title", ""))


def esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def render_authors(authors: list[dict]) -> str:
    out = []
    for a in authors:
        name = esc(a["name"]) + ("<sup>#</sup>" if a.get("equal") else "")
        out.append(f'<span class="author me">{name}</span>' if a["is_me"]
                   else f"<span class='author'>{name}</span>")
    return ", ".join(out)


def render_links(pub: dict) -> str:
    items = []
    if pub.get("doi"):
        items.append(("DOI", f"https://doi.org/{pub['doi']}", "doi"))
    if pub.get("arxiv"):
        items.append(("arXiv", f"https://arxiv.org/abs/{pub['arxiv']}", "arxiv"))
    for label, key in (("PDF", "pdf"), ("Code", "code"), ("Slides", "slides"),
                       ("Video", "video"), ("Data", "data")):
        url = (pub.get("links") or {}).get(key)
        if url:
            items.append((label, url, key))
    if not items and pub.get("url"):
        items.append(("Link", pub["url"], "doi"))

    return "".join(
        f'<a class="publink publink--{cls}" href="{esc(url)}" '
        f'target="_blank" rel="noopener">{label}</a>'
        for label, url, cls in items
    )


def render_publication(pub: dict, indent: str = "        ") -> str:
    year = pub.get("year") or ""
    topics = pub.get("topics") or []
    venue_short = pub.get("venue_short") or ""

    venue_line = esc(pub.get("venue") or "")
    if pub.get("type") == "preprint" and pub.get("arxiv"):
        venue_line = f"arXiv preprint arXiv:{esc(pub['arxiv'])}"
    # Journals read "TSE, 52(5):1657-1671"; conference papers have no volume, so
    # their page range needs "pp." rather than a bare colon.
    if pub.get("volume"):
        venue_line += f", {esc(pub['volume'])}"
        if pub.get("number"):
            venue_line += f"({esc(pub['number'])})"
        if pub.get("pages"):
            venue_line += f":{esc(pub['pages'])}"
    elif pub.get("pages"):
        venue_line += f", pp. {esc(pub['pages'])}"

    badges = ""
    if pub.get("award"):
        badges += (f'<span class="badge badge--award">'
                   f'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4L4.2 7.7l5.4-.8z"/></svg>'
                   f'{esc(pub["award"])}</span>')
    if pub.get("status"):
        badges += f'<span class="badge badge--status">{esc(pub["status"])}</span>'

    note = f'<span class="pub-note">{esc(pub["note"])}</span>' if pub.get("note") else ""

    return f"""{indent}<article class="pub" data-type="{esc(pub.get('type'))}" data-year="{esc(year)}" data-topics="{esc(' '.join(topics))}" data-title="{esc(pub.get('title'))}" data-authors="{esc(' '.join(a['name'] for a in pub.get('authors', [])))}" data-venue="{esc(pub.get('venue'))} {esc(venue_short)}">
{indent}  <div class="pub__rail"><span class="pub__venue-tag">{esc(venue_short)}</span><span class="pub__year">{esc(year)}</span></div>
{indent}  <div class="pub__body">
{indent}    <h3 class="pub__title">{esc(pub.get('title'))}</h3>
{indent}    <p class="pub__authors">{render_authors(pub.get('authors', []))}</p>
{indent}    <p class="pub__venue">{venue_line}{note}</p>
{indent}    <div class="pub__meta">{badges}</div>
{indent}    <div class="pub__links">{render_links(pub)}</div>
{indent}  </div>
{indent}</article>"""


def render_full_list(pubs: list[dict]) -> str:
    """Complete list, grouped by year — for publications.html."""
    blocks, current_year = [], None
    for pub in pubs:
        if pub.get("year") != current_year:
            current_year = pub.get("year")
            blocks.append(f'        <h3 class="pub-year-heading">{esc(current_year)}</h3>')
        blocks.append(render_publication(pub))
    return "\n".join(blocks)


def render_selected(pubs: list[dict]) -> str:
    """Short curated list, no year headings — for the homepage."""
    chosen = [p for p in pubs if p.get("selected")]
    if not chosen:
        # Nothing marked in overrides.yaml — fall back to peer-reviewed work so
        # the homepage is never empty.
        chosen = [p for p in pubs if p["type"] != "preprint"][:6]
    return "\n".join(render_publication(p) for p in chosen)


def inject(marker: str, content: str, page: str, inline: bool = False) -> str:
    """Replace everything between a START/END comment pair. `inline` keeps the
    replacement on one line — newlines would collapse to a stray space inside
    running prose."""
    start, end = f"<!-- {marker}:START -->", f"<!-- {marker}:END -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(page):
        log(f"WARNING: marker {marker} not found")
        return page
    body = f"{start}{content}{end}" if inline else f"{start}\n{content}\n        {end}"
    return pattern.sub(lambda _: body, page)


def render_updated(ts: str) -> str:
    pretty = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").strftime("%d %B %Y")
    return f'<time datetime="{ts}">{pretty}</time>'


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    print("\nRebuilding publications\n" + "-" * 40)
    ov = yaml.safe_load(OVERRIDES_FILE.read_text()) or {}
    author = ov.get("author", {})
    cached = load_cached()

    pubs = parse_dblp(author["dblp_pid"])
    if not pubs and cached.get("publications"):
        log("keeping cached publication list")
        pubs = [dict(p, authors=[a["name"] for a in p["authors"]])
                for p in cached["publications"]]

    pubs = apply_overrides(pubs, ov)
    mark_authors(pubs, author.get("aliases", []))
    pubs.sort(key=sort_key)

    counts = {
        "papers": len(pubs),
        "peer_reviewed": len([p for p in pubs if p["type"] != "preprint"]),
        "preprints": len([p for p in pubs if p["type"] == "preprint"]),
        "selected": len([p for p in pubs if p.get("selected")]),
    }

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "generated_at": generated_at,
        "counts": counts,
        "publications": pubs,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    log(f"wrote {OUTPUT_JSON.relative_to(ROOT)} ({len(pubs)} entries)")

    bib = fetch_bibtex(author["dblp_pid"])
    if bib:
        OUTPUT_BIB.write_text(bib)
        log(f"wrote {OUTPUT_BIB.relative_to(ROOT)}")

    stamp = render_updated(generated_at)

    if INDEX_HTML.exists():
        page = INDEX_HTML.read_text()
        page = inject("SELECTED", render_selected(pubs), page)
        page = inject("UPDATED", stamp, page, inline=True)
        INDEX_HTML.write_text(page)
        log(f"injected {counts['selected'] or 'fallback'} selected into index.html")

    if PUBS_HTML.exists():
        page = PUBS_HTML.read_text()
        page = inject("PUBLICATIONS", render_full_list(pubs), page)
        page = inject("UPDATED", stamp, page, inline=True)
        PUBS_HTML.write_text(page)
        log(f"injected {len(pubs)} into publications.html")

    print("-" * 40)
    print(f"Done — {counts['papers']} papers "
          f"({counts['peer_reviewed']} peer-reviewed, "
          f"{counts['preprints']} preprints), "
          f"{counts['selected']} selected\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
