# -*- coding: utf-8 -*-
"""score_candidates.py — фазы 2–3 скоринга кандидатов на сканирование (v2).

Вход:  library/libfl-scan-candidates.csv + libfl-scan-exclusions.txt
Выход: scratch/libfl-scan-scores.csv (+ ia_cache.json — кэш внешней проверки)

Оси (интервью 12-11-2026): спрос 40% (упоминания ОРС со стоп-токенами и индологическим
гейтом) / канон 30% (жанровые веса по долям интереса истории) / редкость 30%
(archive.org, DLI, год ≤1960, «Очередь на оцифровку»). Внешняя проверка пакетная
(адаптив по длине URL — IA → 400 на ≥7.5 КБ) + индивидуальная верификация топ-400.

Запуск: python score_candidates.py [--skip-net]
"""
import bisect
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "library" / "libfl-scan-candidates.csv"
EXCLUSIONS = ROOT / "library" / "libfl-scan-exclusions.txt"
OUT = Path(__file__).resolve().parent / "libfl-scan-scores.csv"
DEMAND = Path(__file__).resolve().parent / "demand_index.csv"
SEEDS = Path(__file__).resolve().parent / "rarity_seeds.txt"
IA_CACHE = Path(__file__).resolve().parent / "ia_cache.json"

BATCH = 20           # заголовков на пакетный проход (короче URL — меньше 400)
TOP_VERIFY = 400     # сколько топов верифицируем индивидуально точными запросами
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

GENRE_WEIGHTS = [
    ("dissertation", r"автореферат|диссертац|\bdiss\b|thesis|dissertation", 0.10),
    ("dictionary", r"словар|wörterb|dictionary|lexicon|лексикограф", 1.00),
    # «учебник/пособие» даёт 0.90 только в языковом контексте (не экономические пособия об Индии)
    ("grammar",
     r"грамматик|хрестомати|начальный курс|practical grammar|grammar of|\breader\b|"
     r"(учебник|пособи).{0,60}(санскрит|пракрит|язык|грамматик|пали|хинди|бенгал|письм)|"
     r"(санскрит|пракрит|грамматик|пали|хинди|бенгал).{0,60}(учебник|пособи)",
     0.90),
    ("epos", r"рамаян|махабхарат|бхагавадгит|бхагавата|панчатантр|джатак|эпос", 0.85),
    ("vedic", r"вед(а|ы|ий)|ригвед|яджурвед|самaved|атхарвавед|упанишад", 0.80),
    ("buddhist", r"будд|сутр|vinaya|стотра|бхикшу", 0.65),
    ("general_indology", r"инди[ия]|индуизм|индуист|востоковед", 0.50),
]
GENRE_DEFAULT = 0.40

# Стоп-токены матчинга спроса: общелексические/жанровые/географические слова не несят
# идентичности книги (без них «Chontal dictionary» матчился на пост о словаре MW).
STOP = {
    # жанр/тип
    "словарь", "словари", "словарем", "dictionary", "wörterbuch", "worterbuch", "lexicon",
    "грамматика", "грамматикой", "grammar", "учебник", "учебника", "пособие", "пособие",
    "хрестоматия", "хрестоматии", "сборник", "сборника", "статей", "издание", "издания",
    "издательство", "серия", "том", "часть", "язык", "языки", "языка", "language", "linguistics",
    "reader", "textbook", "handbook",
    # география/издательские города
    "москва", "москве", "ленинград", "петербург", "санкт", "ссср", "london", "berlin", "paris",
    "delhi", "bombay", "new", "york", "wiesbaden", "hamburg", "mainz", "leipzig", "strassburg",
    "stuttgart", "cambridge", "bonn", "москва",
    # широкие идентификаторы контекста (второй токен — уже идентичность)
    "sanskrit", "sanscrit", "санскрит", "индия", "индии", "индия", "india", "hindu", "индуизм",
    "english", "russian", "deutsch", "английский", "русский", "германский",
    # годы/номера-мусор
    "том", "выпуск", "вып", "part", "band", "t.",
}

# Индологический гейт: бонус жанра осмыслен только для Индостана.
IND_RE = re.compile(
    r"санскрит|пракрит|вед(а|ы|ий|ик)|упанишад|пали|будд|инди|инду|хинди|бенгал|бенгальск|"
    r"тамил|непал|тибет|дравид|джайн|панини|махабхарат|рамаян|бхагав|эпос|йог|дхарм|кашмир|"
    r"панджаб|панидж|пуран|sanskrit|hindu|india|pali|veda|upanish|buddh|hindi|"
    r"bengal|tamil|tibet|nepal|dravid|jain|panini|mahabharat|ramayan|bhagav|yoga|dharma|"
    r"kashmir|purana|prakrit|arthaś|artha",
    re.I,
)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def clean_citation(c: str) -> str:
    """Убирает артефакты HTML-парсера выдачи: '&type0%5B%5D=Author \"&gt; .' и подобное."""
    if not c:
        return ""
    # всё до последнего '>' внутри кавычек-мусора
    if '">' in c:
        c = c.rsplit('">', 1)[-1]
    c = re.sub(r'^[^0-9A-Za-zА-Яа-яЁё"«]', "", c.strip())
    return c.strip()


def year_of(citation: str):
    ys = [int(y) for y in re.findall(r"\b(1[6-9]\d\d|20[0-2]\d)\b", citation)]
    return min(ys) if ys else None


def load_candidates():
    by_id = {}
    with CAND.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rid = r["record_id"]
            if rid not in by_id:
                by_id[rid] = {
                    "record_id": rid,
                    "citation": clean_citation(r["citation"]),
                    "url": r["url"],
                    "sections": set(),
                    "rubrics": set(),
                }
            by_id[rid]["sections"].add(r["section"])
            by_id[rid]["rubrics"].add(r["rubric"])

    # исключения из library/libfl-scan-exclusions.txt (паттерн<TAB>причина) — MG 13-11-2026
    excl = []
    if EXCLUSIONS.exists():
        for line in EXCLUSIONS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            pat, _, reason = line.partition("\t")
            if pat:
                excl.append((pat.lower().strip(), reason.strip()))
    kept, dropped = {}, []
    for rid, c in by_id.items():
        cl = c["citation"].lower()
        hit = next((reason for pat, reason in excl if pat in cl), None)
        if hit:
            dropped.append((rid, c["citation"][:70], hit))
        else:
            kept[rid] = c
    if dropped:
        print(f"excluded by libfl-scan-exclusions.txt: {len(dropped)}")
        for rid, cit, reason in dropped[:10]:
            print(f"  - {rid} {cit} :: {reason}")
    return list(kept.values())


def load_demand():
    out = []
    if not DEMAND.exists():
        return []
    with DEMAND.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            snip = norm(r["snippet"])
            # слайпы каталожных записей libfl («место издания… предметная рубрика…») —
            # это не упоминание книги в контексте спроса, а паст полей каталога: изымаем
            if any(m in snip for m in ("место издания", "предметная рубрика", "дата издания")):
                continue
            out.append((snip, float(r["year_ratio"] or 0)))
    return out


def load_seeds():
    if not SEEDS.exists():
        return []
    return [norm(line.split("\t", 1)[-1]) for line in SEEDS.read_text(encoding="utf-8").splitlines() if line.strip()]


def match_tokens(citation: str):
    """Токены для матчинга спроса без стоп-слов (жанр/гео/издательство не несут идентичности)."""
    return [t for t in norm(citation).split() if len(t) >= 5 and t not in STOP][:40]


def match_text(citation, hay):
    """Совпадение упоминания: ≥3 не-стоп токена, либо ≥2 с одним ≥10 символов."""
    toks = match_tokens(citation)
    if not toks:
        return False
    hits = [t for t in toks if t in hay]
    if len(hits) >= 3:
        return True
    return len(hits) >= 2 and any(len(t) >= 10 for t in hits)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def ia_query_url(titles, collection=None, rows=150):
    parts = ['title:("%s")' % norm(t)[:120].replace('"', "") for t in titles if norm(t)]
    if not parts:
        return ""
    query = "(" + " OR ".join(parts) + ")"
    if collection:
        query += " AND collection:%s" % collection
    return "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
        {"q": query, "fl[]": "title", "rows": str(rows), "output": "json"}
    )


def ia_query(titles, collection=None, rows=150):
    url = ia_query_url(titles, collection, rows)
    if not url:
        return set()
    data = _get(url)
    return {norm(str(d.get("title", ""))) for d in data.get("response", {}).get("docs", [])}


def ia_query_and(title, collection=None, nwords=9, rows=5):
    """Точный индивидуальный запрос: title:(w1 AND w2 …) — порядко-независимая AND-семантика."""
    toks = [t for t in norm(title).split() if len(t) >= 3][:nwords]
    if len(toks) < 2:
        return None  # слишком мало слов для надёжного запроса — не верифицируем
    q = "title:(%s)" % " AND ".join(toks)
    if collection:
        q += " AND collection:%s" % collection
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
        {"q": q, "fl[]": "title", "rows": str(rows), "output": "json"}
    )
    data = _get(url)
    docs = data.get("response", {}).get("docs", [])
    if not docs:
        return False
    # доп. защита: заглавок хита должен содержать большинство токенов
    best = 0
    for d in docs:
        h = set(norm(str(d.get("title", ""))).split())
        best = max(best, len(set(toks) & h))
    return best >= max(2, len(toks) - 3)


def title_head(citation):
    """Грубое заглавие: до разделителя издания ' — ' или двойной даты."""
    cit = citation or ""
    for sep in (" — ", " – ", " - "):
        if sep in cit:
            cit = cit.split(sep)[0]
            break
    # отрезаем хвост вида '. — Москва, 1987' и ' [1877]'
    cit = re.sub(r"\s*\[[^\]]*\]\s*$", "", cit)
    m = re.match(r"^(.{5,180}?)(?:\.\s|$)", cit)
    head = m.group(1) if m and len(m.group(1)) > 15 else cit
    # убрать ведущого автора «Фамилия,Имя. » — оставить как есть, AND-запрос его переварит
    return head.strip(" .,:;«»")


def batch_check(cands, cache):
    """Грубая пакетная проверка: недостающие И оставшиеся None (после 400-ых ошибок)."""
    def need(c, kind):
        return c["record_id"] not in cache or cache[c["record_id"]].get(kind) is None

    for c in cands:
        cache.setdefault(c["record_id"], {"ia": None, "dli": None, "method": "none"})
    for kind, coll in (("ia", None), ("dli", "digitallibraryindia")):
        todo = [(c, title_head(c["citation"])) for c in cands
                if need(c, kind) and title_head(c["citation"])]
        i, size = 0, BATCH
        while i < len(todo):
            batch = todo[i : i + size]
            # адаптивность: IA отдаёт 400 на URL > ~7.5 КБ (кириллица ×3 в percent-encoding)
            while len(batch) > 1 and len(ia_query_url([t for _, t in batch], coll)) > 7500:
                size = max(1, len(batch) // 2)
                batch = todo[i : i + size]
            hits, err = None, False
            for attempt in range(3):
                try:
                    hits = ia_query([t for _, t in batch], collection=coll)
                    break
                except Exception as e:  # noqa: BLE001
                    print(f"IA-ERR {kind}@{i} attempt{attempt}: {e}", file=sys.stderr)
                    err = True
                    time.sleep(4 * (attempt + 1))
            if hits is None:
                if err and len(batch) > 1:
                    size = max(1, len(batch) // 2)
                    continue  # заново с меньшей пачкой
                if len(batch) > 1:
                    size = max(1, len(batch) // 2)
                    continue
                print(f"IA-GIVEUP {kind} {batch[0][0]['record_id']}", file=sys.stderr)
                i += 1
                size = BATCH
                time.sleep(2)
                continue
            for c, t in batch:
                rec = cache.setdefault(c["record_id"], {"ia": None, "dli": None, "method": "none"})
                tt = set(t.split())
                found = any(t and t in h for h in hits) or any(
                    len(tt & set(h.split())) >= 2 for h in hits if h
                )
                rec["ia" if coll is None else "dli"] = bool(found)
                rec["method"] = "batch"
            IA_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            i += len(batch)
            size = BATCH
            time.sleep(1.2)
    return cache


def verify_top(cands_sorted, cache, top_n=TOP_VERIFY, skip_net=False):
    """Точная индивидуальная верификация топа (только ещё не подтверждённые True)."""
    if skip_net:
        return 0
    checked = 0
    for c in cands_sorted[:top_n]:
        head = title_head(c["citation"])
        if not head:
            continue
        for kind, coll in (("ia", None), ("dli", "digitallibraryindia")):
            rec = cache.setdefault(c["record_id"], {"ia": None, "dli": None, "method": "none"})
            if rec.get(kind) is True:
                continue  # подтверждено — не трогаем
            if "verify" in rec.get("method", ""):
                continue  # уже индивидуально верифицировано (False стабильно) — не повторяем
            try:
                res = ia_query_and(head, collection=coll)
            except Exception as e:  # noqa: BLE001
                print(f"VERIFY-ERR {kind} {c['record_id']}: {e}", file=sys.stderr)
                time.sleep(5)
                continue
            if res is not None:
                rec[kind] = bool(res)
                rec["method"] = "verify+" + rec.get("method", "")
            checked += 1
            time.sleep(0.8)
    IA_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return checked


def compute(cands, demand, seeds, ext):
    ratios = []
    for c in cands:
        cit_n = norm(c["citation"])
        c["_ind"] = bool(IND_RE.search(cit_n))
        matched = [ratio for snip, ratio in demand if match_text(cit_n, snip)]
        c["_demand_raw"] = max(matched) if matched else None
        if matched:
            ratios.append(c["_demand_raw"])
        genre_w = GENRE_DEFAULT
        for _name, pat, w in GENRE_WEIGHTS:
            if re.search(pat, cit_n, re.I):
                genre_w = w
                break
        # индологический гейт: жанровый бонус словаря/учебника имеет смысл только для книг
        # об Индостане/санскрите; для остальных — потолок 0.35 (чуждая аудитории ОРС тема)
        if not c["_ind"]:
            genre_w = min(genre_w, 0.35)
        c["_genre_w"] = genre_w
        yr = year_of(c["citation"])
        c["_year"] = yr
        r = 0.0
        e = ext.get(c["record_id"], {})
        if e.get("ia") is False:
            r += 0.5
        if e.get("dli") is False:
            r += 0.2
        if yr and yr <= 1960:
            r += 0.2
        if any(match_text(cit_n, sd) for sd in seeds):
            r += 0.1
        c["_rarity"] = min(r, 1.0)
        c["_matched"] = len(matched)

    ratios_sorted = sorted(ratios)

    def pct(v):
        return bisect.bisect_left(ratios_sorted, v) / max(len(ratios_sorted) - 1, 1) if ratios_sorted else 0.5

    genre_med = {}
    for w in sorted({c["_genre_w"] for c in cands}):
        sub = [pct(c["_demand_raw"]) for c in cands
               if c["_genre_w"] == w and c["_demand_raw"] is not None and c["_ind"]]
        genre_med[w] = sorted(sub)[len(sub) // 2] if sub else 0.40

    for c in cands:
        if c["_demand_raw"] is not None:
            d = pct(c["_demand_raw"])
        elif c["_ind"]:
            d = genre_med.get(c["_genre_w"], 0.40)
        else:
            d = 0.30  # вне индологии упоминаний ОРС не бывает — консервативный базис
        c["_demand"] = round(d, 3)
        c["_score"] = round(0.4 * d + 0.3 * c["_genre_w"] + 0.3 * c["_rarity"], 4)

    cands.sort(key=lambda c: (-c["_score"], c["citation"]))
    return cands


def main():
    skip_net = "--skip-net" in sys.argv
    cands = load_candidates()
    demand = load_demand()
    seeds = load_seeds()
    print(f"unique candidates: {len(cands)}; demand mentions: {len(demand)}; seeds: {len(seeds)}")

    cache = json.loads(IA_CACHE.read_text(encoding="utf-8")) if IA_CACHE.exists() else {}
    if not skip_net:
        batch_check(cands, cache)

    # итерация 1: грубый скоринг → топ → точная верификация → перескоринг
    compute(cands, demand, seeds, cache)
    n_ver = verify_top(cands, cache, skip_net=skip_net)
    print(f"individual verifications: {n_ver}")
    compute(cands, demand, seeds, cache)

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["rank", "record_id", "score", "axis_demand", "axis_canon", "axis_rarity",
             "ia_hit", "dli_hit", "year", "mentions", "sections", "rubrics", "citation", "url"]
        )
        for i, c in enumerate(cands, 1):
            e = cache.get(c["record_id"], {})
            w.writerow([
                i, c["record_id"], c["_score"], c["_demand"], c["_genre_w"], c["_rarity"],
                e.get("ia"), e.get("dli"), c["_year"] or "", c["_matched"],
                "|".join(sorted(c["sections"])),
                "; ".join(sorted(c["rubrics"])),
                c["citation"], c["url"],
            ])
    print(f"-> {OUT} ({len(cands)} rows)")


if __name__ == "__main__":
    main()
