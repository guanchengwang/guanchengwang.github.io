# Everything you need day to day.
#
#   make          rebuild the whole site from data/
#   make serve    rebuild, then preview at http://localhost:8000
#   make papers   list every paper with the string to paste into `selected:`
#   make check    verify the build is reproducible and nothing leaked

.PHONY: all pubs map serve papers check install

all: pubs map
	@echo "\nSite rebuilt. Review with 'make serve', then: git add -A && git commit && git push\n"

pubs:
	@python3 scripts/update_publications.py

map:
	@python3 scripts/build_worldmap.py

serve: all
	@echo "Serving on http://localhost:8000 — Ctrl-C to stop"
	@python3 -m http.server 8000

papers:
	@python3 scripts/papers.py

install:
	@pip3 install -r scripts/requirements.txt

# Rebuilding twice must produce identical output, and no contact details or
# tracking may appear in the served HTML.
check: all
	@cp index.html /tmp/_gw_check.html
	@python3 scripts/update_publications.py > /dev/null
	@python3 scripts/build_worldmap.py > /dev/null
	@diff -q /tmp/_gw_check.html index.html \
		&& echo "OK  build is reproducible" \
		|| echo "FAIL build is not stable across runs"
	@! grep -qE 'mailto:|guancheng\.wang@|ul\.ie' index.html publications.html 404.html \
		&& echo "OK  no address in the served HTML" \
		|| echo "FAIL an address leaked into the HTML"
	@! grep -qE 'fonts\.googleapis|fonts\.gstatic|googletagmanager|google-analytics' \
		index.html publications.html 404.html \
		&& echo "OK  no third-party requests" \
		|| echo "FAIL a third-party request crept in"
