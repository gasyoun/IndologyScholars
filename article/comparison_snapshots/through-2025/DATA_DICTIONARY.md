# Data dictionary — comparison snapshot `through-2025`

_Created: 06-08-2026 · Last updated: 06-08-2026_

Frozen by `community_lenses/snapshot.py` (h1899-snapshot-1.0.0). Every file in this directory is listed with its SHA-256 in `manifest.json` / `manifest.txt`.

## Files

| File | Contents |
|---|---|
| `records.csv` | one row per included record: stable ids, type, timestamp, period bin, access class, snapshot id. Bodies are never copied; `public_title` is populated only for `access_class=public` records. |
| `source_manifests.csv` | the pinned source snapshot per lens: coverage dates, status, version, input hash, pipeline commit, schema/codebook versions, rights basis. |
| `tables/*.csv` | the frozen denominator-aware metric tables the figures are drawn from. |
| `figures/*.svg` | the six core figures plus their captions. |
| `reports/*.md` | validity, classification, coverage and identity/quote evidence reports. |
| `claims_ledger.csv` | every proposed article claim with its evidence link and verdict. |
| `codebooks/*.csv` | the versioned codebooks the labels come from. |
| `schema.sql` | the DDL of the common relational schema. |
| `quotes_exportable.csv` | quotes approved for export — EMPTY header-only when no rights approval exists (the normal state of this package). |

## Record accounting

| Quantity | Value |
|---|---:|
| Records included | 27270 |
| Excluded — outside this package's period | 427 |
| Excluded — undated (in neither package) | 2 |
| Exportable quotes | 0 |

Undated records belong to no period and are therefore in **neither** package; they are counted here rather than silently absorbed into one of them.

## Reuse rules

1. A metric is read with its own denominator and unit; native units are never summed.
2. `pilot`/`partial` coverage supports within-lens composition only.
3. An `unavailable` lens is an evidence gap, never a zero.
4. Forum orientation (Russia/West/India) is a corpus-selection premise, not nationality.
5. Non-exportable quotes and closed-group identity links do not leave this package.

_Dr. Mārcis Gasūns_
