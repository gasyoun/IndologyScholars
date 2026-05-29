import sys
p = "generate_publication_pages.py"
s = open(p, encoding="utf-8").read()
old = "        writer = csv.DictWriter(handle, fieldnames=list(ledger_rows[0].keys()))"
new = (
    '        ledger_fieldnames = ["presentation_id", "title", "theme_code", '
    '"theme_label_ru", "gumilyov_level", "meso_codes", "reason"]\n'
    "        writer = csv.DictWriter(handle, fieldnames=ledger_fieldnames)"
)
if "ledger_fieldnames" in s:
    print("crashguard already applied")
elif s.count(old) == 1:
    open(p, "w", encoding="utf-8").write(s.replace(old, new))
    print("crashguard applied")
else:
    print("PATCH TARGET NOT FOUND, count=", s.count(old))
    sys.exit(1)
