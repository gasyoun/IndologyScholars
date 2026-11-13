# -*- coding: utf-8 -*-
"""build_demand_index.py — ось «спрос» для libfl-scan-priority.

Читает vk-ors (book_posts.csv + thread-треды), строит:
  scratch/demand_index.csv     — все книжные упоминания с лайками, годом, жанром
  scratch/rarity_seeds.txt     — книжные позиции из «Очереди на оцифровку» (2021) и «Ищу книгу»

Запуск: python build_demand_index.py   (cwd = IndologyScholars/scratch)
Только чтение исходников, запись в scratch/. Одноразовый prep, фаза 3 скормит это скорингу.
"""
import csv
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK_POSTS = ROOT / "vk-ors" / "data" / "processed" / "book_posts.csv"
NAGARI = ROOT / "nagari" / "md"
OUT_INDEX = Path(__file__).resolve().parent / "demand_index.csv"
OUT_RARITY = Path(__file__).resolve().parent / "rarity_seeds.txt"

# Множественные genre-метки (regex, по тексту поста) — доли из дайджеста ОРС:
# словари 21.3%, учебники/грамматика 15.3%, эпос 8.8%, общая индология 33.8%,
# редкие/старые 26.1%, диссертации 0.8%.
GENRES = {
    "dictionary": r"словар|wörterb|dictionary|lexicon|лексикограф|вокабул",
    "grammar": r"грамматик|учебник|пособи|хрестомати|sanskrit grammar|начальный курс| reader|чтени[ея] санскрит",
    "epos": r"рамаян|махабхарат|бхагавадгит|бхагавата|панчатантр|эпос|мнадхвачар|jataka|джатак",
    "vedic": r"вед(а|ы|ий)|ригвед|яджурвед|самaved|атхарвавед|ведийск",
    "buddhist": r"будд|бхикш|сутр[аи] |vinaya|мапхам|лямри|стотра",
    "rare_old": r"репринт|дореволюц|18\d\d|19[0-5]\d|императорск|типограф",
    "dissertation": r"автореферат|диссертац",
    "general_indology": r"инди[ия]|индуист|индуизм|востоковед",
}

RARE_SEED_FILES = [
    NAGARI / "2021" / "Очередь_изданий_на_оцифровку_в_Иностранке__62940160.md",
]
I_WANT_BOOK_GLOB = "*Ищу_книгу*"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,:;«»\"'")


def main() -> int:
    if not BOOK_POSTS.exists():
        print(f"MISSING {BOOK_POSTS}", file=sys.stderr)
        return 1

    rows = []
    with BOOK_POSTS.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        # колонки: id, url, date, year, excerpt, likes, views
        for r in reader:
            text = (r.get("excerpt") or "").replace("\n", " ").strip()
            if not text:
                continue
            try:
                likes = int(r.get("likes") or 0)
            except ValueError:
                likes = 0
            try:
                year = int(r.get("year") or 0)
            except ValueError:
                year = 0
            genres = sorted(g for g, pat in GENRES.items() if re.search(pat, text, re.I))
            has_doc = True  # book_posts = doc-вложения (insights.py:270)
            rows.append(
                {
                    "post_id": r.get("id", ""),
                    "year": year,
                    "likes": likes,
                    "has_doc": int(has_doc),
                    "genres": "|".join(genres),
                    "snippet": norm(text)[:240],
                    "url": r.get("url", ""),
                }
            )

    # нормировка лайков по году (критерий 1 из дайджеста): likes / avg(book posts likes of year)
    by_year = {}
    for r in rows:
        by_year.setdefault(r["year"], []).append(r["likes"])
    avg_year = {y: (sum(v) / len(v) if v else 1) for y, v in by_year.items()}
    for r in rows:
        base = avg_year.get(r["year"]) or 1.0
        r["year_ratio"] = round(r["likes"] / base, 2) if base else 0.0

    with OUT_INDEX.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["post_id", "year", "likes", "year_ratio", "has_doc", "genres", "snippet", "url"],
        )
        w.writeheader()
        w.writerows(rows)

    # rarity seeds: «Очередь на оцифровку» + треды «Ищу книгу»
    seeds: list[str] = []
    for p in RARE_SEED_FILES:
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and len(line) > 8:
                    seeds.append(f"queue2021\t{norm(line)[:200]}")
    for p in sorted(NAGARI.glob(I_WANT_BOOK_GLOB)):
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and len(line) > 12:
                seeds.append(f"iwant\t{norm(line)[:200]}")
    OUT_RARITY.write_text("\n".join(seeds) + ("\n" if seeds else ""), encoding="utf-8")

    print(f"index rows: {len(rows)} -> {OUT_INDEX}")
    print(f"rarity seeds: {len(seeds)} -> {OUT_RARITY}")
    print(f"posts with year: {len(rows)}; avg likes by year: {sorted((y, round(v,1)) for y,v in avg_year.items())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
