import sqlite3, re
c = sqlite3.connect('conferences.db')
c.row_factory = sqlite3.Row
out = []

author_lead = re.compile(r'^\s*(?:[А-ЯЁ][а-яё\-]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]?\.?|[А-ЯЁ]\.\s?[А-ЯЁ]?\.?\s?[А-ЯЁ][а-яё\-]+)')
rows = c.execute("SELECT session_id, session_title FROM session WHERE session_title<>''").fetchall()
typeA = [r for r in rows if author_lead.search(r["session_title"].strip()) or re.search(r'\((?:Онлайн|Online)\)', r["session_title"])]
out.append("TYPE A sessions still holding a talk-like title: %d" % len(typeA))
for r in typeA:
    out.append("  [%s] %r" % (r["session_id"], r["session_title"][:90]))

# Erchenkov talk should now exist as a presentation
erch = c.execute("SELECT presentation_id, title, session_id FROM presentation WHERE title LIKE '%кауладхарма%'").fetchall()
out.append("\nErchenkov 'кауладхарма' presentation rows: %d" % len(erch))
for r in erch:
    out.append("  %s | %s | sess=%s" % (r["presentation_id"], r["title"][:70], r["session_id"]))

# Stepin's talk + its session title
step = c.execute("""
  SELECT p.presentation_id, p.title, s.session_title
  FROM presentation p JOIN session s ON s.session_id=p.session_id
  WHERE p.title LIKE '%Ананда-сутр%'
""").fetchall()
out.append("\nStepin 'Ананда-сутр' presentation + session title:")
for r in step:
    out.append("  %s | %s | session=%r" % (r["presentation_id"], r["title"][:60], r["session_title"]))

# remaining time-junk tails in titles
junk = c.execute("SELECT presentation_id, title FROM presentation WHERE title LIKE '%Там же%' OR title LIKE '%Зеленый зал%' OR title LIKE '%Зелёный зал%'").fetchall()
out.append("\npresentation.title still ending in venue/'Там же' junk: %d" % len(junk))
for r in junk[:40]:
    out.append("  %s | %s" % (r["presentation_id"], r["title"][:90]))

totals = c.execute("SELECT (SELECT COUNT(*) FROM presentation), (SELECT COUNT(*) FROM session), (SELECT COUNT(*) FROM person)").fetchone()
out.append("\nTotals: presentations=%d sessions=%d persons=%d" % tuple(totals))

with open('scratch/verify_slippage_fix.txt','w',encoding='utf-8') as f:
    f.write("\n".join(out))
print("WROTE", len(typeA), len(erch), len(step), len(junk))
