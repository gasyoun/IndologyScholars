# H7242 — Template extraction, slice 1: visualisations-page giant f-string

_Part of the H7242 program (extract inline HTML from `generate_publication_pages.py` into Jinja2 templates). This lands the first slice; the full DoD (file <3k LOC) remains open._

## What moved

| Before | After |
| --- | --- |
| `generate_visualisations_page()` contains a **970-line f-string** (lines 7366–8335, 38 interpolations) holding the page body skeleton (HTML + embedded JS for the interactive atlas) | `templates/visualisations_body.html` — the same skeleton as a Jinja2 template, verbatim |

`generate_publication_pages.py`: **16,553 → 15,625 LOC** (`generate_visualisations_page()` 5,102 → ~4,130 lines).
`generate_publication_docs`, `generate_findings_page`, `generate_nlp_page` and the remaining inline HTML are still open for later slices.

## Mechanism (byte-identical by construction)

- Each `{expr}` interpolation is precomputed in place into a `ctx` dict (`"v000": (expr), …`, same evaluation order as the f-string) and rendered as `{{ vNNN|safe }}` — f-strings insert raw, so no additional escaping is introduced.
- Literal `{{`, `{%`, `{#` sequences inside template text are wrapped in `{% raw %}` blocks.
- Rendered through the existing `_JINJA_ENV` (no trimming flags set, so text passes through byte-exact).
- Data assembly (CSV/sqlite/analytics → `vis*` locals) is untouched and stays Python.

## Proof

Same input, same data, before (origin/main generator) vs after (this tree):

```
PYTHONHASHSEED=0 python generate_publication_pages.py     # twice on origin/main: golden hashes equal
PYTHONHASHSEED=0 python generate_publication_pages.py     # on this tree
python compare.py  # sha256 over all 12 files touched by a run
```

Result: **12/12 generated files byte-identical** (incl. `findings/visualisations.html` and both publication-file manifests).

## ⚠ Pre-existing non-determinism (new finding for the full DoD)

`findings/visualisations.html` is NOT reproducible across plain runs of the *unmodified* generator: two runs on origin/main yield different ARC_DATA edge ordering (sha256 `37d3edc4…` vs `32bc5088…`), caused by set/dict iteration under Python hash randomization. The byte-identical contract for future slices must therefore pin `PYTHONHASHSEED=0` (as done here), or the arc-data producer must sort its edges. Recorded so the DoD check doesn't chase phantom diffs.