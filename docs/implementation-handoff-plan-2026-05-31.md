# Implementation And Handoff Plan, 2026-05-31

This plan turns `docs/academic-career-risk-audit-2026-05-31.md` into an
implementation sequence. It assumes the immediate objective is a defensible PPV
submission and a repository that can survive a skeptical technical reader.

## Ground Rules

- Freeze the current data state before changing article prose.
- Treat article numbers as generated facts, not hand-maintained prose.
- Keep publication claims narrower than the data.
- Do not make generated site churn part of unrelated commits.
- Promote useful scratch code into named tools; archive or ignore the rest.

## Phase 0: Freeze And Triage

Goal: stop new drift while the article is repaired.

Tasks:

1. Tag or note the current failing state.
2. Run and save the following commands:
   - `python validate_publication.py`
   - `python -m pytest tests`
   - `python article/check_ppv_numbers.py`
3. Mark the PPV article as blocked until the number check exits zero.
4. Decide whether `article/ppv_submission_article.md` or
   `article/ppv_submission_article_anonymous.md` is the canonical review
   artifact.

Exit criteria:

- Everyone knows the article is blocked on 21 current drifts.
- No one submits the current draft by accident.

## Phase 1: Repair The PPV Submission

Goal: make the article package internally consistent and review-safe.

Tasks:

1. Remove the working-note block from the start of
   `article/ppv_submission_article.md`.
2. Update all stale article numbers from
   `article/hypothesis_output/ppv_numbers_snapshot.md`.
3. Update the anonymous article in parallel.
4. Update `article/ppv_cover_letter.md` and any submission checklist that
   still cites old 1351/1378-era counts.
5. Add or update an article number check in CI.
6. Add an anonymity checker for the review artifact.
7. Rerun:
   - `python article/check_ppv_numbers.py`
   - `python validate_publication.py`
   - `python -m pytest tests`

Exit criteria:

- `article/check_ppv_numbers.py` exits zero.
- The anonymous review artifact has no author identity, email, ORCID, postal
  address, or self-reference.
- The article starts at the article metadata, not at working notes.

## Phase 2: Fix Tests And CI

Goal: make local and CI truth match.

Tasks:

1. Add `pytest.ini` with `testpaths = tests`, or rename/move scratch
   `test_*.py` files.
2. Replace CI's narrower `python -m unittest discover -s tests` with the same
   command documented for humans, or document why the project standard is
   unittest-only.
3. Add `python article/check_ppv_numbers.py` to CI for article/data changes.
4. Add a lightweight docs count check for README/development/cover-letter
   numbers.
5. Add a generated HTML check for literal backslash-n in root HTML head blocks.

Exit criteria:

- `python -m pytest` succeeds from the repository root.
- CI fails when article counts drift.
- CI fails when public prose counts drift from `site_data.json` or the PPV
  snapshot.

## Phase 3: Institutional And Classification Evidence

Goal: remove the easiest methodological objections.

Tasks:

1. Decide whether institutional analysis is in scope for the first article.
2. If yes, populate `presentation_person.organization_id` with source,
   confidence, and review status.
3. If no, remove or downgrade institution-level claims and label outputs as raw
   affiliation text exploration.
4. Build a classification reliability packet:
   - codebook
   - stratified sample
   - manual adjudication
   - ambiguous cases
   - frozen version and date
5. Rename public-facing classification outputs so the reviewed artifact is the
   citation target, not a raw LLM vendor file.

Exit criteria:

- Institution-level claims have populated relational evidence or are removed.
- Classification claims have a reviewer-facing audit trail.

## Phase 4: Repository Hygiene

Goal: make the repository look like a publication-grade research project.

Tasks:

1. Move active scripts from `scratch/` into `tools/`, `pipeline/`, or `article/`.
2. Archive historical scratch outputs under `archive/` only when they are worth
   preserving.
3. Remove or intentionally archive:
   - `metadata.db`
   - `profile_output.txt`
   - `profile_utf8.txt`
   - `profile_utf8_fast.txt`
   - `temp.js`
4. Add ignore rules for future profiling output, temp JS, local manifests, and
   local scratch experiments.
5. Decide whether generated HTML/PNG pages remain on `main` or move to Pages
   artifacts/releases.
6. Document the source-of-truth layout in `docs/development-en.md`.

Exit criteria:

- A new reviewer can distinguish source, generated artifacts, scratch history,
  and publication outputs within five minutes.
- Generated output churn is no longer mixed into ordinary source commits.

## Phase 5: Release And Reuse

Goal: make public reuse defensible.

Tasks:

1. Split rights statements for code, dataset exports, cached source material,
   and generated site assets.
2. Validate and correct `CITATION.cff`.
3. Create a tagged release for a stable dataset snapshot.
4. Attach or publish checksums/manifests for release artifacts.
5. Consider DOI deposit only after article/data gates pass.

Exit criteria:

- Citation metadata, release version, and data files describe the same object.
- Re-users know what they can legally reuse.

## Handoff Checklist

Immediate owner handoff:

- Read `docs/academic-career-risk-audit-2026-05-31.md`.
- Start with Phase 1, not repository cleanup.
- Treat `article/hypothesis_output/ppv_numbers_snapshot.md` as the numeric
  source for the next article edit.
- Keep the untracked `scratch/generate_sociology_plots.py` out of unrelated
  commits unless it is intentionally promoted.

Recommended first commit after this audit:

1. Fix article counts and remove the preface notes.
2. Add the article number gate to CI.
3. Add pytest discovery configuration.

Recommended second commit:

1. Update README/development/cover-letter counts.
2. Add docs count validation.
3. Fix literal backslash-n generation in public HTML.

Recommended third commit:

1. Quarantine scratch files.
2. Remove profiling/temp artifacts.
3. Add source/generated layout documentation.

## Commands To Rerun Before Handoff Closure

```powershell
python article\check_ppv_numbers.py
python validate_publication.py
python -m pytest
git status -sb
```

Do not call the PPV package ready until all four commands are clean and the
anonymous artifact has passed an explicit identity check.
