# Vigasin corpus — raw source materials

_Created: 22-07-2026 · Last updated: 05-09-2026_

Full-text `.mdx` conversions of A.A. Vigasin's *Изучение Индии в России (очерки и материалы)*
(history of Russian Indology) plus two overlapping biographical fragments from his *Работы
разных лет* — landed per H1443
(`Uprava/handoffs/H1443-Sonnet_IndologyScholars_vigasin-corpus-extract-route_22.07.26.md`).
Converted via LibreOffice `.doc`→`.docx` headless + Pandoc `.docx`→`.mdx`; raw sources and
fuller routing notes live in
[`SanskritLexicography/literature/md/Alexey_Vigasin/`](https://github.com/gasyoun/SanskritLexicography/tree/master/literature/md/Alexey_Vigasin).
Published as full text — repo-owner risk accepted 22-07-2026 (no prior rights review existed
for this specific corpus).

## Why "sources/", not the `/s/<slug>` pages

This site's `/s/<slug>` scholar pages are **fully generated static HTML** built by
[`generate_scholars_pages.py`](https://github.com/gasyoun/IndologyScholars/blob/main/generate_scholars_pages.py) from
[`curation/historical_persons.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/curation/historical_persons.csv) — there is no MDX
pipeline anywhere in this repo and no per-scholar content directory to drop a biography or
letter transcript into. `build_memorial_html()` explicitly documents this as **unbuilt**: every
one of the 26 historical figures currently renders a placeholder —
*"Мемориальный очерк ... будет добавлен на этапе 3"* / *"Библиографический спайн наполняется
на этапе 4"* (Phase 3 essay, Phase 4 bibliography — neither exists yet).

So this landing is **raw material for that future work, not a page update**: the converted
`.mdx` files sit here as citable primary/secondary sources, organized by scholar slug where one
already exists in the registry. Wiring them into `build_memorial_html()`'s Phase 3/4 is
out of scope for H1443 — flag as a follow-up handoff.

## Registry coverage — 4 of 8 target scholars don't exist yet

Checked against `curation/historical_persons.csv` (the 26-row H484 registry) and
`authority_ids.json`:

| Scholar | Slug | Registry status |
|---|---|---|
| Минаев Иван Павлович | `minaev-ivan` | ✅ registered (`RIND_1672f0cd`), `s/minaev-ivan.html` |
| Ольденбург Сергей Фёдорович | `oldenburg-sergei` | ✅ registered (`RIND_da3e06ff`) |
| Щербатской Фёдор Ипполитович | `shcherbatskoi-fedor` | ✅ registered (`RIND_1058b44f`) |
| Сталь-фон-Гольштейн А.А. | `stal-fon-golshtein-aleksandr` | ✅ registered (`RIND_5ac74908`) |
| Мерварт Александр Михайлович | `mervart-aleksandr` | ✅ registered (`RIND_1777ba54`) |
| **Мерварт Людмила Александровна** | — | ❌ **not in the registry** — landed under `scholars/_unregistered/mervart-lyudmila/` |
| **Розенберг (Rosenberg)** | — | ❌ **not in the registry** — landed under `scholars/_unregistered/rosenberg/` |
| **Миронов (Mironov)** | — | ❌ **not in the registry** — landed under `scholars/_unregistered/mironov/` |
| **Паллас (Pallas)** | — | ❌ **not in the registry** — landed under `scholars/_unregistered/pallas/` |

Adding these four as new `historical_persons.csv` rows (with Wikidata resolution via
`tools/resolve_historical_wikidata.py`, following the H484 Phase-2 seeder precedent) is a
follow-up, not done in this pass.

## Layout

```
sources/vigasin/
  front-matter/         Введение, Оглавление, Список иллюстраций, Список использованных архивов
  chapters/              I, III, IV, VII — general history-of-Indology chapters
  scholars/<slug>/        one file per registered scholar (V/VI/пр.6 → minaev-ivan; etc.)
  scholars/_unregistered/<name>/   same convention, no registry row yet
  archival/               приложения 2, 3, 4, 5, 9 (archival documents not tied to one scholar)
  work-b/                 Этюды о людях науки, Предисловие к Этюдам (biographical overlap
                           with Vigasin's other collection, "Работы разных лет" — the rest of
                           that collection, все.docx, stays SanskritLexicography-only)
```

`XII. миронов и сталь-гольштейн.mdx` and `XIII Александр и Людмила Мерварт.mdx` each cover two
people in one document and are duplicated into both relevant scholar folders rather than split.

## Chapter IV — the Böhtlingk/Petersburg dictionary affair

Also lives in `chapters/` here; the primary landing + full context is
[`SanskritLexicography/literature/md/Alexey_Vigasin/README.md`](https://github.com/gasyoun/SanskritLexicography/blob/master/literature/md/Alexey_Vigasin/README.md#chapter-iv--the-böhtlingkpetersburg-dictionary-affair).

---

_Dr. Mārcis Gasūns_
