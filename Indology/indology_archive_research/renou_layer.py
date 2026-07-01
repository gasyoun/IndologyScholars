"""Sparse Renou state/register crosswalk for INDOLOGY archive subjects."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

from indology_archive_research.topics import clean_subject


RENOU_SOURCE_URL = "https://github.com/gasyoun/SanskritLexicography/blob/master/RussianTranslation/RENOU.md"


STATE_ROWS: list[dict[str, str]] = [
    {
        "axis": "state",
        "code": "I",
        "label": "Vedic",
        "covers": "Saṃhitā, Brāhmaṇa, Upaniṣad, Sūtra, Vedāṅga",
        "pattern": r"\b(vedic|veda|rigveda|rgveda|r\u0325gveda|atharvaveda|yajurveda|samaveda|samhita|saṃhitā|brahmana|brāhmaṇa|aranyaka|āraṇyaka|upanishad|upaniṣad|upanisad|vedanga|vedāṅga|srauta|shrauta|śrauta|grhya|gṛhya)\b",
        "confidence": "subject_pattern",
    },
    {
        "axis": "state",
        "code": "II",
        "label": "Pāṇinian",
        "covers": "the classical norm and grammarians' Sanskrit",
        "pattern": r"\b(panini|pāṇini|patanjali|patañjali|ashtadhyayi|aṣṭādhyāyī|vyakarana|vyākaraṇa|grammar|grammatical|grammarian|mahābhāṣya|mahabhasya|kāśikā|kasika|nirukta)\b",
        "confidence": "subject_pattern",
    },
    {
        "axis": "state",
        "code": "III",
        "label": "Epic & prolongements",
        "covers": "Mbh, Rām, Harivaṃśa, Gītā, Purāṇa, Smṛti, Tantra",
        "pattern": r"\b(mahabharata|mahābhārata|mbh|ramayana|rāmāyaṇa|harivamsa|harivaṃśa|gita|gītā|bhagavadgita|bhagavadgītā|purana|purāṇa|smriti|smṛti|tantra|dharmasastra|dharmaśāstra)\b",
        "confidence": "subject_pattern",
    },
    {
        "axis": "state",
        "code": "IV",
        "label": "Classical",
        "covers": "kāvya, drama, kathā, classical śāstra, kośa, later grammar",
        "pattern": r"\b(kavya|kāvya|drama|natya|nāṭya|katha|kathā|shastra|śāstra|sastra|sāstra|kosha|kośa|classical sanskrit|kalidasa|kālidāsa|bhasa|bhāsa|dandin|daṇḍin|campu|campū|poetry|poetic)\b",
        "confidence": "subject_pattern",
    },
    {
        "axis": "state",
        "code": "V",
        "label": "Buddhist / Jaina",
        "covers": "Buddhist Hybrid and Jaina Sanskrit",
        "pattern": r"\b(buddh|bauddha|bhs|buddhist hybrid|jain|jaina|jainism|pali|pāli|prakrit|prākrit|abhidharma|bodhisattva|mahāyāna|mahayana|theravada|vajrayana|vajrayāna|tripitaka|tipitaka)\b",
        "confidence": "subject_pattern",
    },
]


REGISTER_ROWS: list[tuple[str, str, str]] = [
    ("rgveda", "Ṛgveda", r"\b(rigveda|rgveda|r\u0325gveda|ṛgveda|rv\b)"),
    ("atharva", "Atharvaveda", r"\b(atharva|atharvaveda|av\b)"),
    ("yajus", "Yajurveda", r"\b(yajurveda|yajus|yajur)\b"),
    ("brahmana", "Brāhmaṇa", r"\b(brahmana|brāhmaṇa|satapatha|śatapatha|shatapatha|aitareya|taittiriya|taittirīya)\b"),
    ("upanisad", "Upaniṣad", r"\b(upanishad|upaniṣad|upanisad|brhadaranyaka|bṛhadāraṇyaka|chandogya|chāndogya|katha up|kaṭha up)\b"),
    ("sutra", "Sūtra", r"\b(sutra|sūtra|kalpasutra|kalpasūtra|grhya|gṛhya|srauta|śrauta|shrauta)\b"),
    ("vyakarana", "Vyākaraṇa", r"\b(vyakarana|vyākaraṇa|panini|pāṇini|ashtadhyayi|aṣṭādhyāyī|patanjali|patañjali|grammar|grammatical)\b"),
    ("epic", "Epic", r"\b(mahabharata|mahābhārata|mbh|ramayana|rāmāyaṇa|harivamsa|harivaṃśa|epic)\b"),
    ("purana", "Purāṇa", r"\b(purana|purāṇa|bhagavata|bhāgavata|devibhagavata|devībhāgavata|vishnu purana|viṣṇu purāṇa)\b"),
    ("tantra", "Tantra", r"\b(tantra|tantric|tantrism|tantrik|tantrika|kularnava|kulārṇava)\b"),
    ("smrti", "Smṛti", r"\b(smriti|smṛti|manu|yajnavalkya|yājñavalkya|dharmasastra|dharmaśāstra)\b"),
    ("karika", "Kārikā", r"\b(karika|kārikā|karikas|kārikās)\b"),
    ("bhasya", "Bhāṣya", r"\b(bhasya|bhāṣya|commentary|commentarial|commentator|sāyaṇa|sayana|śaṅkara|shankara|tikā|ṭīkā|tika|vrtti|vṛtti)\b"),
    ("katha", "Kathā", r"\b(katha|kathā|story|stories|narrative|tale|tales)\b"),
    ("natya", "Nāṭya", r"\b(natya|nāṭya|drama|dramatic|theatre|theater|play|plays|natyasastra|nāṭyaśāstra)\b"),
    ("kavya", "Kāvya", r"\b(kavya|kāvya|poetry|poetic|poem|verse|kalidasa|kālidāsa|campu|campū)\b"),
    ("bauddha", "Bauddha", r"\b(buddh|bauddha|bhs|buddhist hybrid|abhidharma|bodhisattva|mahāyāna|mahayana|vajrayana|vajrayāna|theravada)\b"),
    ("jaina", "Jaina", r"\b(jain|jaina|jainism|jaina sanskrit|kalpasutra|kalpasūtra)\b"),
    ("epig", "Epigraphic", r"\b(epigraph|epigraphy|inscription|inscriptions|copper[- ]plate|donative|prasasti|praśasti)\b"),
    ("hors_inde", "Outside India", r"\b(khotan|khotanese|sogdian|tocharian|central asian sanskrit|outside india|hors inde)\b"),
]


DEFAULT_RULE_ROWS: list[dict[str, str]] = [
    {**row, "rule_id": f"state_{row['code']}", "source_url": RENOU_SOURCE_URL, "notes": "Renou I-V state axis adapted for subject-line matching."}
    for row in STATE_ROWS
] + [
    {
        "rule_id": f"register_{code}",
        "axis": "register",
        "code": code,
        "label": label,
        "covers": label,
        "pattern": pattern,
        "confidence": "subject_pattern",
        "source_url": RENOU_SOURCE_URL,
        "notes": "Renou register axis adapted for subject-line matching.",
    }
    for code, label, pattern in REGISTER_ROWS
]


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, low_memory=False).fillna("")


def ensure_rules(output_dir: Path) -> Path:
    path = output_dir / "data" / "curation" / "renou_subject_rules.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame(DEFAULT_RULE_ROWS).to_csv(path, index=False, encoding="utf-8")
    return path


def compile_rules(rules: pd.DataFrame) -> list[dict[str, object]]:
    compiled: list[dict[str, object]] = []
    for _, row in rules.iterrows():
        pattern = str(row.get("pattern", "")).strip()
        if not pattern:
            continue
        compiled.append({**row.to_dict(), "_compiled": re.compile(pattern, re.IGNORECASE)})
    return compiled


def match_subject(subject: str, rules: list[dict[str, object]]) -> list[dict[str, str]]:
    cleaned = clean_subject(subject)
    matches: list[dict[str, str]] = []
    for rule in rules:
        regex = rule["_compiled"]
        assert isinstance(regex, re.Pattern)
        match = regex.search(cleaned)
        if match:
            row = {k: str(v) for k, v in rule.items() if not k.startswith("_")}
            row["matched_term"] = match.group(0)
            matches.append(row)
    return matches


def collapse(values: pd.Series) -> str:
    unique = sorted({str(value) for value in values if str(value).strip()})
    return "; ".join(unique)


def strongest_confidence(values: list[str]) -> str:
    if not values:
        return "unmatched"
    order = ["manual", "source_exact", "subject_pattern"]
    for label in order:
        if label in values:
            return label
    return sorted(values)[0]


def export_slug(axis: str, code: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", f"{axis}_{code}".lower()).strip("_")


def write_axis_exports(processed_dir: Path, outputs: dict[str, pd.DataFrame]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    messages = outputs["renou_messages"]
    matches = outputs["renou_message_matches"]
    threads = outputs["renou_thread_matches"]
    summaries = {
        "state": outputs["renou_state_summary"],
        "register": outputs["renou_register_summary"],
    }
    for stale in processed_dir.glob("renou_*_*_messages.csv"):
        stale.unlink()
    for stale in processed_dir.glob("renou_*_*_threads.csv"):
        stale.unlink()
    for stale in processed_dir.glob("renou_*_*_summary.csv"):
        stale.unlink()

    index_rows: list[dict[str, object]] = []
    if not matches.empty:
        for (axis, code, label), group in matches.groupby(["renou_axis", "renou_code", "renou_label"], dropna=False):
            axis = str(axis)
            code = str(code)
            label = str(label)
            slug = export_slug(axis, code)
            message_ids = set(group["archive_id"].astype(str))
            thread_ids = set(group["thread_root_id"].astype(str))
            message_frame = messages[messages["archive_id"].astype(str).isin(message_ids)].copy()
            thread_frame = threads[threads["thread_root_id"].astype(str).isin(thread_ids)].copy()
            summary_frame = summaries.get(axis, pd.DataFrame())
            summary_frame = summary_frame[summary_frame["renou_code"].astype(str).eq(code)].copy() if not summary_frame.empty else pd.DataFrame()
            for kind, frame in [("messages", message_frame), ("threads", thread_frame), ("summary", summary_frame)]:
                filename = f"renou_{slug}_{kind}.csv"
                path = processed_dir / filename
                frame.to_csv(path, index=False, encoding="utf-8")
                paths[path.stem] = path
                index_rows.append(
                    {
                        "renou_axis": axis,
                        "renou_code": code,
                        "renou_label": label,
                        "export_kind": kind,
                        "relative_path": f"data/processed/{filename}",
                        "rows": len(frame),
                    }
                )

    index = pd.DataFrame(index_rows)
    index_path = processed_dir / "renou_export_index.csv"
    index.to_csv(index_path, index=False, encoding="utf-8")
    paths["renou_export_index"] = index_path
    return paths


def build_renou_tables(output_dir: Path) -> dict[str, pd.DataFrame]:
    processed_dir = output_dir / "data" / "processed"
    messages = read_csv(processed_dir / "messages_clean.csv")
    rules_path = ensure_rules(output_dir)
    rules = read_csv(rules_path)
    compiled = compile_rules(rules)

    match_rows: list[dict[str, str]] = []
    index_rows: list[dict[str, str]] = []
    for _, message in messages.iterrows():
        subject = message.get("clean_subject", "") or message.get("subject", "")
        matches = match_subject(subject, compiled)
        state_matches = [row for row in matches if row.get("axis") == "state"]
        register_matches = [row for row in matches if row.get("axis") == "register"]
        states = collapse(pd.Series([row.get("code", "") for row in state_matches]))
        registers = collapse(pd.Series([row.get("code", "") for row in register_matches]))
        confidences = [row.get("confidence", "") for row in matches]
        evidence = "; ".join(
            f"{row.get('axis')}:{row.get('code')}={row.get('matched_term')}"
            for row in matches
        )
        base = {
            "archive_id": message.get("archive_id", ""),
            "message_id": message.get("message_id", ""),
            "thread_root_id": message.get("thread_root_id", ""),
            "date": message.get("date", ""),
            "year": message.get("year", ""),
            "month": message.get("month", ""),
            "archive_url": message.get("archive_url", ""),
            "normalized_author": message.get("normalized_author", ""),
            "clean_subject": subject,
            "primary_topic": message.get("primary_topic", ""),
            "list_function": message.get("list_function", ""),
        }
        index_rows.append(
            {
                **base,
                "renou_states": states,
                "renou_registers": registers,
                "renou_match_count": str(len(matches)),
                "renou_confidence": strongest_confidence(confidences),
                "renou_evidence": evidence,
                "renou_source_url": RENOU_SOURCE_URL if matches else "",
            }
        )
        for row in matches:
            match_rows.append(
                {
                    **base,
                    "rule_id": row.get("rule_id", ""),
                    "renou_axis": row.get("axis", ""),
                    "renou_code": row.get("code", ""),
                    "renou_label": row.get("label", ""),
                    "renou_covers": row.get("covers", ""),
                    "matched_term": row.get("matched_term", ""),
                    "confidence": row.get("confidence", ""),
                    "evidence": f"subject matched `{row.get('matched_term', '')}` using `{row.get('rule_id', '')}`",
                    "source_url": row.get("source_url", RENOU_SOURCE_URL),
                }
            )

    renou_messages = pd.DataFrame(index_rows)
    message_matches = pd.DataFrame(match_rows)
    if message_matches.empty:
        thread_matches = pd.DataFrame()
        axis_summary = pd.DataFrame()
    else:
        thread_base = messages[
            [
                "thread_root_id",
                "clean_subject",
                "year",
                "primary_topic",
                "list_function",
                "thread_length",
                "archive_url",
            ]
        ].drop_duplicates("thread_root_id")
        thread_rollup = (
            message_matches.groupby("thread_root_id")
            .agg(
                renou_states=("renou_code", lambda s: collapse(s[message_matches.loc[s.index, "renou_axis"].eq("state")])),
                renou_registers=("renou_code", lambda s: collapse(s[message_matches.loc[s.index, "renou_axis"].eq("register")])),
                renou_labels=("renou_label", collapse),
                matched_message_count=("archive_id", "nunique"),
                match_count=("archive_id", "count"),
                confidence=("confidence", lambda s: strongest_confidence(list(s))),
                evidence=("evidence", lambda s: "; ".join(list(s.head(6)))),
            )
            .reset_index()
        )
        thread_matches = thread_base.merge(thread_rollup, on="thread_root_id", how="inner").rename(
            columns={
                "clean_subject": "thread_subject",
                "archive_url": "first_url",
            }
        )
        axis_summary = (
            message_matches.groupby(["renou_axis", "renou_code", "renou_label", "year", "primary_topic", "list_function"])
            .agg(
                message_count=("archive_id", "nunique"),
                thread_count=("thread_root_id", "nunique"),
                author_count=("normalized_author", "nunique"),
            )
            .reset_index()
            .sort_values(["renou_axis", "renou_code", "year"])
        )

    coverage_rows = []
    total = len(renou_messages)
    matched = int(pd.to_numeric(renou_messages.get("renou_match_count", pd.Series(dtype=str)), errors="coerce").fillna(0).gt(0).sum()) if total else 0
    coverage_rows.append(
        {
            "scope": "messages",
            "total_rows": total,
            "matched_rows": matched,
            "matched_percent": round(matched * 100 / total, 2) if total else 0,
            "source_url": RENOU_SOURCE_URL,
        }
    )
    if not thread_matches.empty:
        total_threads = messages["thread_root_id"].nunique()
        matched_threads = thread_matches["thread_root_id"].nunique()
        coverage_rows.append(
            {
                "scope": "threads",
                "total_rows": total_threads,
                "matched_rows": matched_threads,
                "matched_percent": round(matched_threads * 100 / total_threads, 2) if total_threads else 0,
                "source_url": RENOU_SOURCE_URL,
            }
        )
    coverage = pd.DataFrame(coverage_rows)
    state_summary = axis_summary[axis_summary["renou_axis"].eq("state")].copy() if not axis_summary.empty else pd.DataFrame()
    register_summary = axis_summary[axis_summary["renou_axis"].eq("register")].copy() if not axis_summary.empty else pd.DataFrame()
    return {
        "renou_messages": renou_messages,
        "renou_message_matches": message_matches,
        "renou_thread_matches": thread_matches,
        "renou_state_summary": state_summary,
        "renou_register_summary": register_summary,
        "renou_coverage": coverage,
    }


def run_renou_layer(output_dir: Path) -> dict[str, Path]:
    processed_dir = output_dir / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    outputs = build_renou_tables(output_dir)
    paths: dict[str, Path] = {}
    for name, frame in outputs.items():
        path = processed_dir / f"{name}.csv"
        frame.to_csv(path, index=False, encoding="utf-8")
        paths[name] = path
    paths.update(write_axis_exports(processed_dir, outputs))
    return paths


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    outputs = run_renou_layer(args.output_dir)
    print({key: str(value) for key, value in outputs.items()})


if __name__ == "__main__":
    main()
