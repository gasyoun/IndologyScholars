"""Indologist-facing guided atlas summaries for the INDOLOGY archive."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd


FUNCTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "list administration",
        re.compile(r"\b(digest|unsubscribe|subscription|mailman|moderator|list\s+admin|test message)\b", re.I),
    ),
    (
        "obituary/memorial",
        re.compile(r"\b(obituary|memorial|in memoriam|passed away|has died|death of|gone$|tribute|remembering)\b", re.I),
    ),
    (
        "job/position",
        re.compile(r"\b(job|position|postdoc|post-doc|phd|studentship|fellowship|vacancy|professorship|lecturer)\b", re.I),
    ),
    (
        "announcement/event",
        re.compile(r"\b(call for papers|cfp|conference|workshop|symposium|seminar|lecture|webinar|course|summer school|program|programme|new publication)\b", re.I),
    ),
    (
        "bibliographic request",
        re.compile(r"\b(pdf|scan|offprint|article request|copy of|bibliograph|reference|looking for.*article|seeking.*pdf|does anyone have)\b", re.I),
    ),
    (
        "identification/help request",
        re.compile(r"\b(help|identify|identification|looking for|seeking|does anyone know|can anyone|query|question|where can i find|need information)\b", re.I),
    ),
    (
        "digital resource/tool",
        re.compile(r"\b(digital|database|online|website|web site|unicode|font|keyboard|software|ocr|xml|html|corpus|etext|e-text|github|download|searchable)\b", re.I),
    ),
    (
        "technical support",
        re.compile(r"\b(font|unicode|keyboard|encoding|transliteration|display|browser|software|technical|bug|error|install)\b", re.I),
    ),
    (
        "debate/controversy",
        re.compile(r"\b(debate|controversy|bias|sexism|politics|dispute|critique|response to|rebuttal|problem with)\b", re.I),
    ),
    (
        "philological discussion",
        re.compile(r"\b(meaning|translation|edition|commentary|reading|variant|manuscript|verse|passage|text|grammar|etymology|sandhi|sutra|sūtra)\b", re.I),
    ),
)

CASE_SIGNALS = {
    "request_like": re.compile(r"\b(request|looking for|seeking|does anyone|can anyone|help|identify|query|question|pdf|scan|article)\b", re.I),
    "resolution_like": re.compile(r"\b(thanks|thank you|solved|found|got it|correction|fixed|answer)\b", re.I),
    "debate_like": re.compile(r"\b(debate|controversy|bias|sexism|politics|problem|critique|response)\b", re.I),
}


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, low_memory=False).fillna("") if path.exists() else pd.DataFrame()


def classify_list_function(subject: str, topic: str = "") -> str:
    text = f"{subject or ''} {topic or ''}".strip()
    for label, pattern in FUNCTION_RULES:
        if pattern.search(text):
            return label
    return "general discussion"


def add_list_function(messages: pd.DataFrame) -> pd.DataFrame:
    work = messages.copy()
    work["list_function"] = [
        classify_list_function(subject, topic)
        for subject, topic in zip(work["clean_subject"].fillna(""), work["primary_topic"].fillna(""))
    ]
    return work


def build_timeline(messages: pd.DataFrame) -> pd.DataFrame:
    work = messages.copy()
    work["year_int"] = pd.to_numeric(work["year"], errors="coerce")
    work["thread_length_int"] = pd.to_numeric(work["thread_length"], errors="coerce").fillna(1)
    rows = []
    for year, group in work.groupby("year_int", dropna=True):
        topic = group["primary_topic"].mode().iloc[0] if not group.empty else ""
        function = group["list_function"].mode().iloc[0] if not group.empty else ""
        rows.append(
            {
                "year": int(year),
                "decade": f"{int(year // 10 * 10)}s",
                "message_count": len(group),
                "thread_count": group["thread_root_id"].nunique(),
                "author_count": group["normalized_author"].replace("", pd.NA).dropna().nunique(),
                "avg_thread_length": round(float(group["thread_length_int"].mean()), 2),
                "dominant_topic": topic,
                "dominant_list_function": function,
            }
        )
    return pd.DataFrame(rows).sort_values("year")


def build_topic_profiles(messages: pd.DataFrame) -> pd.DataFrame:
    work = messages.copy()
    work["year_int"] = pd.to_numeric(work["year"], errors="coerce")
    rows = []
    for topic, group in work.groupby("primary_topic"):
        years = group["year_int"].dropna().astype(int)
        functions = group["list_function"].value_counts()
        thread_lengths = pd.to_numeric(group["thread_length"], errors="coerce").fillna(1)
        rows.append(
            {
                "topic": topic,
                "message_count": len(group),
                "thread_count": group["thread_root_id"].nunique(),
                "author_count": group["normalized_author"].replace("", pd.NA).dropna().nunique(),
                "first_year": int(years.min()) if not years.empty else "",
                "last_year": int(years.max()) if not years.empty else "",
                "median_thread_length": round(float(thread_lengths.median()), 2),
                "top_list_function": functions.index[0] if len(functions) else "",
                "top_list_function_count": int(functions.iloc[0]) if len(functions) else 0,
            }
        )
    return pd.DataFrame(rows).sort_values("message_count", ascending=False)


def build_list_functions(messages: pd.DataFrame) -> pd.DataFrame:
    counts = (
        messages.groupby(["decade", "list_function"], dropna=False)
        .size()
        .reset_index(name="message_count")
        .sort_values(["decade", "message_count"], ascending=[True, False])
    )
    totals = counts.groupby("decade")["message_count"].transform("sum")
    counts["share_of_decade"] = (counts["message_count"] / totals).round(4)
    return counts


def build_people_summary(messages: pd.DataFrame, reply_edges: pd.DataFrame) -> pd.DataFrame:
    work = messages[messages["normalized_author"] != ""].copy()
    reply_work = reply_edges.copy()
    outgoing = reply_work[reply_work["target_author"] != ""].groupby("source_author").size()
    incoming = reply_work[reply_work["target_author"] != ""].groupby("target_author").size()
    rows = []
    for author, group in work.groupby("normalized_author"):
        years = pd.to_numeric(group["year"], errors="coerce").dropna().astype(int)
        top_topic = group["primary_topic"].mode().iloc[0] if not group.empty else ""
        top_function = group["list_function"].mode().iloc[0] if not group.empty else ""
        rows.append(
            {
                "normalized_author": author,
                "author_id": group["author_id"].iloc[0],
                "message_count": len(group),
                "thread_count": group["thread_root_id"].nunique(),
                "first_year": int(years.min()) if not years.empty else "",
                "last_year": int(years.max()) if not years.empty else "",
                "top_topic": top_topic,
                "top_list_function": top_function,
                "resolved_replies_sent": int(outgoing.get(author, 0)),
                "resolved_replies_received": int(incoming.get(author, 0)),
                "author_status": group["author_status"].mode().iloc[0],
            }
        )
    return pd.DataFrame(rows).sort_values(["message_count", "thread_count"], ascending=False)


def build_reply_summary(reply_edges: pd.DataFrame) -> pd.DataFrame:
    if reply_edges.empty:
        return pd.DataFrame(columns=["confidence", "reply_rows", "resolved_rows", "share"])
    counts = reply_edges.groupby("confidence").size().reset_index(name="reply_rows")
    counts["resolved_rows"] = counts["confidence"].map(
        lambda label: int(len(reply_edges[(reply_edges["confidence"] == label) & (reply_edges["target_author"] != "")]))
    )
    counts["share"] = (counts["reply_rows"] / len(reply_edges)).round(4)
    return counts.sort_values("reply_rows", ascending=False)


def build_case_study_candidates(messages: pd.DataFrame, threads: pd.DataFrame, reply_edges: pd.DataFrame) -> pd.DataFrame:
    work = messages.copy()
    work["thread_length_int"] = pd.to_numeric(work["thread_length"], errors="coerce").fillna(1).astype(int)
    reply_counts = reply_edges[reply_edges["target_author"] != ""].groupby("thread_root_id").size()
    rows = []
    for thread_id, group in work.groupby("thread_root_id"):
        subject = group.sort_values(["thread_depth", "date"])["clean_subject"].iloc[0]
        subject_blob = " ".join(group["clean_subject"].astype(str).unique())
        author_count = group["normalized_author"].replace("", pd.NA).dropna().nunique()
        message_count = len(group)
        topic_count = group["primary_topic"].nunique()
        reply_count = int(reply_counts.get(thread_id, 0))
        request_like = bool(CASE_SIGNALS["request_like"].search(subject_blob))
        resolution_like = bool(CASE_SIGNALS["resolution_like"].search(subject_blob))
        debate_like = bool(CASE_SIGNALS["debate_like"].search(subject_blob))
        score = (
            message_count
            + author_count * 3
            + reply_count * 2
            + topic_count * 4
            + (12 if request_like else 0)
            + (10 if resolution_like else 0)
            + (10 if debate_like else 0)
        )
        first = group.sort_values("date").iloc[0]
        rows.append(
            {
                "thread_root_id": thread_id,
                "score": int(score),
                "subject": subject,
                "primary_topic": group["primary_topic"].mode().iloc[0],
                "dominant_list_function": group["list_function"].mode().iloc[0],
                "message_count": message_count,
                "author_count": author_count,
                "reply_count": reply_count,
                "topic_count": topic_count,
                "request_like": request_like,
                "resolution_like": resolution_like,
                "debate_like": debate_like,
                "first_date": first["date"],
                "first_url": first["archive_url"],
                "authors": " | ".join(sorted(a for a in group["normalized_author"].unique() if a)[:12]),
                "evidence": "; ".join(
                    label
                    for label, flag in [
                        ("long thread", message_count >= 10),
                        ("multi-author", author_count >= 4),
                        ("resolved replies", reply_count >= 3),
                        ("request/help language", request_like),
                        ("thanks/correction language", resolution_like),
                        ("debate language", debate_like),
                    ]
                    if flag
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("score", ascending=False).head(250)


def run_atlas(output_dir: Path) -> dict[str, pd.DataFrame]:
    processed_dir = output_dir / "data" / "processed"
    messages = read_csv(processed_dir / "messages_clean.csv")
    threads = read_csv(processed_dir / "threads.csv")
    reply_edges = read_csv(processed_dir / "reply_edges.csv")
    if messages.empty:
        raise FileNotFoundError("messages_clean.csv is required before generating atlas layers")

    messages_with_functions = add_list_function(messages)
    messages_with_functions.to_csv(processed_dir / "messages_clean.csv", index=False, encoding="utf-8")

    outputs = {
        "atlas_timeline": build_timeline(messages_with_functions),
        "atlas_topic_profiles": build_topic_profiles(messages_with_functions),
        "atlas_list_functions": build_list_functions(messages_with_functions),
        "atlas_people_summary": build_people_summary(messages_with_functions, reply_edges),
        "atlas_reply_summary": build_reply_summary(reply_edges),
        "case_study_candidates": build_case_study_candidates(messages_with_functions, threads, reply_edges),
    }
    for name, frame in outputs.items():
        frame.to_csv(processed_dir / f"{name}.csv", index=False, encoding="utf-8")
    return outputs


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    run_atlas(args.output_dir)


if __name__ == "__main__":
    main()

