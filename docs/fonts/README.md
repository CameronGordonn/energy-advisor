# Fonts

Self-hosted rather than loaded from a third-party CDN. The site tells visitors their data
never leaves their computer; fetching fonts from someone else's server would report every
visitor's IP address to that company on every page view, which would undercut the claim on
the one page making it. See `../privacy.html`.

All three families are licensed under the **SIL Open Font License, Version 1.1** — full text
in `OFL.txt`, which applies to all of them.

| Family | Used for | Files | Upstream |
|---|---|---|---|
| Newsreader | headings and display prose | `newsreader-*.woff2` (variable, one file per subset) | Copyright 2020 The Newsreader Project Authors, github.com/productiontype/Newsreader |
| Public Sans | body and UI text | `public-sans-*.woff2` (variable, one file per subset) | Copyright the Public Sans Project Authors, github.com/uswds/public-sans |
| IBM Plex Mono | labels, eyebrows, chart axes | `ibm-plex-mono-{400,500,600}-*.woff2` (static instances) | Copyright 2017 IBM Corp., github.com/IBM/plex |

Extracted from the Google Fonts CSS API (`latin` and `latin-ext` subsets only) and served by
`../fonts.css`, which is a stylesheet of `@font-face` rules and nothing else — kept separate
from `site.css` so `methodology.html` can take the fonts without inheriting the shared page
chrome, whose `th{width:44%}` would break that page's tables.

`latin-ext` is declared but, because each `@font-face` carries a `unicode-range`, it is only
downloaded when a visitor actually needs those glyphs. A typical English page view fetches
about 204 KB of fonts; the directory totals 368 KB.

To update: re-request the same families from the Google Fonts CSS API, keep the `latin` and
`latin-ext` faces, and note that Newsreader and Public Sans are variable — the API serves one
identical file for every weight you ask for, so store it once and declare a weight range.
