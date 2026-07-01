"""Generate a Renou state/register layer for the main conference dataset.

This layer adapts the Renou I-V state axis and register lattice already used in
the INDOLOGY archive appendix, but keeps the main-site outputs separate.  It is
metadata-first: matches come from presentation titles and tags, not full papers.
"""

from __future__ import annotations

import csv
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote


RENOU_SOURCE_URL = "https://github.com/gasyoun/SanskritLexicography/blob/master/RussianTranslation/RENOU.md"

RULE_ROWS: list[dict[str, str]] = [
    {
        "axis": "state",
        "code": "I",
        "label": "Vedic",
        "covers": "Saṃhitā, Brāhmaṇa, Upaniṣad, Sūtra, Vedāṅga",
        "pattern": r"\b(vedic|veda|vedā|rigveda|rgveda|ṛgveda|atharvaveda|yajurveda|samaveda|samhita|saṃhitā|brahmana|brāhmaṇa|aranyaka|āraṇyaka|upanishad|upaniṣad|upanisad|vedanga|vedāṅga|srauta|shrauta|śrauta|grhya|gṛhya|pravargya)\b|вед(ийск|ическ|а|ы|ы)|ригвед|атхарвавед|яджурвед|самавед|упанишад|брахман|араньяк|шраут|грихь|праварг",
        "confidence": "title_tag_pattern",
    },
    {
        "axis": "state",
        "code": "II",
        "label": "Pāṇinian",
        "covers": "the classical norm and grammarians' Sanskrit",
        "pattern": r"\b(panini|pāṇini|patanjali|patañjali|ashtadhyayi|aṣṭādhyāyī|vyakarana|vyākaraṇa|grammar|grammatical|grammarian|mahābhāṣya|mahabhasya|kāśikā|kasika|nirukta)\b|панини|пāṇini|патанджал|аш[тṭ]адхьяй|аштападх|вьякаран|vyākaraṇa|грамматик|нир?укт",
        "confidence": "title_tag_pattern",
    },
    {
        "axis": "state",
        "code": "III",
        "label": "Epic & prolongements",
        "covers": "Mbh, Rām, Harivaṃśa, Gītā, Purāṇa, Smṛti, Tantra",
        "pattern": r"\b(mahabharata|mahābhārata|mbh|ramayana|rāmāyaṇa|harivamsa|harivaṃśa|gita|gītā|bhagavadgita|bhagavadgītā|purana|purāṇa|smriti|smṛti|tantra|dharmasastra|dharmaśāstra)\b|махабхарат|рамаян|хариванш|гит[аеы]|бхагавадгит|пуран|смрит|тантр|дхармашастр|дхарма-шастр",
        "confidence": "title_tag_pattern",
    },
    {
        "axis": "state",
        "code": "IV",
        "label": "Classical",
        "covers": "kāvya, drama, kathā, classical śāstra, kośa, later grammar",
        "pattern": r"\b(kavya|kāvya|drama|natya|nāṭya|katha|kathā|shastra|śāstra|sastra|sāstra|kosha|kośa|classical sanskrit|kalidasa|kālidāsa|bhasa|bhāsa|dandin|daṇḍin|campu|campū|poetry|poetic)\b|кавь|kāvya|драм|натья|натъя|катх|шастр|классическ(ий|ого|ая)? санскрит|калидас|бхас|данди|поэз|стих",
        "confidence": "title_tag_pattern",
    },
    {
        "axis": "state",
        "code": "V",
        "label": "Buddhist / Jaina",
        "covers": "Buddhist Hybrid and Jaina Sanskrit",
        "pattern": r"\b(buddh|bauddha|bhs|buddhist hybrid|jain|jaina|jainism|pali|pāli|prakrit|prākrit|abhidharma|bodhisattva|mahāyāna|mahayana|theravada|vajrayana|vajrayāna|tripitaka|tipitaka)\b|будд|баудд|джайн|jaina|палий|пали\b|пракрит|абхидхарм|бодхисаттв|махаян|тхеравад|ваджраян|трипитак",
        "confidence": "title_tag_pattern",
    },
    ("register", "rgveda", "Ṛgveda", "Ṛgveda", r"\b(rigveda|rgveda|r\u0325gveda|ṛgveda|rv\b)\b|ригвед", "title_tag_pattern"),
    ("register", "atharva", "Atharvaveda", "Atharvaveda", r"\b(atharva|atharvaveda|av\b)\b|атхарвав", "title_tag_pattern"),
    ("register", "yajus", "Yajurveda", "Yajurveda", r"\b(yajurveda|yajus|yajur)\b|яджурвед", "title_tag_pattern"),
    ("register", "brahmana", "Brāhmaṇa", "Brāhmaṇa", r"\b(brahmana|brāhmaṇa|satapatha|śatapatha|shatapatha|aitareya|taittiriya|taittirīya)\b|брахман|ш?атапатх|айтре|тайттир", "title_tag_pattern"),
    ("register", "upanisad", "Upaniṣad", "Upaniṣad", r"\b(upanishad|upaniṣad|upanisad|brhadaranyaka|bṛhadāraṇyaka|chandogya|chāndogya|katha up|kaṭha up)\b|упанишад|брихадараньяк|чхандог", "title_tag_pattern"),
    ("register", "sutra", "Sūtra", "Sūtra", r"\b(sutra|sūtra|kalpasutra|kalpasūtra|grhya|gṛhya|srauta|śrauta|shrauta)\b|сутр|кальпасутр|грихь|шраут", "title_tag_pattern"),
    ("register", "vyakarana", "Vyākaraṇa", "Vyākaraṇa", r"\b(vyakarana|vyākaraṇa|panini|pāṇini|ashtadhyayi|aṣṭādhyāyī|patanjali|patañjali|grammar|grammatical)\b|вьякаран|панини|патанджал|грамматик", "title_tag_pattern"),
    ("register", "epic", "Epic", "Epic", r"\b(mahabharata|mahābhārata|mbh|ramayana|rāmāyaṇa|harivamsa|harivaṃśa|epic)\b|махабхарат|рамаян|эпос|эпическ|хариванш", "title_tag_pattern"),
    ("register", "purana", "Purāṇa", "Purāṇa", r"\b(purana|purāṇa|bhagavata|bhāgavata|devibhagavata|devībhāgavata|vishnu purana|viṣṇu purāṇa)\b|пуран|бхагават", "title_tag_pattern"),
    ("register", "tantra", "Tantra", "Tantra", r"\b(tantra|tantric|tantrism|tantrik|tantrika|kularnava|kulārṇava)\b|тантр", "title_tag_pattern"),
    ("register", "smrti", "Smṛti", "Smṛti", r"\b(smriti|smṛti|manu|yajnavalkya|yājñavalkya|dharmasastra|dharmaśāstra)\b|смрит|ману|яджнявалк|дхармашастр", "title_tag_pattern"),
    ("register", "karika", "Kārikā", "Kārikā", r"\b(karika|kārikā|karikas|kārikās)\b|карик", "title_tag_pattern"),
    ("register", "bhasya", "Bhāṣya", "Bhāṣya", r"\b(bhasya|bhāṣya|commentary|commentarial|commentator|sāyaṇa|sayana|śaṅkara|shankara|tikā|ṭīkā|tika|vrtti|vṛtti)\b|бхашь|коммент|шанкар|саян|тика|вритт", "title_tag_pattern"),
    ("register", "katha", "Kathā", "Kathā", r"\b(katha|kathā|story|stories|narrative|tale|tales)\b|катх|повеств|рассказ|сюжет", "title_tag_pattern"),
    ("register", "natya", "Nāṭya", "Nāṭya", r"\b(natya|nāṭya|drama|dramatic|theatre|theater|play|plays|natyasastra|nāṭyaśāstra)\b|натья|драм|театр|пьес", "title_tag_pattern"),
    ("register", "kavya", "Kāvya", "Kāvya", r"\b(kavya|kāvya|poetry|poetic|poem|verse|kalidasa|kālidāsa|campu|campū)\b|кавь|поэз|поэм|стих|калидас|чампу", "title_tag_pattern"),
    ("register", "bauddha", "Bauddha", "Bauddha", r"\b(buddh|bauddha|bhs|buddhist hybrid|abhidharma|bodhisattva|mahāyāna|mahayana|vajrayana|vajrayāna|theravada)\b|будд|баудд|абхидхарм|бодхисаттв|махаян|ваджраян", "title_tag_pattern"),
    ("register", "jaina", "Jaina", "Jaina", r"\b(jain|jaina|jainism|jaina sanskrit|kalpasutra|kalpasūtra)\b|джайн", "title_tag_pattern"),
    ("register", "epig", "Epigraphic", "Epigraphic", r"\b(epigraph|epigraphy|inscription|inscriptions|copper[- ]plate|donative|prasasti|praśasti)\b|эпиграф|надпис|прашаст", "title_tag_pattern"),
    ("register", "hors_inde", "Outside India", "Outside India", r"\b(khotan|khotanese|sogdian|tocharian|central asian sanskrit|outside india|hors inde)\b|хотан|согд|тохар|центральноазиатск", "title_tag_pattern"),
]


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def normalized_rules() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in RULE_ROWS:
        if isinstance(item, dict):
            row = item.copy()
        else:
            axis, code, label, covers, pattern, confidence = item
            row = {
                "axis": axis,
                "code": code,
                "label": label,
                "covers": covers,
                "pattern": pattern,
                "confidence": confidence,
            }
        row["rule_id"] = f"{row['axis']}_{row['code']}"
        row["source_url"] = RENOU_SOURCE_URL
        row["notes"] = "Main-site conference-title adaptation of Renou state/register matching."
        rows.append(row)
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def seed_rules(path: Path) -> list[dict[str, str]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        write_csv(
            path,
            normalized_rules(),
            ["axis", "code", "label", "covers", "pattern", "confidence", "rule_id", "source_url", "notes"],
        )
    return read_csv(path)


def collapse(values: list[object]) -> str:
    return "; ".join(sorted({str(value) for value in values if str(value).strip()}))


def presentation_rows(root: Path) -> list[dict[str, object]]:
    scholars = json.loads((root / "site_data_scholars.json").read_text(encoding="utf-8"))
    rows: dict[str, dict[str, object]] = {}
    for scholar in scholars:
        scholar_id = scholar.get("id", "")
        scholar_name = scholar.get("full_name_en") or scholar.get("full_name_ru") or scholar.get("name", "")
        scholar_url = f"s/{scholar.get('url_slug')}.html" if scholar.get("url_slug") else ""
        for talk in scholar.get("talks", []):
            pid = talk.get("presentation_id")
            if not pid:
                continue
            row = rows.setdefault(
                pid,
                {
                    "presentation_id": pid,
                    "title": talk.get("title", ""),
                    "year": talk.get("year", ""),
                    "series": talk.get("series", ""),
                    "theme_code": (talk.get("theme") or {}).get("code", ""),
                    "theme_en": (talk.get("theme") or {}).get("en", ""),
                    "tags": [],
                    "meso_codes": [],
                    "public_path": talk.get("public_path", ""),
                    "source_url": talk.get("source_url", ""),
                    "scholar_ids": [],
                    "scholars": [],
                    "scholar_urls": [],
                },
            )
            row["tags"].extend(talk.get("tags") or [])
            row["meso_codes"].extend(talk.get("meso_codes") or [])
            row["scholar_ids"].append(scholar_id)
            row["scholars"].append(scholar_name)
            if scholar_url:
                row["scholar_urls"].append(scholar_url)
    clean_rows: list[dict[str, object]] = []
    for row in rows.values():
        row["tags"] = collapse(row["tags"])
        row["meso_codes"] = collapse(row["meso_codes"])
        row["scholar_ids"] = collapse(row["scholar_ids"])
        row["scholars"] = collapse(row["scholars"])
        row["scholar_urls"] = collapse(row["scholar_urls"])
        clean_rows.append(row)
    return sorted(clean_rows, key=lambda r: (str(r.get("year", "")), str(r.get("presentation_id", ""))))


def match_text(row: dict[str, object]) -> str:
    return " ".join(str(row.get(key, "")) for key in ["title", "tags", "meso_codes", "theme_en", "theme_code"])


def compile_rules(rules: list[dict[str, str]]) -> list[dict[str, object]]:
    compiled = []
    for rule in rules:
        pattern = rule.get("pattern", "").strip()
        if pattern:
            compiled.append({**rule, "_regex": re.compile(pattern, flags=re.IGNORECASE)})
    return compiled


def apply_rules(rows: list[dict[str, object]], rules: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    presentation_out = []
    match_out = []
    for row in rows:
        text = match_text(row)
        matches = []
        for rule in rules:
            regex = rule["_regex"]
            assert isinstance(regex, re.Pattern)
            match = regex.search(text)
            if not match:
                continue
            matches.append(rule)
            match_out.append(
                {
                    "presentation_id": row["presentation_id"],
                    "year": row["year"],
                    "series": row["series"],
                    "title": row["title"],
                    "renou_axis": rule["axis"],
                    "renou_code": rule["code"],
                    "renou_label": rule["label"],
                    "matched_term": match.group(0),
                    "confidence": rule.get("confidence", "title_tag_pattern"),
                    "rule_id": rule["rule_id"],
                    "public_path": row["public_path"],
                    "source_url": row["source_url"],
                }
            )
        state_matches = [m for m in matches if m["axis"] == "state"]
        register_matches = [m for m in matches if m["axis"] == "register"]
        presentation_out.append(
            {
                **row,
                "renou_states": collapse([m["code"] for m in state_matches]),
                "renou_state_labels": collapse([m["label"] for m in state_matches]),
                "renou_registers": collapse([m["code"] for m in register_matches]),
                "renou_register_labels": collapse([m["label"] for m in register_matches]),
                "renou_match_count": len(matches),
                "renou_match_status": "matched" if matches else "unmatched",
                "renou_evidence": "; ".join(f"{m['axis']}:{m['code']}" for m in matches),
            }
        )
    return presentation_out, match_out


def summarize_matches(matches: list[dict[str, object]], presentations: list[dict[str, object]], axis: str) -> list[dict[str, object]]:
    ids_by_code: dict[str, set[str]] = defaultdict(set)
    label_by_code: dict[str, str] = {}
    years_by_code: dict[str, set[str]] = defaultdict(set)
    series_by_code: dict[str, set[str]] = defaultdict(set)
    for match in matches:
        if match["renou_axis"] != axis:
            continue
        code = str(match["renou_code"])
        ids_by_code[code].add(str(match["presentation_id"]))
        label_by_code[code] = str(match["renou_label"])
        years_by_code[code].add(str(match["year"]))
        series_by_code[code].add(str(match["series"]))
    rows = []
    for code, ids in ids_by_code.items():
        scholar_names = set()
        for row in presentations:
            if str(row["presentation_id"]) in ids:
                scholar_names.update(str(row.get("scholars", "")).split("; "))
        rows.append(
            {
                "renou_axis": axis,
                "renou_code": code,
                "renou_label": label_by_code.get(code, ""),
                "presentation_count": len(ids),
                "scholar_count": len({name for name in scholar_names if name}),
                "first_year": min(years_by_code[code]) if years_by_code[code] else "",
                "last_year": max(years_by_code[code]) if years_by_code[code] else "",
                "series": collapse(list(series_by_code[code])),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["presentation_count"]), row["renou_code"]))


def summarize_years(presentations: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in presentations:
        grouped[str(row.get("year", ""))].append(row)
    rows = []
    for year, group in sorted(grouped.items()):
        matched = [row for row in group if row["renou_match_status"] == "matched"]
        states = []
        registers = []
        for row in matched:
            states.extend(str(row.get("renou_states", "")).split("; "))
            registers.extend(str(row.get("renou_registers", "")).split("; "))
        rows.append(
            {
                "year": year,
                "presentation_count": len(group),
                "matched_presentations": len(matched),
                "matched_percent": round((len(matched) / len(group) * 100), 2) if group else 0,
                "renou_states": collapse(states),
                "renou_registers": collapse(registers),
            }
        )
    return rows


def summarize_scholars(presentations: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in presentations:
        for scholar_id in str(row.get("scholar_ids", "")).split("; "):
            if scholar_id:
                grouped[scholar_id].append(row)
    rows = []
    for scholar_id, group in grouped.items():
        first = group[0]
        states = []
        registers = []
        for row in group:
            states.extend(str(row.get("renou_states", "")).split("; "))
            registers.extend(str(row.get("renou_registers", "")).split("; "))
        rows.append(
            {
                "scholar_id": scholar_id,
                "scholar": str(first.get("scholars", "")).split("; ")[0],
                "talk_count": len(group),
                "renou_matched_talks": sum(1 for row in group if row["renou_match_status"] == "matched"),
                "renou_states": collapse(states),
                "renou_registers": collapse(registers),
                "scholar_url": str(first.get("scholar_urls", "")).split("; ")[0],
            }
        )
    return sorted(rows, key=lambda row: (-int(row["renou_matched_talks"]), row["scholar"]))


def write_filtered_exports(out_dir: Path, presentations: list[dict[str, object]], summaries: dict[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    index_rows = []
    for axis_name, summary_rows in [("state", summaries["state"]), ("register", summaries["register"])]:
        for summary in summary_rows:
            code = str(summary["renou_code"])
            slug = re.sub(r"[^a-z0-9]+", "_", f"renou_{axis_name}_{code}".lower()).strip("_")
            field = "renou_states" if axis_name == "state" else "renou_registers"
            rows = [row for row in presentations if code in str(row.get(field, "")).split("; ")]
            filename = f"{slug}_presentations.csv"
            write_csv(out_dir / filename, rows)
            index_rows.append(
                {
                    "renou_axis": axis_name,
                    "renou_code": code,
                    "renou_label": summary["renou_label"],
                    "export_kind": "presentations",
                    "relative_path": f"analytics_output/{filename}",
                    "rows": len(rows),
                }
            )
    return index_rows


def link(href: object, label: object) -> str:
    href_text = html.escape(str(href), quote=True)
    return f'<a href="{href_text}">{html.escape(str(label))}</a>'


def page_link(path: object, label: object) -> str:
    if not path:
        return ""
    return link(f"../{path}", label)


def csv_page_link(filename: str, label: object) -> str:
    return link(f"../analytics_output/{filename}", label)


def render_table(rows: list[dict[str, object]], columns: list[str], limit: int = 20) -> str:
    if not rows:
        return "<p>No rows.</p>"
    lines = ['<table class="data"><thead><tr>']
    lines.extend(f"<th>{html.escape(col)}</th>" for col in columns)
    lines.append("</tr></thead><tbody>")
    for row in rows[:limit]:
        lines.append("<tr>")
        for col in columns:
            lines.append(f"<td>{row.get(col, '')}</td>")
        lines.append("</tr>")
    lines.append("</tbody></table>")
    return "".join(lines)


def write_page(root: Path, outputs: dict[str, list[dict[str, object]]]) -> None:
    findings = root / "findings"
    findings.mkdir(exist_ok=True)
    coverage = outputs["coverage"][0]
    state_rows = []
    for row in outputs["state_summary"]:
        code = row["renou_code"]
        state_rows.append(
            {
                **row,
                "renou_code": csv_page_link(f"renou_state_{str(code).lower()}_presentations.csv", code),
                "renou_label": csv_page_link(f"renou_state_{str(code).lower()}_presentations.csv", row["renou_label"]),
                "presentation_count": csv_page_link(f"renou_state_{str(code).lower()}_presentations.csv", row["presentation_count"]),
                "scholar_count": csv_page_link("renou_scholar_summary.csv", row["scholar_count"]),
            }
        )
    register_rows = []
    for row in outputs["register_summary"]:
        code = row["renou_code"]
        register_rows.append(
            {
                **row,
                "renou_code": csv_page_link(f"renou_register_{code}_presentations.csv", code),
                "renou_label": csv_page_link(f"renou_register_{code}_presentations.csv", row["renou_label"]),
                "presentation_count": csv_page_link(f"renou_register_{code}_presentations.csv", row["presentation_count"]),
                "scholar_count": csv_page_link("renou_scholar_summary.csv", row["scholar_count"]),
            }
        )
    examples = []
    for row in [r for r in outputs["presentations"] if r["renou_match_status"] == "matched"][:25]:
        examples.append(
            {
                "year": row["year"],
                "series": row["series"],
                "title": page_link(row["public_path"], row["title"]),
                "renou_states": row["renou_states"],
                "renou_registers": row["renou_registers"],
                "scholars": row["scholars"],
            }
        )
    content = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Renou Layer · Indology Scholars</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; color: #202124; background: #fafafa; line-height: 1.5; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
    h1 {{ font-size: 34px; margin: 0 0 8px; }}
    h2 {{ margin-top: 36px; border-top: 1px solid #ddd; padding-top: 22px; }}
    a {{ color: #245f73; }}
    .note {{ color: #555; max-width: 900px; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 24px 0; }}
    .stat {{ background: white; border: 1px solid #ddd; border-radius: 8px; padding: 14px; }}
    .stat strong {{ display: block; font-size: 24px; }}
    table.data {{ width: 100%; border-collapse: collapse; margin: 12px 0 18px; background: white; font-size: 13px; }}
    table.data th, table.data td {{ border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }}
    table.data th {{ background: #eef3f1; text-align: left; }}
  </style>
</head>
<body>
<main>
  <p><a href="../index.html">Home</a> · <a href="index.html">Findings</a> · <a href="/IndologyScholars/IndologyArchive/dashboard/index.html">INDOLOGY archive atlas</a></p>
  <h1>Renou Layer For Conference Metadata</h1>
  <p class="note">This page applies the Renou I-V state axis and register lattice to main-site conference presentation titles and tags. It is a finding aid for public metadata: a match means a title/tag triggered an editable rule, not that the presentation has been fully interpreted or ranked.</p>
  <section class="stats">
    <div class="stat"><strong>{coverage['presentation_count']}</strong>presentations</div>
    <div class="stat"><strong>{coverage['matched_presentations']}</strong>matched presentations</div>
    <div class="stat"><strong>{coverage['matched_percent']}%</strong>matched by title/tag rules</div>
    <div class="stat"><strong>{coverage['matched_scholars']}</strong>scholars with matched talks</div>
  </section>
  <p><strong>CSV downloads: </strong>{csv_page_link('renou_presentations.csv', 'presentations')} · {csv_page_link('renou_presentation_matches.csv', 'matches')} · {csv_page_link('renou_state_summary.csv', 'state summary')} · {csv_page_link('renou_register_summary.csv', 'register summary')} · {csv_page_link('renou_year_summary.csv', 'year summary')} · {csv_page_link('renou_scholar_summary.csv', 'scholar summary')} · {csv_page_link('renou_export_index.csv', 'filtered export index')}</p>
  <p class="note">Rules are seeded in {link('../curation/renou_conference_rules.csv', 'curation/renou_conference_rules.csv')} and trace back to {link(RENOU_SOURCE_URL, 'RENOU.md')}. The INDOLOGY archive appendix remains separate, but both layers share the same cautious method.</p>

  <h2>State Axis</h2>
  {render_table(state_rows, ['renou_code', 'renou_label', 'presentation_count', 'scholar_count', 'first_year', 'last_year', 'series'])}

  <h2>Register Axis</h2>
  {render_table(register_rows, ['renou_code', 'renou_label', 'presentation_count', 'scholar_count', 'first_year', 'last_year', 'series'], limit=25)}

  <h2>Year Coverage</h2>
  {render_table(outputs['year_summary'], ['year', 'presentation_count', 'matched_presentations', 'matched_percent', 'renou_states', 'renou_registers'], limit=30)}

  <h2>Matched Presentation Examples</h2>
  {render_table(examples, ['year', 'series', 'title', 'renou_states', 'renou_registers', 'scholars'], limit=25)}
</main>
</body>
</html>
"""
    (findings / "renou.html").write_text(content, encoding="utf-8")


def run(root: Path) -> dict[str, int]:
    curation_dir = root / "curation"
    out_dir = root / "analytics_output"
    rules = compile_rules(seed_rules(curation_dir / "renou_conference_rules.csv"))
    presentations = presentation_rows(root)
    presentation_rows_out, matches = apply_rules(presentations, rules)
    state_summary = summarize_matches(matches, presentation_rows_out, "state")
    register_summary = summarize_matches(matches, presentation_rows_out, "register")
    year_summary = summarize_years(presentation_rows_out)
    scholar_summary = summarize_scholars(presentation_rows_out)
    matched_presentations = [row for row in presentation_rows_out if row["renou_match_status"] == "matched"]
    matched_scholars = {
        scholar_id
        for row in matched_presentations
        for scholar_id in str(row.get("scholar_ids", "")).split("; ")
        if scholar_id
    }
    coverage = [
        {
            "presentation_count": len(presentation_rows_out),
            "matched_presentations": len(matched_presentations),
            "matched_percent": round((len(matched_presentations) / len(presentation_rows_out) * 100), 2) if presentation_rows_out else 0,
            "matched_scholars": len(matched_scholars),
            "source_url": RENOU_SOURCE_URL,
            "method": "title_tag_pattern",
        }
    ]
    outputs = {
        "presentations": presentation_rows_out,
        "matches": matches,
        "state_summary": state_summary,
        "register_summary": register_summary,
        "year_summary": year_summary,
        "scholar_summary": scholar_summary,
        "coverage": coverage,
    }
    write_csv(out_dir / "renou_presentations.csv", presentation_rows_out)
    write_csv(out_dir / "renou_presentation_matches.csv", matches)
    write_csv(out_dir / "renou_state_summary.csv", state_summary)
    write_csv(out_dir / "renou_register_summary.csv", register_summary)
    write_csv(out_dir / "renou_year_summary.csv", year_summary)
    write_csv(out_dir / "renou_scholar_summary.csv", scholar_summary)
    write_csv(out_dir / "renou_coverage.csv", coverage)
    export_index = write_filtered_exports(out_dir, presentation_rows_out, {"state": state_summary, "register": register_summary})
    write_csv(out_dir / "renou_export_index.csv", export_index)
    write_page(root, outputs)
    return {
        "presentations": len(presentation_rows_out),
        "matches": len(matches),
        "matched_presentations": len(matched_presentations),
        "state_rows": len(state_summary),
        "register_rows": len(register_summary),
    }


def main() -> None:
    configure_stdio()
    result = run(Path("."))
    print(result)


if __name__ == "__main__":
    main()
