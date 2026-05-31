# Academic Career Risk Audit, 2026-05-31

This is an adversarial audit of the repository as if the reader wanted the
project, article, dataset, and public site to fail under hostile review. It is
not a judgement of the author. It is a list of the easiest objections a
reviewer, editor, data re-user, or technical maintainer could make.

## Executive Verdict

Do not submit the PPV article, advertise the dataset as stable, or invite
external reuse until the critical blockers below are fixed. The public site
build currently passes `python validate_publication.py`, and the scoped test
suite under `tests/` passes, but the article number gate fails and the default
`pytest` command fails by collecting stale scratch tests. That combination
would let a hostile reviewer say: "the repository looks automated, but the
actual guarantees are selective."

The most damaging issue is not one bug. It is the mismatch between scholarly
claims, generated data, and repository process. Current data says 1352
presentations and 1379 author participations; several public docs and the PPV
draft still say 1351 and 1378. `article/check_ppv_numbers.py` now reports 21
article drifts. That must be treated as a submission blocker.

## Current Evidence

- Repository: `C:\Users\user\Documents\GitHub\IndologyScholars`
- Branch: `main`, tracking `origin/main`
- Pre-existing local change not touched for this audit: untracked
  `scratch/generate_sociology_plots.py`
- `python validate_publication.py`: passed
- `python -m pytest tests`: 40 passed
- `python -m pytest`: failed during collection of `scratch/test_phase2.py`
  with `sqlite3.OperationalError: no such column: o.city_ru`
- `python article/check_ppv_numbers.py`: failed with 21 article drifts
- Tracked files: 4333
- Tracked generated-heavy areas: 1364 `p/` pages, 620 `s/` pages, 1622
  `assets/og/` images, 73 `analytics_output/` files, 134 `scratch/` files
- Tracked local/debug artifacts include `metadata.db`, `profile_output.txt`,
  `profile_utf8.txt`, `profile_utf8_fast.txt`, and `temp.js`
- Current database counts: 270 persons, 1352 presentations, 1379
  presentation-person rows, 40 events, 243 sessions, 95 media rows
- Current missing birth years: 41 of 270 people
- Current `presentation_person.organization_id` coverage: 0 of 1379 rows
  populated
- Literal backslash-n sequences appear in generated root HTML pages such as
  `known-limitations.html`, `download-data.html`, `classification-criteria.html`,
  `hypotheses.html`, and `networks.html`

## Critical Blockers

1. The article is numerically stale.

`article/check_ppv_numbers.py` now expects 1352 presentations, 1379 author
participations, Zograf 880 presentations, Zograf 902 author participations,
G1 = 1161, G2 = 182, and G3 = 9. The draft still reports older values in the
abstract, methods, table, and argument-scale section. This is the cleanest
attack path for a reviewer: the article's headline claims do not match the
repository's own validation script.

Fix: update `article/ppv_submission_article.md`,
`article/ppv_submission_article_anonymous.md`, `article/ppv_cover_letter.md`,
README files, and development docs from the refreshed
`article/hypothesis_output/ppv_numbers_snapshot.*`; then rerun
`python article/check_ppv_numbers.py` until it exits zero.

2. The submission draft starts with working notes before the article.

`article/ppv_submission_article.md` begins with an editorial note and a
standalone essay-like block before the UDC/title. This is fatal in a journal
submission package: it looks unfinished, unfiltered, and careless. It also
makes automated character counts and anonymity checks untrustworthy.

Fix: move that preface to a private working note or a named appendix draft,
and make the submission file start at the actual article metadata.

3. The blind-review package is not protected by a hard gate.

There is an anonymous article file, but the non-anonymous submission file
contains author identity, email, ORCID, and postal address. The repo has no
single command that asserts "this is the anonymous review artifact and it has
no self-identifying metadata." A reviewer can reject on process before reading
the argument.

Fix: add an `article/check_anonymity.py` gate for the review artifact, run it
in CI, and keep the personal metadata only in the final non-anonymous package.

4. The public documentation disagrees with the data.

`README.md`, `README_EN.md`, `docs/development.md`,
`docs/development-en.md`, and `article/ppv_cover_letter.md` still contain
1351/1378-era counts while the current database and site summary are at
1352/1379. The project asks readers to trust generated data while leaving
visible stale prose.

Fix: add a single generated count include or a docs count checker so summary
numbers cannot drift independently across prose files.

5. Institutional claims outrun institutional data.

Every row in `presentation_person.organization_id` is currently empty, while
the organization table has only 8 rows. The project has raw affiliation text
and some normalized display logic, but the relational institutional layer is
not actually populated. Any strong claim about institution-level structure,
bridges, or institutional gravity is therefore exposed.

Fix: either populate `presentation_person.organization_id` with provenance and
confidence, or explicitly downgrade organization-level outputs to raw-text
exploration until that normalization exists.

6. The affiliation argument is methodologically fragile.

The article correctly warns that city-only Zograf rows are a source-format
problem, but the database still lacks enough external biographical
verification to separate source visibility from employment reality. A hostile
reader can say the project measures programme editorial style, not academic
precarity or institutional belonging.

Fix: keep the city-only finding as a source-critical observation; do not let it
become a sociological claim until a verified biography/affiliation trajectory
layer covers the target population.

7. The theme and G-scale classifications need a stronger audit trail.

Files named around DeepSeek and LLM classification are in public analytics
outputs. Even if the classifications are useful, the current evidentiary story
is too easy to dismiss as "machine labels on Russian titles." The repository
needs a reviewer-facing reliability dossier: codebook, sampling frame,
manual adjudication, disagreements, confusion patterns, and frozen version.

Fix: create a classification reliability appendix with a stratified manual
sample, adjudication notes, and a table of known ambiguous cases. Rename or
wrap LLM-named outputs in reviewed public artifacts.

8. The null model and statistical claims need a reproducibility envelope.

The article's overlap result is central. It needs an obvious route from raw
data to statistic: seed, assumptions, number of permutations, exact definition
of activity preservation, confidence/interval conventions, and which tests are
confirmatory versus exploratory.

Fix: make the null-model script, parameters, and output table first-class
publication artifacts; then cite them in the article and data dictionary.

9. Default test execution is broken.

`python -m pytest tests` passes, but `python -m pytest` fails by collecting
`scratch/test_phase2.py`. This is a reputational smell: the clean command a
new contributor will run says the project is broken.

Fix: add `pytest.ini` with `testpaths = tests`, rename scratch test scripts, or
move scratch experiments outside importable test discovery. CI should run the
same command documented for humans.

10. CI hides the article blocker.

The CI validation workflow runs database/site validation but does not run
`article/check_ppv_numbers.py`. The article can drift while CI remains green.

Fix: add the article number gate to CI, at least when article files,
classification outputs, `conferences.db`, or analytics files change.

11. The deploy workflow mutates `main`.

The scheduled rebuild workflow fetches programs, regenerates artifacts, commits
them, pushes to `main`, then deploys. That is convenient, but it mixes source
changes, generated data, and publication state. It can also update article-
relevant counts without forcing article prose to update.

Fix: separate source branch, generated artifact branch, and release tags. If
main must receive generated artifacts, require all article/data gates before
auto-commit.

12. Generated artifacts dominate the repository.

The repo tracks thousands of generated HTML/PNG/data files alongside source
scripts, scratch experiments, databases, and publication drafts. A reviewer
trying to inspect the method must fight the repository shape before reaching
the method.

Fix: define a source-of-truth layout. Move generated public site artifacts to
GitHub Pages artifacts/releases or clearly generated directories; keep source,
curation, and reproducibility scripts in a compact top-level structure.

13. Scratch files are not quarantined.

There are 134 tracked files under `scratch/`, including `test_*.py` scripts,
manifest CSVs, old CI manifests, backups, and exploratory injection scripts.
Some are useful history; some are active hazards.

Fix: split `scratch/` into `archive/scratch-history/` for preserved material
and ignored local scratch for experiments. Anything still used by CI should be
promoted into `tools/` or `pipeline/`.

14. Local/debug artifacts are committed.

`profile_output.txt`, `profile_utf8.txt`, `profile_utf8_fast.txt`, `temp.js`,
and a zero-byte `metadata.db` are tracked. They make the repository look
improvised and make it harder to review meaningful changes.

Fix: remove or archive them deliberately, add ignore rules for future profiling
output, and document where reproducible profiling should live.

15. Dependencies are not locked.

`requirements.txt` is unpinned except for Pillow minimum version, CI uses
Python 3.11, and local tests here ran on Python 3.14. That is not a stable
reproducibility story.

Fix: pin a tested dependency set, add a lock or constraints file, and define
the official Python runtime. Keep compatibility testing optional and explicit.

16. Rights and licensing need separation.

The repo is Apache-2.0, but it includes cached conference material, a PDF, full
generated pages, derived images, and dataset exports. Code, curated facts,
conference program text, and third-party source caches may not all share the
same reuse rights.

Fix: add a rights statement that separates code license, dataset license,
cached source material, and generated site assets. Make clear what users may
reuse and what remains source quotation or archival cache.

17. Citation metadata is not polished enough.

`CITATION.cff` is useful, but the author name structure appears odd
(`name-particle: "Dr."`). Citation metadata is a front door for reuse; wrong
metadata broadcasts inattention.

Fix: validate CFF with a CFF validator, remove title-like particles from name
fields, and align version/date with an actual release tag or DOI.

18. The public HTML has small but visible generator defects.

Literal `\n` sequences in root HTML pages are not a scholarly data error, but
they are visible evidence that generated output has not been inspected at the
HTML level. A hostile technical reader can use this to cast doubt on deeper
pipeline quality.

Fix: fix the generator that emits the manifest/RSS/PWA head block, add a
validation check for literal backslash-n in generated HTML head sections, and
regenerate.

19. Validation coverage is too narrow for the claims.

`validate_publication.py` checks many publication artifacts, but it does not
catch stale prose counts, article anonymity, default pytest failure, literal
HTML escape artifacts, rights metadata, or institutional normalization
coverage. Passing validation is therefore not the same as "ready for scholarly
release."

Fix: split validation into `site`, `data`, `article`, `repo-hygiene`, and
`release` gates, then publish a pre-release checklist that runs all of them.

20. The article's scope still invites overclaiming.

The current article has improved caveats, but the title and abstract still
allow readers to hear "Russian Indology" where the corpus only observes two
conference series. This is not cosmetic; it is the conceptual line between a
defensible prosopography of public programmes and a sociology of a discipline.

Fix: frame all claims as "publicly observable conference life in two long-
running venues" unless an external corpus supports broader field claims.

## Fix List By Priority

P0, before any article submission:

- Sync article numbers and rerun `article/check_ppv_numbers.py` to zero drift.
- Remove pre-article working notes from `ppv_submission_article.md`.
- Produce and gate the anonymous review artifact.
- Update public prose counts in README, development docs, and cover letter.
- Add the PPV number gate to CI.

P1, before public data/reuse push:

- Fix default `pytest` collection.
- Add count-drift checks for public documentation.
- Clarify institutional normalization coverage and downgrade claims that lack
  populated `organization_id`.
- Add classification reliability documentation.
- Add rights/licensing separation.

P2, before larger promotion:

- Split source and generated artifacts.
- Quarantine scratch work.
- Remove committed debug/profile/temp files.
- Pin dependencies and define the runtime.
- Fix generated HTML literal escape defects.
- Correct and validate `CITATION.cff`.

P3, scholarly strengthening:

- Build verified affiliation trajectories at higher coverage.
- Add publication-conversion tracking.
- Document null-model assumptions and release exact reproducibility scripts.
- Add external comparison corpora before making field-wide claims.
