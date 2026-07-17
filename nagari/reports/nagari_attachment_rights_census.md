# nagari — rights-triage census of the 2 030 attachments (H1142)

_Created: 17-07-2026 · Last updated: 17-07-2026_

Requested by MG 17-07-2026 («analyse them»). The archive's 2 030 attachments were a black
box — metadata-only ingest, no blob ever extracted, rights unknown. This census looked.
**Nothing here is a publication step**: every verdict is advice to a human, the blobs stay
local (`nagari/data/attachments/`, inside the blanket-ignored `nagari/data/`), and the
publish-surface audit was re-run clean after extraction.

## Method

1. All 2 030 blobs matched from `topics.mbox` by Message-Id + filename, with a size-based
   fallback for RFC2231-mangled names — **1 992/2 030 extracted (98.1%)**; 38 residual
   mismatches counted, not guessed
   ([extract_attachments.py](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/scripts/extract_attachments.py)).
2. Census universe = the **413 book-like** attachments (`pdf 294 · doc 92 · docx 21 ·
   djvu 6`, 246 MB). The often-quoted «367 files / 294 PDF / 216 MB» was a PDF-weighted
   earlier cut; this census states its own definition and sticks to it.
3. Every row was read (filename + poster + thread subject + PDF metadata + first-page
   text) by Fable 5 (`claude-fable-5`) and bucketed with per-item evidence
   ([classify_attachment_rights.py](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/scripts/classify_attachment_rights.py)
   — the override table IS the judgment record);
   homogeneous author-posted series (Карицкий's lessons, Тихвинский's project files,
   Navyan's drafts) carry series-level evidence.
4. PD (B) verdicts state the rule: imprint pre-1930 **and** author dead ≥70 years
   (RU/EU 70 pma); one leg unverified → B-cand, never B.

## Verdicts — 413 book-like attachments

| Bucket | n | MB | Reading |
|---|---:|---:|---|
| **A — MG's own work** | 98 | 24.0 | errata lists, tables, plans, own papers/PhD, own editions' typeset layers, specimens |
| **B — public domain** | 24 | 56.3 | pre-1930 imprints, authors d. ≥70y: Bayer 1735, Brockhaus 1841, Weber 1852, Гумбольдт 1859, Коссович, Кнауэр-материалы, Кудрявский 1917, Bühler (d. 1898), Festgruss-волюмы 1888/1893 |
| **B-cand** | 1 | 0.2 | ЛГУ План НИР 1940 (Soviet corporate-work term to confirm) |
| **C-cand — freely-distributed, licence to confirm** | 14 | 5.1 | Scharf & Hyman LIES 2011 (Sanskrit Library free PDF), dattapeetham bhajan sheets, prayer book, CFPs, WSC circular |
| **D-author — poster's own work, permission one email away** | 169 | 105.3 | Карицкий's complete teaching corpus (121 files), Тихвинский/Густяков translation project, Navyan's drafts, Prasad's own articles |
| **D-third — in copyright, no evident permission** | 62 | 39.2 | **the expected big bucket among true third-party scans**: Зализняк (d. 2017), Елизаренкова 1982, Кочергина 1998, Gonda 1963, Palsule 1955, Belvalkar 1943 (d. 1967), Kale 1961 printing, JSTOR articles, Vogel 1999, Топоров, ИНИОН 2002, Flight of the Garuda (its own front matter marks it restricted) |
| **E — unidentifiable / not individually triaged** | 45 | 16.4 | honest residue: cryptic names with no text layer + the Marcis-posted tail not itemized this pass — re-triage on demand, never guessed into B |

**The servable-in-principle residue is small and specific:** 24 B + up to 15 B-cand/C-cand
pending confirmation — ~57 MB, dominated by the 19th-century scans. Everything else is
either someone's living work (231 files across A/D-author — MG's own plus known posters')
or plainly in copyright (62) or unidentified (45).

## Honesty notes

1. **Deviation from the handoff's bucket A definition** («posted by MG») — verdicts follow
   CONTENT authorship, not poster identity: a third-party scan posted by MG is B/D by its
   imprint, not A. The literal definition would launder scans through the owner.
2. **D-author ≠ servable.** Posting to a members-only list is not permission to republish;
   the bucket exists because permission is *obtainable* from a known person, not implied.
3. **The three A-tagged Zalizniak-konspekt files** are MG's typeset layer over Зализняк's
   in-copyright text — the A verdict covers the layer, not the underlying content; serving
   them inherits the D-third caveat.
4. **E is a real count** (45, 10.9%) — mostly the un-itemized Marcis tail and no-text-layer
   files. The census prefers this number visible over inflating B.

## What a human decides next (advice, not action)

- Vote the **39 B/B-cand/C-cand rows**: `review/indologyscholars-nagari-attachment-rights_17.07.26_review.html`
  (local, gitignored; writes `…_decisions.json` beside itself). The vote confirms LEGAL
  status only; serving anything is a separate decision.
- The two standing `@DECIDE`s in [nagari/.ai_state.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/.ai_state.md)
  (mirror publication; attachments) now have an evidence base.

_Verification: `audit_publish_surface.py` re-run after extraction — `[md]`/`[page]`
redaction holds; `[blob]` now REPORTS the extracted blobs (1 796 on disk, 986 MB —
duplicates across messages included) with its «investigate before publishing» caution:
they live only under the blanket-ignored `nagari/data/`, none is staged or in any
publishable path (`git status` clean of blobs), and this census IS the investigation the
caution asks for. The committed CSV carries poster names only, no addresses._

_Fable 5 (`claude-fable-5`), H1142._

_Dr. Mārcis Gasūns_
