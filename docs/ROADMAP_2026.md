# IndologyScholars — Roadmap 2026

**Goal:** a submission-ready PPV data paper ([`article/ppv_draft.md`](../article/ppv_draft.md)) in **2026** (soft deadline), with the corpus's data gaps filled and four new analyses added. Direction set via a roadmap interview on 2026-06-14.

## Guiding decisions

- **Driver:** PPV data-paper submission (paper-first).
- **Data:** fill **both** birth-year and affiliation gaps, **Wikidata-first** — `ru.wikipedia` is RKN-blocked from the CI/automation host, so use [`scratch/enwiki_bridge.py`](../scratch/enwiki_bridge.py) (en.wiki → ru-title → Q-ID).
- **Analyses:** add **all four** — co-authorship networks, topic/theme evolution, geographic mobility, gatekeeping/centrality.
- **Stats:** harden **before** submitting (not deferred to a revision round).
- **Already settled this cycle:** retention metric kept as-is (distinct-years vs presentation-count was ~nil impact — 0/1 scholars reclassified); Kaplan-Meier one-timer censoring **fixed** (median career span 7→15 Zograf, PR #33); **no branch protection** (a required check would block the `[skip ci]` rebuild bot, and `enforce_admins=false` makes a required-PR gate ineffective anyway).

## Critical path

**Affiliations → co-authorship network → gatekeeping / centrality.** Topic-evolution has no data dependency and runs in parallel from day one.

## Phase 1 — Data foundation (Wikidata-first)

Unblocks three of the four analyses.

- [ ] **Birth years** — **39 of 270** scholars still lack one (231 have it). Resolve the `curation/birth_year_missing` priority list via `enwiki_bridge.py` + Wikidata `P569`; mint missing items with [`tools/generate_wikidata_batch.py`](../tools/generate_wikidata_batch.py). Reduces the bias the age / generation-cohort / age-at-debut / KM analyses currently carry from missing data.
- [ ] **Affiliations** — **138 distinct** raw affiliations in `conferences.db`, but only **9 organisations** carry a Q-ID in [`authority_ids.json`](../authority_ids.json). Resolve org Q-IDs (`P108`) for the high-frequency unmatched affiliations — this is the data the network / mobility / gatekeeping analyses run on, so it is the binding constraint.
- **Method:** automate everything Wikidata-reachable from the CI host; hand-curate the residual priority names from bios/programmes.

## Phase 2 — New analyses

Infrastructure already exists for all four — this is *develop into the paper*, not build from scratch.

- [ ] **Topic / theme evolution** — *start now, no data dependency.* Theme/meso codes + LDA are already computed (`analytics_output/meso_codes_deepseek.csv`, the NLP pipeline in `generate_publication_pages.py`). Add a time-series of how disciplinary themes shift across editions.
- [ ] **Co-authorship networks** — [`generate_network_json.py`](../generate_network_json.py) / `site_data_network.json` exist; formalise the collaboration graph and the brokers/bridges between Zograf and Roerich.
- [ ] **Geographic mobility** — *needs Phase-1 affiliations.* [`findings/mobility.html`](../findings/mobility.html) + the city data are the starting point.
- [ ] **Gatekeeping / centrality** — *last; needs the co-authorship network.* [`gatekeeping.html`](../gatekeeping.html) exists; add centrality / anchoring measures over the collaboration + participation graph.

## Phase 3 — Pre-submission hardening

- [ ] [`article/check_data_paper_numbers.py`](../article/check_data_paper_numbers.py): replace substring-presence checks with **anchored value assertions** (a wrong figure must fail the gate, not pass because the right string appears somewhere).
- [ ] Per-year gender-share CIs: replace the i.i.d. Wilson interval with a **design-aware / cluster-robust** one (participations cluster by scholar, so the bands are currently too narrow).
- [ ] Re-run `article/check_anonymity.py` + `article/check_ppv_numbers.py`; freeze the DOI snapshot ([`tools/freeze_article_data.py`](../tools/freeze_article_data.py)).

## Phase 4 — Submission

- [ ] Figures ([`article/make_ppv_figures.py`](../article/make_ppv_figures.py)), prose + the four new-analysis sections, cover letter ([`article/ppv_cover_letter.md`](../article/ppv_cover_letter.md)).
- [ ] Optional: deposit the dataset (`datapackage.json` + a Zenodo DOI) so it is citable alongside the paper.

---
*Drafted with Claude Code, 2026-06-14. Edit freely — this captures the agreed direction, not a contract.*
