# IndologyScholars — Roadmap 2026

**Goal:** a submission-ready PPV data paper ([`article/ppv_draft.md`](../article/ppv_draft.md)) in **2026** (soft deadline), with the corpus's data gaps filled and four new analyses added. Direction set via a roadmap interview on 2026-06-14.

## Guiding decisions

- **Driver:** PPV data-paper submission (paper-first).
- **Data:** fill **both** birth-year and affiliation gaps, **Wikidata-first** — `ru.wikipedia` is RKN-blocked from the CI/automation host, so use [`scratch/enwiki_bridge.py`](../scratch/enwiki_bridge.py) (en.wiki → ru-title → Q-ID).
- **Analyses:** add **all four** — co-authorship networks, topic/theme evolution, geographic mobility, gatekeeping/centrality.
- **Stats:** harden **before** submitting (not deferred to a revision round).
- **Already settled this cycle:** retention metric kept as-is (distinct-years vs presentation-count was ~nil impact — 0/1 scholars reclassified); Kaplan-Meier one-timer censoring **fixed** (median career span 7→15 Zograf, PR #33); **no branch protection** (a required check would block the `[skip ci]` rebuild bot, and `enforce_admins=false` makes a required-PR gate ineffective anyway).

## Critical path

**Co-authorship network → gatekeeping / centrality** is the only hard dependency chain: the network is built from `presentation_person` (already in the DB, no gap) and gatekeeping/centrality derives from it. Topic-evolution and geographic mobility have no blocking dependency and run in parallel from day one — mobility needs only a short foreign-city geocoding tail in [`geography.json`](../assets/data/geography.json). Affiliations are **not** on the critical path: they are already ~91% resolved (see Phase 1). Birth years are a data-*quality* fix for the existing age / cohort / KM analyses, not a gate on the four new ones.

## Phase 1 — Data foundation (Wikidata-first)

De-risks data quality before submission. **None of the four new analyses is hard-blocked here** (see Critical path) — this phase removes the missing-data bias in the existing age / cohort / age-at-debut / KM analyses and closes a small affiliation tail.

- [ ] **Birth years (the real Phase-1 gap)** — **34 of 268** scholars still lack one (234 have it); all 34 are a genuine *source* gap (no seed entry), not a key mismatch. **Source of truth:** birth years are seeded from `BIOGRAPHICAL_DATA` in [`pipeline/biography.py`](../pipeline/biography.py) (keyed by `normalized_key`); the rebuild DROPs and re-seeds the `person` table from it ([`pipeline/schema.py`](../pipeline/schema.py) → [`build_and_populate_db.py`](../build_and_populate_db.py)), so a *durable* fix means **adding entries there** — not editing `conferences.db`. ⚠️ The existing toolchain ([`tools/scrape_birth_years.py`](../tools/scrape_birth_years.py) → `birth_year_findings.csv` → [`tools/apply_birth_years.py`](../tools/apply_birth_years.py)) writes only to `conferences.db`, which is dropped and re-seeded on the next rebuild, so its results **do not persist** — `apply_birth_years.py` must be redirected to emit `BIOGRAPHICAL_DATA` rows. The scraper also queries `ru.wikipedia.org` directly (RKN-blocked from the CI host) — route it through [`scratch/enwiki_bridge.py`](../scratch/enwiki_bridge.py) (en.wiki → ru-title → Q-ID → `P569`) or run from an unblocked host. Most of the 34 are lower-profile researchers sourced from [orientalstudies.ru](https://www.orientalstudies.ru) programmes with no Wikidata item, so expect a hand-curated residual. **Scouted 2026-06-14:** a conservative Wikidata + `ru.wiki` identity pass resolves **0 of 34** — this is the long tail neither source covers (their orientalstudies.ru links are programme pages, not bios). The bias is also small and concentrated: only **5** of the 34 are recurring speakers (Донских 3, + four with 2), while the remaining **29** are one-time presenters. So the realistic task is *targeted manual curation of the ~5 recurring names* (institutional / dissertation sources), with the remainder documented as an acknowledged ~12.7% missing-birth-year limitation. Filling the recurring ones reduces the missing-data bias in the age / generation-cohort / age-at-debut / KM analyses.
- [ ] **Affiliations (mostly resolved — minor org tail only)** — of **1388** affiliation mentions, the **9** authority organisations in [`authority_ids.json`](../authority_ids.json) resolve ~**290**, [`geography.json`](../assets/data/geography.json) resolves ~**620** city mentions, and **345** are an irreducible *«Не указана»* (no affiliation given). The genuine residual is a low-frequency tail of ~**14** institutions / ~**60** mentions (≈4% of all mentions) with no Q-ID — ГИИ, РУДН, МГППУ, ИСАА, ИМЛИ РАН, ИЯ РАН, ИЭА РАН, ГАУГН, МЦР, ИВ НАН Украины, Ulster University, … — plus a handful of foreign cities to add to `geography.json`. Mint the institution Q-IDs (`P108`) opportunistically; despite the earlier draft, this is **not** the binding constraint.
- **Method:** automate everything Wikidata-reachable from the CI host; hand-curate the residual priority names from bios/programmes.

## Phase 2 — New analyses

Infrastructure already exists for all four — this is *develop into the paper*, not build from scratch.

- [ ] **Topic / theme evolution** — *start now, no data dependency.* Theme/meso codes + LDA are already computed (`analytics_output/meso_codes_deepseek.csv`, the NLP pipeline in `generate_publication_pages.py`). Add a time-series of how disciplinary themes shift across editions.
- [ ] **Co-authorship networks** — [`generate_network_json.py`](../generate_network_json.py) / `site_data_network.json` exist; formalise the collaboration graph and the brokers/bridges between Zograf and Roerich.
- [ ] **Geographic mobility** — *needs Phase-1 affiliations.* [`findings/mobility.html`](../findings/mobility.html) + the city data are the starting point.
- [ ] **Gatekeeping / centrality** — *last; needs the co-authorship network.* [`gatekeeping.html`](../gatekeeping.html) exists; add centrality / anchoring measures over the collaboration + participation graph.

## Phase 3 — Pre-submission hardening

- [x] [`article/check_data_paper_numbers.py`](../article/check_data_paper_numbers.py): replace substring-presence checks with **anchored value assertions** (a wrong figure must fail the gate, not pass because the right string appears somewhere). **Done H1467** (PR #132, 2026-07-22/23): phrase-anchored regex + `tests/test_data_paper_number_gate.py`.
- [ ] Per-year gender-share CIs: replace the i.i.d. Wilson interval with a **design-aware / cluster-robust** one (participations cluster by scholar, so the bands are currently too narrow).
- [x] Freeze the DOI snapshot ([`tools/freeze_article_data.py`](../tools/freeze_article_data.py)) — **`article/snapshots/2026-07-17/`** (H1072). Re-run `article/check_anonymity.py` + `article/check_ppv_numbers.py` at deposit time if prose changes.

## Phase 4 — Submission

- [ ] Figures ([`article/make_ppv_figures.py`](../article/make_ppv_figures.py)), prose + the four new-analysis sections, cover letter ([`article/ppv_cover_letter.md`](../article/ppv_cover_letter.md)).
- [ ] Optional: deposit the dataset (`datapackage.json` + a Zenodo DOI) so it is citable alongside the paper.

---
*Drafted with Claude Code, 2026-06-14. Edit freely — this captures the agreed direction, not a contract.*
