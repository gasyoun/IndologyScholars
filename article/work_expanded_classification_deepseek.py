"""Reclassify the expanded presentation corpus with DeepSeek.

This is the publication-facing classification pass. It keeps the thematic
scheme used by the article, separates Gumilyov argument scale from geographic
or disciplinary subject matter, and supplies controlled meso-level indexes for
the site. A failed or incomplete API result is never converted into L2.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from classification_overrides import CLASSIFICATION_OVERRIDES, MESO_LABELS  # noqa: E402
from title_normalization import canonical_title  # noqa: E402


DB = ROOT / "conferences.db"
ANALYTICS = ROOT / "analytics_output"
OUT = ROOT / "article" / "hypothesis_output"
WORK_CSV = ANALYTICS / "expanded_classification_deepseek_work.csv"
AUDIT_CSV = ANALYTICS / "expanded_gumilyov_elevated_audit.csv"
FINAL_CSV = ANALYTICS / "expanded_classification_deepseek.csv"
THEME_DETAILED_CSV = ANALYTICS / "theme_codes_final.csv"
THEME_PUBLIC_CSV = ANALYTICS / "theme_codes_final_v2.csv"
GUMILYOV_CSV = ANALYTICS / "gumilyov_scale.csv"
MESO_CSV = ANALYTICS / "meso_codes_deepseek.csv"
SUMMARY_JSON = OUT / "expanded_classification_summary.json"
SUMMARY_MD = OUT / "expanded_classification_summary.md"

PROMPT_VERSION = "expanded-corpus-v1-2026-05-25"
AUDIT_VERSION = "scale-audit-v2-2026-05-25"
PROMOTED_MESO_PROPOSALS = {"sikh_studies"}
SCALE_EDITORIAL_OVERRIDES = {
    "PRES_b88ce66786": {
        "level": 2,
        "reason": "Схема рациональности обобщает индийскую философскую традицию, но не заявляет межцивилизационное или глобальное сравнение.",
    },
    "PRES_131430ee4f": {
        "level": 2,
        "reason": "Южноазиатская схема рациональности используется для обобщения одной философской традиции; это L2, а не глобальная рамка.",
    },
}
BATCH_SIZE = 20
MAX_RETRIES = 3
REQUEST_TIMEOUT = 120

DETAILED_L1 = {
    "linguistics",
    "philosophy",
    "literature",
    "history",
    "religion",
    "tibetology",
    "ethnography",
    "art_archaeology",
    "pedagogy_applied",
    "other",
}
PERIODS = {"vedic", "classical", "medieval", "colonial", "modern", "contemporary", "unspecified"}
MATERIALS = {"text", "fieldwork", "archive", "artefact", "image", "unspecified"}
CHARACTERS = {"fundamental", "applied", "methodological"}

PUBLIC_L1 = {
    "linguistics": "linguistics_and_philology",
    "philosophy": "religion_and_philosophy",
    "literature": "literature_and_poetry",
    "history": "history_and_culture",
    "religion": "religion_and_philosophy",
    "tibetology": "history_and_culture",
    "ethnography": "history_and_culture",
    "art_archaeology": "art_and_material_culture",
    "pedagogy_applied": "history_and_culture",
    "other": "unspecified",
}

SYSTEM_PROMPT = """Ты выполняешь воспроизводимую разметку заголовков докладов по российской индологии.
Исходными данными являются только название, год и серия конференции. Для каждого id верни JSON-объект.

1. theme_l1: один дисциплинарный код:
linguistics, philosophy, literature, history, religion, tibetology, ethnography,
art_archaeology, pedagogy_applied, other.

2. period_l2: один код периода:
vedic, classical, medieval, colonial, modern, contemporary, unspecified.

3. material_l3: один код материала:
text, fieldwork, archive, artefact, image, unspecified.

4. character_l4: один код:
fundamental, applied, methodological.

5. argument_level: масштаб заявленного аргумента, целое 1, 2 или 3:
L1 / 1 = частный исследовательский кейс: один текст, автор, образ, термин, обряд,
артефакт, коллекция, экспедиция, языковое явление, перевод, локальное сравнение
или конкретный корпус. ЭТО УРОВЕНЬ ПО УМОЛЧАНИЮ.
L2 / 2 = в самом заголовке заявлено обобщение уровня целой традиции, школы,
исторической линии, регионального процесса или крупного класса явлений.
L3 / 3 = явно заявлена цивилизационная, межрегиональная, глобальная или
общеметодологическая синтетическая рамка.

КРИТИЧЕСКИ ВАЖНО: упоминание Индии, Тибета, Бенгалии, Гималаев, эпохи,
языка, традиции, слова "сравнительный" или двух объектов само по себе НЕ
повышает уровень с L1. Масштаб темы и масштаб аргумента не одно и то же.

6. meso_codes: от 0 до 3 устойчивых контуров из переданного списка. Код выбирай
только если он является центральным предметом заголовка, а не случайным словом.
7. proposed_meso: максимум один короткий snake_case-код, только если заголовок
очевидно входит в повторяемый контур, которого нет в списке; иначе "".
8. confidence: число 0.0-1.0; rationale: краткая фраза по-русски с основанием
уровня аргументации.

Ответ строго в форме {"results":[...]}, без markdown. Для каждого входного id
нужен ровно один результат, с полями id, theme_l1, period_l2, material_l3,
character_l4, argument_level, meso_codes, proposed_meso, confidence, rationale."""

AUDIT_PROMPT = """Ты выполняешь строгий второй аудит только докладов, которые
предварительно получили повышенный масштаб аргумента L2 или L3. Задача аудита
не в тематической классификации, а в предотвращении ложного повышения уровня.

L1 = конкретный текст, автор, термин, обряд, объект, экспедиция, перевод,
коллекция, языковое явление, один локальный сюжет или сопоставление ограниченных
объектов. Названия страны, региона, языка, эпохи или традиции сами по себе
НЕ выводят доклад из L1.
К L1 относятся также: одна формула в традиции; один концепт у двух названных
мыслителей; одно произведение в контексте истории жанра; один текст и его
рецепция; одна надпись или ограниченная группа надписей.
L2 = заголовок явно обещает обобщение о целой традиции, школе, региональном
процессе, исторической линии либо большом классе явлений.
L3 = заголовок явно заявляет цивилизационную, глобальную, межрегиональную или
общеметодологическую рамку.
Обзор одной традиции, одного региона или одного исторического процесса остается
L2, даже если он охватывает длительное время: например, "буддизм и война:
исторический обзор", "буддийский ренессанс в Южной Азии" или "культурные
традиции средневековой Индии" не являются L3 без внешней сравнительной рамки.

При сомнении выбирай L1. L3 сохраняй только при очень явной широкой рамке.
Верни строго {"results":[{"id":"...","argument_level":1,"confidence":0.9,
"rationale":"..."}]} без markdown. Нельзя возвращать поля, не указанные в схеме."""


def read_dotenv() -> tuple[str, str, str]:
    load_dotenv(dotenv_path=ROOT / ".env")
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    if not key:
        raise SystemExit("DEEPSEEK_API_KEY is not configured in .env")
    return key, base, model


def load_presentations() -> list[dict[str, object]]:
    con = sqlite3.connect(DB)
    rows = con.execute(
        """
        select pr.presentation_id, e.year, es.event_series_id, es.series_name_en, pr.title
        from presentation pr
        join session s using(session_id)
        join event_day_venue edv using(event_day_venue_id)
        join event_day ed using(event_day_id)
        join event e using(event_id)
        join event_series es using(event_series_id)
        where pr.title is not null and trim(pr.title) != ''
        order by e.year, es.event_series_id, pr.presentation_id
        """
    ).fetchall()
    con.close()
    return [
        {
            "presentation_id": pid,
            "year": int(year),
            "series_id": int(series_id),
            "series": series,
            "raw_title": raw_title,
            "title": canonical_title(pid, raw_title),
        }
        for pid, year, series_id, series, raw_title in rows
    ]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def user_prompt(batch: list[dict[str, object]]) -> str:
    vocabulary = "\n".join(f"- {code}: {label}" for code, label in sorted(MESO_LABELS.items()))
    titles = "\n".join(
        f'- id={row["presentation_id"]}; year={row["year"]}; series={row["series"]}; title="{row["title"]}"'
        for row in batch
    )
    return f"Допустимые meso_codes:\n{vocabulary}\n\nРазметь заголовки:\n{titles}"


def call_deepseek(
    api_key: str, base_url: str, model: str, batch: list[dict[str, object]]
) -> tuple[list[dict[str, object]], dict[str, int]]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt(batch)},
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "max_tokens": 6000,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = requests.post(
        f"{base_url}/chat/completions", headers=headers, json=payload, timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()
    body = response.json()
    parsed = json.loads(body["choices"][0]["message"]["content"])
    results = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(results, list):
        raise ValueError("DeepSeek response does not contain a results list")
    return results, body.get("usage", {})


def call_scale_audit(
    api_key: str, base_url: str, model: str, batch: list[dict[str, object]]
) -> tuple[list[dict[str, object]], dict[str, int]]:
    titles = "\n".join(
        f'- id={row["presentation_id"]}; preliminary=L{row["gumilyov_level"]}; title="{row["title"]}"; preliminary_reason="{row["rationale"]}"'
        for row in batch
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": AUDIT_PROMPT},
            {"role": "user", "content": "Проверь повышенные уровни:\n" + titles},
        ],
        "temperature": 0.0,
        "max_tokens": 4000,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = requests.post(
        f"{base_url}/chat/completions", headers=headers, json=payload, timeout=REQUEST_TIMEOUT
    )
    if not response.ok:
        raise requests.HTTPError(
            f"{response.status_code} {response.text[:400]}", response=response
        )
    body = response.json()
    parsed = json.loads(body["choices"][0]["message"]["content"])
    results = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(results, list):
        raise ValueError("DeepSeek audit response does not contain a results list")
    return results, body.get("usage", {})


def normalize_result(source: dict[str, object], presentation: dict[str, object]) -> dict[str, object]:
    theme = str(source.get("theme_l1", "")).strip()
    period = str(source.get("period_l2", "")).strip()
    material = str(source.get("material_l3", "")).strip()
    character = str(source.get("character_l4", "")).strip()
    theme = {
        "art_and_material_culture": "art_archaeology",
        "history_of_indology": "history",
        "religious_studies": "religion",
    }.get(theme, theme)
    period = {
        "ancient": "classical",
        "multi_period": "unspecified",
    }.get(period, period)
    material = {
        "epigraphy": "text",
        "inscription": "text",
        "inscriptions": "text",
        "manuscript": "text",
        "manuscripts": "text",
        "texts_and_manuscripts": "text",
        "ritual_and_practice": "text",
    }.get(material, material)
    character = {
        "descriptive": "methodological",
    }.get(character, character)
    try:
        argument_level = int(source.get("argument_level", 0))
    except (TypeError, ValueError):
        argument_level = 0
    codes = source.get("meso_codes", [])
    if not isinstance(codes, list):
        codes = []
    codes = [str(code).strip() for code in codes if str(code).strip() in MESO_LABELS][:3]
    proposed = str(source.get("proposed_meso", "") or "").strip()
    try:
        confidence = float(source.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    valid = (
        theme in DETAILED_L1
        and period in PERIODS
        and material in MATERIALS
        and character in CHARACTERS
        and argument_level in (1, 2, 3)
        and 0 <= confidence <= 1
    )
    row = {
        **presentation,
        "theme_l1": theme,
        "period_l2": period,
        "material_l3": material,
        "character_l4": character,
        "gumilyov_level": argument_level if valid else "",
        "meso_codes": "|".join(dict.fromkeys(codes)),
        "proposed_meso": proposed,
        "confidence": round(confidence, 3),
        "rationale": str(source.get("rationale", "") or "").strip(),
        "source": "deepseek",
        "prompt_version": PROMPT_VERSION,
        "valid": "yes" if valid else "no",
    }
    manual = CLASSIFICATION_OVERRIDES.get(str(presentation["presentation_id"]), {})
    if manual:
        row["gumilyov_level"] = manual.get("gumilyov_level", row["gumilyov_level"])
        row["meso_codes"] = "|".join(manual.get("meso_codes", codes))
        row["rationale"] = manual.get("reason", row["rationale"])
        row["source"] = "expert_override_after_deepseek"
    return row


FIELDS = [
    "presentation_id",
    "year",
    "series_id",
    "series",
    "raw_title",
    "title",
    "theme_l1",
    "period_l2",
    "material_l3",
    "character_l4",
    "gumilyov_level",
    "meso_codes",
    "proposed_meso",
    "confidence",
    "rationale",
    "source",
    "prompt_version",
    "valid",
]


def classify(args: argparse.Namespace) -> list[dict[str, object]]:
    api_key, base_url, model = read_dotenv()
    presentations = load_presentations()
    if args.limit:
        presentations = presentations[: args.limit]
    existing = {}
    if not args.restart:
        existing = {
            row["presentation_id"]: row
            for row in read_csv(WORK_CSV)
            if row.get("prompt_version") == PROMPT_VERSION and row.get("valid") == "yes"
        }
    todo = [row for row in presentations if row["presentation_id"] not in existing]
    completed: dict[str, dict[str, object]] = dict(existing)
    print(f"Presentations: {len(presentations)}; already valid: {len(existing)}; to classify: {len(todo)}")
    tokens = Counter()
    failed: list[list[str]] = []
    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start : start + BATCH_SIZE]
        batch_number = start // BATCH_SIZE + 1
        total_batches = (len(todo) + BATCH_SIZE - 1) // BATCH_SIZE
        response_rows = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response_rows, usage = call_deepseek(api_key, base_url, model, batch)
                tokens.update(
                    {key: value for key, value in usage.items() if isinstance(value, int)}
                )
                break
            except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError) as exc:
                print(f"[{batch_number}/{total_batches}] attempt {attempt} failed: {exc}", file=sys.stderr)
                if attempt < MAX_RETRIES:
                    time.sleep(2**attempt)
        if response_rows is None:
            failed.append([str(row["presentation_id"]) for row in batch])
            continue
        by_id = {str(row.get("id")): row for row in response_rows if isinstance(row, dict)}
        accepted = 0
        for presentation in batch:
            raw = by_id.get(str(presentation["presentation_id"]))
            if not raw:
                continue
            normalized = normalize_result(raw, presentation)
            if normalized["valid"] == "yes":
                completed[str(presentation["presentation_id"])] = normalized
                accepted += 1
            else:
                print(
                    "Rejected schema for "
                    f'{presentation["presentation_id"]}: '
                    f'theme={normalized["theme_l1"]}; period={normalized["period_l2"]}; '
                    f'material={normalized["material_l3"]}; character={normalized["character_l4"]}; '
                    f'level={normalized["gumilyov_level"]}; confidence={normalized["confidence"]}',
                    file=sys.stderr,
                )
        write_csv(WORK_CSV, list(completed.values()), FIELDS)
        print(f"[{batch_number}/{total_batches}] accepted {accepted}/{len(batch)}; cumulative {len(completed)}")
    ordered = [completed[str(row["presentation_id"])] for row in presentations if str(row["presentation_id"]) in completed]
    print(f"Valid classifications: {len(ordered)}/{len(presentations)}; failed batches: {len(failed)}")
    if tokens:
        print(f"Token usage: {dict(tokens)}")
    if failed:
        print("Incomplete ids: " + ", ".join(pid for batch in failed for pid in batch), file=sys.stderr)
    return ordered


def audit_elevated(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    api_key, base_url, model = read_dotenv()
    audit_fields = [
        "presentation_id",
        "preliminary_level",
        "audited_level",
        "confidence",
        "rationale",
        "prompt_version",
    ]
    prior = {
        row["presentation_id"]: row
        for row in read_csv(AUDIT_CSV)
        if row.get("prompt_version") == AUDIT_VERSION
    }
    elevated = [
        row for row in rows
        if int(row["gumilyov_level"]) > 1 and row["source"] != "expert_override_after_deepseek"
    ]
    todo = [row for row in elevated if str(row["presentation_id"]) not in prior]
    print(f"Elevated-scale audit: {len(elevated)} preliminary L2/L3; to audit: {len(todo)}")
    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start : start + BATCH_SIZE]
        response_rows = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response_rows, _usage = call_scale_audit(api_key, base_url, model, batch)
                break
            except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError) as exc:
                print(f"Audit attempt {attempt} failed: {exc}", file=sys.stderr)
                if attempt < MAX_RETRIES:
                    time.sleep(2**attempt)
        if response_rows is None:
            continue
        by_id = {str(item.get("id")): item for item in response_rows if isinstance(item, dict)}
        for source in batch:
            item = by_id.get(str(source["presentation_id"]))
            if not item:
                continue
            try:
                audited_level = int(item.get("argument_level", 0))
                confidence = float(item.get("confidence", 0))
            except (TypeError, ValueError):
                continue
            if audited_level not in (1, 2, 3) or not 0 <= confidence <= 1:
                continue
            prior[str(source["presentation_id"])] = {
                "presentation_id": source["presentation_id"],
                "preliminary_level": source["gumilyov_level"],
                "audited_level": audited_level,
                "confidence": round(confidence, 3),
                "rationale": str(item.get("rationale", "") or "").strip(),
                "prompt_version": AUDIT_VERSION,
            }
        write_csv(AUDIT_CSV, list(prior.values()), audit_fields)
        print(f"Audited elevated rows: {len(prior)}/{len(elevated)}")
    if len(prior) < len(elevated):
        raise SystemExit(f"Not publishing: elevated-scale audit incomplete ({len(prior)}/{len(elevated)})")
    updated = []
    for row in rows:
        audit = prior.get(str(row["presentation_id"]))
        if not audit:
            updated.append(row)
            continue
        revised = dict(row)
        revised["gumilyov_level"] = audit["audited_level"]
        revised["rationale"] = audit["rationale"]
        revised["confidence"] = audit["confidence"]
        revised["source"] = "deepseek_strict_scale_audit"
        updated.append(revised)
    for row in updated:
        editorial = SCALE_EDITORIAL_OVERRIDES.get(str(row["presentation_id"]))
        if not editorial:
            continue
        row["gumilyov_level"] = editorial["level"]
        row["rationale"] = editorial["reason"]
        row["source"] = "editorial_scale_adjudication_after_deepseek"
    changes = sum(
        1 for row in elevated if str(prior[str(row["presentation_id"])]["audited_level"]) != str(row["gumilyov_level"])
    )
    print(f"Elevated-scale audit revised {changes} preliminary levels.")
    return updated


def publish(rows: list[dict[str, object]], expected_total: int) -> None:
    if len(rows) != expected_total:
        raise SystemExit(f"Not publishing: {len(rows)} valid rows for {expected_total} presentations")
    for row in rows:
        proposal = str(row.get("proposed_meso") or "")
        if proposal not in PROMOTED_MESO_PROPOSALS:
            continue
        codes = [code for code in str(row.get("meso_codes") or "").split("|") if code]
        if proposal not in codes:
            row["meso_codes"] = "|".join([*codes, proposal])
    write_csv(FINAL_CSV, rows, FIELDS)
    detailed = [
        {
            "presentation_id": row["presentation_id"],
            "year": row["year"],
            "series": row["series"],
            "title": row["title"],
            "l1": row["theme_l1"],
            "l2": row["period_l2"],
            "l3": row["material_l3"],
            "l4": row["character_l4"],
            "source": row["source"],
            "confidence": row["confidence"],
            "why": row["rationale"],
        }
        for row in rows
    ]
    write_csv(
        THEME_DETAILED_CSV,
        detailed,
        ["presentation_id", "year", "series", "title", "l1", "l2", "l3", "l4", "source", "confidence", "why"],
    )
    public = [{**row, "l1": PUBLIC_L1.get(str(row["l1"]), "unspecified")} for row in detailed]
    write_csv(
        THEME_PUBLIC_CSV,
        public,
        ["presentation_id", "year", "series", "title", "l1", "l2", "l3", "l4", "source", "confidence", "why"],
    )
    scale = [
        {
            "presentation_id": row["presentation_id"],
            "year": row["year"],
            "series_id": row["series_id"],
            "title": row["raw_title"],
            "gumilyov_level": row["gumilyov_level"],
            "confidence": row["confidence"],
            "source": row["source"],
            "why": row["rationale"],
        }
        for row in rows
    ]
    write_csv(
        GUMILYOV_CSV,
        scale,
        ["presentation_id", "year", "series_id", "title", "gumilyov_level", "confidence", "source", "why"],
    )
    meso = [
        {
            "presentation_id": row["presentation_id"],
            "year": row["year"],
            "series": row["series"],
            "title": row["title"],
            "meso_codes": row["meso_codes"],
            "proposed_meso": row["proposed_meso"],
            "source": row["source"],
            "confidence": row["confidence"],
        }
        for row in rows
    ]
    write_csv(
        MESO_CSV,
        meso,
        ["presentation_id", "year", "series", "title", "meso_codes", "proposed_meso", "source", "confidence"],
    )
    write_summary(rows)


def write_summary(rows: list[dict[str, object]]) -> None:
    scale = Counter(str(row["gumilyov_level"]) for row in rows)
    scale_by_series: dict[str, Counter[str]] = defaultdict(Counter)
    themes: dict[str, Counter[str]] = defaultdict(Counter)
    meso = Counter()
    proposals = Counter()
    for row in rows:
        series = str(row["series"])
        scale_by_series[series][str(row["gumilyov_level"])] += 1
        themes[series][str(row["theme_l1"])] += 1
        for code in str(row["meso_codes"]).split("|"):
            if code:
                meso[code] += 1
        if row["proposed_meso"]:
            proposals[str(row["proposed_meso"])] += 1
    summary = {
        "prompt_version": PROMPT_VERSION,
        "presentations": len(rows),
        "gumilyov_scale": dict(scale),
        "gumilyov_by_series": {key: dict(value) for key, value in scale_by_series.items()},
        "themes_by_series": {key: dict(value) for key, value in themes.items()},
        "meso_counts": dict(meso.most_common()),
        "proposed_meso_counts": dict(proposals.most_common()),
        "manual_overrides_applied": sum(1 for row in rows if row["source"] == "expert_override_after_deepseek"),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Expanded Classification Summary",
        "",
        f"DeepSeek prompt version: `{PROMPT_VERSION}`.",
        f"Presentations classified: {len(rows)}.",
        "",
        "## Gumilyov Argument Scale",
        "",
        "| Level | Presentations | Share |",
        "|---|---:|---:|",
    ]
    for level in ("1", "2", "3"):
        count = scale[level]
        lines.append(f"| L{level} | {count} | {count / len(rows) * 100:.1f}% |")
    lines += ["", "## Meso-Level Coverage", "", "| Meso-level | Presentations |", "|---|---:|"]
    for code, count in meso.most_common():
        lines.append(f"| {MESO_LABELS.get(code, code)} (`{code}`) | {count} |")
    lines += ["", "## Proposed Missing Meso-Levels", ""]
    if proposals:
        lines.extend(f"- `{code}`: {count}" for code, count in proposals.most_common())
    else:
        lines.append("- DeepSeek did not propose an additional recurring contour.")
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restart", action="store_true", help="Ignore the existing checkpoint for this prompt version.")
    parser.add_argument("--limit", type=int, default=0, help="Classify only the first N rows; never publish.")
    args = parser.parse_args()
    rows = classify(args)
    if args.limit:
        return
    expected_total = len(load_presentations())
    if len(rows) != expected_total:
        raise SystemExit(f"Not auditing or publishing: {len(rows)} valid rows for {expected_total} presentations")
    rows = audit_elevated(rows)
    publish(rows, expected_total)
    print(f"Published {len(rows)} classifications to analytics_output and article/hypothesis_output.")


if __name__ == "__main__":
    main()
