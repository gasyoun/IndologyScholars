import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

c = sqlite3.connect('conferences.db')
c.row_factory = sqlite3.Row

# Author-citation pattern at START of a string: "Фамилия И.О." or "И.О. Фамилия" or "И. О. Фамилия"
author_lead = re.compile(r'^[\s]*(?:[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]?\.?|[А-ЯЁ]\.\s?[А-ЯЁ]?\.?\s?[А-ЯЁ][а-яё]+)')
# Author-citation appearing MID-string (sign of a second talk glued on)
author_mid = re.compile(r'[.»?!)]\s+(?:[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]?\.|[А-ЯЁ]\.\s?[А-ЯЁ]?\.\s?[А-ЯЁ][а-яё]+)')
# numbered item glued in: ". 3. " etc.
numbered = re.compile(r'[.»?!]\s+\d+\.\s+[А-ЯЁ]')
# program-timing junk glued to a title
timejunk = re.compile(r'\d{1,2}[.:]\d{2}\.?\s*(Там же|Перерыв|$)')

print("=" * 70)
print("TYPE A — session.session_title that is actually a PRESENTATION")
print("=" * 70)
rows = c.execute("""
  SELECT s.session_id, s.session_title,
         (SELECT COUNT(*) FROM presentation p WHERE p.session_id=s.session_id) AS npres
  FROM session s
  WHERE s.session_title IS NOT NULL AND s.session_title != ''
""").fetchall()
typeA = []
for r in rows:
    t = r["session_title"].strip()
    # A real session title is short/generic. Flag if it leads with an author citation
    # or carries an (Онлайн) tag or ends like a talk.
    if author_lead.search(t) or re.search(r'\((?:Онлайн|Online)\)', t):
        typeA.append(r)
for r in typeA:
    affected = c.execute(
        "SELECT p.presentation_id, p.title FROM presentation p WHERE p.session_id=?",
        (r["session_id"],)).fetchall()
    print(f"\nsession_id={r['session_id']}  ({r['npres']} pres attached)")
    print(f"  session_title = {r['session_title']!r}")
    for a in affected:
        print(f"    -> {a['presentation_id']}: {a['title'][:70]}")
print(f"\nTYPE A total: {len(typeA)} sessions")

print("\n" + "=" * 70)
print("TYPE B — presentation.title that glues TWO talks / program junk")
print("=" * 70)
pres = c.execute("SELECT presentation_id, title, source_snippet FROM presentation").fetchall()
typeB = []
for p in pres:
    t = (p["title"] or "").strip()
    reasons = []
    if author_mid.search(t):
        reasons.append("2nd-author-mid")
    if numbered.search(t):
        reasons.append("numbered-item")
    if timejunk.search(t):
        reasons.append("time-junk-tail")
    if reasons:
        typeB.append((p["presentation_id"], reasons, t))
for pid, reasons, t in typeB:
    print(f"\n{pid}  {reasons}")
    print(f"   {t[:200]}")
print(f"\nTYPE B total: {len(typeB)} presentations")
