import sqlite3, json, re, sys
sys.stdout.reconfigure(encoding='utf-8')

DB = 'conferences.db'
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

print("=== TABLES ===")
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print(tables)

# find the presentations-like table
for t in tables:
    cols = [d[1] for d in c.execute(f'PRAGMA table_info("{t}")')]
    print(f"\n=== {t} cols ===")
    print(cols)

# Heuristics: detect a talk record whose 'session'/'title' field contains a SECOND talk.
# Signs of slippage:
#  - a field contains an author-initial pattern "Фамилия И.О." far into the string
#  - contains "(Онлайн)" / "(Online)" embedded
#  - title field abnormally long (> 200 chars) or contains two '«' ... '»' title segments

initials = re.compile(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.')   # Surname I.O.
online = re.compile(r'\((?:Онлайн|Online|онлайн)\)')

def scan_table(t):
    cols = [d[1] for d in c.execute(f'PRAGMA table_info("{t}")')]
    textcols = [col for col in cols]
    rows = list(c.execute(f'SELECT * FROM "{t}"'))
    flagged = []
    for r in rows:
        d = dict(r)
        for col in textcols:
            v = d.get(col)
            if not isinstance(v, str):
                continue
            hits = initials.findall(v)
            problems = []
            if online.search(v):
                problems.append('has(Онлайн)')
            if len(hits) >= 1 and len(v) > 60:
                problems.append(f'initials={hits[:3]}')
            if len(v) > 200:
                problems.append(f'len={len(v)}')
            # two title quotes
            if v.count('«') + v.count('»') >= 4:
                problems.append('multi-«»')
            if problems:
                idcol = d.get('id') or d.get('presentation_id') or d.get('rowid')
                flagged.append((t, col, idcol, problems, v[:300]))
    return flagged

all_flagged = []
for t in tables:
    try:
        all_flagged += scan_table(t)
    except Exception as e:
        print(f"skip {t}: {e}")

print(f"\n=== FLAGGED FIELDS: {len(all_flagged)} ===")
for t, col, idc, probs, snippet in all_flagged[:200]:
    print(f"\n[{t}.{col}] id={idc} {probs}")
    print(f"   {snippet}")
