"""Resolve directed reply edges from INDOLOGY message headers."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd


MESSAGE_ID_RE = re.compile(r"<[^>]+>")


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def extract_message_ids(value: str) -> list[str]:
    if not value:
        return []
    return MESSAGE_ID_RE.findall(str(value))


def _author(row: pd.Series) -> str:
    return row.get("normalized_author") or row.get("author_display") or ""


def build_reply_edges(messages: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = messages.copy().fillna("")
    work["date_sort"] = pd.to_datetime(work["date"], errors="coerce", utc=True)
    work["thread_depth_int"] = pd.to_numeric(work["thread_depth"], errors="coerce").fillna(0).astype(int)
    work["archive_id_sort"] = pd.to_numeric(work["archive_id"], errors="coerce")
    message_lookup = {row["message_id"]: row for _, row in work.iterrows() if row.get("message_id")}

    sorted_work = work.sort_values(["thread_root_id", "date_sort", "archive_id_sort"])
    previous_in_thread: dict[str, list[pd.Series]] = {}
    rows = []
    for _, row in sorted_work.iterrows():
        source_author = _author(row)
        target = None
        confidence = "unresolved"
        evidence = ""

        in_reply_ids = extract_message_ids(row.get("in_reply_to", ""))
        for message_id in reversed(in_reply_ids):
            if message_id in message_lookup:
                target = message_lookup[message_id]
                confidence = "exact_in_reply_to"
                evidence = message_id
                break

        if target is None:
            ref_ids = extract_message_ids(row.get("references", ""))
            for message_id in reversed(ref_ids):
                if message_id in message_lookup:
                    target = message_lookup[message_id]
                    confidence = "references_chain"
                    evidence = message_id
                    break

        thread_id = row.get("thread_root_id", "")
        history = previous_in_thread.setdefault(thread_id, [])
        if target is None and int(row["thread_depth_int"]) > 0 and history:
            shallower = [item for item in history if int(item.get("thread_depth_int", 0)) < int(row["thread_depth_int"])]
            target = shallower[-1] if shallower else history[-1]
            confidence = "thread_inferred"
            evidence = "nearest previous message in thread with shallower or previous depth"

        if target is not None:
            rows.append(
                {
                    "source_author": source_author,
                    "target_author": _author(target),
                    "source_message_id": row.get("message_id", ""),
                    "target_message_id": target.get("message_id", ""),
                    "date": row.get("date", ""),
                    "thread_root_id": thread_id,
                    "subject": row.get("clean_subject", ""),
                    "confidence": confidence,
                    "evidence": evidence,
                    "source_url": row.get("archive_url", ""),
                    "target_url": target.get("archive_url", ""),
                }
            )
        elif row.get("in_reply_to", "") or row.get("references", "") or int(row["thread_depth_int"]) > 0:
            rows.append(
                {
                    "source_author": source_author,
                    "target_author": "",
                    "source_message_id": row.get("message_id", ""),
                    "target_message_id": "",
                    "date": row.get("date", ""),
                    "thread_root_id": thread_id,
                    "subject": row.get("clean_subject", ""),
                    "confidence": "unresolved",
                    "evidence": "reply-like message but no target could be resolved in harvested archive",
                    "source_url": row.get("archive_url", ""),
                    "target_url": "",
                }
            )
        history.append(row)

    reply_edges = pd.DataFrame(
        rows,
        columns=[
            "source_author",
            "target_author",
            "source_message_id",
            "target_message_id",
            "date",
            "thread_root_id",
            "subject",
            "confidence",
            "evidence",
            "source_url",
            "target_url",
        ],
    )
    resolved = reply_edges[(reply_edges["target_author"] != "") & (reply_edges["source_author"] != "")]
    aggregate = (
        resolved.groupby(["source_author", "target_author", "confidence"], dropna=False)
        .size()
        .reset_index(name="weight")
        .sort_values("weight", ascending=False)
    )
    return reply_edges, aggregate


def run_reply_network(output_dir: Path) -> dict[str, pd.DataFrame]:
    processed_dir = output_dir / "data" / "processed"
    messages_path = processed_dir / "messages_clean.csv"
    if not messages_path.exists():
        raise FileNotFoundError(f"missing {messages_path}; run cleaning first")
    messages = pd.read_csv(messages_path, dtype=str, low_memory=False).fillna("")
    reply_edges, aggregate = build_reply_edges(messages)
    reply_edges.to_csv(processed_dir / "reply_edges.csv", index=False, encoding="utf-8")
    aggregate.to_csv(processed_dir / "reply_network_edges.csv", index=False, encoding="utf-8")
    return {"reply_edges": reply_edges, "reply_network_edges": aggregate}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    run_reply_network(args.output_dir)


if __name__ == "__main__":
    main()

