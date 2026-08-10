# Guancheng Wang — academic homepage

A static, dependency-free personal site whose publication list **rebuilds itself
every night** from DBLP, so it stops going stale.

- **Live site:** https://guanchengwang.github.io *(after the setup below)*
- **Stack:** hand-written HTML/CSS/JS + one Python script. No Jekyll, no npm, no build step.

---

## How the auto-updating works

```
                                              ┌─►  data/publications.json
DBLP  ──►  scripts/update_publications.py  ───┼─►  data/publications.bib
                        ▲                     ├─►  index.html         (6 selected)
                        │                     └─►  publications.html  (full list)
             data/overrides.yaml
```

Every night a GitHub Action runs the script, and commits only if something
actually changed. Both lists are written into the pages as **real HTML**, not
fetched by JavaScript at page load — so they stay indexable by search engines
and Google Scholar, and work with JS disabled.

**Sources, and why:**

| Source | Used for | Failure behaviour |
| --- | --- | --- |
| [DBLP](https://dblp.org/pid/196/5011-1) | The publication record itself | Falls back to the last committed `publications.json` |
| `data/overrides.yaml` | Everything DBLP gets wrong or lacks | — |

Citation counts, h-index and i10-index are deliberately **not** collected or
shown. That is a display choice, and it also removes the build's only fragile
dependency: Google Scholar has no API and blocks CI IP ranges.

---

## The file you will actually edit: `data/overrides.yaml`

DBLP lags acceptances, drops subtitles, ignores Chinese-language venues, and
knows nothing about awards or artifact links. Everything in `overrides.yaml`
wins over DBLP.

**A paper was just accepted** (DBLP still shows only the arXiv preprint) — add a
`patch` entry to promote it:

```yaml
patch:
  - match: "Your Paper Title As It Appears On arXiv"
    type: conference          # or journal
    venue: "48th International Conference on Software Engineering"
    venue_short: "ICSE"
    year: 2027
    month: "May"
    award: "ACM SIGSOFT Distinguished Paper Award"   # optional
    topics: ["LLM4SE", "Test Generation"]
```

**Choosing what appears on the homepage** — the homepage shows a short list,
everything else lives on `publications.html`. Edit `selected:` at the top of
`overrides.yaml`:

```yaml
selected:
  - "Exact Title Of A Paper To Feature"
```

Titles are matched *after* any `title:` correction below, and a title that
matches nothing prints a warning when the script runs. Empty the list and the
homepage falls back to the six most recent peer-reviewed papers.

**A paper DBLP will never index** (Chinese journals, some workshops) — add it
under `extra:` with the full author list.

**Marking equal contribution** — authors listed here get a `#`:

```yaml
    equal_contrib: ["Guancheng Wang", "Ruobing Shen"]
```

**Adding code / slides / PDF links** — keyed by title:

```yaml
links:
  "Probabilistic Delta Debugging":
    code: "https://github.com/Amocy-Wang/ProbDD"
    slides: "https://…"
```

After editing, preview locally:

```bash
python3 scripts/update_publications.py
```

Then open `index.html` and `publications.html` in a browser. Commit and push
when it looks right.

---

## Editing everything else

All the prose lives directly in the HTML, in clearly-marked sections:

| Want to change | Where |
| --- | --- |
| Bio, name, affiliation | `index.html` → `<section class="hero">` |
| Research interests (sidebar) | `index.html` → `<div class="sidecard">` |
| News items | `<ul class="news">` — copy an `<li>`, newest first |
| Research themes | `<div class="cards">` |
| Awards | `<div class="awards">` |
| Service / teaching | `<div class="timeline">` |
| Colours, fonts, spacing | `assets/css/style.css` (CSS variables at the top) |
| Selected papers on homepage | `data/overrides.yaml` → `selected:` |

The design is deliberately restrained: one ink-blue accent used almost only for
links, serif headings, hairline rules, no gradients or ambient effects. Gold is
reserved for the two Distinguished Paper awards. If you change `--accent` in
`style.css`, everything follows.

### Privacy choices baked in

- **Your email is never in the served HTML.** It is stored as reversed base64
  in a single `data-e` attribute and decoded in the browser. No fragment — not
  the local part, not the domain, not an `[at]` spelling — appears in the page
  source, so there is nothing for a harvester to reassemble. Splitting it into
  adjacent `user` / `domain` attributes, the common trick, is *not* enough: a
  one-line regex rejoins them.

  To change the address, regenerate the token and paste it into both `.js-mail`
  links in `index.html`:

  ```bash
  python3 -c "import base64;print(base64.b64encode(b'you@example.com').decode()[::-1])"
  ```
- **Fonts are self-hosted** in `assets/fonts/`, so the site makes zero
  third-party requests. Embedding Google Fonts directly would send every
  visitor's IP to Google, which EU courts have found to breach GDPR.

### The travel map

The `Places` section is an inline SVG world map — no tiles, no Google Maps
embed, so it makes no third-party request and leaks no visitor IPs. Add a place
to `data/places.yaml` and rebuild:

```bash
python3 scripts/build_worldmap.py
```

Coordinates are plain decimal degrees; copying the pair from any map site is
accurate enough at this size. `category` picks the marker colour and controls
the legend, which only lists categories actually in use. Country outlines come
from Natural Earth (public domain) and are cached in `data/world-paths.svg`, so
the rebuild is offline after the first run.

**Your photo:** drop a square image at `assets/img/avatar.jpg`. It replaces the
`GW` monogram automatically; if the file is missing the monogram just stays.

---

## First-time deployment

1. **Rename your GitHub account** to `guanchengwang`
   (Settings → Account → Change username). This is what makes the URL
   `guanchengwang.github.io` rather than `amocy-wang.github.io` — GitHub ties
   user-site URLs to the account name, not the repo name. GitHub redirects your
   old repo links automatically.

2. **Create a repository named exactly `guanchengwang.github.io`.**

3. **Push this directory:**

   ```bash
   git remote add origin https://github.com/guanchengwang/guanchengwang.github.io.git
   git add -A && git commit -m "feat: new academic homepage"
   git push -u origin main
   ```

4. **Turn on Pages:** repo → Settings → Pages → *Source: **GitHub Actions***.
   (Not "Deploy from a branch" — the workflows here use the Actions path.)

5. **Allow the Action to commit:** Settings → Actions → General → Workflow
   permissions → **Read and write permissions**. Without this the nightly
   refresh can fetch but not commit.

6. Trigger the first run: Actions tab → *Refresh publications* → **Run workflow**.

---

## Using a custom domain

`gcwang.dev` was unregistered as of the last check and is the shortest sensible
option. Once you own a domain:

1. Create a file named `CNAME` in this directory containing only the domain:

   ```
   gcwang.dev
   ```

2. At your registrar, add these DNS records:

   | Type | Name | Value |
   | --- | --- | --- |
   | A | `@` | `185.199.108.153` |
   | A | `@` | `185.199.109.153` |
   | A | `@` | `185.199.110.153` |
   | A | `@` | `185.199.111.153` |
   | CNAME | `www` | `guanchengwang.github.io.` |

3. Repo → Settings → Pages → Custom domain → enter it → tick **Enforce HTTPS**.

4. Update the three absolute URLs in `index.html` (`<link rel="canonical">`,
   `og:url`, and `url` in the JSON-LD block).

---

## Maintenance: what you actually have to do

**Normally: nothing.** A GitHub Action runs at 04:17 UTC daily, pulls DBLP,
regenerates both publication lists, writes any news the change implies, and
redeploys. It commits only when something really changed, so a quiet week
produces no commits at all.

Three things it cannot know, and how long each takes:

| When | What you do | Effort |
| --- | --- | --- |
| A paper is accepted | Add a `patch` entry in `data/overrides.yaml` promoting it from arXiv to the real venue | ~1 min |
| You want it featured | Add a fragment under `selected:` | ~15 s |
| Non-paper news (PC, award, talk, move) | Add an item to `data/news.yaml` | ~30 s |

Then:

```bash
make && git commit -am "update" && git push
```

`make` rebuilds everything; pushing triggers the deploy.

### Choosing the homepage papers

```bash
make papers
```

Prints every paper with a ★ against the ones currently featured and a
ready-made fragment for each. Copy a quoted string into `selected:` in
`data/overrides.yaml` — a distinctive fragment is enough, no exact titles to
keep in sync. Fragments that match nothing, or match two papers, are reported
when you build.

### News

You should not need to write paper news by hand again. When DBLP first indexes
a paper, or when one of your preprints becomes an accepted paper, the build
writes the item for you into `data/news-auto.json`:

- new paper → *"New preprint: …"* or *"… appears in **TSE**."*
- preprint accepted → *"… is accepted at **ICSE**."*

`data/news.yaml` is for what a publication record cannot see — PC invitations,
awards, talks, moves. `**bold**` and `*italic*` work. Items sort by date
automatically, `max_items` controls how many show, and anything auto-generated
that you dislike can be dropped by putting a fragment of it under `hide:`.

### Before pushing

```bash
make check
```

Confirms the build is reproducible, that no email address leaked into the HTML,
and that no third-party request crept in. Worth running after any edit to the
templates.

### If something looks wrong

- **A paper is missing** — DBLP has not indexed it yet. Add it under `extra:`
  in `overrides.yaml`; when DBLP catches up, the duplicate is merged away.
- **A duplicate preprint and paper** — add the pair under `merge:`.
- **The Action fails to push** — Settings → Actions → General → Workflow
  permissions must be **Read and write**.
- **DBLP is down** — the build falls back to the last committed
  `publications.json`, so the site never empties out.


## Local preview

```bash
make serve
```

Rebuilds and serves at http://localhost:8000.
