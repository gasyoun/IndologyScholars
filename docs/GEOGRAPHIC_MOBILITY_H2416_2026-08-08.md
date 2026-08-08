# Geographic mobility formalisation (H2416)

_Created: 08-08-2026 · Last updated: 08-08-2026_

**Handoff:** [H2416](https://github.com/gasyoun/Uprava/blob/main/handoffs/H2416-Grok_IndologyScholars_geographic-mobility-formalize_08.08.26.md) · **Executor:** Grok 4.5 (`grok-4.5`)  
**Phase-2 residual** after co-authorship (H2367) and gatekeeping/centrality (H2411).

## Goal

Make geographic mobility **recomputable** and surface gravity + retention tables on [`findings/mobility.html`](../findings/mobility.html) — without inventing moves. City labels come only from programme affiliation text.

## Recipe

```text
python tools/compute_geographic_mobility.py
python -c "import generate_publication_pages as g; g.generate_mobility_page()"
```

Optional related audit (city-only → institution matching):

```text
python tools/city_trajectory_audit.py
```

## Outputs

| File | Content |
|---|---|
| `analytics_output/geographic_mobility_movers.csv` | multi-city programme speakers |
| `analytics_output/geographic_mobility_affiliation_changers.csv` | distinct affiliation strings >1 |
| `analytics_output/geographic_mobility_distribution.csv` | SPb/Moscow/Regions × Zograf/Roerich talks |
| `analytics_output/geographic_mobility_retention.csv` | retention by home-city bucket |
| `analytics_output/geographic_mobility_summary.json` | headline counts |
| `article/hypothesis_output/geographic_*.csv` | refreshed in sync when DB present |

Page: [`findings/mobility.html`](../findings/mobility.html).

## Counts (2026-08-08)

| Metric | Value |
|---|---:|
| Scholars | 268 |
| Multi-city movers | **8** (3.0%) |
| Affiliation-string changers | **27** (10.1%) |
| Avg cities among movers | **2.1** |

### Gravity (talks)

| City | Zograf talks (%) | Roerich talks (%) |
|---|---:|---:|
| SPb | 301 (33.0%) | 33 (6.9%) |
| Moscow | 277 (30.4%) | 260 (54.5%) |
| Regions/Foreign | 333 (36.6%) | 184 (38.6%) |

### Retention (≥2 years in bucket)

| City | Returning / total | % |
|---|---:|---:|
| Moscow | 77 / 119 | 64.7 |
| SPb | 54 / 80 | 67.5 |
| Regions/Foreign | 27 / 69 | 39.1 |

## Guardrails

- City ≠ employing institution.
- City-only affiliation is often a **Zograf programme format** artifact (paper H4), not precarization.
- Multi-city list uses `geography.json` aliases on talk geography from `site_data`.
- Gravity/retention buckets reuse the same SPb/Moscow regex family as `article/work_ppv_hypotheses.py` H9.

## Multi-city movers (live)

See `geographic_mobility_movers.csv` — page lists all 8 with profile links.

## Non-goals

- Minting Q-IDs for the ~14 residual institutions (Phase-1 affiliation tail, opportunistic).
- Proving geographic precarization as a career claim.

_Dr. Mārcis Gasūns_
