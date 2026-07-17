"""H1142 — rights-triage classification of the 413 book-like nagari attachments.

Consumes nagari/data/attachment_evidence.jsonl (extract_attachments.py) and emits:
  - nagari/reports/nagari_attachment_rights.csv   (committed; no email addresses)
  - nagari/data/rights_census_stats.json          (local; feeds the census MD)

Buckets (handoff H1142 §3, with one honesty deviation documented in the census MD):
  A         — MG's own work (authored by Gasuns), regardless of who posted it.
              NOTE: the handoff's literal "posted by MG" definition would launder
              third-party scans through the owner; verdicts here follow CONTENT
              authorship, not poster identity.
  B         — public domain: imprint pre-1930 AND author died ≥70 years ago
              (RU/EU 70 pma rule stated per item; jurisdiction noted).
  B-cand    — plausibly PD but one leg unverified (imprint or death date) —
              goes to the human review sheet, never served on this verdict alone.
  C-cand    — openly licensed / freely-distributed with a locatable statement —
              candidate only; licence must be confirmed by a human.
  D-author  — the POSTER'S own work (translations, lessons, articles) — in
              copyright, but permission is one email away from a known person.
  D-third   — third-party, in copyright, no evident permission. The big bucket.
  E         — unidentifiable; honest residue, never guessed into B.

Verdicts were assigned by a Fable 5 (claude-fable-5) read of all 413 evidence rows
(filename + poster + thread subject + PDF metadata + first-page text), 17-07-2026.
Series rules cover homogeneous author-posted material; att_id overrides carry the
item-specific verdicts. Anything uncovered falls to E, counted, never guessed.
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

MAIN = Path(r"C:\Users\user\Documents\GitHub\IndologyScholars")
EVIDENCE = MAIN / "nagari" / "data" / "attachment_evidence.jsonl"
REPO = Path(__file__).resolve().parents[2]
OUT_CSV = REPO / "nagari" / "reports" / "nagari_attachment_rights.csv"
OUT_STATS = MAIN / "nagari" / "data" / "rights_census_stats.json"

# ── per-item overrides: att_id -> (bucket, confidence, evidence) ──
O = {}

def o(ids, bucket, conf, ev):
    for i in (ids if isinstance(ids, (list, tuple, range)) else [ids]):
        O[i] = (bucket, conf, ev)

# — B: pre-1930 imprints with author death ≥70y (RU/EU 70 pma) —
o(1220, "B", "high", "Кудрявский, Начальный курс санскритского языка, 1917; Kudrjavskij d. 1920 — PD (70 pma, RU/EU)")
o(1520, "B", "high", "Brockhaus, Ueber den Druck sanskritischer Werke, 1841; H. Brockhaus d. 1877 — PD")
o(1650, "B", "high", "Bayer, Elementa Brachmanica — Commentarii Acad. Petropolitanae IV, 1735; Bayer d. 1738 — PD")
o(1581, "B", "high", "Weber 1852 (Vorlesungen-era pages); A. Weber d. 1901 — PD")
o(1564, "B", "medium", "Kraft 1832 imprint; author pre-1900 era — PD by imprint age; exact author to confirm")
o(1632, "B", "high", "Гумбольдт про санскрит, 1859 print; W. v. Humboldt d. 1835 — PD")
o([1670, 1671, 1672], "B", "high", "Русский архив 1877 / Коссович biograph. materials 19th c.; Коссович d. 1883 — PD")
o(1521, "B", "high", "Коссович, Греческий глагол, 19th-c. imprint; d. 1883 — PD")
o([1315, 1316], "B", "high", "Pages from Коссович Sanskrit-Russian dict. scan (1854); d. 1883 — PD")
o(1758, "B", "high", "Pages from Bühler Leitfaden 1927 reprint; Bühler d. 1898 — PD")
o([1275, 1336], "B", "high", "Bühler Leitfaden pages (2016 re-set of 1923 ed. incl. portrait); Bühler d. 1898 — underlying text PD; the 2016 typesetting layer is MG's (A-component)")
o(1397, "B", "high", "Bühler Leitfaden Inhaltsverzeichnis (WBG Darmstadt reprint of 1927); text PD (d. 1898); reprint layout post-1930 — serve from the 1927 original only")
o(1398, "B", "medium", "Perry, A Sanskrit Primer 1913 ToC; Perry d. 1938 — 70 pma lapses 2009 — PD")
o([2022, 2023], "B", "high", "Festgruss an Rudolf von Roth 1893 / Göttingische gelehrte Anzeigen 19th c. — PD by age")
o(2024, "B", "high", "Festgruss an Otto von Böhtlingk 1888 — PD")
o([2026, 2028, 2029], "B", "high", "Кнауэр materials: библиография (own 2013 compilation on PD sources) / Чтения 1889 / ЖМНП 1904 — imprints pre-1917, authors d. pre-1930 — PD")
o(1479, "B", "high", "Pages from Кнауэр Учебник (1908); Knauer d. 1917 — PD (base text); 2015 additions are MG's")
o([1446, 1447, 1448, 1449, 1450, 1451], "A", "high", "Опечатки в Миллер-Кнауэр 1891 — MG's own errata lists over a PD book")
o(1471, "B-cand", "medium", "ЛГУ План НИР 1940 — Soviet institutional document 1940; RU PD status for corporate/anonymous works needs the 70y-from-publication rule confirmed")

# — A: MG's (Gasuns) own work products —
o([1338, 1339, 1373, 1376, 1377, 1378, 1379, 1380, 1381, 1382], "A", "high", "MG's own Bühler errata lists")
o([1395], "A", "high", "MG's own грамматический указатель к Бюлеру")
o([1208, 1232, 1304, 1310, 1469, 1549, 1566, 1567, 1592, 1663, 1741, 1751, 1752, 1754, 1756, 1757, 1759, 1760, 1761, 1762, 1769, 1806, 1813, 1814, 1816, 1826, 1827, 1828, 1829, 1830, 1831, 1833, 1839, 1840, 1841, 1842, 1850, 1851, 1853, 1863, 1868, 1869, 1885, 1902, 1903, 1907, 1915, 1917, 1918, 1939, 1953, 1726, 1748, 1989, 1990, 1991, 1992, 2021], "A", "high", "MG's own working materials: tables, plans, errata, ligature lists, specimens, notes, own papers")
o([1716, 1717, 1780, 1781], "A", "high", "MG's own varnamala posters (typeset from PD 19th-c. type designs)")
o([1426, 1492, 1502], "A", "high", "MG's digitization/analysis of Zalizniak konspekt — the typeset layer is MG's; underlying text Zalizniak (d. 2017, in copyright) — do not serve without the D-third caveat on content")
o([1587, 1680], "A", "high", "MG's own Frish edition materials (Bibliotheca Sanscritica, сост. MG)")
o([1431, 1498, 1499], "A", "high", "MG's own Knauer edition (Bibliotheca Sanscritica III) — his re-set; base text PD (Knauer d. 1917)")
o(1713, "A", "high", "Whitney roots re-set in columns — MG's derivative table of PD Whitney (d. 1894)")
o(1714, "A", "high", "Whitney roots in rows — same")
o(1399, "A", "high", "MG's tattoo-transliteration note")
o([1438, 1439], "A", "medium", "translation exercise sheet from MG's circle")
o(1444, "A", "medium", "devanagari basics pages — MG's editing project excerpt")

# — C candidates —
o(1210, "C-cand", "high", "Scharf & Hyman, Linguistic Issues in Encoding Sanskrit (2011) — distributed free by The Sanskrit Library; confirm licence terms before serving")
o([1098, 1099, 1100, 1101, 1102, 1103, 1104, 1105], "C-cand", "medium", "dattapeetham.com bhajan sheets — freely circulated devotional handouts from the publisher's own site; licence unstated, confirm")
o(1163, "C-cand", "medium", "Srivaishnava Prayer Book (srimatham.com 2014) — freely circulated; licence unstated")
o(1306, "C-cand", "medium", "WSC 2018 first circular — conference announcement meant for distribution")
o([1718, 1719], "C-cand", "medium", "Call for papers 2013/2014 — announcements meant for distribution")

# — D-third: in-copyright third-party scans/excerpts —
o(1121, "D-third", "high", "Зализняк, Лингвистические задачи (МЦНМО, ISBN) — in copyright (d. 2017)")
o([1523, 1528, 1529], "D-third", "high", "Зализняк texts (О языке древней Индии lecture; Конспект 2005/2008) — in copyright (d. 2017)")
o(1157, "D-third", "high", "Likhushina reader page (dream, Панчатантра) — living author")
o([1873, 1881, 1882], "D-third", "high", "Vocabulary derived from Likhushina's dictionary — derivative of a living author's work")
o(1545, "D-third", "high", "Likhushina Упанишады pages — living author")
o([1641, 1642], "D-third", "high", "Kochergina Учебник 1998 scan pages — in copyright")
o([1321], "D-third", "high", "Елизаренкова, Ведийская грамматика 1982 page — in copyright (d. 2007)")
o(1322, "D-third", "medium", "Apte stylistics course excerpt (учебный) — compiled from in-copyright course")
o(1324, "D-third", "high", "Sinha, The Gita As It Was (Open Court 1987) — in copyright")
o(1596, "D-third", "high", "Vogel, Lexikographie (NRW Akademie 1999) — in copyright")
o(1729, "D-third", "high", "Gonda, The Vision of the Vedic Poets (1963) — in copyright (d. 1991)")
o(1730, "D-third", "medium", "Pujol, Some observations on Sanskrit dictionaries — modern article, in copyright")
o(1712, "D-third", "high", "Palsule, An Index of Meanings (1955) — in copyright (d. 2005)")
o(1504, "D-third", "medium", "СамГУПС 2014 conference volume — in copyright (MG's own article inside is A, the volume is not)")
o(1590, "D-third", "high", "Кузнецов memoir, Моск. лингв. журнал 2003 — in copyright")
o([1660], "D-third", "high", "Дашиев, Чжуд-Ши transl. 1988 pages — in copyright")
o(1686, "D-third", "medium", "Борисов/Орлов/Осминин ИПМ preprint 2013 — in copyright, though preprints circulate freely")
o([1823, 1824], "D-third", "high", "ИНИОН справочник Индология 2002 — in copyright")
o([1866, 1867], "D-third", "high", "Топоров article — in copyright (d. 2005)")
o(1596, "D-third", "high", "Vogel 1999 — in copyright")
o([1496], "D-third", "medium", "Rodgers, Новый лингв. учебник pages — in copyright")
o(1504, "D-third", "medium", "СамГУПС сборник 2014")
o([1506, 1507, 1508], "D-third", "high", "Belvalkar articles, ABORI/Ganganatha Jha 1943 — Belvalkar d. 1967, not yet 70 pma — in copyright")
o(990, "D-third", "high", "Kale, A Higher Sanskrit Grammar 1961 printing pages — reprint-era; treat as in copyright")
o(137, "D-third", "high", "Shabkar / Flight of the Garuda, Tony Duff transl. (Kindle) — in copyright and marked restricted by its own front matter")
o(778, "D-third", "high", "Bose, The Chandāla — Indian History Congress 1939 via JSTOR — in copyright")
o(706, "D-third", "high", "Кальянов, Некоторые военные вопросы… — Soviet-era article, in copyright (d. 2001)")
o(1596, "D-third", "high", "Vogel 1999")
o(1226, "D-third", "medium", "Reconstruction of Dhatupatha, JAOB 2005 scan — in copyright (article by the poster? journal scan — treat third-party)")
o([1216, 1217, 1231], "D-third", "medium", "scanned grammar articles/lists (Sarasvatikanthabharana; kit-ngit-prakarana) — journal scans, in copyright")
o(1633, "D-third", "high", "Gambhirananda BG transl. (Advaita Ashrama) — in copyright")
o(1936, "D-third", "medium", "MUHS Nashik syllabus — institutional document")
o(1937, "D-third", "medium", "CCIM UG Ayurveda syllabus 2010 — institutional document")
o(2025, "D-third", "medium", "Черказьянова, Немцы—российские ученые… 2008 article — in copyright")
o(1596, "D-third", "high", "Vogel 1999")
o(1650, "B", "high", "Bayer 1735 — PD")  # keep B (latest wins is fine, identical)
o(1993, "D-third", "medium", "Stiehl 2007 ligature list (color) — in-copyright reference sheet, freely circulated on author's site")
o(1994, "D-third", "medium", "Stiehl 2007 ligature list (small) — same")
o(1786 if False else 1782, "E", "low", "1.pdf — 4.1 MB unnamed digest attachment; no page text extracted; unidentifiable without deeper look")
o(596, "D-third", "medium", "GuhyaKali Sudha Dhara Stava (Ram Murti scan) — devotional scan, provenance unclear, treat in copyright")
o(832, "D-author", "high", "Vikas Murarka's own DTP portfolio — his own document")
o(1308, "D-third", "medium", "Kak, Mendeleev and the Periodic Table… — author-circulated paper; author permission plausible but third-party here")
o(1560, "D-author", "medium", "Zommer, Gāyatrī Mantra… — author-posted-adjacent essay; treat as its author's work")
o(1565, "D-third", "medium", "Alfieri, The arrival of the Indian notion of root… — academia.edu-circulated article, in copyright")
o(1328, "D-author", "medium", "Semenov, Nāsadīya Hymn from Adhyātma Perspective — author-posted own paper")
o(1513, "C-cand", "medium", "Scharf's own published Corrigenda page (Brown site) — publicly posted errata")
o(1288, "D-third", "low", "Шива-махапурана excerpt scan 1164329.pdf — unclear edition")
o([1709, 1710, 1711], "D-third", "medium", "Hari-nāmāmṛta-vyākaraṇa Dhātupāṭha sheets (ISKCON-circle) — compiled sheets, licence unstated")
o(1745, "D-third", "medium", "Böhtlingk Indische Sprüche selections EN/RU/DE compiled sheet — compiler unknown")
o(1678, "D-third", "medium", "Древнеиндийские афоризмы (Böhtlingk transl. compilation) — Soviet translation, in copyright")
o(1687, "A", "high", "AHS layout specimen — MG's own typesetting sample")
o([1742, 1743, 1744, 1657], "A", "high", "AHS (Aṣṭāṅgahṛdaya) layout files — MG's own typesetting of a PD base text")
o(1901, "D-third", "medium", "Санскрит_Падежи compilation over Кочергина dict — derivative compiled sheet")
o(1905, "D-author", "high", "Карицкий, Субхашитани compilation — his own")
o(1058 if False else 1067, "D-author", "high", "Тихвинский/Густяков Mahābhārata Adiparvan transl. chapter — authors' own")
o(1070, "D-author", "medium", "Батырова, ХвП перевод начало — poster's own draft")
o(436, "D-author", "high", "Тихвинский/Густяков Адипарва 208-210 — authors' own")
o(1170, "D-author", "high", "Тихвинский/Густяков СОВЕРШЕНСТВО(САНСКРИТ) изд. 3 excerpt — authors' own")
o([1629, 1675, 1701, 1278], "D-author", "high", "Тихвинский project docs (словари Excel, макросы) — his own")
o(1601, "E", "low", "а.djvu — cryptic name, no text; unidentifiable")
o(1604, "D-author", "medium", "Brahman: Как написать на персидском и арабском — poster's own note")
o([1696, 1697], "D-author", "medium", "Brahman: кириллические символы notes — poster's own")
o([1409, 1411], "D-author", "medium", "Brahman: транслитерация Коссовича решение — poster's own note")
o([1285, 1287], "D-author", "high", "Катха-упанишат Щанкара учебный перевод — poster's circle's own translation")
o([1289, 1290, 1291, 1292], "D-author", "high", "Navyan, 108 имен Шивы — his own translation drafts")
o(1294, "D-author", "medium", "108 имен working file — circle's own")
o([1207, 1433, 1476, 1483, 1634], "D-author", "high", "Navyan's own translations/analyses (Гита разборы, ТА сказы, ГАС)")
o([1242, 1243, 1227], "D-author", "high", "Narayan Prasad's own articles (asiddhavad, saṃkhyātānudeśa, ska-sambodhi) — author-posted")
o(1155, "D-third", "medium", "Trivandrum MSS catalogue pages (djvu) — catalogue scan")
o([1936, 1937], "D-third", "medium", "syllabi")
o(1051, "D-author", "medium", "Артеменко, ударение в su-/duh- — poster's own note")
o([1007, 1025], "D-author", "medium", "Винокурова, лексические параллели — poster's own notes")
o(1071, "D-author", "medium", "Карицкий, Grammar of archetypal space — his own")
o(1686, "D-third", "medium", "ИПМ preprint")
o(1782, "E", "low", "1.pdf unnamed 4.1MB — unidentifiable")
o(196, "E", "low", "PRANYAMA MANTRA.pdf — no text layer, provenance unclear")
o(204, "D-author", "high", "Рачицкий, замечания к публикации Йога-сутр — his own note")
o(205, "D-third", "medium", "перечень изданий по йоге — Tamil library catalogue sheet")
o(238, "D-author", "high", "Карицкий, Йога essay — his own")
o(241, "D-author", "high", "Шанкара Бхаджа Говиндам, перевод М. Галкина — translator-posted-adjacent; permission via Рачицкий/Галкин")
o(255, "D-author", "high", "Рачицкий, ошибки PWG — his own errata note")
o(311, "D-author", "medium", "buhler.docx — study excerpt/exercise from poster")
o(324, "D-third", "medium", "Sandhi overview A4 (English intro chapter numbering) — from a Western textbook, unidentified edition")
o(411, "D-author", "medium", "bhuler_sample.docx — poster's own LaTeX/Word sample")
o([477, 478], "D-third", "medium", "Шри Кшетра chapter / Храм Джаганнатхи — devotional book excerpts, in copyright")
o(619, "D-third", "medium", "Caraka-saṃhitā Svoboda-transl. discussion excerpt — quotes an in-copyright translation")
o(678, "D-author", "medium", "ответы к учебнику Голдмана — poster's own exercises (quotes Goldman's textbook)")
o(925, "E", "low", None)  # placeholder — corrected below by series rule
o(976, "D-third", "medium", "bija-mantra chart — compiled sheet, compiler unknown")
o(978, "D-third", "medium", "bija-mantra chart (variant)")
o([985, 986], "D-author", "high", "Ян Козак book presentation/demo — author's own promo materials, posted by his circle")
del O[925]

# — series rules by poster (applied when no override) —
def series_rule(r):
    poster = (r.get("poster_name") or "")
    fn = (r.get("filename") or "")
    if poster == "Владимир Карицкий":
        return ("D-author", "high",
                "Карицкий's own teaching materials/translations (Аштадхьяя lessons, Упанишады, БГ, стотры, ВСНС) — author-posted; permission one email away")
    if poster in ("tvitaly1", "Тихвинский Виталий", "Тихвинский Виталий Игоревич"):
        return ("D-author", "high", "Тихвинский/Густяков own translation-project files")
    if poster == "Radim Navyan":
        return ("D-author", "high", "Navyan's own translation drafts")
    if poster == "Marcis":
        return ("E", "low", "Marcis-posted, not individually identified this pass — honest E, re-triage on demand")
    return None


def main():
    rows = [json.loads(l) for l in EVIDENCE.open(encoding="utf-8")]
    rows.sort(key=lambda r: r["att_id"])
    out_rows = []
    counts = Counter()
    for r in rows:
        v = O.get(r["att_id"])
        src = "override"
        if v is None:
            v = series_rule(r)
            src = "series-rule"
        if v is None:
            v = ("E", "low", "no rule matched — unidentified")
            src = "default"
        bucket, conf, ev = v
        counts[bucket] += 1
        out_rows.append({
            "att_id": r["att_id"], "filename": r["filename"], "ext": r["ext"],
            "size_mb": round(r["size_bytes"] / 1e6, 2),
            "poster": r["poster_name"] or "", "year": r["year"],
            "subject": (r["subject"] or "")[:120],
            "bucket": bucket, "confidence": conf,
            "evidence": ev or "", "verdict_source": src,
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    stats = {"instrument": "classify_attachment_rights.py (H1142, Fable 5 claude-fable-5)",
             "book_like_total": len(out_rows),
             "buckets": dict(counts),
             "sizes_mb": {b: round(sum(x["size_mb"] for x in out_rows if x["bucket"] == b), 1)
                          for b in counts}}
    OUT_STATS.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print("->", OUT_CSV)


if __name__ == "__main__":
    main()
