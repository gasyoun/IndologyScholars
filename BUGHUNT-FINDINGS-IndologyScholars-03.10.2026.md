_Created: 03-10-2026 · Last updated: 03-10-2026_

# BUGHUNT-FINDINGS — IndologyScholars — 03.10.2026

Nightly one-repo bug hunt (MG ruling 26-09-2026). Scope: repo CODE surface — `pipeline/`, `scripts/`, `tools/`, `tests/`, root-level Python. Skipped: vendored copies, lockfiles, `node_modules`, data payloads, `__pycache__`. Hunt tier: read-only static + live probes; model GLM 5.3 Flash (zai-coding-plan/glm-5.3-flash).

Links below are frozen at the hunt-time commit `140bd57eb7952c46484dcd65754d1919fbead32e` (origin/main tip).

## Elapsed

~32 min wall (hunt + verify + report), 03-10-2026.

## Ranked findings

No HIGH findings. Nothing qualifies for the HIGH bar (money / security / data-loss / crash of the published pipeline) and no committed secrets, `shell=True`, TLS-disables or bare `except:` were found in the code surface. No HIGH credential/infra finding → no GTD row, and per the ruling MEDIUM/LOW are report-only (no code edits this run).

| # | Sev | Finding | Where |
|---|-----|---------|-------|
| M1 | MEDIUM | 5 scholars publish broken mixed-script `full_name_en` (Cyrillic inside "English" field) into the DB + 4 site payloads | [pipeline/biography.py:141](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/pipeline/biography.py#L141) et al. |
| M2 | MEDIUM | `calendar_sync.py` sends all-day events with `end.date == start.date` — violates the exclusive-end contract; every insert fails, and the loop is also non-idempotent (no existing-event check) | [calendar_sync.py:87](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/calendar_sync.py#L87), [#L103](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/calendar_sync.py#L103) |
| M3 | MEDIUM | Age-group analytics hardcode `2026 - birth_year`; silently stale from 2027 | [generate_site_data.py:1108](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/generate_site_data.py#L1108) |
| M4 | MEDIUM | `requirements.txt` cannot install on the repo's own declared Python floor (3.9): `Pillow>=12.3.0` has no 3.9 distribution — documented setup fails at the floor interpreter | [requirements.txt:8](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/requirements.txt#L8) vs [scripts/pyfloor.py:32](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/scripts/pyfloor.py#L32) |
| L1 | LOW | `DEGREE_DATA` dead keys: a degree string used as a person key; `renkovskaya е а` (Latin prefix) never matches the canonical `ренковская е а` — curated degree row never applies | [pipeline/biography.py:388](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/pipeline/biography.py#L388), [#L392](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/pipeline/biography.py#L392) |
| L2 | LOW | `media_id = f"YT_{video_id}"` unvalidated — an empty `video_id` would collapse rows into one `YT_` media row (DELETE+INSERT, last-wins). Latent: live CSV has 0 empty / 0 dup among 89 active | [pipeline/verification.py:149](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/pipeline/verification.py#L149) |
| L3 | LOW | Roerich fetcher caches the news-overview page as `roerich_{year}.html` when no programme card is found; sticky cache then persists a non-programme page for the parser | [fetch_latest_programs.py:97](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/fetch_latest_programs.py#L97) |
| L4 | LOW | Dead doc reference: `docs/DECISION_PYTHON_INTERPRETER_FLOOR_2026.md` cited by pyfloor does not exist | [scripts/pyfloor.py:38](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/scripts/pyfloor.py#L38) |
| L5 | LOW | Legacy scraper truncates names at the first period: `Ivanov, I. V.` → `Ivanov, I` | [scraper.py:71](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/scraper.py#L71) |

## Evidence (live, run this pass)

### M1 — mixed-script EN names are published

- Live dict scan: `python3 -c "from pipeline.biography import BIOGRAPHICAL_DATA; ..."` → exactly 5 rows whose EN field contains Cyrillic:
  - [biography.py:141](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/pipeline/biography.py#L141) `"Soboleva Diana Владимировна"`
  - [biography.py:187](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/pipeline/biography.py#L187) `"Atmanova Yulia Георгиевна"`
  - [biography.py:229](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/pipeline/biography.py#L229) `"Maretina Ksenia Александровна"`
  - [biography.py:231](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/pipeline/biography.py#L231) `"Bychikhina Olga Владимировна"`
  - [biography.py:234](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/pipeline/biography.py#L234) `"Golubev Sergey Владимирович"`
- `grep -l "Soboleva Diana Владимировна|..." *.json *.html conferences.db` → hits in `search-index.json`, `site_data.json`, `site_data_scholars.json`, `site_data_summary.json`, `conferences.db`. The broken value is live in the published site payload, not just source.

### M2 — calendar_sync inserts are contract-invalid and non-idempotent

- Code: `'start': {'date': b_event_date}, 'end': {'date': b_event_date}` ([calendar_sync.py:86-88](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/calendar_sync.py#L86), same for death at [#L102-104](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/calendar_sync.py#L102)); the loop then calls `events().insert(...).execute()` unconditionally with no existing-event check.
- Google Calendar API v3 Event resource: `start` is **inclusive**, `end` is **exclusive** — for `date`-based events the end date must be the day *after* start; equal dates violate the contract (API rejects the insert). Source: Google Workspace Calendar API v3 reference, Event resource (`end` — "The exclusive end time of the event"), checked live via Context7 during the hunt.
- Consequence: on a real calendar the first `insert` raises `HttpError` and the script dies mid-loop; once the end-date is fixed, re-runs duplicate every anniversary (no dedupe).

### M3 — hardcoded year in live analytics

- [generate_site_data.py:1108](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/generate_site_data.py#L1108): `age = 2026 - int(s["birth_year"])` — one-line probe confirms the constant sits inside the age-group census that feeds `site_data.json`. Deterministic today, wrong by +1 each year from 2027 (silent staleness, no assert nearby). Contrast: `generate_publication_pages.py` uses 2004–2026 as a frozen corpus range, which is deliberate; this one is a live "current age" computation.

### M4 — requirements.txt vs declared floor

- `python3 -m pip install -r requirements.txt` on Python 3.9.6 → `ERROR: No matching distribution found for Pillow>=12.3.0` (run live this pass).
- [scripts/pyfloor.py:32](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/scripts/pyfloor.py#L32) declares `FLOOR = (3, 9)` as the machine-readable floor; [docs/development.md](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/docs/development.md) instructs `python -m pip install -r requirements.txt`.
- CI is unaffected (workflows pin 3.11), so the contradiction is local-setup-only — hence MEDIUM, not HIGH.

### L1 — dead DEGREE_DATA keys

- Live probe: `canonical_person_key("Ренковская Евгения Алексеевна")` → `'ренковская е а'`; `in BIOGRAPHICAL_DATA: True`; `in DEGREE_DATA: False`. The degree row exists under the mixed-script key `'renkovskaya е а'` ([biography.py:392](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/pipeline/biography.py#L392)) and can never match. Same class: the key `"доктор исторических наук"` at [biography.py:388](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/pipeline/biography.py#L388) is a degree string, not a person key.

### L2 — YT_ media_id collision guard

- [pipeline/verification.py:149-150](https://github.com/gasyoun/IndologyScholars/blob/140bd57eb7952c46484dcd65754d1919fbead32e/pipeline/verification.py#L149): `video_id` is stripped but never validated before building `media_id`; an empty id yields `"YT_"`, and each such row DELETEs the previous. Live probe of `analytics_output/video_presentation_mapping.csv`: 178 rows, 89 active, **0 empty video_id, 0 duplicates** — latent today, guard still missing.

### L5 — scraper name split

- Live probe: `re.split(r'\.', 'Ivanov, I. V. Some biography text', maxsplit=1)[0]` → `'Ivanov, I'` — the initial loses its dot boundary and the stored `extracted_name` is a truncated token.

## What verified green

- Full test suite on Python 3.13.15 (fresh venv, `requirements.txt` + pytest): **464 passed, 13 skipped, 0 failed** in ~59 s.
- Secret sweep over `scripts/ tools/ pipeline/ tests/` + root `*.py|*.json|*.yml|*.md`: 0 hits (AKIA/ghp/github_pat/sk-/AIza/xox patterns; hardcoded `api_key|password|secret|token = "literal"`).
- 0 `shell=True`, 0 `verify=False`, 0 bare `except:` in the hunted code surface. All `requests` call sites carry timeouts (checked continuation lines).
- `pipeline/historical.py` collision/idempotency guards, `scripts/git_ops.py` env-filtering seam, and `scripts/publish_safety_gate.py` fail-closed gate all read clean.

## Disposition

Per MG ruling 26-09-2026: HIGH code bugs would be auto-fixed in-run — **none found**; HIGH credential/infra findings would get a GTD @DO row — **none found**. M1–M4 / L1–L5 are recorded here for a follow-up fix lane; the highest-value next fixes are M1 (published data quality, mechanical string corrections) and M2 (calendar script rewrite: exclusive end + idempotency).

_Гасунс_
