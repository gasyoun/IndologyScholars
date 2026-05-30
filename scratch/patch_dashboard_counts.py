p = "assets/dashboard.js"
s = open(p, encoding="utf-8").read()
repls = [
    ("1378 участий в 1351 уникальных докладах", "1379 участий в 1352 уникальных докладах"),
    ("В корпусе: 270 ученых, 1351 уникальных докладов и 1378 авторских участий.",
     "В корпусе: 270 ученых, 1352 уникальных докладов и 1379 авторских участий."),
    ("1378 participations across 1351 unique talks", "1379 participations across 1352 unique talks"),
]
n = 0
for a, b in repls:
    c = s.count(a)
    if c:
        s = s.replace(a, b)
        n += c
open(p, "w", encoding="utf-8").write(s)
print("dashboard.js replacements:", n)
