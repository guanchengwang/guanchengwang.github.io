# Guancheng Wang — academic homepage

A static, dependency-free personal site whose **publication list and news
rebuild themselves nightly** from DBLP, so it cannot go stale the way a
hand-edited page does.

No Jekyll, no npm, no build step, no third-party requests. Hand-written
HTML/CSS/JS plus three Python scripts.

---

## Contents

- [The 30-second version](#the-30-second-version)
- [Everyday maintenance](#everyday-maintenance) ← the part you will actually use
- [Where everything lives](#where-everything-lives)
- [How the automation works](#how-the-automation-works)
- [Reference: the data files](#reference-the-data-files)
- [Design and privacy decisions](#design-and-privacy-decisions)
- [First-time deployment](#first-time-deployment)
- [Changing the site address](#changing-the-site-address)
- [Troubleshooting](#troubleshooting)

---

## The 30-second version

```bash
make          # rebuild everything from data/
make papers   # list papers, pick which appear on the homepage
make serve    # preview at http://localhost:8000
make check    # verify before pushing
```

Edit a file in `data/`, run `make`, commit, push. That is the whole workflow.

```bash
make && git commit -am "update" && git push
```

---

## Everyday maintenance

**Normally you do nothing.** A GitHub Action runs at 04:17 UTC daily: it pulls
DBLP, regenerates both publication lists, derives any news the change implies,
and redeploys. It commits **only when something actually changed**, so a quiet
month produces no commits.

Three things the automation cannot know:

| When | What you do | Effort |
| --- | --- | --- |
| A paper is accepted | Add a `patch` entry in `data/overrides.yaml` promoting it from arXiv to the real venue | ~1 min |
| You want it on the homepage | Add a fragment under `selected:` | ~15 s |
| Non-paper news — PC, award, talk, move | Add an item to `data/news.yaml` | ~30 s |
| You travelled somewhere | Add an entry to `data/places.yaml` | ~20 s |

### A paper got accepted

DBLP will still be showing only the arXiv preprint. Tell it the real venue:

```yaml
patch:
  - match: "Call-Chain-Aware LLM-Based Test Generation"   # a fragment is fine
    type: conference          # or journal
    venue: "48th International Conference on Software Engineering"
    venue_short: "ICSE"       # what shows in the left rail
    year: 2027
    month: "May"
    award: "ACM SIGSOFT Distinguished Paper Award"   # optional
    topics: ["LLM4SE", "Test Generation"]
```

Run `make`. The news item — *"… is accepted at **ICSE**."* — writes itself.

When DBLP later indexes the published version properly, the patch keeps
agreeing with it and the arXiv preprint is folded in automatically.

### Choosing the homepage papers

```bash
make papers
```

```
 ★ 2026  TSE        "Mutation-Guided Unit"
   2026  arXiv      "BeSpec: Behavior-Level"
```

★ marks what is currently featured. Copy a quoted fragment into `selected:` in
`data/overrides.yaml`. **A distinctive fragment is enough** — you never need to
paste a full title or keep it in sync when a venue renames the paper. An exact
title beats a partial one, and a fragment matching nothing (or two papers) is
reported when you build.

To filter, call the script directly — `make` would read the word as a target:

```bash
python3 scripts/papers.py llm
```

### News

**You should not need to write paper news by hand again.** The build diffs the
publication record against the previous run and writes items itself:

| Change | Item written |
| --- | --- |
| DBLP indexes a new preprint | *"New preprint: …"* |
| DBLP indexes a new paper | *"… appears in **TSE**."* |
| A preprint of yours becomes accepted | *"… is accepted at **ICSE**."* |

These accumulate in `data/news-auto.json` — a generated file, do not edit it.

`data/news.yaml` is for everything a publication record cannot see:

```yaml
items:
  - date: 2027-03                    # "YYYY-MM" or just "YYYY"
    text: "Giving a talk at **Some Workshop** on trustworthy test generation."
```

`**bold**` and `*italic*` work. Items sort by date automatically, so append
anywhere. `settings.max_items` caps how many show. To suppress an auto-written
item, put a fragment of its text under `hide:`.

### Before pushing

```bash
make check
```

Three assertions:

1. the build is **reproducible** — running twice gives identical output;
2. **no email address** appears in any served HTML;
3. **no third-party request** has crept in.

Worth running after any edit to the templates or scripts.

---

## Where everything lives

```
data/            ← you edit these
  overrides.yaml     publication corrections, selected papers, artifact links
  news.yaml          hand-written news
  places.yaml        travel map
  publications.json  GENERATED — the merged record
  news-auto.json     GENERATED — auto-derived news
  publications.bib   GENERATED — BibTeX for the whole record
  world-paths.svg    GENERATED — cached country outlines

scripts/
  update_publications.py   DBLP → publications + news → both pages
  build_worldmap.py        places.yaml → the map
  papers.py                `make papers`
  set_site_url.py          repoint canonical / og:url / JSON-LD

index.html         homepage — prose is edited here directly
publications.html  full list — generated content only
404.html
assets/            css, js, self-hosted fonts, avatar
```

Generated blocks in the HTML sit between markers such as
`<!-- PUBLICATIONS:START -->`. **Anything between a START/END pair is
overwritten on every build** — edit the data file instead.

Prose lives directly in `index.html`:

| Want to change | Where |
| --- | --- |
| Bio, name, affiliation, pronunciation | `<section class="hero">` |
| Research themes | `<div class="cards">` |
| Awards | `<div class="awards">` |
| Service, teaching | `<div class="timeline">` |
| Contact text | `<section id="contact">` |
| Colours, fonts, spacing | `assets/css/style.css` — variables at the top |

**Your photo:** drop a square image at `assets/img/avatar.jpg`. It replaces the
`GW` monogram automatically; if the file is missing the monogram simply stays.

---

## How the automation works

```
                                       ┌─►  data/publications.json
DBLP  ──►  update_publications.py  ────┼─►  data/publications.bib
                    ▲                  ├─►  data/news-auto.json
                    │                  ├─►  index.html         (6 selected + news)
      overrides.yaml + news.yaml       └─►  publications.html  (full list)
```

Both lists are written into the pages as **real HTML**, not fetched by
JavaScript at load. They stay indexable by search engines and Google Scholar,
and work with JavaScript disabled.

**DBLP is the only network source.** Citation counts, h-index and i10-index are
deliberately not collected or displayed — a display choice that also removes
the build's one fragile dependency, since Google Scholar has no API and blocks
CI address ranges.

If DBLP is unreachable the build falls back to the last committed
`publications.json`, so the site never empties out.

---

## Reference: the data files

### `data/overrides.yaml`

Everything here wins over DBLP.

| Key | Purpose |
| --- | --- |
| `selected:` | Which papers appear on the homepage (fragments) |
| `patch:` | Correct or promote an entry DBLP already has |
| `extra:` | Papers DBLP will never index — Chinese venues, some workshops |
| `merge:` | Collapse a preprint into its published version when retitled |
| `links:` | Per-paper code / slides / PDF / video links |
| `hide:` | Drop an entry entirely |

Equal contribution, giving authors a `#`:

```yaml
patch:
  - match: "Probabilistic Delta Debugging"
    equal_contrib: ["Guancheng Wang", "Ruobing Shen"]
```

Artifact links, keyed by title:

```yaml
links:
  "Probabilistic Delta Debugging":
    code: "https://github.com/Amocy-Wang/ProbDD"
    slides: "https://…"
```

> Do not advertise a replication package for a paper that has not been
> accepted. The CAT entry is commented out for exactly this reason — uncomment
> it when the paper lands.

### `data/places.yaml`

```yaml
- { name: "Kyoto", country: "Japan", lat: 35.0116, lon: 135.7681 }
```

Decimal degrees; copying the pair off any map site is accurate enough at this
size. `category: work` marks the current work location — accent colour, larger
pin, always labelled. Everything else defaults to `visited`.

Country outlines come from Natural Earth (public domain), cached in
`data/world-paths.svg`, so rebuilds are offline. To regenerate them, delete
that file and run `make map`.

### `data/news.yaml`

See [News](#news) above. `settings.auto_from_publications: false` turns off
auto-derived items entirely.

---

## Design and privacy decisions

Restrained editorial: one ink-blue accent used almost exclusively for links,
serif headings over a sans body, hairline rules, no gradients or ambient
effects. Gold is reserved for the two Distinguished Paper awards. Changing
`--accent` in `style.css` moves everything with it.

Three deliberate privacy choices, each of which a conventional implementation
would have got wrong:

- **The email address never appears in the served HTML.** It is stored as
  reversed base64 in one `data-e` attribute and decoded only when a visitor
  clicks *Show email address*. There is no `mailto:` link anywhere — a
  `mailto:` is a one-click target for automated mail and has to put the address
  in the DOM to work at all. Splitting it across adjacent `user`/`domain`
  attributes, the usual trick, is **not** enough: a one-line regex rejoins them.

  To change the address, regenerate the token and paste it into both `.js-mail`
  elements in `index.html`:

  ```bash
  python3 -c "import base64;print(base64.b64encode(b'you@example.com').decode()[::-1])"
  ```

  This stops bulk harvesters, which do not run JavaScript. A scraper
  deliberately targeting you and simulating a click still wins — no
  client-side scheme can prevent that, since the browser needs the address to
  make the link work.

- **Fonts are self-hosted** in `assets/fonts/`. Embedding Google Fonts sends
  every visitor's IP to Google, which EU courts have found to breach GDPR.

- **The travel map is inline SVG**, not map tiles. A Leaflet/OSM or Google Maps
  embed would send every visitor's IP and approximate location to the tile host.

`make check` enforces the first and second of these.

---

## First-time deployment

> **Decide the URL first.** GitHub ties a user-site address to the *account*
> name, not the repo name — `guanchengwang.github.io` requires the account
> itself to be `guanchengwang`. Renaming later means redoing steps 2–4.

1. **Rename the GitHub account** to `guanchengwang`
   (Settings → Account → Change username). GitHub redirects old repo links
   automatically. *Skip if you are keeping `Amocy-Wang`, and run
   `python3 scripts/set_site_url.py https://amocy-wang.github.io` instead.*

2. **Create a repository named exactly `<account>.github.io`**, empty — no
   README, no .gitignore, no licence.

3. **Push:**

   ```bash
   git remote add origin git@github.com:guanchengwang/guanchengwang.github.io.git
   git push -u origin main
   ```

4. **Settings → Pages → Source: GitHub Actions.**
   Not "Deploy from a branch" — the workflows here use the Actions path.

5. **Settings → Actions → General → Workflow permissions → Read and write.**
   Without this the nightly refresh can fetch but cannot commit.

6. **Actions → *Refresh publications* → Run workflow** to trigger the first
   build rather than waiting for 04:17 UTC.

The site is live a minute or two later. Check the Actions tab if it is not.

---

## Changing the site address

Three absolute URLs must agree with where the site actually lives — the
canonical link, `og:url`, and `url` in the JSON-LD block — or search results
and link previews point at the wrong place. One command does all of them on
every page:

```bash
python3 scripts/set_site_url.py https://gcwang.dev
```

For a custom domain it also writes the `CNAME` file. Then at your registrar:

| Type | Name | Value |
| --- | --- | --- |
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `<account>.github.io.` |

Then repo → Settings → Pages → Custom domain → enter it → tick
**Enforce HTTPS**. DNS can take an hour or so to propagate.

`gcwang.dev`, `gcwang.io` and `gcwang.me` were all unregistered as of
August 2026.

---

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| A paper is missing | DBLP has not indexed it. Add it under `extra:`; when DBLP catches up the duplicate is merged away automatically. |
| A preprint and paper both listed | Add the pair under `merge:` in `overrides.yaml`. |
| A `selected:` fragment did nothing | The build prints a warning. Run `make papers` for a fragment that works. |
| Nightly Action fails to push | Settings → Actions → General → Workflow permissions → **Read and write**. |
| Site not updating | Actions tab → check the last run. Pages source must be **GitHub Actions**. |
| `make check` says not reproducible | Something in the build depends on the clock or on ordering. The last-updated stamp is deliberately frozen unless the record changed; check anything you added since. |
| Wrong URL in Google results | `python3 scripts/set_site_url.py <the right one>`, rebuild, push. |
| Map markers in the wrong place | Latitude and longitude are the other way round in `places.yaml`. |

### Rebuilding from scratch

```bash
rm data/world-paths.svg      # re-fetch and re-project country outlines
make
```

`data/publications.json` is safe to delete too — it is refetched from DBLP —
but it doubles as the offline fallback and as the baseline for auto-news, so
deleting it means the next run derives no news items.
