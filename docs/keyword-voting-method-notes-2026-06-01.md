# Keyword and Talk-Marking Notes

Updated: 2026-06-01

This note records the editorial and implementation decisions for the keyword
cleanup, compact scholar profile facts, local talk marking, and the
programme-versus-event caveat.

## Keyword Policy

Public keyword chips are intended to help readers navigate subject matter, not
to reproduce every token extracted from titles.

The shared filter is implemented in `keyword_filtering.py`.

Public pages use:

- `analytics_output/keyword_stats.csv` for visible subject keywords;
- `keywords/index.html` for the public keyword page;
- `keywords/review.html` for editor-facing review of public and hidden terms;
- `analytics_output/keyword_filter_audit.csv` for the full decision log.

Terms are hidden when they are function words, overly broad discipline labels,
generic methodological words, generic chronological adjectives, or geographic
markers already represented by other facets. For example, `есть`, `ключевой`,
`контекст`, `толкование`, `традиция`, `философия`, and `фраза` are hidden, while
`упанишад` remains public.

To revise the policy, edit `KEYWORD_STOPLIST` in `keyword_filtering.py` and
rebuild:

```bash
python generate_scholars_pages.py
python generate_publication_pages.py
```

## Scholar Profile Facts

Affiliations, geographic centers, and status notes are now shown in one compact
horizontal grid on scholar profile pages. This reduces vertical scrolling for
profiles where these fields contain short values or explicit "no data" markers.

For a scholar with exactly one archived presentation, the profile label changes
from "основной профиль" to "засвидетельствованный профиль". The old wording is
kept only for profiles where multiple talks make a dominant profile defensible.

## Talk-Marking Page

`voting.html` is a static GitHub Pages-compatible page. It does not transmit
data to a server.

It records two local browser flags per talk:

- `heard`: what the listener actually attended;
- `liked`: what the listener found especially successful.

The page stores marks in `localStorage` under
`indology-talk-votes-v1` and provides CSV/JSON export for sending the results to
the editor, organizer, or researcher. The default year is the newest programme
year available in the generated corpus.

## Programme vs. Performed Event

The archive treats published programmes as evidence of public programme
visibility, not as automatic proof that a talk was delivered in exactly the
published format and order.

A separate caveat now appears in:

- `known-limitations.html`;
- `article/ppv_draft.md`.

The accepted formulation is that an offline talk may be delivered online, the
order of talks may change, a speaker may cancel or fail to appear, and the
public programme may remain uncorrected after the event. Claims about actual
attendance, delivery, reception, or no-show status require independent
verification through video recordings, day-of-event schedules, participant
testimony, or minutes.

## Verification Used

The 2026-06-01 implementation was checked with:

- `python generate_site_data.py`;
- `python generate_scholars_pages.py`;
- `python generate_publication_pages.py`;
- `python validate_publication.py`;
- `python -m unittest discover -s tests`;
- `python article/check_ppv_numbers.py`;
- browser checks of `s/pushkareva-yuliya.html`, `keywords/review.html`, and
  `voting.html` on the local generated site.
