"""Generate derived insight tables and figures for the INDOLOGY atlas."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


INSIGHT_TABLE_DESCRIPTIONS = {
    "reply_confidence_year_counts.csv": "Yearly directed-reply evidence counts by confidence level.",
    "topic_decade_share.csv": "Topic message counts and within-decade shares for topic drift analysis.",
    "list_function_decade_share.csv": "List-function message counts and within-decade shares.",
    "thread_typology.csv": "Thread-level typology table with volume, participation, and reply-density evidence.",
    "case_score_components.csv": "Readable components behind generated case-study candidate scores.",
    "review_queue_summary.csv": "Review-burden summary by human-attention domain.",
    "author_participation_cohorts.csv": "Author participation cohorts by first active decade and active-span class.",
}

INSIGHT_FIGURES = [
    "reply_confidence_over_time.png",
    "topic_share_slope_1990s_2020s.png",
    "list_function_decade_mix.png",
    "thread_typology_scatter.png",
    "case_score_components.png",
    "review_queue_summary.png",
    "author_participation_cohorts.png",
]


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, low_memory=False).fillna("") if path.exists() else pd.DataFrame()


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


def save_table(frame: pd.DataFrame, path: Path) -> pd.DataFrame:
    frame.to_csv(path, index=False, encoding="utf-8")
    return frame


def build_reply_confidence_year_counts(reply_edges: pd.DataFrame) -> pd.DataFrame:
    columns = ["year", "confidence", "reply_rows", "resolved_rows", "share_of_year"]
    if reply_edges.empty:
        return pd.DataFrame(columns=columns)
    work = reply_edges.copy()
    work["year"] = pd.to_datetime(work["date"], errors="coerce", utc=True).dt.year
    work = work[work["year"].notna()].copy()
    work["year"] = work["year"].astype(int)
    work["is_resolved"] = work["target_author"].astype(str).ne("")
    grouped = (
        work.groupby(["year", "confidence"], dropna=False)
        .agg(reply_rows=("confidence", "size"), resolved_rows=("is_resolved", "sum"))
        .reset_index()
    )
    yearly_totals = grouped.groupby("year")["reply_rows"].transform("sum")
    grouped["share_of_year"] = (grouped["reply_rows"] / yearly_totals).round(4)
    return grouped[columns].sort_values(["year", "confidence"])


def build_topic_decade_share(topic_decade: pd.DataFrame) -> pd.DataFrame:
    columns = ["decade", "primary_topic", "message_count", "share_of_decade"]
    if topic_decade.empty:
        return pd.DataFrame(columns=columns)
    work = topic_decade.copy()
    work["message_count"] = pd.to_numeric(work["message_count"], errors="coerce").fillna(0).astype(int)
    totals = work.groupby("decade")["message_count"].transform("sum")
    work["share_of_decade"] = (work["message_count"] / totals.where(totals.ne(0), 1)).round(4)
    return work[columns].sort_values(["decade", "message_count"], ascending=[True, False])


def build_list_function_decade_share(list_functions: pd.DataFrame) -> pd.DataFrame:
    columns = ["decade", "list_function", "message_count", "share_of_decade"]
    if list_functions.empty:
        return pd.DataFrame(columns=columns)
    work = list_functions.copy()
    work["message_count"] = pd.to_numeric(work["message_count"], errors="coerce").fillna(0).astype(int)
    if "share_of_decade" not in work.columns:
        totals = work.groupby("decade")["message_count"].transform("sum")
        work["share_of_decade"] = (work["message_count"] / totals.where(totals.ne(0), 1)).round(4)
    else:
        work["share_of_decade"] = pd.to_numeric(work["share_of_decade"], errors="coerce").fillna(0).round(4)
    return work[columns].sort_values(["decade", "message_count"], ascending=[True, False])


def build_thread_typology(threads: pd.DataFrame, reply_edges: pd.DataFrame, messages: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "thread_root_id",
        "year",
        "thread_subject",
        "primary_topic",
        "list_function",
        "message_count",
        "author_count",
        "reply_count",
        "reply_density",
    ]
    if threads.empty:
        return pd.DataFrame(columns=columns)
    work = threads.copy()
    for column in ["message_count", "author_count", "year"]:
        work[column] = pd.to_numeric(work[column], errors="coerce").fillna(0).astype(int)
    resolved = reply_edges[reply_edges.get("target_author", pd.Series(dtype=str)).astype(str).ne("")] if not reply_edges.empty else pd.DataFrame()
    reply_counts = resolved.groupby("thread_root_id").size().rename("reply_count") if not resolved.empty else pd.Series(dtype=int)
    functions = pd.Series(dtype=str)
    if not messages.empty and {"thread_root_id", "list_function"}.issubset(messages.columns):
        functions = messages.groupby("thread_root_id")["list_function"].agg(lambda values: values.mode().iloc[0] if not values.mode().empty else "")
    work = work.merge(reply_counts, on="thread_root_id", how="left")
    work["reply_count"] = pd.to_numeric(work["reply_count"], errors="coerce").fillna(0).astype(int)
    work["list_function"] = work["thread_root_id"].map(functions).fillna("general discussion")
    work["reply_density"] = (work["reply_count"] / work["message_count"].where(work["message_count"].ne(0), 1)).round(4)
    return work[columns].sort_values(["message_count", "author_count"], ascending=False)


def build_case_score_components(cases: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "thread_root_id",
        "subject",
        "primary_topic",
        "score",
        "message_component",
        "author_component",
        "reply_component",
        "topic_component",
        "request_component",
        "resolution_component",
        "debate_component",
        "message_count",
        "author_count",
        "reply_count",
        "topic_count",
    ]
    if cases.empty:
        return pd.DataFrame(columns=columns)
    work = cases.copy()
    for column in ["score", "message_count", "author_count", "reply_count", "topic_count"]:
        work[column] = pd.to_numeric(work[column], errors="coerce").fillna(0).astype(int)
    work["message_component"] = work["message_count"]
    work["author_component"] = work["author_count"] * 3
    work["reply_component"] = work["reply_count"] * 2
    work["topic_component"] = work["topic_count"] * 4
    work["request_component"] = work["request_like"].astype(str).str.lower().eq("true").map(lambda flag: 12 if flag else 0)
    work["resolution_component"] = work["resolution_like"].astype(str).str.lower().eq("true").map(lambda flag: 10 if flag else 0)
    work["debate_component"] = work["debate_like"].astype(str).str.lower().eq("true").map(lambda flag: 10 if flag else 0)
    return work[columns].sort_values("score", ascending=False)


def build_review_queue_summary(processed_dir: Path, reply_edges: pd.DataFrame) -> pd.DataFrame:
    authors = read_csv_if_exists(processed_dir / "authors_needing_review.csv")
    case_queue = read_csv_if_exists(processed_dir / "case_review_queue.csv")
    count_mismatch = read_csv_if_exists(processed_dir / "count_mismatch_audit.csv")
    noisy = read_csv_if_exists(processed_dir / "noisy_subjects.csv")
    named_replies = read_csv_if_exists(processed_dir / "named_reply_network_summary.csv")
    unresolved = reply_edges[reply_edges.get("confidence", pd.Series(dtype=str)).astype(str).eq("unresolved")] if not reply_edges.empty else pd.DataFrame()
    self_replies = (
        named_replies[named_replies.get("is_self_reply", pd.Series(dtype=str)).astype(str).eq("True")]
        if not named_replies.empty
        else pd.DataFrame()
    )
    rows = [
        ("author_normalization", len(authors), "high", "Ambiguous author strings retained without identity merging."),
        ("case_study_review", len(case_queue), "medium", "Generated case-study candidates awaiting human curation."),
        ("count_mismatch", len(count_mismatch), "high", "Archive index and mbox count disagreements."),
        ("noisy_subjects", len(noisy), "low", "Low-signal or mechanical subject lines."),
        ("unresolved_replies", len(unresolved), "medium", "Reply-like rows without resolved target messages."),
        ("named_network_caution", len(self_replies), "medium", "Self-reply or named-network rows needing careful interpretation."),
    ]
    return pd.DataFrame(rows, columns=["domain", "review_items", "priority", "interpretive_note"])


def active_span_class(span: int) -> str:
    if span <= 1:
        return "one-year"
    if span <= 4:
        return "short-term"
    if span <= 12:
        return "decade-scale"
    return "multi-decade"


def build_author_participation_cohorts(people: pd.DataFrame) -> pd.DataFrame:
    columns = ["first_decade", "active_span_class", "author_count", "message_count", "thread_count"]
    if people.empty:
        return pd.DataFrame(columns=columns)
    work = people.copy()
    work["first_year"] = pd.to_numeric(work["first_year"], errors="coerce")
    work["last_year"] = pd.to_numeric(work["last_year"], errors="coerce")
    work = work[work["first_year"].notna() & work["last_year"].notna()].copy()
    work["message_count"] = pd.to_numeric(work["message_count"], errors="coerce").fillna(0).astype(int)
    work["thread_count"] = pd.to_numeric(work["thread_count"], errors="coerce").fillna(0).astype(int)
    work["active_span"] = (work["last_year"] - work["first_year"] + 1).astype(int)
    work["first_decade"] = (work["first_year"].astype(int) // 10 * 10).astype(str) + "s"
    work["active_span_class"] = work["active_span"].map(active_span_class)
    return (
        work.groupby(["first_decade", "active_span_class"], dropna=False)
        .agg(
            author_count=("normalized_author", "nunique"),
            message_count=("message_count", "sum"),
            thread_count=("thread_count", "sum"),
        )
        .reset_index()
        .sort_values(["first_decade", "active_span_class"])
    )[columns]


def plot_reply_confidence(path: Path, table: pd.DataFrame) -> None:
    if table.empty:
        return
    pivot = table.pivot_table(index="year", columns="confidence", values="share_of_year", aggfunc="sum", fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    pivot.plot.area(ax=ax, linewidth=0)
    ax.set_title("Reply Evidence Confidence Over Time")
    ax.set_ylabel("Share of reply rows")
    ax.set_xlabel("Year")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    fig.savefig(path)
    plt.close(fig)


def plot_topic_slope(path: Path, table: pd.DataFrame) -> None:
    if table.empty:
        return
    start_decade = "1990s"
    end_decade = "2020s"
    work = table[table["decade"].isin([start_decade, end_decade])].copy()
    if work.empty or work["decade"].nunique() < 2:
        return
    pivot = work.pivot_table(index="primary_topic", columns="decade", values="share_of_decade", aggfunc="sum", fill_value=0)
    pivot["change"] = pivot[end_decade] - pivot[start_decade]
    pivot = pivot.reindex(pivot["change"].abs().sort_values(ascending=False).head(10).index)
    fig, ax = plt.subplots(figsize=(9, 6))
    for topic, row in pivot.iterrows():
        ax.plot([0, 1], [row[start_decade], row[end_decade]], marker="o", linewidth=1.5)
        ax.text(-0.03, row[start_decade], topic, ha="right", va="center", fontsize=8)
        ax.text(1.03, row[end_decade], topic, ha="left", va="center", fontsize=8)
    ax.set_xticks([0, 1], [start_decade, end_decade])
    ax.set_xlim(-0.45, 1.45)
    ax.set_ylabel("Share of decade messages")
    ax.set_title("Largest Topic Share Changes")
    fig.savefig(path)
    plt.close(fig)


def plot_list_function_mix(path: Path, table: pd.DataFrame) -> None:
    if table.empty:
        return
    pivot = table.pivot_table(index="decade", columns="list_function", values="share_of_decade", aggfunc="sum", fill_value=0)
    top_functions = pivot.sum().sort_values(ascending=False).head(8).index
    fig, ax = plt.subplots(figsize=(10, 5))
    pivot[top_functions].plot(kind="bar", stacked=True, ax=ax)
    ax.set_title("List Function Mix By Decade")
    ax.set_ylabel("Share of decade messages")
    ax.set_xlabel("")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    fig.savefig(path)
    plt.close(fig)


def plot_thread_typology(path: Path, table: pd.DataFrame) -> None:
    if table.empty:
        return
    work = table.copy()
    work["message_count"] = pd.to_numeric(work["message_count"], errors="coerce").fillna(0)
    work["author_count"] = pd.to_numeric(work["author_count"], errors="coerce").fillna(0)
    work["reply_density"] = pd.to_numeric(work["reply_density"], errors="coerce").fillna(0)
    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(
        work["author_count"],
        work["message_count"],
        c=work["reply_density"],
        s=(work["reply_density"].clip(0, 2) * 60) + 16,
        alpha=0.55,
        cmap="viridis",
    )
    ax.set_xscale("symlog", linthresh=1)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_xlabel("Authors in thread")
    ax.set_ylabel("Messages in thread")
    ax.set_title("Thread Typology: Size, Participation, Reply Density")
    fig.colorbar(scatter, ax=ax, label="Resolved replies per message")
    fig.savefig(path)
    plt.close(fig)


def plot_case_components(path: Path, table: pd.DataFrame) -> None:
    if table.empty:
        return
    components = [
        "message_component",
        "author_component",
        "reply_component",
        "topic_component",
        "request_component",
        "resolution_component",
        "debate_component",
    ]
    top = table.head(15).copy()
    labels = top["subject"].astype(str).str.slice(0, 48)
    fig, ax = plt.subplots(figsize=(10, 7))
    left = pd.Series([0] * len(top))
    for component in components:
        values = pd.to_numeric(top[component], errors="coerce").fillna(0)
        ax.barh(labels, values, left=left, label=component.replace("_component", ""))
        left += values
    ax.invert_yaxis()
    ax.set_title("Case Candidate Score Components")
    ax.set_xlabel("Score contribution")
    ax.legend(loc="lower right", frameon=False)
    fig.savefig(path)
    plt.close(fig)


def plot_review_summary(path: Path, table: pd.DataFrame) -> None:
    if table.empty:
        return
    work = table.copy()
    work["review_items"] = pd.to_numeric(work["review_items"], errors="coerce").fillna(0).astype(int)
    work = work.sort_values("review_items")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(work["domain"], work["review_items"], color="#6c7f63")
    ax.set_title("Human Review Queue Summary")
    ax.set_xlabel("Rows needing attention")
    fig.savefig(path)
    plt.close(fig)


def plot_author_cohorts(path: Path, table: pd.DataFrame) -> None:
    if table.empty:
        return
    order = ["one-year", "short-term", "decade-scale", "multi-decade"]
    pivot = table.pivot_table(index="first_decade", columns="active_span_class", values="author_count", aggfunc="sum", fill_value=0)
    pivot = pivot.reindex(columns=[label for label in order if label in pivot.columns])
    fig, ax = plt.subplots(figsize=(9, 5))
    pivot.plot(kind="bar", stacked=True, ax=ax)
    ax.set_title("Author Participation Cohorts")
    ax.set_ylabel("Authors")
    ax.set_xlabel("First active decade")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    fig.savefig(path)
    plt.close(fig)


def run_insights(output_dir: Path, make_figures: bool = True) -> dict[str, pd.DataFrame]:
    processed_dir = output_dir / "data" / "processed"
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    messages = read_csv_if_exists(processed_dir / "messages_clean.csv")
    threads = read_csv_if_exists(processed_dir / "threads.csv")
    reply_edges = read_csv_if_exists(processed_dir / "reply_edges.csv")
    topic_decade = read_csv_if_exists(processed_dir / "topic_decade_counts.csv")
    list_functions = read_csv_if_exists(processed_dir / "atlas_list_functions.csv")
    cases = read_csv_if_exists(processed_dir / "case_study_candidates.csv")
    people = read_csv_if_exists(processed_dir / "atlas_people_summary.csv")

    outputs = {
        "reply_confidence_year_counts": build_reply_confidence_year_counts(reply_edges),
        "topic_decade_share": build_topic_decade_share(topic_decade),
        "list_function_decade_share": build_list_function_decade_share(list_functions),
        "thread_typology": build_thread_typology(threads, reply_edges, messages),
        "case_score_components": build_case_score_components(cases),
        "review_queue_summary": build_review_queue_summary(processed_dir, reply_edges),
        "author_participation_cohorts": build_author_participation_cohorts(people),
    }
    for name, frame in outputs.items():
        save_table(frame, processed_dir / f"{name}.csv")

    if make_figures:
        set_plot_style()
        plot_reply_confidence(figures_dir / "reply_confidence_over_time.png", outputs["reply_confidence_year_counts"])
        plot_topic_slope(figures_dir / "topic_share_slope_1990s_2020s.png", outputs["topic_decade_share"])
        plot_list_function_mix(figures_dir / "list_function_decade_mix.png", outputs["list_function_decade_share"])
        plot_thread_typology(figures_dir / "thread_typology_scatter.png", outputs["thread_typology"])
        plot_case_components(figures_dir / "case_score_components.png", outputs["case_score_components"])
        plot_review_summary(figures_dir / "review_queue_summary.png", outputs["review_queue_summary"])
        plot_author_cohorts(figures_dir / "author_participation_cohorts.png", outputs["author_participation_cohorts"])
    return outputs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument("--skip-figures", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    outputs = run_insights(args.output_dir, make_figures=not args.skip_figures)
    print({name: len(frame) for name, frame in outputs.items()})


if __name__ == "__main__":
    main()
