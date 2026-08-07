#!/usr/bin/env python3
"""Multi-layer network centrality + Zograf↔Roerich series bridges (H2411).

Reads conferences.db (preferred) or falls back to analytics_output/network_*.csv.
Writes stdlib-only CSV/JSON under analytics_output/ for gatekeeping pages and paper.

Layers (edge semantics deliberately NOT mixed):
  collaboration  — person_person_copresentation (true co-talks on one programme line)
  session        — person_person_same_session
  event          — person–person projection of co-attendance at the same event year

Betweenness: Brandes algorithm, undirected, normalized by 1/((n-1)(n-2)).
Degree: unweighted neighbour count in that layer.

Usage:
  python tools/compute_network_centrality.py
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict, deque
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "conferences.db"
OUT = ROOT / "analytics_output"
NET_EDGES = OUT / "network_edges.csv"
NET_NODES = OUT / "network_nodes.csv"


def betweenness_centrality(graph: dict[str, set[str]]) -> dict[str, float]:
    nodes = list(graph)
    centrality = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack: list[str] = []
        predecessors: dict[str, list[str]] = {w: [] for w in nodes}
        sigma = dict.fromkeys(nodes, 0.0)
        sigma[source] = 1.0
        distance = dict.fromkeys(nodes, -1)
        distance[source] = 0
        queue = deque([source])
        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in graph[v]:
                if distance[w] < 0:
                    queue.append(w)
                    distance[w] = distance[v] + 1
                if distance[w] == distance[v] + 1:
                    sigma[w] += sigma[v]
                    predecessors[w].append(v)
        delta = dict.fromkeys(nodes, 0.0)
        while stack:
            w = stack.pop()
            for v in predecessors[w]:
                if sigma[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != source:
                centrality[w] += delta[w]
    n = len(nodes)
    if n > 2:
        scale = 1 / ((n - 1) * (n - 2))
        for node in centrality:
            centrality[node] *= scale
    return centrality


def empty_graph(ids: list[str]) -> dict[str, set[str]]:
    return {i: set() for i in ids}


def add_undirected(graph: dict[str, set[str]], a: str, b: str) -> None:
    if a == b:
        return
    graph.setdefault(a, set()).add(b)
    graph.setdefault(b, set()).add(a)


def load_from_db(con: sqlite3.Connection) -> tuple[dict[str, str], dict[str, dict], dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    names: dict[str, str] = {}
    series_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"zograf": 0, "roerich": 0})
    collab = defaultdict(set)
    session = defaultdict(set)
    event = defaultdict(set)

    for pid, dname, ru in con.execute(
        "SELECT person_id, display_name, full_name_ru FROM person"
    ):
        names[pid] = ru or dname or pid

    # participation counts by series
    for pid, series in con.execute(
        """
        SELECT pp.person_id, es.series_name_en
        FROM presentation_person pp
        JOIN presentation pr USING (presentation_id)
        JOIN session s USING (session_id)
        JOIN event_day_venue edv USING (event_day_venue_id)
        JOIN event_day ed USING (event_day_id)
        JOIN event e USING (event_id)
        JOIN event_series es USING (event_series_id)
        """
    ):
        key = "zograf" if "Zograf" in (series or "") else ("roerich" if "Roerich" in (series or "") else None)
        if key:
            series_counts[pid][key] += 1

    # collaboration: multi-person presentations
    pres_people: dict[str, list[str]] = defaultdict(list)
    for pres_id, pid in con.execute(
        "SELECT presentation_id, person_id FROM presentation_person"
    ):
        pres_people[pres_id].append(pid)
    for people in pres_people.values():
        people = sorted(set(people))
        if len(people) < 2:
            continue
        for i, a in enumerate(people):
            for b in people[i + 1 :]:
                add_undirected(collab, a, b)

    # session co-presence
    sess_people: dict[str, list[str]] = defaultdict(list)
    for pid, sid in con.execute(
        """
        SELECT pp.person_id, s.session_id
        FROM presentation_person pp
        JOIN presentation pr USING (presentation_id)
        JOIN session s USING (session_id)
        """
    ):
        sess_people[sid].append(pid)
    for people in sess_people.values():
        people = sorted(set(people))
        if len(people) < 2:
            continue
        for i, a in enumerate(people):
            for b in people[i + 1 :]:
                add_undirected(session, a, b)

    # event co-attendance projection
    event_people: dict[str, list[str]] = defaultdict(list)
    for pid, eid in con.execute(
        """
        SELECT DISTINCT pp.person_id, e.event_id
        FROM presentation_person pp
        JOIN presentation pr USING (presentation_id)
        JOIN session s USING (session_id)
        JOIN event_day_venue edv USING (event_day_venue_id)
        JOIN event_day ed USING (event_day_id)
        JOIN event e USING (event_id)
        """
    ):
        event_people[eid].append(pid)
    for people in event_people.values():
        people = sorted(set(people))
        if len(people) < 2:
            continue
        for i, a in enumerate(people):
            for b in people[i + 1 :]:
                add_undirected(event, a, b)

    # ensure isolated nodes appear
    for pid in names:
        collab.setdefault(pid, set())
        session.setdefault(pid, set())
        event.setdefault(pid, set())

    return names, series_counts, collab, session, event


def load_from_csv() -> tuple[dict[str, str], dict[str, dict], dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    names: dict[str, str] = {}
    series_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"zograf": 0, "roerich": 0})
    collab: dict[str, set[str]] = defaultdict(set)
    session: dict[str, set[str]] = defaultdict(set)
    event: dict[str, set[str]] = defaultdict(set)

    with NET_NODES.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["node_type"] != "person":
                continue
            pid = row["local_id"]
            names[pid] = row["label"]
            collab.setdefault(pid, set())
            session.setdefault(pid, set())
            event.setdefault(pid, set())

    def person_local(node_id: str) -> str | None:
        if node_id.startswith("person:"):
            return node_id.split(":", 1)[1]
        return None

    with NET_EDGES.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            et = row["edge_type"]
            a = person_local(row["source"])
            b = person_local(row["target"])
            if not a or not b:
                continue
            if et == "person_person_copresentation":
                add_undirected(collab, a, b)
            elif et == "person_person_same_session":
                add_undirected(session, a, b)
            # person_event is bipartite — rebuild event projection is incomplete from edges alone
            # without pairing people via shared events; skip dense event from CSV path

    return names, series_counts, collab, session, event


def layer_rows(
    names: dict[str, str],
    series_counts: dict[str, dict],
    graph: dict[str, set[str]],
    betweenness: dict[str, float],
    layer: str,
) -> list[dict]:
    rows = []
    for pid, neigh in graph.items():
        z = int(series_counts.get(pid, {}).get("zograf", 0))
        r = int(series_counts.get(pid, {}).get("roerich", 0))
        total = z + r
        if total == 0 and not neigh and betweenness.get(pid, 0) == 0:
            continue
        series_attended = "both" if z and r else ("zograf_only" if z else ("roerich_only" if r else "none"))
        rows.append(
            {
                "person_id": pid,
                "display_name": names.get(pid, pid),
                "layer": layer,
                "degree": len(neigh),
                "betweenness": round(float(betweenness.get(pid, 0.0)), 6),
                "zograf_talks": z,
                "roerich_talks": r,
                "total_talks": total,
                "series_attended": series_attended,
                "is_series_bridge": "yes" if z and r else "no",
            }
        )
    rows.sort(key=lambda r: (float(r["betweenness"]), int(r["degree"]), int(r["total_talks"])), reverse=True)
    return rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    source = "db"
    if DB_PATH.exists():
        con = sqlite3.connect(str(DB_PATH))
        names, series_counts, collab, session, event = load_from_db(con)
        con.close()
    elif NET_EDGES.exists() and NET_NODES.exists():
        source = "csv"
        names, series_counts, collab, session, event = load_from_csv()
        print("WARN: conferences.db missing; event layer incomplete from CSV path", file=sys.stderr)
    else:
        print("FAIL: need conferences.db or analytics_output/network_*.csv", file=sys.stderr)
        return 1

    layers = {
        "collaboration": collab,
        "session": session,
        "event": event,
    }
    all_fields = [
        "person_id",
        "display_name",
        "layer",
        "degree",
        "betweenness",
        "zograf_talks",
        "roerich_talks",
        "total_talks",
        "series_attended",
        "is_series_bridge",
    ]
    summary_layers = {}
    combined_top: list[dict] = []

    for layer_name, graph in layers.items():
        # only compute betweenness on nodes with at least one edge + isolates that have talks
        bt = betweenness_centrality(graph) if graph else {}
        rows = layer_rows(names, series_counts, graph, bt, layer_name)
        out_path = OUT / f"network_centrality_{layer_name}.csv"
        write_csv(out_path, rows, all_fields)
        n_edges = sum(len(v) for v in graph.values()) // 2
        n_nonzero_deg = sum(1 for v in graph.values() if v)
        summary_layers[layer_name] = {
            "nodes": len(graph),
            "nodes_with_degree": n_nonzero_deg,
            "undirected_edges": n_edges,
            "max_degree": max((len(v) for v in graph.values()), default=0),
            "max_betweenness": max((bt.get(k, 0.0) for k in graph), default=0.0),
            "top3": [
                {
                    "person_id": r["person_id"],
                    "display_name": r["display_name"],
                    "degree": r["degree"],
                    "betweenness": r["betweenness"],
                    "series_attended": r["series_attended"],
                }
                for r in rows[:3]
            ],
            "csv": str(out_path.relative_to(ROOT)).replace("\\", "/"),
        }
        combined_top.extend(rows[:15])
        print(f"{layer_name}: nodes={len(graph)} edges={n_edges} deg>0={n_nonzero_deg} -> {out_path.name}")

    # series bridges: people with talks in BOTH series, ranked by event-layer betweenness then degree
    event_bt = betweenness_centrality(event) if event else {}
    bridges = []
    for pid, sc in series_counts.items():
        z, r = int(sc.get("zograf", 0)), int(sc.get("roerich", 0))
        if not (z and r):
            continue
        bridges.append(
            {
                "person_id": pid,
                "display_name": names.get(pid, pid),
                "zograf_talks": z,
                "roerich_talks": r,
                "total_talks": z + r,
                "balance": round((z - r) / (z + r), 3) if (z + r) else 0,
                "event_degree": len(event.get(pid, ())),
                "event_betweenness": round(float(event_bt.get(pid, 0.0)), 6),
                "session_degree": len(session.get(pid, ())),
                "collaboration_degree": len(collab.get(pid, ())),
            }
        )
    bridges.sort(
        key=lambda r: (
            float(r["event_betweenness"]),
            int(r["event_degree"]),
            int(r["total_talks"]),
        ),
        reverse=True,
    )
    bridge_fields = [
        "person_id",
        "display_name",
        "zograf_talks",
        "roerich_talks",
        "total_talks",
        "balance",
        "event_degree",
        "event_betweenness",
        "session_degree",
        "collaboration_degree",
    ]
    bridge_path = OUT / "network_series_bridges.csv"
    write_csv(bridge_path, bridges, bridge_fields)
    print(f"series_bridges: n={len(bridges)} -> {bridge_path.name}")

    summary = {
        "generated": date.today().isoformat(),
        "source": source,
        "handoff": "H2411",
        "layers": summary_layers,
        "series_bridge_people": len(bridges),
        "series_bridge_csv": str(bridge_path.relative_to(ROOT)).replace("\\", "/"),
        "series_bridge_top5": [
            {
                "display_name": b["display_name"],
                "zograf_talks": b["zograf_talks"],
                "roerich_talks": b["roerich_talks"],
                "event_betweenness": b["event_betweenness"],
                "collaboration_degree": b["collaboration_degree"],
            }
            for b in bridges[:5]
        ],
        "notes": [
            "Betweenness is structural connectivity, not scholarly quality.",
            "Collaboration layer uses programme co-presentation only (n edges small).",
            "Do not mix edge types into one undifferentiated network (see network_robustness_checks.csv).",
        ],
    }
    summary_path = OUT / "network_centrality_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"summary -> {summary_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
