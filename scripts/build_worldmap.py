#!/usr/bin/env python3
"""
Render the travel map into index.html from data/places.yaml.

Run after editing places:      python3 scripts/build_worldmap.py

The country outlines come from Natural Earth (public domain, 110m scale),
projected with Robinson and cached to data/world-paths.svg on first run. After
that the build is offline — the nightly publication refresh never touches this,
and adding a place needs no network access.

Everything is inline SVG: no map tiles, no Google Maps embed, no third-party
request. A tile-based map would leak every visitor's IP and approximate
location to the tile host, which is exactly what the rest of this site avoids.
"""

from __future__ import annotations

import json
import math
import re
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PLACES_FILE = DATA / "places.yaml"
CACHE_PATHS = DATA / "world-paths.svg"
GEOJSON_CACHE = DATA / "ne_110m_countries.geojson"
INDEX_HTML = ROOT / "index.html"

GEOJSON_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
               "master/geojson/ne_110m_admin_0_countries.geojson")

# Map canvas. Robinson is 2:1-ish; these numbers give a comfortable aspect.
WIDTH, HEIGHT = 1000.0, 515.0

# With Antarctica dropped, the frame carries empty ocean above ~84°N and below
# ~57°S. Cropping the viewBox to the inhabited band removes roughly 15% of the
# section height without moving a single marker.
VIEW_TOP, VIEW_HEIGHT = 8.0, 448.0

# Robinson projection lookup, 5-degree steps. X scales longitude, Y sets the
# vertical position of each parallel; values between rows are interpolated.
ROBINSON = [
    (0.0, 1.0000, 0.0000), (5.0, 0.9986, 0.0620), (10.0, 0.9954, 0.1240),
    (15.0, 0.9900, 0.1860), (20.0, 0.9822, 0.2480), (25.0, 0.9730, 0.3100),
    (30.0, 0.9600, 0.3720), (35.0, 0.9427, 0.4340), (40.0, 0.9216, 0.4958),
    (45.0, 0.8962, 0.5571), (50.0, 0.8679, 0.6176), (55.0, 0.8350, 0.6769),
    (60.0, 0.7986, 0.7346), (65.0, 0.7597, 0.7903), (70.0, 0.7186, 0.8435),
    (75.0, 0.6732, 0.8936), (80.0, 0.6213, 0.9394), (85.0, 0.5722, 0.9761),
    (90.0, 0.5322, 1.0000),
]

# Antarctica is dropped: it adds a heavy band across the bottom of a Robinson
# map and no one is plotting a conference there.
SKIP = {"Antarctica"}


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def robinson(lon: float, lat: float) -> tuple[float, float]:
    """Project lon/lat degrees to SVG coordinates."""
    alat = min(abs(lat), 90.0)
    i = min(int(alat // 5), len(ROBINSON) - 2)
    lo_lat, lo_x, lo_y = ROBINSON[i]
    hi_lat, hi_x, hi_y = ROBINSON[i + 1]
    t = 0.0 if hi_lat == lo_lat else (alat - lo_lat) / (hi_lat - lo_lat)

    xf = lo_x + (hi_x - lo_x) * t
    yf = lo_y + (hi_y - lo_y) * t
    if lat < 0:
        yf = -yf

    # 0.8487 / 1.3523 are Robinson's standard scaling constants.
    x = 0.8487 * xf * math.radians(lon)
    y = 1.3523 * yf

    # Normalise into the viewBox: x spans ±0.8487·π, y spans ±1.3523.
    sx = (x / (0.8487 * math.pi) + 1) / 2 * WIDTH
    sy = (1 - y / 1.3523) / 2 * HEIGHT
    return sx, sy


def ring_to_path(ring: list, min_area: float) -> str | None:
    """Convert one polygon ring to an SVG path, dropping specks."""
    pts = []
    last = None
    for lon, lat in ring:
        x, y = robinson(lon, lat)
        p = (round(x, 1), round(y, 1))
        if p != last:            # collapse duplicates after rounding
            pts.append(p)
            last = p
    if len(pts) < 4:
        return None

    # Shoelace area, to discard islands too small to see at this size.
    area = abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] -
                   pts[(i + 1) % len(pts)][0] * pts[i][1]
                   for i in range(len(pts)))) / 2
    if area < min_area:
        return None

    head = f"M{pts[0][0]} {pts[0][1]}"
    tail = "".join(f"L{x} {y}" for x, y in pts[1:])
    return head + tail + "Z"


def build_world_paths(min_area: float = 1.5) -> str:
    if CACHE_PATHS.exists():
        log(f"using cached {CACHE_PATHS.relative_to(ROOT)}")
        return CACHE_PATHS.read_text()

    if GEOJSON_CACHE.exists():
        raw = GEOJSON_CACHE.read_text()
    else:
        log("fetching Natural Earth 110m countries (public domain)…")
        with urllib.request.urlopen(GEOJSON_URL, timeout=90) as resp:
            raw = resp.read().decode("utf-8")
        GEOJSON_CACHE.write_text(raw)

    geo = json.loads(raw)
    paths = []
    for feat in geo["features"]:
        if feat["properties"].get("NAME") in SKIP:
            continue
        geom = feat["geometry"]
        polys = ([geom["coordinates"]] if geom["type"] == "Polygon"
                 else geom["coordinates"])
        for poly in polys:
            for ring in poly:            # ring 0 is outer, rest are holes
                d = ring_to_path(ring, min_area)
                if d:
                    paths.append(d)

    svg = f'<path class="map__land" d="{"".join(paths)}"/>'
    CACHE_PATHS.write_text(svg)
    log(f"wrote {CACHE_PATHS.relative_to(ROOT)} "
        f"({len(paths)} rings, {len(svg) / 1024:.0f} KB)")
    # The raw GeoJSON is only needed to regenerate; keep the repo lean.
    GEOJSON_CACHE.unlink(missing_ok=True)
    return svg


def render_markers(places: list[dict]) -> tuple[str, str]:
    """Returns (svg markers, html list grouped by country).

    Once the list runs past a dozen entries, one row per place is unreadable.
    Grouping by country and running the names inline keeps it scannable at any
    length, and each name still cross-highlights with its pin."""
    dots = []
    groups: dict[str, list[str]] = {}      # insertion-ordered by first use

    for i, p in enumerate(places):
        x, y = robinson(float(p["lon"]), float(p["lat"]))
        cat = p.get("category", "visited")
        name = p["name"]
        note = p.get("note", "")
        country = p.get("country", "")
        label = ", ".join(filter(None, [name, country]))
        if note:
            label += f" — {note}"

        dots.append(
            f'      <g class="map__pin map__pin--{cat}" data-place="{i}" '
            f'transform="translate({x:.1f} {y:.1f})" tabindex="0" role="img" '
            f'aria-label="{label}">\n'
            f'        <circle class="map__halo" r="8"/>\n'
            + ('        <circle class="map__ring" r="6"/>\n' if cat == "work" else "")
            + f'        <circle class="map__dot" r="3.2"/>\n'
            + (f'        <text class="map__label" x="10" y="3.5">{name}</text>\n'
               if cat == "work" else "")
            + f'        <title>{label}</title>\n'
            f'      </g>'
        )
        groups.setdefault(country, []).append(
            f'<span class="place place--{cat}" data-place="{i}"'
            + (f' title="{note}"' if note else "")
            + f'>{name}</span>'
        )

    items = []
    for country, names in groups.items():
        items.append(
            f'          <li class="places__group">'
            f'<span class="places__country">{country}</span>'
            f'<span class="places__names">{", ".join(names)}</span></li>'
        )
    return "\n".join(dots), "\n".join(items)


def inject(marker: str, content: str, page: str) -> str:
    start, end = f"<!-- {marker}:START -->", f"<!-- {marker}:END -->"
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pat.search(page):
        log(f"WARNING: marker {marker} not found in index.html")
        return page
    return pat.sub(lambda _: f"{start}\n{content}\n      {end}", page)


def main() -> int:
    print("\nBuilding travel map\n" + "-" * 40)
    if not PLACES_FILE.exists():
        log(f"missing {PLACES_FILE.relative_to(ROOT)}")
        return 1

    cfg = yaml.safe_load(PLACES_FILE.read_text()) or {}
    places = cfg.get("places") or []
    land = build_world_paths()
    dots, items = render_markers(places)

    # Only legend the categories actually in use — an empty key is noise.
    used = {p.get("category", "visited") for p in places}
    legend = "".join(
        f'<span class="map__key map__key--{key}">{meta["label"]}</span>'
        for key, meta in (cfg.get("categories") or {}).items() if key in used
    )

    countries = len({p.get("country", "") for p in places})
    summary = (f'<p class="map__count">{len(places)} places across '
               f'{countries} countries</p>')

    svg = (f'      <svg class="map__svg" '
           f'viewBox="0 {VIEW_TOP:.0f} {WIDTH:.0f} {VIEW_HEIGHT:.0f}" '
           f'role="group" aria-label="World map of places visited" '
           f'xmlns="http://www.w3.org/2000/svg">\n'
           f'        {land}\n{dots}\n      </svg>\n'
           f'      <p class="map__legend">{legend}{summary}</p>\n'
           f'      <details class="places-toggle">\n'
           f'        <summary>Show the list</summary>\n'
           f'        <ul class="places">\n{items}\n        </ul>\n'
           f'      </details>')

    page = INDEX_HTML.read_text()
    page = inject("MAP", svg, page)
    INDEX_HTML.write_text(page)

    by_cat: dict[str, int] = {}
    for p in places:
        by_cat[p.get("category", "visited")] = by_cat.get(p.get("category", "visited"), 0) + 1
    log(f"placed {len(places)} marker(s): " +
        ", ".join(f"{v} {k}" for k, v in sorted(by_cat.items())))
    print("-" * 40 + "\nDone\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
