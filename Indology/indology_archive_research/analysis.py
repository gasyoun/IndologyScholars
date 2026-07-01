"""Build summary tables and figures from harvested INDOLOGY metadata."""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

from .topics import classify_subject, clean_subject, is_noisy_subject


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def read_messages(processed_dir: Path) -> pd.DataFrame:
    path = processed_dir / "messages_raw.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}; run scrape first")
    df = pd.read_csv(path, dtype=str).fillna("")
    df["archive_year"] = pd.to_numeric(df["archive_year"], errors="coerce").astype("Int64")
    df["archive_month"] = pd.to_numeric(df["archive_month"], errors="coerce").astype("Int64")
    df["thread_depth"] = pd.to_numeric(df["thread_depth"], errors="coerce").fillna(0).astype(int)
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df["year"] = df["date"].dt.year.fillna(df["archive_year"]).astype("Int64")
    df["month"] = df["date"].dt.month.fillna(df["archive_month"]).astype("Int64")
    df["decade"] = (df["year"].astype(float) // 10 * 10).astype("Int64").astype(str) + "s"
    df["clean_subject"] = df["subject"].where(df["subject"].ne(""), df["subject_html"]).map(clean_subject)
    classified = df["clean_subject"].map(classify_subject)
    df["primary_topic"] = classified.map(lambda x: x[0])
    df["topic_tags"] = classified.map(lambda x: "|".join(x[1]))
    df["is_noisy_subject"] = df["clean_subject"].map(is_noisy_subject)
    df["author_display"] = df["author_html"].where(df["author_html"].ne(""), df["author"])
    return df


def build_threads(messages: pd.DataFrame) -> pd.DataFrame:
    grouped = messages.groupby("thread_root_id", dropna=False)
    rows = []
    for thread_id, group in grouped:
        topic_counts = group["primary_topic"].value_counts()
        rows.append(
            {
                "thread_root_id": thread_id,
                "slug": group["slug"].iloc[0],
                "year": int(group["year"].dropna().iloc[0]) if group["year"].notna().any() else "",
                "month": int(group["month"].dropna().iloc[0]) if group["month"].notna().any() else "",
                "thread_subject": group.sort_values("thread_depth")["clean_subject"].iloc[0],
                "message_count": len(group),
                "author_count": group["author_display"].nunique(),
                "primary_topic": topic_counts.index[0] if len(topic_counts) else "General scholarly discussion",
                "authors": " | ".join(sorted(a for a in group["author_display"].unique() if a)),
            }
        )
    return pd.DataFrame(rows).sort_values(["year", "month", "thread_root_id"])


def build_network_edges(messages: pd.DataFrame, min_thread_messages: int = 2) -> pd.DataFrame:
    edges: dict[tuple[str, str], dict[str, object]] = {}
    for _, group in messages.groupby("thread_root_id"):
        authors = sorted(a for a in group["author_display"].unique() if a)
        if len(group) < min_thread_messages or len(authors) < 2:
            continue
        topic = group["primary_topic"].mode().iloc[0]
        for left, right in itertools.combinations(authors, 2):
            key = (left, right)
            if key not in edges:
                edges[key] = {"source": left, "target": right, "weight": 0, "topics": set(), "edge_type": "thread_coparticipation"}
            edges[key]["weight"] = int(edges[key]["weight"]) + 1
            edges[key]["topics"].add(topic)
    rows = []
    for row in edges.values():
        rows.append({**row, "topics": "|".join(sorted(row["topics"]))})
    return pd.DataFrame(rows).sort_values("weight", ascending=False) if rows else pd.DataFrame(columns=["source", "target", "weight", "topics"])


def save_tables(output_dir: Path) -> dict[str, pd.DataFrame]:
    processed_dir = output_dir / "data" / "processed"
    messages = read_messages(processed_dir)
    threads = build_threads(messages)
    messages = messages.merge(threads[["thread_root_id", "message_count"]].rename(columns={"message_count": "thread_length"}), on="thread_root_id", how="left")

    monthly = (
        messages.groupby(["archive_year", "archive_month"], dropna=False)
        .size()
        .reset_index(name="message_count")
        .sort_values(["archive_year", "archive_month"])
    )
    yearly = messages.groupby("year", dropna=False).size().reset_index(name="message_count").sort_values("year")
    topic_year = (
        messages.groupby(["year", "primary_topic"], dropna=False)
        .size()
        .reset_index(name="message_count")
        .sort_values(["year", "primary_topic"])
    )
    topic_decade = (
        messages.groupby(["decade", "primary_topic"], dropna=False)
        .size()
        .reset_index(name="message_count")
        .sort_values(["decade", "primary_topic"])
    )
    author_eras = (
        messages.groupby(["author_display", "decade"], dropna=False)
        .size()
        .reset_index(name="message_count")
        .sort_values(["author_display", "decade"])
    )
    noisy = messages[messages["is_noisy_subject"]][["archive_id", "date", "author_display", "clean_subject", "archive_url"]]
    network_edges = build_network_edges(messages)

    outputs = {
        "messages": messages,
        "threads": threads,
        "monthly_counts": monthly,
        "yearly_counts": yearly,
        "topic_year_counts": topic_year,
        "topic_decade_counts": topic_decade,
        "author_eras": author_eras,
        "noisy_subjects": noisy,
        "network_edges": network_edges,
    }
    for name, frame in outputs.items():
        frame.to_csv(processed_dir / f"{name}.csv", index=False, encoding="utf-8")
    return outputs


def set_plot_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 140,
            "savefig.dpi": 180,
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "figure.constrained_layout.use": True,
        }
    )


def plot_figures(output_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    set_plot_style()
    messages = tables["messages"].copy()
    messages["period"] = pd.to_datetime(
        messages["archive_year"].astype(str) + "-" + messages["archive_month"].astype(str).str.zfill(2) + "-01",
        errors="coerce",
    )

    monthly = tables["monthly_counts"].copy()
    monthly["period"] = pd.to_datetime(monthly["archive_year"].astype(str) + "-" + monthly["archive_month"].astype(str).str.zfill(2) + "-01")
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(monthly["period"], monthly["message_count"], color="#2f6f73", linewidth=1.2)
    ax.set_title("INDOLOGY Monthly Message Volume")
    ax.set_ylabel("Messages")
    ax.set_xlabel("")
    fig.savefig(figures_dir / "monthly_message_volume.png")
    plt.close(fig)

    yearly = tables["yearly_counts"].copy()
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(yearly["year"].astype(int), yearly["message_count"], color="#7a5c61")
    ax.set_title("INDOLOGY Yearly Message Volume")
    ax.set_ylabel("Messages")
    ax.set_xlabel("Year")
    fig.savefig(figures_dir / "yearly_message_volume.png")
    plt.close(fig)

    topic_year = tables["topic_year_counts"].copy()
    pivot = topic_year.pivot_table(index="year", columns="primary_topic", values="message_count", aggfunc="sum", fill_value=0)
    top_topics = pivot.sum().sort_values(ascending=False).head(9).index
    fig, ax = plt.subplots(figsize=(11, 5))
    pivot[top_topics].plot.area(ax=ax, linewidth=0)
    ax.set_title("Topic Mix Over Time")
    ax.set_ylabel("Messages")
    ax.set_xlabel("Year")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    fig.savefig(figures_dir / "topic_stream.png")
    plt.close(fig)

    topic_decade = tables["topic_decade_counts"].copy()
    heat = topic_decade.pivot_table(index="primary_topic", columns="decade", values="message_count", aggfunc="sum", fill_value=0)
    heat = heat.loc[heat.sum(axis=1).sort_values(ascending=False).index]
    heat_share = heat.div(heat.sum(axis=1).replace(0, pd.NA), axis=0).fillna(0) * 100
    fig, ax = plt.subplots(figsize=(10, 5.5))
    image = ax.imshow(heat_share.values, aspect="auto", cmap="YlGnBu", vmin=0, vmax=100)
    ax.set_title("Topic Distribution By Decade")
    ax.set_yticks(range(len(heat.index)), heat.index)
    ax.set_xticks(range(len(heat.columns)), heat.columns, rotation=45, ha="right")
    ax.set_xlabel("Decade")
    for row_index, topic in enumerate(heat.index):
        for col_index, decade in enumerate(heat.columns):
            count = int(heat.loc[topic, decade])
            share = heat_share.loc[topic, decade]
            text_color = "white" if share >= 55 else "#253238"
            ax.text(col_index, row_index, f"{share:.0f}%\n{count:,}", ha="center", va="center", fontsize=8, color=text_color)
    fig.colorbar(image, ax=ax, label="Share of each topic's messages (%)")
    fig.savefig(figures_dir / "topic_decade_heatmap.png")
    plt.close(fig)

    threads = tables["threads"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(threads["message_count"], bins=range(1, int(threads["message_count"].max()) + 2), color="#8a7f39", edgecolor="white")
    ax.set_title("Thread Length Distribution")
    ax.set_xlabel("Messages in thread")
    ax.set_ylabel("Threads")
    fig.savefig(figures_dir / "thread_length_distribution.png")
    plt.close(fig)

    author_eras = tables["author_eras"].copy()
    top_authors = author_eras.groupby("author_display")["message_count"].sum().sort_values(ascending=False).head(30).index
    author_heat = author_eras[author_eras["author_display"].isin(top_authors)].pivot_table(
        index="author_display", columns="decade", values="message_count", aggfunc="sum", fill_value=0
    )
    author_heat = author_heat.loc[top_authors.intersection(author_heat.index)]
    fig, ax = plt.subplots(figsize=(8, max(5, len(author_heat) * 0.22)))
    image = ax.imshow(author_heat.values, aspect="auto", cmap="PuBuGn")
    ax.set_title("Contributor Activity By Era")
    ax.set_yticks(range(len(author_heat.index)), author_heat.index)
    ax.set_xticks(range(len(author_heat.columns)), author_heat.columns, rotation=45, ha="right")
    fig.colorbar(image, ax=ax, label="Messages")
    fig.savefig(figures_dir / "author_era_matrix.png")
    plt.close(fig)

    top_for_multiples = list(top_topics[:8])
    rows = 4
    cols = 2
    fig, axes = plt.subplots(rows, cols, figsize=(10, 8), sharex=True)
    for ax, topic in zip(axes.ravel(), top_for_multiples):
        series = pivot[topic] if topic in pivot else pd.Series(dtype=float)
        ax.plot(series.index.astype(int), series.values, color="#375a7f")
        ax.set_title(topic)
        ax.set_ylabel("Messages")
    for ax in axes.ravel()[len(top_for_multiples) :]:
        ax.axis("off")
    fig.savefig(figures_dir / "topic_small_multiples.png")
    plt.close(fig)

    edges = tables["network_edges"].head(80)
    if not edges.empty:
        graph = nx.Graph()
        for _, row in edges.iterrows():
            graph.add_edge(row["source"], row["target"], weight=float(row["weight"]))
        degrees = dict(graph.degree(weight="weight"))
        keep = sorted(degrees, key=degrees.get, reverse=True)[:50]
        graph = graph.subgraph(keep).copy()
        pos = nx.spring_layout(graph, seed=42, k=0.45)
        fig, ax = plt.subplots(figsize=(9, 7))
        weights = [graph[u][v]["weight"] for u, v in graph.edges()]
        nx.draw_networkx_edges(graph, pos, ax=ax, width=[0.5 + w * 0.35 for w in weights], alpha=0.35, edge_color="#6b6b6b")
        nx.draw_networkx_nodes(graph, pos, ax=ax, node_size=[80 + degrees[n] * 10 for n in graph.nodes()], node_color="#5b8c85", alpha=0.9)
        nx.draw_networkx_labels(graph, pos, ax=ax, font_size=7)
        ax.set_title("Thread Co-Participation Network")
        ax.axis("off")
        fig.savefig(figures_dir / "thread_coparticipation_network.png")
        plt.close(fig)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--skip-figures", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    tables = save_tables(args.output_dir)
    if not args.skip_figures:
        plot_figures(args.output_dir, tables)


if __name__ == "__main__":
    main()
