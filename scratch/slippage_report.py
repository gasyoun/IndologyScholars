import sqlite3, re

c = sqlite3.connect('conferences.db')
c.row_factory = sqlite3.Row
out = []

# ---- TYPE A: session_title that is really a presentation ----
author_lead = re.compile(r'^\s*(?:[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]?\.?|[А-ЯЁ]\.\s?[А-ЯЁ]?\.?\s?[А-ЯЁ][а-яё]+)')
rows = c.execute("SELECT session_id, session_title FROM session WHERE session_title<>''").fetchall()
typeA = []
for r in rows:
    t = r["session_title"].strip()
    if author_lead.search(t) or re.search(r'\((?:Онлайн|Online)\)', t):
        typeA.append(r)
out.append("TYPE A  session_title is actually a talk: %d" % len(typeA))
for r in typeA:
    pres = c.execute("SELECT presentation_id,title FROM presentation WHERE session_id=?", (r["session_id"],)).fetchall()
    out.append("  [%s] title=%r" % (r["session_id"], r["session_title"]))
    for p in pres:
        out.append("       attached pres %s : %s" % (p["presentation_id"], p["title"]))

# ---- TYPE B: presentation.title gluing two talks / junk ----
# second author citation anywhere after position 5
cit = re.compile(r'(?:[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\s?\.\s?[А-ЯЁ]?\s?\.?|[А-ЯЁ]\s?\.\s?[А-ЯЁ]\s?\.\s?[А-ЯЁ][а-яё]+)')
numbered = re.compile(r'\.\s*\d+\.\s+[А-ЯЁ]')
timejunk = re.compile(r'\d{1,2}[.:]\d{2}\.?\s*(?:Там же|Перерыв)')
pres = c.execute("SELECT presentation_id,title FROM presentation WHERE title<>''").fetchall()
typeB = []
for p in pres:
    t = p["title"].strip()
    reasons = []
    # find author-citation occurrences not at the very start
    for m in cit.finditer(t):
        if m.start() > 8:
            reasons.append("2nd-citation@%d:%r" % (m.start(), m.group()))
            break
    if numbered.search(t):
        reasons.append("numbered-item")
    if timejunk.search(t):
        reasons.append("time-junk")
    if reasons:
        typeB.append((p["presentation_id"], reasons, t))
out.append("")
out.append("TYPE B  presentation.title glues two talks/junk: %d" % len(typeB))
for pid, reasons, t in typeB:
    out.append("  [%s] %s" % (pid, "; ".join(reasons)))
    out.append("       %s" % t)

with open('scratch/slippage_report.txt', 'w', encoding='utf-8') as f:
    f.write("\n".join(out))
print("done", len(typeA), len(typeB))
