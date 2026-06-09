# Automated Contributor Context

The maintained engineering instructions for this repository are in
[docs/development-en.md](docs/development-en.md), with a Russian counterpart in
[docs/development.md](docs/development.md). Use [README.md](README.md) only for
the user-facing Russian description of the collection.

Three rules matter before making automated changes:

1. Treat `site_data.json` and generated HTML/CSV/JSON outputs as derived
   artifacts; edit their source or generator and rebuild them.
2. Preserve explicit uncertainty: a continued open affiliation is shown as
   tentative with `(?)`, and an unvalidated classification is not published as
   `L2`.
3. Before publication, run `python validate_publication.py` and
   `python -m pytest`.
4. Editable geographic data (city aliases, coordinates, and Wikidata Q-IDs)
   lives in `assets/data/geography.json`. Shared utility functions like
   `normalize_affiliation` belong in `publication_helpers.py` — do not
   duplicate them across generator scripts.
5. The `scratch/` directory is for experiments and logs. Published pages
   (including `findings/mobility.html`) must be generated from the main
   pipeline in `generate_publication_pages.py`, not from `scratch/`.
6. International data integration: Wikidata Q-IDs for cities and themes
   are in `assets/data/geography.json`; the Wikidata creation guide is
   `docs/wikidata-guide.md`; the English data paper draft is
   `article/data_paper_draft.md`; the example analysis notebook is
   `notebooks/example_analysis.py`.
7. The frozen data snapshot for DOI deposition lives in
   `article/snapshots/` and is created by `tools/freeze_article_data.py`.
   Inter-rater reliability sampling is handled by
   `tools/build_interrater_sample.py` and
   `tools/compute_interrater_agreement.py`.
