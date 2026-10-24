# Network centrality + series bridges for gatekeeping (H2411)

_Created: 07-08-2026 · Last updated: 05-09-2026_

**Handoff:** [H2411](https://github.com/gasyoun/Uprava/blob/main/handoffs/H2411-Grok_IndologyScholars_gatekeeping-centrality-measures_07.08.26.md) · **Executor:** Grok 4.5 (`grok-4.5`)  
**Depends on:** co-authorship export truth-pass [H2367](https://github.com/gasyoun/Uprava/blob/main/handoffs/archive/H2367-Grok_IndologyScholars_coauthorship-network-regen_07.08.26.md)

## Goal

Add **recomputable** centrality / anchoring measures over the collaboration + participation graphs, and surface them on the gatekeeping pages — without inventing edges or mixing edge semantics.

## Recipe

```text
python tools/compute_network_centrality.py
# then regenerate pages (subset):
python -c "import generate_publication_pages as g; g.generate_gatekeeping_page()"
```

## Outputs

| File | Content |
|---|---|
| [`analytics_output/network_centrality_collaboration.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/network_centrality_collaboration.csv) | degree + betweenness on **co-presentation** pairs only |
| [`analytics_output/network_centrality_session.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/network_centrality_session.csv) | same-session co-presence graph |
| [`analytics_output/network_centrality_event.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/network_centrality_event.csv) | same-event-year co-attendance projection |
| [`analytics_output/network_series_bridges.csv`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/network_series_bridges.csv) | people with talks in **both** Zograf and Roerich |
| [`analytics_output/network_centrality_summary.json`](https://github.com/gasyoun/IndologyScholars/blob/main/analytics_output/network_centrality_summary.json) | layer counts + top-3 snapshots |

Pages: [`gatekeeping.html`](https://github.com/gasyoun/IndologyScholars/blob/main/gatekeeping.html) / [`gatekeeping-en.html`](https://github.com/gasyoun/IndologyScholars/blob/main/gatekeeping-en.html) — section **Measured centrality and bridges (H2411)** with live tables.

## Counts (2026-08-07, from `conferences.db`)

| Layer | Nodes | Undirected edges | Deg>0 | Max betweenness (top name) |
|---|---:|---:|---:|---|
| collaboration | 294 | **18** | 33 | Краснодембская / Соболева (~4.7e-5) |
| session | 294 | **3091** | 268 | Рыжакова (0.062) |
| event | 294 | **10911** | 268 | Тавастшерна (0.036) |
| series bridges (both) | **41** people | — | — | ranked by event betweenness |

**Interpretation guardrails (also on the page):**

- Betweenness is **structural connectivity**, not scholarly quality.
- Session co-presence ≠ collaboration (see `network_robustness_checks.csv` NET01/NET02).
- Collaboration graph is sparse (programme multi-author lines only) — high event/session bridges often have **collaboration_degree = 0**.
- Do not mix edge types into one undifferentiated network.

## Prior art reused

- Brandes betweenness already in [`article/work_ppv_hypotheses.py`](https://github.com/gasyoun/IndologyScholars/blob/main/article/work_ppv_hypotheses.py) (`network_bridges*.csv` for the paper appendix).
- H2411 adds a **stdlib tool under `tools/`**, typed layer CSVs under `analytics_output/`, and wires tables into the public gatekeeping pages.

## Non-goals

- Geographic mobility formalisation (still open Phase-2 unit).
- Proving the 2026 institutional-filter hypothesis (hypothesis only).
- Hand-editing network edges.

_Dr. Mārcis Gasūns_
