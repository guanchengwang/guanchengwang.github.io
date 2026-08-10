#!/usr/bin/env python3
"""
Point the site at a different address.

    python3 scripts/set_site_url.py https://guanchengwang.github.io
    python3 scripts/set_site_url.py https://gcwang.dev

Three absolute URLs have to agree with where the site actually lives, or search
results and link previews point at the wrong place: <link rel="canonical">,
og:url, and "url" in the JSON-LD block. They are easy to update individually
and easy to forget, so this does all of them across every page.

Passing a custom domain also writes the CNAME file GitHub Pages needs.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = {"index.html": "", "publications.html": "publications.html"}
GITHUB_PAGES_HOSTS = ("github.io",)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1

    base = sys.argv[1].rstrip("/")
    if not base.startswith("http"):
        print("Give a full URL, e.g. https://gcwang.dev")
        return 1

    host = base.split("//", 1)[1].split("/", 1)[0]

    for filename, suffix in PAGES.items():
        path = ROOT / filename
        if not path.exists():
            continue
        page = path.read_text()
        target = f"{base}/{suffix}"

        page = re.sub(r'(<link rel="canonical" href=")[^"]*(")',
                      lambda m: m.group(1) + target + m.group(2), page)
        page = re.sub(r'(<meta property="og:url" content=")[^"]*(")',
                      lambda m: m.group(1) + target + m.group(2), page)
        page = re.sub(r'("url":\s*")https?://[^"]*(")',
                      lambda m: m.group(1) + base + "/" + m.group(2), page)
        path.write_text(page)
        print(f"  {filename} -> {target}")

    cname = ROOT / "CNAME"
    if host.endswith(GITHUB_PAGES_HOSTS):
        if cname.exists():
            cname.unlink()
            print("  removed CNAME (back to a github.io address)")
    else:
        cname.write_text(host + "\n")
        print(f"  wrote CNAME -> {host}")
        print("\n  Remember the DNS records — see 'Using a custom domain' in the README.")

    print("\nDone. Rebuild and push:  make && git commit -am 'set site url' && git push\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
