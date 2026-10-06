"""Co-citation network of indologists over the nagari corpus (H6060).

A "citing document" is one nagari googlegroup thread exported under
``nagari/md/<year>/<slug>__<thread_id>.md``. Two scholars from
``conferences.db`` (person table) are co-cited in a thread when capitalised
surname-stem forms of both appear in the thread text. Edge weight = number of
threads co-mentioning the pair. Nodes enter the network at
``--min-threads`` (default 2) co-citation-relevant threads.

Determinism: sorted persons, sorted files, fixed iteration order, no RNG.

Outputs (all under analytics_output/ unless --out overrides):
  cocitation_network_nodes.csv      per-person citation + network metrics
  cocitation_network_edges.csv      weighted co-citation edges
  cocitation_network_metrics.json   summary: hubs, channels, schools, anchor
  cocitation_network_data.json      vis-network payload for cocitation-network.html

Extension anchor (H5931): threads mentioning Cappeller (Цапеллер/Cappeller)
and Kochergina (Кочергин*) are counted separately — neither is a person row,
so they live in the metrics/report only, not in the graph.
"""

from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
import math
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Given-name tokens that appear in first/last position for some persons and
# must never act as surname candidates (order-agnostic name storage).
GIVEN_NAME_STOPLIST = {
    "Мария", "Вишну", "Радха", "Ярослав", "Владимир", "Иван", "Елена",
    "Екатерина", "Андрей", "Сергей", "Юрий", "Михаил", "Борис", "Павел",
    "Пётр", "Петр", "Фёдор", "Федор", "Каэтан", "Оттон", "Эдгар",
    "Светлана", "Наталия", "Наталья", "Юлия", "Маргарита", "Дарья",
    "Ирина", "Влада", "Кока", "Алексей", "Александр", "Николай",
    "Всеволод", "Василий", "Дмитрий", "Евгений", "Олег", "Леонид",
}

WORD_RX = re.compile(r"[А-ЯЁA-Z][а-яёa-z]+")
THREAD_ID_RX = re.compile(r"__(\d+)\.md$")
# Russian patronymic endings: tokens like «Николаевич»/«Владимировна» are
# middle-name forms, never surname candidates.
PATRONYMIC_RX = re.compile(r"(евич|ович|ьич|инична|евна|овна|ична)$")
ANCHOR_CAPPELLER = ("Цапеллер", "Cappeller")
ANCHOR_KOCHERGINA = ("Кочергин", "Kochergina")


def surname_candidates(name: str) -> list[str]:
    """First and last alphabetic tokens of a stored name, minus given names.

    Storage mixes «Фамилия Имя Отчество» and «Given Surname» orders, so both
    edge tokens are candidates; the stoplist and ambiguity filter keep this
    honest. Middle tokens (patronymics) are never candidates.
    """
    tokens = [t.strip('«»"\'') for t in (name or "").split()]
    tokens = [
        t for t in tokens
        if t.isalpha() and len(t) >= 4 and not PATRONYMIC_RX.search(t)
    ]
    if not tokens:
        return []
    candidates = []
    for tok in (tokens[0], tokens[-1]):
        if tok not in GIVEN_NAME_STOPLIST and tok not in candidates:
            candidates.append(tok)
    return candidates


def stem(token: str) -> str | None:
    """Declension-tolerant stem: drop 2 tail chars (>=7) or 1 (>=5)."""
    if len(token) >= 7:
        return token[:-2]
    if len(token) >= 5:
        return token[:-1]
    return None


def load_persons(db_path: Path) -> tuple[dict[str, dict], dict[str, str], list[str]]:
    """Return (persons, stem->person_id index, skipped_ambiguous names)."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT person_id, display_name, full_name_ru, person_kind FROM person"
        ).fetchall()
    finally:
        con.close()
    persons: dict[str, dict] = {}
    cand_count: collections.Counter[str] = collections.Counter()
    cand_pid: dict[str, list[str]] = collections.defaultdict(list)
    for pid, disp, ru, kind in rows:
        names = [n for n in (ru, disp) if n]
        cands: list[str] = []
        for name in names:
            for c in surname_candidates(name):
                if c not in cands:
                    cands.append(c)
        persons[pid] = {
            "person_id": pid,
            "name": ru or disp,
            "kind": kind or "",
            "candidates": cands,
        }
        for c in cands:
            cand_count[c] += 1
            cand_pid[c].append(pid)
    stem_index: dict[str, str] = {}
    skipped: list[str] = []
    seen_ambiguous_pids: set[str] = set()
    for cand, count in sorted(cand_count.items()):
        if count > 1:
            skipped.append(cand)
            seen_ambiguous_pids.update(cand_pid[cand])
            continue
        # Register BOTH declension cuts (-1 and -2) so oblique forms match:
        # «Кочергиной»[-2:] == «Кочергин», «Кочергина»[-2:] == «Кочерги».
        for st in (cand[:-1], cand[:-2]):
            if len(st) >= 4 and st not in stem_index:
                stem_index[st] = cand_pid[cand][0]
    for pid in persons:
        if pid in seen_ambiguous_pids:
            persons[pid]["ambiguous"] = True
    return persons, stem_index, skipped


def scan_corpus(corpus_dir: Path, stem_index: dict[str, str]):
    """One pass over thread files.

    Returns per-person counters, per-pair counter, per-pair year ranges,
    thread totals, and anchor thread sets.
    """
    files = sorted(corpus_dir.glob("*/*.md"))
    person_mentions = collections.Counter()
    person_threads = collections.Counter()
    pair_threads: collections.Counter[tuple[str, str]] = collections.Counter()
    pair_years: dict[tuple[str, str], list[int]] = collections.defaultdict(list)
    anchor_cappeller = 0
    anchor_kochergina = 0
    anchor_both = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        year_match = re.match(r"(\d{4})", path.parent.name)
        year = int(year_match.group(1)) if year_match else 0
        hit: set[str] = set()
        for word in WORD_RX.findall(text):
            for cut in (word[:-1], word[:-2]):
                pid = stem_index.get(cut)
                if pid is not None:
                    hit.add(pid)
                    person_mentions[pid] += 1
        for pid in hit:
            person_threads[pid] += 1
        ordered = sorted(hit)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                pair_threads[(a, b)] += 1
                if year:
                    pair_years[(a, b)].append(year)
        has_cappeller = any(a in text for a in ANCHOR_CAPPELLER)
        has_kochergina = any(a in text for a in ANCHOR_KOCHERGINA)
        if has_cappeller:
            anchor_cappeller += 1
        if has_kochergina:
            anchor_kochergina += 1
        if has_cappeller and has_kochergina:
            anchor_both += 1
    return {
        "files": len(files),
        "mentions": person_mentions,
        "threads": person_threads,
        "pairs": pair_threads,
        "pair_years": pair_years,
        "anchor_cappeller": anchor_cappeller,
        "anchor_kochergina": anchor_kochergina,
        "anchor_both": anchor_both,
    }


def build_graph(pair_threads, person_threads, min_threads: int):
    nodes = sorted(pid for pid, n in person_threads.items() if n >= min_threads)
    node_set = set(nodes)
    edges = [
        (a, b, w)
        for (a, b), w in sorted(pair_threads.items())
        if a in node_set and b in node_set
    ]
    adj: dict[str, list[tuple[str, float]]] = {n: [] for n in nodes}
    for a, b, w in edges:
        adj[a].append((b, w))
        adj[b].append((a, w))
    return nodes, edges, adj


def betweenness_weighted(nodes, adj) -> dict[str, float]:
    """Brandes 2001 on weighted graphs (distance = 1/weight)."""
    btw = {n: 0.0 for n in nodes}
    order = sorted(nodes)
    for s in order:
        stack: list[str] = []
        preds: dict[str, list[str]] = {n: [] for n in order}
        sigma = {n: 0 for n in order}
        sigma[s] = 1
        dist = {n: math.inf for n in order}
        dist[s] = 0.0
        # Dijkstra
        import heapq

        heap = [(0.0, s)]
        while heap:
            d, v = heapq.heappop(heap)
            if d > dist[v]:
                continue
            stack.append(v)
            for nbr, w in adj[v]:
                nd = d + 1.0 / w
                if nd < dist[nbr]:
                    dist[nbr] = nd
                    sigma[nbr] = sigma[v]
                    preds[nbr] = [v]
                    heapq.heappush(heap, (nd, nbr))
                elif nd == dist[nbr]:
                    sigma[nbr] += sigma[v]
                    preds[nbr].append(v)
        delta = {n: 0.0 for n in order}
        while stack:
            w = stack.pop()
            for v in preds[w]:
                if sigma[w] > 0:
                    c = (sigma[v] / sigma[w]) * (1.0 + delta[w])
                    delta[v] += c
            if w != s:
                btw[w] += delta[w]
    scale = 1.0 / 2.0 if len(order) > 2 else 1.0
    return {n: b * scale for n, b in btw.items()}


def pagerank_weighted(nodes, adj, damping: float = 0.85, iters: int = 60):
    n = len(nodes)
    if n == 0:
        return {}
    rank = {v: 1.0 / n for v in nodes}
    out_w = {v: sum(w for _, w in adj[v]) or 1.0 for v in nodes}
    for _ in range(iters):
        nxt = {v: (1.0 - damping) / n for v in nodes}
        dangling = damping * (1.0 / n) * sum(rank[v] for v in nodes if not adj[v])
        for v in nodes:
            if not adj[v]:
                continue
            share = damping * rank[v] / out_w[v]
            for nbr, w in adj[v]:
                nxt[nbr] += share * w
        for v in nodes:
            nxt[v] += dangling / n
        rank = nxt
    return rank


def communities_greedy(nodes, adj) -> tuple[dict[str, str], int, float]:
    """Deterministic greedy modularity (CNM-style best-merge).

    Returns (labels node->community rep, n_communities, modularity Q).
    Q uses the per-community form Q = sum_c [ Wc/m - (Kc/2m)^2 ], where Wc is
    intra-community weight (edges once), Kc community degree, m total weight.
    """
    nodes = sorted(nodes)
    idx = {v: i for i, v in enumerate(nodes)}
    n = len(nodes)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    m = sum(w for v in nodes for _, w in adj[v]) / 2.0
    # inter-community weights, keyed canonically (min root, max root)
    inter: dict[tuple[int, int], float] = {}
    deg = {v: sum(w for _, w in adj[v]) for v in nodes}
    for v in nodes:
        for nbr, w in adj[v]:
            a, b = find(idx[v]), find(idx[nbr])
            if a == b:
                continue
            key = (min(a, b), max(a, b))
            inter[key] = inter.get(key, 0.0) + w
    for k in list(inter):
        inter[k] /= 2.0  # each edge seen from both sides
    com_deg: dict[int, float] = {i: float(deg[v]) for i, v in enumerate(nodes)}
    if m == 0:
        labels = {v: v for v in nodes}
        return labels, n, 0.0
    while True:
        best_delta = 1e-12
        best_pair = None
        for (ra, rb), w in sorted(inter.items()):
            delta = w / m - (com_deg[ra] * com_deg[rb]) / (2.0 * m * m)
            if delta > best_delta:
                best_delta = delta
                best_pair = (ra, rb)
        if best_pair is None:
            break
        ra, rb = best_pair
        new_root, absorbed = (ra, rb) if ra < rb else (rb, ra)
        # merge inter-weights into the surviving root
        for key in list(inter):
            other = None
            if key == best_pair:
                other = None
            elif key[0] == absorbed:
                other = key[1]
            elif key[1] == absorbed:
                other = key[0]
            if other is not None:
                nk = (min(new_root, other), max(new_root, other))
                inter[nk] = inter.get(nk, 0.0) + inter.pop(key)
            elif key == best_pair:
                inter.pop(key)
        com_deg[new_root] = com_deg.get(new_root, 0.0) + com_deg.pop(absorbed)
        parent[absorbed] = new_root
    labels: dict[str, str] = {}
    for v in nodes:
        r = find(idx[v])
        labels[v] = nodes[r]
    roots = sorted(set(labels.values()))
    # modularity per community
    intra: dict[str, float] = {r: 0.0 for r in roots}
    cdeg: dict[str, float] = {r: 0.0 for r in roots}
    for v in nodes:
        cdeg[labels[v]] += deg[v]
        for nbr, w in adj[v]:
            if labels[nbr] == labels[v]:
                intra[labels[v]] += w
    for r in roots:
        intra[r] /= 2.0
    q = sum(intra[r] / m - (cdeg[r] / (2.0 * m)) ** 2 for r in roots)
    return labels, len(roots), q


def connected_components(nodes, adj):
    seen: set[str] = set()
    comps = []
    for v in sorted(nodes):
        if v in seen:
            continue
        comp, stack = [], [v]
        seen.add(v)
        while stack:
            u = stack.pop()
            comp.append(u)
            for nbr, _ in adj[u]:
                if nbr not in seen:
                    seen.add(nbr)
                    stack.append(nbr)
        comps.append(sorted(comp))
    return sorted(comps, key=len, reverse=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "Co-citation network builder for H6060.").splitlines()[0]
    )
    ap.add_argument("--db", default=str(ROOT / "conferences.db"))
    ap.add_argument("--corpus", default=str(ROOT / "nagari" / "md"))
    ap.add_argument("--out", default=str(ROOT / "analytics_output"))
    ap.add_argument("--min-threads", type=int, default=2)
    args = ap.parse_args(argv)

    db_path, corpus_dir, out_dir = Path(args.db), Path(args.corpus), Path(args.out)
    if not db_path.exists():
        print(f"db not found: {db_path}", file=sys.stderr)
        return 2
    if not corpus_dir.is_dir():
        print(f"corpus not found: {corpus_dir}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    persons, stem_index, skipped_ambiguous = load_persons(db_path)
    scan = scan_corpus(corpus_dir, stem_index)
    nodes, edges, adj = build_graph(scan["pairs"], scan["threads"], args.min_threads)

    strength = {v: 0.0 for v in nodes}
    degree = {v: 0 for v in nodes}
    for a, b, w in edges:
        strength[a] += w
        strength[b] += w
        degree[a] += 1
        degree[b] += 1
    btw = betweenness_weighted(nodes, adj)
    pr = pagerank_weighted(nodes, adj)
    # Communities on the weight>=2 backbone: weight-1 edges are mostly
    # single-thread list coincidences and blur community structure on this
    # dense graph. Backbone Q is computed by the greedy partition itself.
    backbone_edges = [(a, b, w) for a, b, w in edges if w >= 2]
    backbone_nodes = sorted({v for a, b, _ in backbone_edges for v in (a, b)})
    backbone_adj: dict[str, list[tuple[str, float]]] = {n: [] for n in backbone_nodes}
    for a, b, w in backbone_edges:
        backbone_adj[a].append((b, w))
        backbone_adj[b].append((a, w))
    labels_bb, n_communities, q = communities_greedy(backbone_nodes, backbone_adj)
    labels = {v: labels_bb.get(v, v) for v in nodes}
    n_isolate_communities = len({labels[v] for v in nodes}) - n_communities
    comps = connected_components(nodes, adj)

    def row_for(pid):
        return {
            "person_id": pid,
            "name": persons[pid]["name"],
            "person_kind": persons[pid]["kind"],
            "mentions": scan["mentions"].get(pid, 0),
            "threads": scan["threads"].get(pid, 0),
            "degree": degree[pid],
            "strength": int(strength[pid]),
            "betweenness": round(btw[pid], 6),
            "pagerank": round(pr[pid], 8),
            "community": labels[pid],
        }

    node_rows = [row_for(pid) for pid in nodes]

    # CSV outputs
    nodes_csv = out_dir / "cocitation_network_nodes.csv"
    with nodes_csv.open("w", encoding="utf-8", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(node_rows[0].keys()) if node_rows else
                             ["person_id", "name"])
        wtr.writeheader()
        wtr.writerows(node_rows)

    edges_csv = out_dir / "cocitation_network_edges.csv"
    with edges_csv.open("w", encoding="utf-8", newline="") as f:
        wtr = csv.writer(f)
        wtr.writerow(["source_id", "source_name", "target_id", "target_name",
                      "weight", "first_year", "last_year"])
        for a, b, w in edges:
            years = sorted(set(scan["pair_years"].get((a, b), [])))
            wtr.writerow([a, persons[a]["name"], b, persons[b]["name"], w,
                          years[0] if years else "", years[-1] if years else ""])

    hubs = sorted(node_rows, key=lambda r: (-r["strength"], r["person_id"]))[:15]
    channels = sorted(node_rows, key=lambda r: (-r["betweenness"], r["person_id"]))[:15]
    comm_groups: dict[str, list[dict]] = collections.defaultdict(list)
    for r in node_rows:
        comm_groups[r["community"]].append(r)
    schools = []
    for rep, members in sorted(comm_groups.items(), key=lambda kv: -len(kv[1])):
        if len(members) < 3:
            continue
        members_sorted = sorted(members, key=lambda r: (-r["strength"], r["person_id"]))
        schools.append({
            "community": rep,
            "size": len(members),
            "top_members": [
                {"person_id": m["person_id"], "name": m["name"],
                 "strength": m["strength"]}
                for m in members_sorted[:8]
            ],
        })

    n_undirected_pairs = len(nodes) * (len(nodes) - 1) // 2
    density = (len(edges) / n_undirected_pairs) if n_undirected_pairs else 0.0
    metrics = {
        "generated": dt.date.today().isoformat(),
        "handoff": "H6060",
        "method": {
            "citing_document": "nagari googlegroup thread (nagari/md/<year>/*.md)",
            "unit": "capitalised surname-stem co-occurrence within one thread",
            "node_filter": f"mentioned in >= {args.min_threads} threads",
            "deterministic": True,
        },
        "corpus": {
            "threads_scanned": scan["files"],
            "db_persons": len(persons),
            "persons_matched_any_thread": len(scan["threads"]),
            "surname_stems_indexed": len(stem_index),
            "ambiguous_surnames_skipped": len(skipped_ambiguous),
            "ambiguous_surnames_list": skipped_ambiguous,
        },
        "network": {
            "nodes": len(nodes),
            "edges": len(edges),
            "density": round(density, 6),
            "total_cocitation_weight": int(sum(w for _, _, w in edges)),
            "components": len(comps),
            "largest_component": len(comps[0]) if comps else 0,
            "communities": n_communities,
            "communities_isolate_nodes": n_isolate_communities,
            "modularity_q": round(q, 6),
            "backbone": {
                "edge_min_weight": 2,
                "nodes": len(backbone_nodes),
                "edges": len(backbone_edges),
            },
        },
        "top_hubs_strength": [
            {"person_id": r["person_id"], "name": r["name"], "strength": r["strength"],
             "threads": r["threads"], "community": r["community"]} for r in hubs
        ],
        "top_channels_betweenness": [
            {"person_id": r["person_id"], "name": r["name"],
             "betweenness": r["betweenness"], "degree": r["degree"]}
            for r in channels if r["betweenness"] > 0
        ],
        "schools": schools,
        "limitations": [
            ("co-mention in community discourse (one googlegroup thread), "
             "not bibliometric co-citation from reference lists"),
            ("surname-stem matching: same-surname persons outside the DB are "
             "inseparable; skipped ambiguous stems are listed in "
             "corpus.ambiguous_surnames_list"),
            ("name homonyms (Ivanov, Smirnov, …) can produce false positives; "
             "edge weights read as order of magnitude, not exact counts"),
            ("export author lines use pseudonyms, not surnames; authorship "
             "contribution to co-mention is minimal but non-zero"),
        ],
        "anchor_h5931_cappeller_kochergina": {
            "threads_cappeller": scan["anchor_cappeller"],
            "threads_kochergina": scan["anchor_kochergina"],
            "threads_both": scan["anchor_both"],
            "note": ("Cappeller and Kochergina are corpus-mentioned indologists "
                     "outside the conferences.db person table; they anchor the "
                     "H5931 dictionary-channel result (rho 0.571 by article "
                     "lengths) but are not graph nodes."),
        },
    }
    metrics_csv = out_dir / "cocitation_network_metrics.json"
    metrics_csv.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")

    # vis-network payload
    comm_ids = sorted({str(labels[v]) for v in nodes})
    comm_color: dict[str, int] = {c: i for i, c in enumerate(comm_ids)}
    viz = {
        "generated": metrics["generated"],
        "nodes": [
            {
                "id": r["person_id"],
                "label": r["name"],
                "title": (f"{r['name']} — {r['threads']} тредов, "
                          f"вес {r['strength']}"),
                "value": r["strength"],
                "group": comm_color[r["community"]],
                "kind": r["person_kind"],
            }
            for r in node_rows
        ],
        "edges": [
            {"from": a, "to": b, "value": w,
             "title": f"{persons[a]['name']} — {persons[b]['name']}: {w}"}
            for a, b, w in edges
        ],
        "legend": {str(i): rep for rep, i in comm_color.items()},
    }
    viz_path = out_dir / "cocitation_network_data.json"
    viz_path.write_text(json.dumps(viz, ensure_ascii=False) + "\n", encoding="utf-8")

    # Human report
    report = build_report(metrics, node_rows, edges)
    (out_dir / "cocitation_report.md").write_text(report, encoding="utf-8")

    print(f"nodes={len(nodes)} edges={len(edges)} weight={metrics['network']['total_cocitation_weight']}"
          f" Q={q:.4f} communities={n_communities}")
    print(f"wrote: {nodes_csv.name}, {edges_csv.name}, {metrics_csv.name},"
          f" {viz_path.name}, cocitation_report.md")
    return 0


def build_report(metrics, node_rows, edges):
    lines = []
    a = lines.append
    a(f"_Created: {metrics['generated']} · builder: tools/build_cocitation_network.py (H6060)_\n")
    a("# Сеть со-цитирований индологов (корпус nagari)\n")
    a("Со-цитирование = два индолога из базы `conferences.db` упомянуты в одном треде "
      "закрытой гуглгруппы «Общество ревнителей санскрита» (2005–2026, экспорт в "
      "`nagari/md/`). Вес ребра — число тредов, где пара встретилась вместе.\n")
    n = metrics["network"]
    a("## Сводка\n")
    a(f"- Тредов просканировано: **{metrics['corpus']['threads_scanned']}**")
    a(f"- Персон в базе: **{metrics['corpus']['db_persons']}**, упомянуты хоть в одном "
      f"треде: **{metrics['corpus']['persons_matched_any_thread']}**")
    a(f"- Узлов сети (≥{metrics['method']['node_filter'].split('>= ')[1]}): **{n['nodes']}**, "
      f"рёбер: **{n['edges']}**, суммарный вес: **{n['total_cocitation_weight']}**")
    a(f"- Плотность: {n['density']}; компонент: {n['components']}"
      f" (крупнейшая {n['largest_component']})")
    a(f"- Сообществ (label propagation): **{n['communities']}**, модулярность Q = "
      f"**{n['modularity_q']}**\n")
    a("## Хабы (по суммарному весу со-цитирований)\n")
    a("| # | Индолог | Вес | Тредов |")
    a("|---|---------|-----|--------|")
    for i, h in enumerate(metrics["top_hubs_strength"][:10], 1):
        a(f"| {i} | {h['name']} | {h['strength']} | {h['threads']} |")
    a("")
    a("## Каналы (по betweenness — связывают обсуждения друг с другом)\n")
    a("| # | Индолог | Betweenness | Degree |")
    a("|---|---------|-------------|--------|")
    for i, c in enumerate(metrics["top_channels_betweenness"][:10], 1):
        a(f"| {i} | {c['name']} | {c['betweenness']} | {c['degree']} |")
    a("")
    a("## Школы/сцепки (сообщества ≥3 узлов)\n")
    for s in metrics["schools"]:
        names = ", ".join(m["name"] for m in s["top_members"][:5])
        a(f"- **Сообщество {s['community'][:12]}…** ({s['size']} узлов): {names}"
          + ("…" if len(s["top_members"]) > 5 else ""))
    a("")
    a("## Мост к H5931 (Цапеллер ↔ Кочергина)\n")
    anc = metrics["anchor_h5931_cappeller_kochergina"]
    a(f"Тредов с Цапеллером: {anc['threads_cappeller']}; с Кочергиной: "
      f"{anc['threads_kochergina']}; с обоими: **{anc['threads_both']}**. "
      + (
          "Канал «словарь Кочергиной ← Цапеллер» (ρ 0.571 по длинам статей, "
          "H5931) проявляется и в дискурсе сообщества."
          if anc["threads_both"] > 0 else
          "Совместных обсуждений нет: канал «словарь Кочергиной ← Цапеллер» "
          "(ρ 0.571 по длинам статей, H5931) остаётся лексикографическим "
          "фактом, который дискурс сообщества не проговаривает, — словарь "
          "обсуждается без имени его источника. Ни Цапеллер, ни Кочергина не "
          "входят в таблицу person и потому не являются узлами графа."
      ) + "\n")
    a("## Ограничения (guardrails)\n")
    a("- Совпадение по стемам фамилий (падежи учтены усечением); однофамильцы "
      f"вне базы не отделимы: {metrics['corpus']['ambiguous_surnames_list']}")
    a("- Имена-омонимы (Иванов, Смирнов и т.п.) могут давать ложные срабатывания; "
      "веса следует читать как «порядок», а не точные числа.")
    a("- Авторские строки экспорта используют псевдонимы, а не фамилии; вклад "
      "авторства в со-цитирования минимален, но не нулевой.")
    a("- Это со-упоминания в дискурсе сообщества (co-mention), а не строгие "
      "библиометрические со-цитирования по спискам литературы.")
    a("- Визуализация: [cocitation-network.html](https://gasyoun.github.io/"
      "IndologyScholars/cocitation-network.html); данные: "
      "`analytics_output/cocitation_network_data.json`.\n")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
