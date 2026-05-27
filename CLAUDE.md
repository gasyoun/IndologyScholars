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
