# Co-authorship network regen + truth-pass (H2367)

_Created: 07-08-2026 · Last updated: 07-08-2026_

**Handoff:** [H2367](https://github.com/gasyoun/Uprava/blob/main/handoffs/H2367-Grok_IndologyScholars_coauthorship-network-regen_07.08.26.md) · **Executor:** Grok 4.5 (`grok-4.5`)

## Goal

Regenerate the co-authorship / participation network export from the live `conferences.db` (including current affiliation strings on `presentation_person`), package JSON for [`networks.html`](https://github.com/gasyoun/IndologyScholars/blob/main/networks.html), and spot-check co-presentation edges against the DB. No invented scholar links.

## Regen commands

```text
python generate_analytics.py
python generate_network_json.py
```

- `generate_analytics.py` → `analytics_output/network_nodes.csv`, `network_edges.csv` (and sibling analytics CSVs).
- `generate_network_json.py` → `analytics_output/network_data.json` (CSV package + 20 teacher–student genealogy edges from `pipeline/genealogy`).

`site_data_network.json` is a **separate** lighter chunk written by `generate_site_data.py` (not the Vis.js package). It was not re-run here; the co-authorship / participation UI path is `network_data.json`.

## Counts (2026-08-07)

| Artifact | Nodes | Edges | Notes |
|---|---:|---:|---|
| `network_nodes.csv` / `network_edges.csv` | 344 | 8095 | from `generate_network_exports` |
| `network_data.json` | 344 | 8115 | +20 `person_person_genealogy` |
| `site_data_network.json` (unchanged) | 268 | 3080 links | site chunk; different schema |

### Node types (`network_data.json`)

| Type | Count |
|---|---:|
| person | 268 |
| event | 38 |
| organization | 32 |
| theme | 6 |

### Edge types (`network_data.json`)

| Type | Count |
|---|---:|
| person_person_same_session | 4733 |
| person_theme | 1383 |
| person_event | 1375 |
| person_organization | 363 |
| organization_theme | 215 |
| person_person_copresentation | 26 |
| person_person_genealogy | 20 |

**True co-authorship signal** for the paper is `person_person_copresentation` (26 year-series edges; multi-year pairs accumulate weight). Same-session co-presence is much denser and is **not** treated as co-authorship. Affiliation truth-pass surface is `person_organization` (363 edges, 107 people with ≥1 org edge), derived from `affiliation_text_raw` via `normalize_affiliation`.

### Currency check

After regen, newline-normalized content of `network_nodes.csv`, `network_edges.csv`, and `network_data.json` matched `origin/main` HEAD (commit `445fe56f7` auto-rebuild). **No byte change to commit for those three files** — the export was already current; this pass documents the recipe, counts, and edge audit.

## Spot-check (≥5 co-presentation edges vs DB)

Query: joint `presentation` rows where both named people appear on the same `presentation_person` set. All five pairs **CONFIRMED** in `conferences.db`.

| Pair | Network weight (summed years) | DB joint talks | Sample evidence |
|---|---:|---:|---|
| Соболева Е. С. ↔ Краснодембская Н. Г. | 5 | 5 | Zograf 2013–2024 (MAE collections / Assam / jātaka) |
| Ренковская Е. А. ↔ Крылова А. С. | 4 | 4 | Zograf 2019–2022 + Roerich 2021 (Munda / Kullui) |
| Рудой В. И. ↔ Островская Е. П. | 2 | 2 | Zograf 2006, 2008 (Abhidharmakośa) |
| Псху Р. В. ↔ Вечерина О. П. | 1 | 1 | Zograf 2023 (Tamil / Sufi female-mystic) |
| Иванов В. П. ↔ Зорин А. В. | 1 | 1 | Zograf 2021 (Messerschmidt notes) |

Also: `coauthorship_review.csv` still has **26** source-backed multi-person programme lines (`review_status=source_backed_review`) — same count as copresentation edges; residual human confirm action is unchanged and is **not** auto-approved.

## Non-goals (not claimed)

- Geographic mobility viz
- Birth-year residual fill
- Broker / bridge metrics for Zograf↔Roerich (belongs with gatekeeping / centrality)

## Reproduce

```text
cd IndologyScholars   # needs conferences.db
python generate_analytics.py
python generate_network_json.py
# expect: 344 nodes, 8095 CSV edges; network_data.json 344 / 8115
```

_Dr. Mārcis Gasūns_
