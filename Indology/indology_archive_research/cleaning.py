"""Author normalization and archive-quality audits."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import pandas as pd


EMAILISH_RE = re.compile(r"(^|\s)([\w.+-]+)\s+(?:at|\[at\]|\(at\))\s+([\w.-]+)", re.I)
REAL_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
SPACE_RE = re.compile(r"\s+")
ARTIFACT_RE = re.compile(
    r"^(|unknown|none|anonymous|yahoo!?mail.*|mail delivery subsystem|mailer-daemon|postmaster|root|administrator)$",
    re.I,
)


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def clean_author_string(value: str) -> str:
    text = str(value or "").replace("\u00a0", " ")
    text = text.strip().strip('"').strip("'")
    text = SPACE_RE.sub(" ", text)
    return text


def is_email_like(value: str) -> bool:
    return bool(EMAILISH_RE.search(value) or REAL_EMAIL_RE.search(value))


def canonical_for_exact_group(values: pd.Series) -> str:
    counts = values.value_counts()
    non_empty = [v for v in counts.index if v]
    if not non_empty:
        return ""
    human_like = [v for v in non_empty if not is_email_like(v) and not ARTIFACT_RE.match(v)]
    return human_like[0] if human_like else non_empty[0]


def author_id(normalized_author: str, status: str) -> str:
    if not normalized_author or status == "excluded":
        return ""
    digest = hashlib.sha1(normalized_author.casefold().encode("utf-8")).hexdigest()[:10]
    return f"indology-author-{digest}"


def build_author_aliases(messages: pd.DataFrame) -> pd.DataFrame:
    rows = []
    work = messages.copy()
    work["raw_author"] = work["author_display"].fillna("").map(clean_author_string)
    work["author_key"] = work["raw_author"].map(lambda x: SPACE_RE.sub(" ", x.casefold()).strip())
    canonical_by_key = work.groupby("author_key")["raw_author"].apply(canonical_for_exact_group).to_dict()

    grouped = work.groupby("raw_author", dropna=False)
    for raw_author, group in grouped:
        raw_author = clean_author_string(raw_author)
        key = SPACE_RE.sub(" ", raw_author.casefold()).strip()
        first_seen = pd.to_datetime(group["date"], errors="coerce", utc=True).min()
        last_seen = pd.to_datetime(group["date"], errors="coerce", utc=True).max()
        if ARTIFACT_RE.match(raw_author):
            normalized = ""
            status = "excluded"
            confidence = 1.0
            evidence = "mail-client/list artifact or empty author string"
        elif is_email_like(raw_author):
            normalized = raw_author
            status = "needs_review"
            confidence = 0.4
            evidence = "email-like public archive author string; not merged to a real-name identity"
        elif len(raw_author) <= 3 or len(raw_author.split()) == 1:
            normalized = raw_author
            status = "needs_review"
            confidence = 0.5
            evidence = "short or single-token display name; retained without merge"
        else:
            normalized = canonical_by_key.get(key, raw_author)
            status = "confirmed" if normalized == raw_author else "inferred"
            confidence = 1.0 if status == "confirmed" else 0.85
            evidence = "exact normalized display-name group" if status == "confirmed" else "case/spacing-only display-name variant"

        rows.append(
            {
                "raw_author": raw_author,
                "normalized_author": normalized,
                "author_id": author_id(normalized, status),
                "status": status,
                "confidence": confidence,
                "evidence": evidence,
                "first_seen": first_seen.isoformat() if pd.notna(first_seen) else "",
                "last_seen": last_seen.isoformat() if pd.notna(last_seen) else "",
                "message_count": len(group),
                "unique_subject_count": group["clean_subject"].nunique(),
            }
        )
    aliases = pd.DataFrame(rows).sort_values(["status", "message_count", "raw_author"], ascending=[True, False, True])
    return aliases


def apply_author_aliases(messages: pd.DataFrame, aliases: pd.DataFrame) -> pd.DataFrame:
    alias_map = aliases.set_index("raw_author").to_dict(orient="index")
    rows = []
    for _, row in messages.iterrows():
        raw_author = clean_author_string(row.get("author_display", ""))
        alias = alias_map.get(raw_author, {})
        rows.append(
            {
                "normalized_author": alias.get("normalized_author", raw_author),
                "author_id": alias.get("author_id", ""),
                "author_status": alias.get("status", "needs_review"),
                "author_confidence": alias.get("confidence", 0.0),
                "author_evidence": alias.get("evidence", "no alias row found"),
            }
        )
    additions = pd.DataFrame(rows)
    return pd.concat([messages.reset_index(drop=True), additions], axis=1)


def build_count_mismatch_audit(processed_dir: Path) -> pd.DataFrame:
    months_path = processed_dir / "months.csv"
    skipped_path = processed_dir / "skipped_mbox_rows.csv"
    if not months_path.exists():
        return pd.DataFrame()
    months = pd.read_csv(months_path)
    skipped = pd.read_csv(skipped_path, dtype=str).fillna("") if skipped_path.exists() else pd.DataFrame()
    mismatches = months[months["message_count_index"] != months["message_count_mbox"]].copy()
    rows = []
    for _, row in mismatches.iterrows():
        slug = row["slug"]
        skipped_for_slug = skipped[skipped["slug"] == slug] if not skipped.empty else pd.DataFrame()
        rows.append(
            {
                "slug": slug,
                "archive_count": int(row["message_count_index"]),
                "mbox_count": int(row["message_count_mbox"]),
                "difference": int(row["message_count_mbox"]) - int(row["message_count_index"]),
                "skipped_mbox_rows": len(skipped_for_slug),
                "classification": "known_minor_archive_or_mbox_count_quirk",
                "downstream_status": "handled_by_subject_alignment",
                "notes": "Extra mbox rows were recorded in skipped_mbox_rows.csv; archive-index rows remain the canonical message set.",
            }
        )
    return pd.DataFrame(rows)


def run_cleaning(output_dir: Path) -> dict[str, pd.DataFrame]:
    processed_dir = output_dir / "data" / "processed"
    messages_path = processed_dir / "messages.csv"
    if not messages_path.exists():
        raise FileNotFoundError(f"missing {messages_path}; run analysis first")
    messages = pd.read_csv(messages_path, dtype=str, low_memory=False).fillna("")
    aliases = build_author_aliases(messages)
    messages_clean = apply_author_aliases(messages, aliases)
    needs_review = aliases[aliases["status"] == "needs_review"].copy()
    excluded = aliases[aliases["status"] == "excluded"].copy()
    mismatch_audit = build_count_mismatch_audit(processed_dir)

    outputs = {
        "author_aliases": aliases,
        "authors_needing_review": needs_review,
        "excluded_author_artifacts": excluded,
        "messages_clean": messages_clean,
        "count_mismatch_audit": mismatch_audit,
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
    run_cleaning(args.output_dir)


if __name__ == "__main__":
    main()

