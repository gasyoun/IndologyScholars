"""
LLM-кодирование 860 заголовков из theme_review_queue.csv через DeepSeek API.

Считывает ключ из .env (DEEPSEEK_API_KEY). Сохраняет результаты построчно
и поддерживает возобновление: если analytics_output/theme_codes_llm.csv уже
содержит presentation_id — пропускаем.

Финальный продукт:
  analytics_output/theme_codes_llm.csv         — LLM-разметка
  analytics_output/theme_codes_final.csv       — baseline ∪ LLM (LLM приоритет)
  analytics_output/theme_codes_uncertain.csv   — confidence<0.6 → ручная сверка
"""

import os
import sys
import csv
import json
import time
import re
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY не задан в .env", file=sys.stderr)
    sys.exit(1)

QUEUE_PATH = "analytics_output/theme_review_queue.csv"
BASELINE_PATH = "analytics_output/theme_codes_baseline.csv"
OUT_LLM = "analytics_output/theme_codes_llm.csv"
OUT_FINAL = "analytics_output/theme_codes_final.csv"
OUT_UNCERTAIN = "analytics_output/theme_codes_uncertain.csv"

BATCH_SIZE = 20
MAX_RETRIES = 2
REQUEST_TIMEOUT = 90

SYSTEM_PROMPT = """Ты — эксперт по русской индологии и востоковедению. Тебе даны
заголовки докладов на двух конференциях (Зографские и Рериховские чтения, 2004–2026).
Для каждого заголовка нужно проставить четыре кодa по жёстким спискам.

L1 — дисциплина (один лучший вариант):
  linguistics       — грамматика, языкознание, этимология, диалекты, переводоведение
  philosophy        — даршаны, эпистемология, мадхьямака, йогачара, веданта, санкхья
  literature        — кавья, эпос, проза, поэтика, фольклорные сюжеты, литература хинди/бенгальская/санскритская
  history           — политическая, культурная, экономическая история; источниковедение; биография учёных-индологов
  religion          — буддизм, индуизм, ритуал, паломничество, иконография, тантра, бхакти, мифология
  tibetology        — тибетская традиция, Камалашила, Махаяна-вопросы, буддизм в Гималаях
  ethnography       — антропология, племенные группы, межкультурная коммуникация
  art_archaeology   — архитектура, иконография, музейные памятники, изображения
  pedagogy_applied  — методика преподавания, школьная практика, прикладные темы
  other             — если ни одна категория не подходит

L2 — период:
  vedic         — ведийский период (~1500–600 до н.э.)
  classical     — классический санскрит, эпос, Панини, ранняя философия (~600 до н.э. – 600 н.э.)
  medieval      — бхакти, тантра, Шанкара, Рамануджа, кашмирский шиваизм (~600–1500)
  colonial      — XVII–XIX вв., колониальный период, ранние востоковеды
  modern        — XX в., советская/российская индология, литература хинди-урду
  contemporary  — современная Индия, диаспора, после 1990 г.
  unspecified   — не определён

L3 — материал:
  text       — анализ текста, перевод, рукописи, эпиграфика
  fieldwork  — полевые материалы, этнография, антропологическое наблюдение
  archive    — архивы, биография, история науки, музейные коллекции
  artefact   — материальный артефакт: храм, скульптура, монета
  image      — изобразительный материал: миниатюра, рельеф, фотография
  unspecified

L4 — характер:
  fundamental     — академическое исследование первоисточника или теоретическая работа
  applied         — прикладной (методика преподавания, перевод-как-практика, рецензия книги)
  methodological  — методологический/обзорный/хроника

Также проставь confidence от 0.0 до 1.0 и одну фразу обоснования.

ОТВЕЧАЙ СТРОГО валидным JSON-массивом, без markdown, без объяснений вне JSON.
Формат: [{"id":"PRES_xxx","l1":"...","l2":"...","l3":"...","l4":"...","conf":0.85,"why":"..."}, ...].
Порядок ответов должен совпадать с порядком вопросов."""


def build_user_prompt(batch):
    lines = ["Закодируй следующие заголовки:"]
    for item in batch:
        lines.append(f'  id={item["presentation_id"]} year={item["year"]} series={item["series"]} title="{item["title"]}"')
    return "\n".join(lines)


def call_deepseek(messages):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "max_tokens": 4000,
    }
    resp = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return content, data.get("usage", {})


def parse_response(content):
    """Parse LLM JSON response. Accepts either {"results":[...]} or [...]."""
    obj = json.loads(content)
    if isinstance(obj, dict):
        for key in ("results", "items", "data", "codes"):
            if key in obj and isinstance(obj[key], list):
                return obj[key]
        # Single-object fallback (rare)
        if "id" in obj:
            return [obj]
        raise ValueError(f"Unexpected JSON shape: keys={list(obj.keys())}")
    if isinstance(obj, list):
        return obj
    raise ValueError(f"Unexpected JSON type: {type(obj)}")


def load_queue():
    with open(QUEUE_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_existing_results():
    if not os.path.exists(OUT_LLM):
        return {}
    with open(OUT_LLM, encoding="utf-8") as f:
        return {row["presentation_id"]: row for row in csv.DictReader(f)}


def append_results(rows):
    write_header = not os.path.exists(OUT_LLM) or os.path.getsize(OUT_LLM) == 0
    fields = ["presentation_id", "year", "series", "title", "l1", "l2", "l3", "l4", "conf", "why"]
    with open(OUT_LLM, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def main():
    queue = load_queue()
    done = load_existing_results()
    todo = [r for r in queue if r["presentation_id"] not in done]
    print(f"Очередь: {len(queue)} строк. Уже размечено: {len(done)}. К обработке: {len(todo)}.")

    total_in_tokens = 0
    total_out_tokens = 0
    n_failed_batches = 0

    for batch_idx in range(0, len(todo), BATCH_SIZE):
        batch = todo[batch_idx:batch_idx + BATCH_SIZE]
        batch_num = batch_idx // BATCH_SIZE + 1
        total_batches = (len(todo) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n[{batch_num}/{total_batches}] Батч из {len(batch)} заголовков...")

        user_msg = build_user_prompt(batch)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        results = None
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                content, usage = call_deepseek(messages)
                total_in_tokens += usage.get("prompt_tokens", 0)
                total_out_tokens += usage.get("completion_tokens", 0)
                results = parse_response(content)
                break
            except (requests.exceptions.RequestException, json.JSONDecodeError, ValueError) as e:
                print(f"  attempt {attempt} failed: {type(e).__name__}: {str(e)[:140]}", file=sys.stderr)
                if attempt > MAX_RETRIES:
                    break
                time.sleep(2 ** attempt)

        if results is None:
            n_failed_batches += 1
            print(f"  ! Батч пропущен после {MAX_RETRIES + 1} попыток", file=sys.stderr)
            continue

        # Map results back to batch by id
        by_id = {r.get("id"): r for r in results if isinstance(r, dict)}
        out_rows = []
        for item in batch:
            r = by_id.get(item["presentation_id"])
            if not r:
                continue
            out_rows.append({
                "presentation_id": item["presentation_id"],
                "year": item["year"],
                "series": item["series"],
                "title": item["title"],
                "l1": r.get("l1", ""),
                "l2": r.get("l2", ""),
                "l3": r.get("l3", ""),
                "l4": r.get("l4", ""),
                "conf": r.get("conf", ""),
                "why": r.get("why", ""),
            })
        append_results(out_rows)
        print(f"  + записано {len(out_rows)} строк (cumulative in={total_in_tokens}, out={total_out_tokens} tokens)")

    print(f"\nГотово. Неудачных батчей: {n_failed_batches}.")
    print(f"Total tokens — input: {total_in_tokens}, output: {total_out_tokens}")
    # DeepSeek pricing (rough): $0.27/1M input + $1.10/1M output for deepseek-chat
    est_cost = total_in_tokens * 0.27e-6 + total_out_tokens * 1.10e-6
    print(f"Примерная стоимость: ${est_cost:.4f}")

    merge_and_summarize()


def merge_and_summarize():
    """Merge LLM results with baseline to produce theme_codes_final.csv."""
    if not os.path.exists(OUT_LLM):
        return
    llm = {}
    with open(OUT_LLM, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            llm[r["presentation_id"]] = r

    final_rows = []
    uncertain = []
    with open(BASELINE_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pid = r["presentation_id"]
            if pid in llm:
                lr = llm[pid]
                try:
                    conf = float(lr.get("conf") or 0)
                except ValueError:
                    conf = 0.0
                final_rows.append({
                    "presentation_id": pid,
                    "year": r["year"],
                    "series": r["series"],
                    "title": r["title"],
                    "l1": lr["l1"],
                    "l2": lr["l2"],
                    "l3": lr["l3"],
                    "l4": lr["l4"],
                    "source": "llm",
                    "confidence": conf,
                    "why": lr.get("why", ""),
                })
                if conf < 0.6:
                    uncertain.append(final_rows[-1])
            else:
                final_rows.append({
                    "presentation_id": pid,
                    "year": r["year"],
                    "series": r["series"],
                    "title": r["title"],
                    "l1": r["l1"],
                    "l2": r["l2"],
                    "l3": r["l3"],
                    "l4": r["l4"],
                    "source": "baseline",
                    "confidence": float(r.get("l1_conf") or 0),
                    "why": "",
                })
                if final_rows[-1]["confidence"] < 0.6:
                    uncertain.append(final_rows[-1])

    fields = ["presentation_id", "year", "series", "title", "l1", "l2", "l3", "l4", "source", "confidence", "why"]
    with open(OUT_FINAL, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(final_rows)
    with open(OUT_UNCERTAIN, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(uncertain)
    print(f"Final: {len(final_rows)} rows → {OUT_FINAL}")
    print(f"Uncertain (conf<0.6): {len(uncertain)} → {OUT_UNCERTAIN}")

    # Summary by L1 per series
    from collections import Counter
    by_series = defaultdict(Counter)
    for r in final_rows:
        by_series[r["series"]][r["l1"]] += 1
    print("\nL1 распределение после LLM-сверки:")
    for series, ctr in sorted(by_series.items()):
        total = sum(ctr.values())
        print(f"\n  -- {series} (n={total}) --")
        for cat, n in ctr.most_common():
            print(f"    {cat or 'unspec':25s}: {n:4d} ({100*n/total:5.1f}%)")


if __name__ == "__main__":
    main()
