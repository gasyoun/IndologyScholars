# SEO authority enrichment — Gemini Flash paste batch

Generated: 2026-05-19
Target file: `authority_ids.json` (sections: `places`, `organizations`)
Already-enriched items are SKIPPED in the lists below.

---

You are enriching authority records for a Russian Indology research archive
(Zograf Readings + Roerich Readings, since 2004). The enriched data feeds
schema.org/Place and schema.org/ResearchOrganization JSON-LD blocks on the
public site so search engines (Yandex, Google) can resolve scholar
affiliations to authoritative entities.

**For each item below, reply with ONE JSON object per line, inside a single
```jsonl fenced block. Reply NOTHING outside the fenced block.**

Rules:
1. Set unknown fields to `null`. **Do NOT guess.** A missing field is far
   better than a wrong Wikidata QID.
2. `wikidata` is a bare Q-number (e.g. `"Q649"`), no URL prefix.
3. `ror` is a bare ROR identifier (e.g. `"02nps9w79"`), no URL prefix.
4. `url` is the canonical homepage. Prefer https. No trailing slash unless
   the site requires one.
5. `alternateName` is a list of 0–3 widely-used variants. Do NOT repeat the
   `key`, `name_en`, or `full_name_ru` inside `alternateName`.
6. Keep `key` exactly as written in the lists below — it is the lookup
   identifier in `authority_ids.json`.

**Place schema:**
```
{"item_type":"place","key":"<exact Cyrillic name>","name_en":"<English canonical>","alternateName":[...],"wikidata":"Q...","country":"<English country>","country_ru":"<Russian country>"}
```

**Organization schema (Russian academic institutions):**
```
{"item_type":"organization","key":"<exact short name>","full_name_ru":"<full Russian name>","name_en":"<English canonical name>","alternateName":[...],"url":"https://...","wikidata":"Q...","ror":"<ROR id>"}
```


## Places to enrich (10 items)

- `Санкт-Петербург` — currently displayed in the archive as **St. Petersburg**
- `Москва` — currently displayed in the archive as **Moscow**
- `Пенза` — currently displayed in the archive as **Penza**
- `Краснодар` — currently displayed in the archive as **Krasnodar**
- `Казань` — currently displayed in the archive as **Kazan**
- `Элиста` — currently displayed in the archive as **Elista**
- `Новосибирск` — currently displayed in the archive as **Novosibirsk**
- `Нижний Новгород` — currently displayed in the archive as **Nizhny Novgorod**
- `Вильнюс` — currently displayed in the archive as **Vilnius**
- `Улан-Удэ` — currently displayed in the archive as **Ulan-Ude**

## Organizations to enrich (9 items)

- `ИВ РАН` — 160 presentation records in archive
- `СПбГУ` — 38 presentation records in archive
- `МГУ` — 36 presentation records in archive
- `НИУ ВШЭ` — 15 presentation records in archive
- `ИФ РАН` — 12 presentation records in archive
- `РГГУ` — 4 presentation records in archive
- `МАЭ РАН` — 2 presentation records in archive
- `Государственный Эрмитаж` — 1 presentation record in archive
- `ИВР РАН` — 1 presentation record in archive

---
Reply with a single fenced ```jsonl block, one JSON object per item.
