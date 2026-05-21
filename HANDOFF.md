# HANDOFF: IndologyScholars Article (v0.3)

**Last Updated:** 2026-05-21 (evening session)  
**Session:** Continuation of comprehensive retrospective on Russian Indology (Zograf & Roerich Readings)  
**Status:** Article draft ready for journal submission; auxiliary analytics complete; CI/deploy pipeline restored; live site current

---

## 📋 Current Article Status

**File:** `article/ppv_draft.md`  
**Version:** v0.3 (post-publication refinements + appendices B & C filled)  
**Size:** ~60k characters (~20 pages with appendices)  
**Target Journal:** ППВ (Письменные памятники Востока); fallback: Восток (Oriens)  
**Submission Format:** 22–26 pages, 10 sections + 3 appendices

### Recent Corrections (Session 2026-05-21, morning)

1. **Biographical Data Fixed:**
   - Tsvetkova: Database corrected (Софья → Светлана)
   - Vertogradova: Removed incorrect death year (was 2022, still alive)
   - Vecherina: Added dates (1960–2023)

2. **Article Refinements:**
   - §8.1: Added explicit methodology on theme-scholar correlation (collective orientation ≠ individual preferences)
   - §8.2: Added footnote clarifying post-war indology examples from XLVII Zograf 2026 program
   - Appendix A: Updated 39-scholar table with corrected biographical data

3. **New Analytics Generated:**
   - `analytics_output/debut_timing.csv` — 66 scholars with age-at-debut analysis
   - `analytics_output/debut_timing.svg` — Scatter plot visualization (debut year vs age)
   - `analytics_output/youtube_playlist_summary.csv` — Zograf YouTube recording counts

### Session 2026-05-21 (evening) — Appendices, OpenAlex experiment, CI restoration

4. **Appendix B filled** (`article/ppv_draft_appendix_b.md` + spliced into main draft):
   - 20-year yearly table (2004–2026) showing % newcomers and median age per series.
   - Key finding: newcomer rate collapse 100% → 10–11% by 2021–2022, median age rise to 57–59 by 2025–2026. Apparent rebounds in 2025 (Rerikh 38.9%) and 2026 (Zograf 31.7%) — likely reflect organizational changes (worth flagging in commentary).

5. **Appendix C filled** (`article/ppv_draft_appendix_c.md` + spliced into main draft):
   - 3 summary tables (L1 discipline, L2 period, L4 character) + 30-row representative sample (confidence ≥ 0.8).
   - Full 895-row CSV at `article/supplementary_theme_codes.csv` for journal submission.
   - Numbers confirmed: Zograf = literature 22% + philosophy 21.7%; Rerikh = religion 25.4% + history 15.8% + art 9.6%. L4 fundamental ~93% on both sides → H4 (applied-topic filter) not supported.

6. **OpenAlex birth-year proxy — REJECTED.** Tested as Task #9 alternative method. Tried twice (60 top scholars, then stricter filter). Both runs systematically under-estimated by 30–50 years for senior scholars (Альбедиль "1990" but actually ~1946; Краснодембская "1994" but 1937). Root cause: OpenAlex doesn't index Russian humanities pre-~2010. Documented as §7 footnote ^2^. Audit scripts kept in `scratch/fetch_openalex_birthyears*.py`. **Do not retry this method.**

7. **CI / deploy pipeline restored** (4 fixes):
   - `requirements.txt` added (was missing → pip cache failed before any Python ran for 15+ pushes).
   - `validate_publication.py` made slug-rename-aware: follows `<link rel="canonical">` on redirect pages to verify the slug target exists.
   - `environment: github-pages` declared on the deploy job (required by `actions/deploy-pages@v4`).
   - `pypdf` added to requirements so CI can read `html_cache/zograf_2026.pdf` (the script does conditional import + warning fallback otherwise).
   - **Live site now reflects 226 scholars / 899 presentations / 2026** (was frozen at 188 / 707 / 2025 since ~2026-05-19).

8. **Legacy-redirect cleanup**: emptied `legacy_redirects.json` (was holding 7 orphan PERS_<hash> → current-scholar redirects from past dedup merges). Validator no longer defends against orphan canonicals — any future orphan will fail validation, forcing cleanup at the source.

9. **`index.html` stats auto-patched on every CI run.** `generate_publication_pages.py` now ends with `patch_index_stats(data)`, which regex-replaces the four `#stat-*-count` divs (scholars, talks, years, overlap), the `stat-years-desc` range, and the per-series year strings (RU + EN) in the meta description, sub-heading, and chart titles from the current `site_data.json` summary. `index.html` added to the workflow's `git add` list so the bot commits the patched version. **Crawlers, social-card scrapers, and tools that don't execute JS now see live numbers (226/899/23/39/2026) instead of the previous hardcoded fallbacks (188/707/22/30/2025).**

10. **README.md and README_RU.md updated**: all scholar/talk/cohort numbers refreshed to current state (226 / 899 / 39 overlap / 132 Zograf-only / 55 Roerich-only). Timeline note added in RU readme that Zograf extends to 2026 while Roerich stays at 2025. README files remain in workflow's `paths-ignore` so they don't re-trigger CI.

11. **YouTube data integrated** (172 video archive):
    - Added 5th stat-card to `index.html` (#card-youtube, "172 Видеозаписи / Зографские чтения 2023–2025 на YouTube").
    - `patch_index_stats()` extended to read `analytics_output/youtube_playlist_summary.csv` (2023: 68, 2024: 56, 2025: 36, secondary: 12) and inline the total on each CI rebuild.
    - Article §4.4 updated: replaced vague "более ста единиц" with exact figures and explicit 68→56→36 decline observation.
    - Deleted broken `analytics_output/youtube_stats.csv` (was error-stubs from a failed scrape attempt; real data is in playlist_summary).
    - Added `article/ppv_corr.md` (author's revision-notes WIP) to `.gitignore`.

### Key Findings (Ready for Discussion)

**Debut-Timing Profile:**
- Median age at first talk: **41 years**
- Range: 18–78 years
- Early debutants (pre-2010): avg 45.9 years
- Recent debutants (2015+): avg 40.6 years
- ➜ Suggests constant cohort replacement, not systematic aging-out until post-2010

**YouTube Recordings:**
- 2023: 68 videos
- 2024: 56 videos  
- 2025: 36 videos
- Secondary playlist: 12 videos
- ➜ Decline in 2025 (possibly organizational; not thematic)

---

## 📁 File Structure & Key Artifacts

| Path | Purpose | Status |
|------|---------|--------|
| `article/ppv_draft.md` | Main manuscript (10 sections + 3 appendices) | ✅ v0.3 ready |
| `conferences.db` | SQLite database (12 normalized tables, 226 scholars, 899 presentations) | ✅ Current |
| `analytics_output/debut_timing.csv` | Age-at-debut analysis (66 scholars) | ✅ NEW |
| `analytics_output/debut_timing.svg` | Visualization: debut year vs age | ✅ NEW |
| `analytics_output/youtube_playlist_summary.csv` | Zograf video counts 2023–2025 | ✅ NEW |
| `analytics_output/theme_codes_final.csv` | LLM-coded 895 presentations (L1/L2/L3/L4) | ✅ Complete |
| `analytics_output/zograf_2026_no_affiliation.md` | Affiliation verification for Zograf 2026 (41/60 undocumented) | ✅ Reference |
| `zograf-roerich-db.md` | Seed metadata (venues, dates, coordinates) | ✅ Complete |

---

## 🔍 Article Structure (v0.3)

### Main Body (10 Sections)
1. **Введение** — Two institutional models; calendar timing; visitor access barriers
2. **Методология** — Data sources; deduplication; theme taxonomy (L1–L4); no technical implementation details
3. **Объём и границы** — 226 scholars, 899 presentations, 2004–2026; note 2024 data pending
4. **Метрики закрытости** — Gini coefficient, core retention, newcomer rate; includes subsection 4.4 on participation barriers (online collapse 100% → 1.7%)
5. **Критерии членства** — Documentary evidence for Zograf 2026 (19 A / 41 B / 1 C classification); 68.3% without institutional documentation
6. **Миграции и сети** — Individual institution trajectories; teacher-student examples (Lysenko, Kuzina); RGGU→HSE migration
7. **Демография** — Aging cohorts; death year corrections (Vertogradova, Kullanda, Dubianski); birth year availability (99/226)
8. **Тематические профили** — L1 (discipline), L2 (period), L3 (material), L4 (character); theme-scholar methodology; post-war indology via 2026 program
9. **Hypothesis Summary** — H1–H7 with empirical support; note: H4 (applied topics filter) NOT confirmed by aggregate data
10. **Заключение** — Two models confirmed; demographic aging; future recruitment challenge

### Appendices
- **A.** 39-scholar overlap cohort (full table: birth year, death year, affiliation, talk counts)
- **B.** Yearly statistics [placeholder: to fill with `age_cohort_trend.csv`, `newcomer_rate_by_year.csv`]
- **C.** Theme codes [placeholder: full list from `theme_codes_final.csv`]

---

## 🧬 Database Schema (Quick Reference)

12 tables with full referential integrity:
```
event_series → event → event_day → event_day_venue → session → presentation → presentation_person ↔ person
                                                                                              ↑
                                                                                       organization
                                                                                              ↑
                                                                                            place
```

**Critical columns:**
- `person.display_name` — Canonical rendering (e.g., "Цветкова Светлана Олеговна")
- `person.full_name_ru` — Full name in Russian (recently corrected)
- `presentation.title` — Presentation title
- `event.year` — Year (2004–2026)
- `theme_codes_final.csv` — L1, L2, L3, L4 codes with LLM confidence

---

## 📋 Pending Tasks (Priority Order)

### High Priority
1. **Degrees & Alma Mater Extraction** (Task #6)
   - Extract канд./докт. наук for core ≥3-talk scholars
   - Alma mater focus: Rostfak SPbGU vs ISAA MGU distinction
   - Method: RINC, dissertation abstracts, manual verification
   - Goal: Visualize "Leningrad school" vs "Moscow school"

2. **Teacher-Student Graphs** (Task #8)
   - Paribok → Desnitskaya, Kuzina, et al.
   - Method: Dissertation advisors + user knowledge
   - Goal: Show institutional lineages within core 37

3. ~~**Birth Year Proxies**~~ — **REJECTED 2026-05-21**. OpenAlex coverage gap makes the first-publication-year proxy unusable for Soviet-era scholars (under-estimates by 30–50 years). See §7 ^2^. For the 110 missing scholars, only manual research or RSL/RINC will work.

### Medium Priority
4. **Collections/Sborniki Analysis**
   - Identify publications in indology-focused sborniki
   - Check prefaces for theme statements
   - Mark up which core scholars appear

5. **Print Layout & Final Formatting**
   - Convert v0.3 to PDF for journal submission
   - Verify footnotes, bibliography, table formatting
   - Get author's sign-off on final version

### Low Priority (Optional Enhancements)
- Expand Appendix B with trend tables
- Full theme codes in Appendix C (may exceed journal page limits)
- Interactive web dashboard for peer review

---

## 🔐 Data Quality Checklist

- [x] Biographical data verified (Tsvetkova, Vertogradova, Vecherina)
- [x] 39-scholar overlap cohort: complete birth/death years where known (17/39)
- [x] Theme codes: 895 presentations, 26 flagged as uncertain (confidence < 0.6)
- [x] Affiliation verification: Zograf 2026 (41/60 without documented affiliation)
- [x] Online participation: collapse from 100% (2020) → 1.7% (2026)
- [x] YouTube recordings: 160 main channel + 12 secondary (2023–2025)
- [ ] Degrees: not yet extracted (pending task #6)
- [ ] Alma mater: not yet extracted (pending task #6)
- [ ] Teacher-student links: not yet formalized (pending task #8)

---

## 📚 Key References & Files

**Article Source:**
- Primary: `article/ppv_draft.md` (current working version)
- Backup: Commit `aa15d53` (most recent stable version with corrections)

**Database:**
- SQLite: `conferences.db` (rebuilt from `build_and_populate_db.py`)
- Import source: `zograf-roerich-db.md` (seed metadata)
- HTML cache: `html_cache/` (raw program snapshots)

**Analytics:**
- Theme codes: `analytics_output/theme_codes_final.csv` (895 rows, LLM-coded)
- Closedness metrics: `analytics_output/closedness_*.csv`
- Overlap cohort: `analytics_output/overlap_cohort.csv`
- Debut timing: `analytics_output/debut_timing.csv` + `.svg`
- YouTube: `analytics_output/youtube_playlist_summary.csv`

**Metadata:**
- Current state: `.ai_state.md` (session journal)
- Project guide: `CLAUDE.md` (architecture, phase descriptions)
- Config: `.env` (not committed; contains DEEPSEEK_API_KEY)

---

## 🎯 Author Context

- **Name:** М. Ю. Гасунс (Marcis Gasuns, also Gasyoun)
- **Affiliation:** Independent researcher, Moscow
- **Role:** First author; one of the case studies ("отказ" cases mentioned anon. in §5)
- **Tone:** Open first-person perspective; no direct naming of adversaries (e.g., Zakharyin anonymized); data speaks for itself
- **Expertise:** Russian indology, digital humanities, bibliometrics

**Author's Preferences (from prior sessions):**
- Remove technical implementation details (SQLite, JSON, DeepSeek, confidence thresholds)
- Translate English terms or provide Russian equivalents
- Cite sources for all scholars; link to affiliations where possible
- Document teaching lineages; note conflicts/breaks with caveats
- Avoid personalization of criticism; frame around institutional structures

---

## 🚀 Deployment & Next Session Workflow

### If Continuing Article Work:
1. Read `article/ppv_draft.md` from commit `aa15d53` for context
2. Address pending task #6 (degrees/alma mater) to support institutional school distinction
3. Fill Appendix B & C with prepared CSVs
4. Generate PDF for submission; get author review

### If Launching New Analysis:
1. Ensure `conferences.db` is current (last: 2026-05-21)
2. Use `analytics_output/theme_codes_final.csv` for all thematic queries
3. Cross-reference with `analytics_output/overlap_cohort.csv` for 39-scholar subset
4. Check `.ai_state.md` for latest blockers

### Before Journal Submission:
- [ ] Verify all 39-scholar names and dates in Appendix A
- [ ] Get author sign-off on final biographical corrections
- [ ] Verify footnotes (currently 1 footnote added; may expand)
- [ ] Check journal formatting (page limits, reference style)
- [ ] Double-check Zograf 2026 quotes and program dates

---

## 💡 Known Limitations & Open Questions

1. **Birth Years:** Only 99/226 (44%) have documented birth years
   - OpenAlex first-publication-year proxy was tested and rejected (see Recent Corrections item 6 and §7 ^2^). Need manual research for the remaining 127.

2. **Degrees:** Not yet extracted (0/226)
   - Critical for distinguishing institutional hierarchies
   - Requires RINC or dissertation abstract lookups

3. **Alma Mater:** Known for ~50% of core scholars
   - Rostfak SPbGU vs ISAA MGU distinction not yet quantified

4. **Theme Confidence:** 26/895 (2.9%) flagged < 0.6 confidence
   - Mostly 2022 truncated titles
   - Manual review recommended before publication

5. **Online Participation:** PDF parsing missed some "(онлайн)" markers
   - Not blocking for current analysis
   - Affiliation verification was primary goal

---

## ✉️ Contact & Authorization

**For Questions About:**
- Article content, hypotheses, interpretations → Contact author (М. Ю. Гасунс)
- Data extraction, schema, analytics → Refer to `CLAUDE.md` and `.ai_state.md`
- Journal submission details (editor contact, format) → Check author's notes

**Credentials:**
- GitHub repo: [IndologyScholars](https://github.com/gasyoun/IndologyScholars)
- Live site: https://gasyoun.github.io/IndologyScholars/
- Author email: gasyoun@gmail.com

---

## 📝 Session Notes

**Session 2026-05-21 (morning):**
- Fixed 3 biographical errors (names, dates)
- Generated debut-timing analysis (66 scholars, median 41 years)
- Clarified theme-scholar methodology in §8
- Added footnote on 2026 program examples
- Extracted YouTube statistics (160+12 recordings)
- Committed changes to main (commit aa15d53)

**Session 2026-05-21 (evening):**
- Filled Appendices B & C via delegated Haiku subagents; spliced into ppv_draft.md
- §7 ^2^ footnote: OpenAlex birth-year proxy tested twice and rejected (audit scripts kept)
- Restored CI deploy pipeline (4 commits: pip cache, validator slug-awareness, pages environment, pypdf)
- Cleaned up 7 orphan PERS_<hash> redirects + tightened validator (no more bookmark-preservation defense)
- Added `patch_index_stats()` to build pipeline so static `index.html` fallbacks stay in sync with `site_data.json` (for crawlers/no-JS readers)
- Updated README.md + README_RU.md with current scholar/talk/cohort numbers
- Verified live site at https://gasyoun.github.io/IndologyScholars/ now serves 226/899/2026 in both JS-rendered AND static HTML views

**For Next Session:**
- Article is ready for PDF conversion → ППВ submission (Task #5 in Pending)
- Address Task #6 (degrees/alma mater) for institutional school distinction
- Author sign-off on final v0.3 text before PDF
- 127 unknown birth years: only addressable by manual RSL/RINC research, NOT OpenAlex

---

**END OF HANDOFF**

*This document captures the state of the IndologyScholars article project as of 2026-05-21 23:00 UTC. For latest updates, check commit history and `.ai_state.md`.*
