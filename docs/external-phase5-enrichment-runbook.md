# External Phase-5 Enrichment Runbook

This runbook is for running the network-dependent Phase-5 roster enrichment on
a computer outside the current blocked automation environment. Use it when
Wikidata REST and ru.wikipedia article HTML are reachable.

The goal is narrow: enrich the Russian indologist roster without changing the
PPV article corpus. The article remains a two-venue Zograf/Roerich study.

## 0. Required Access

The external computer needs:

- Git
- Python 3.10 or newer
- access to GitHub
- access to Wikidata REST:
  `https://www.wikidata.org/wiki/Special:EntityData/Q4103377.json`
- access to ru.wikipedia article HTML:
  `https://ru.wikipedia.org/wiki/Ванина,_Евгения_Юрьевна`

If either Wikidata or ru.wikipedia times out, stop. That host is not useful for
this task.

## 1. Clone The Repository

```bash
git clone https://github.com/gasyoun/IndologyScholars.git
cd IndologyScholars
git checkout main
git pull origin main
```

## 2. Create A Python Environment

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Playwright is not needed for the basic Wikidata and ru.wikipedia pass. Install
it only if the institutional scraper will be run later.

## 3. Check Reachability

Linux/macOS:

```bash
python - <<'PY'
import requests

urls = [
    "https://www.wikidata.org/wiki/Special:EntityData/Q4103377.json",
    "https://ru.wikipedia.org/wiki/%D0%92%D0%B0%D0%BD%D0%B8%D0%BD%D0%B0,_%D0%95%D0%B2%D0%B3%D0%B5%D0%BD%D0%B8%D1%8F_%D0%AE%D1%80%D1%8C%D0%B5%D0%B2%D0%BD%D0%B0",
]
for url in urls:
    r = requests.get(url, timeout=20)
    print(r.status_code, len(r.content), url)
PY
```

Windows PowerShell:

```powershell
@'
import requests

urls = [
    "https://www.wikidata.org/wiki/Special:EntityData/Q4103377.json",
    "https://ru.wikipedia.org/wiki/%D0%92%D0%B0%D0%BD%D0%B8%D0%BD%D0%B0,_%D0%95%D0%B2%D0%B3%D0%B5%D0%BD%D0%B8%D1%8F_%D0%AE%D1%80%D1%8C%D0%B5%D0%B2%D0%BD%D0%B0",
]
for url in urls:
    r = requests.get(url, timeout=20)
    print(r.status_code, len(r.content), url)
'@ | python -
```

Expected result: HTTP `200` and non-zero byte counts for both URLs.

## 4. Run Wikidata Enrichment

```bash
python scratch/wikidata_enrich.py --dry-run
python scratch/wikidata_enrich.py
```

This fills empty birth/death years from Wikidata Q-IDs. Existing curated values
are not overwritten.

Current priority Q-IDs:

- Евгения Юрьевна Ванина — `Q4103377`
- Ирина Петровна Глушкова — `Q253832`
- Александр Николаевич Сенкевич — `Q4416180`

These records already have birth years in the current master roster. If
Wikidata has no death year for a living person, the run may correctly produce no
change.

## 5. Run ru.wikipedia Infobox Enrichment

```bash
python scratch/expand_wikipedia_indologists.py
```

This non-destructively merges ru.wikipedia infobox evidence into:

```text
scratch/wikipedia_indologists_expanded.json
```

It may fill fields such as workplace, alma mater, degree, role, field, and new
reachable names. It must not shrink the existing roster.

## 6. Inspect The Diff

```bash
git status -sb
git diff --stat
git diff -- scratch/wikipedia_indologists_expanded.json
```

If the diff is empty, the external pass produced no new source data. That is an
acceptable result, but do not fabricate promotions.

If the diff shows mass deletion from
`scratch/wikipedia_indologists_expanded.json`, stop and do not commit.

## 7. Rebuild Roster Artifacts

Run this after any roster or authority data changed:

```bash
python scratch/crossref_nonparticipants.py
python tools/build_non_participant_registry.py --dry-run
python tools/build_non_participant_registry.py
python tools/link_roster_participants.py --dry-run
python tools/link_roster_participants.py
python validate_publication.py
python -m pytest -q
```

Do not promote `candidate` registry rows to `verified` unless the row has a
non-empty, source-backed `source_url`.

## 8. Check Registry Health

```bash
python - <<'PY'
import csv

with open("curation/non_participant_indologists.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

verified = [r for r in rows if r["status"] == "verified"]
bad = [r for r in verified if not r["source_url"]]
names = [r["full_name_ru"] for r in rows]

print("total", len(rows))
print("verified", len(verified))
print("verified_without_source_url", len(bad))
print("duplicate_names", len(names) - len(set(names)))
PY
```

Current baseline before external enrichment:

- total registry rows: `94`
- verified rows: `24`
- verified rows without `source_url`: `0`
- duplicate names: `0`

The best outcome is verified coverage above `24`. If coverage does not rise,
record that no supported promotions were found.

## 9. Commit Or Return Files

If the external computer can push to GitHub, stage only source and curation
outputs:

```bash
git status -sb
git add scratch/wikipedia_indologists_expanded.json \
        scratch/non_participants.md \
        curation/non_participant_indologists.csv \
        analytics_output/roster_participant_links.csv \
        authority_ids.json
git commit -m "data: phase-5 external roster enrichment"
git pull --rebase origin main
git push origin main
```

Do not run `git add -A`.

If the external computer cannot push, copy these files back to the main working
machine:

```text
scratch/wikipedia_indologists_expanded.json
scratch/non_participants.md
curation/non_participant_indologists.csv
analytics_output/roster_participant_links.csv
authority_ids.json
```

Then run the rebuild, validation, tests, commit, and push from the main machine.

## 10. Stop Conditions

Stop without committing if:

- `validate_publication.py` fails
- `pytest` fails
- duplicate registry names appear
- a `verified` registry row lacks `source_url`
- the roster JSON loses existing people
- the diff contains unrelated generated HTML or sitemap churn
