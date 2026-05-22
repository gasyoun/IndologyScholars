"""Generate the DEGREE_DATA dict literal for build_and_populate_db.py.

Reads degree_lookup_queue.csv, keeps rows with a confirmed degree, computes
the normalized_key with the SAME function the build uses, and prints a Python
dict literal: normalized_key -> (degree, degree_year, degree_source_url).
Paste the output into build_and_populate_db.py.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


# --- copied verbatim from build_and_populate_db.normalize_person_name ---
def normalize_person_name(name):
    name = name.strip().replace('\xa0', ' ').replace('​', '')
    name = re.sub(r'\bC(?=\.)', 'С', name)
    name = re.sub(r'[\.,;\s]+$', '', name)
    m1 = re.match(r'^([А-ЯЁA-Z])\.\s*([А-ЯЁA-Z])\.\s*([А-ЯЁA-Z][а-яёa-z\-]+)$', name)
    if m1:
        return f"{m1.group(3).lower()} {m1.group(1).lower()} {m1.group(2).lower()}"
    m2 = re.match(r'^([А-ЯЁA-Z][а-яёa-z\-]+)\s+([А-ЯЁA-Z])\.\s*([А-ЯЁA-Z])\.$', name)
    if m2:
        return f"{m2.group(1).lower()} {m2.group(2).lower()} {m2.group(3).lower()}"
    m3 = re.match(r'^([А-ЯЁA-Z])\.\s*([А-ЯЁA-Z][а-яёa-z\-]+)$', name)
    if m3:
        return f"{m3.group(2).lower()} {m3.group(1).lower()}"
    m4 = re.match(r'^([А-ЯЁA-Z][а-яёa-z\-]+)\s+([А-ЯЁA-Z])\.$', name)
    if m4:
        return f"{m4.group(1).lower()} {m4.group(2).lower()}"
    parts = [p for p in name.split() if p]
    if len(parts) >= 3:
        patronymic_idx = -1
        for idx, part in enumerate(parts):
            if part.endswith(('вич', 'вна', 'чна', 'чич', 'вна.', 'вич.')):
                patronymic_idx = idx
                break
        if patronymic_idx != -1:
            patronymic = parts[patronymic_idx]
            if patronymic_idx == 2 and len(parts) == 3:
                last = parts[0]; first = parts[1]
                if parts[2].lower().endswith(('ова', 'ева', 'ина', 'ын', 'ий', 'ев', 'ов')):
                    last = parts[2]; first = parts[0]
            elif patronymic_idx == 1 and len(parts) == 3:
                last = parts[0]; first = parts[2]
            else:
                last = parts[0]; first = parts[1]
            return f"{last.lower()} {first[0].lower()} {patronymic[0].lower()}"
    words = [w.lower() for w in re.findall(r'[А-ЯЁа-яёA-Za-z\-]+', name)]
    return " ".join(words)


QUEUE = Path(__file__).resolve().parent / "hypothesis_output" / "degree_lookup_queue.csv"
rows = list(csv.DictReader(QUEUE.open(encoding="utf-8")))

print("DEGREE_DATA = {")
print("    # normalized_key -> (degree, degree_year, degree_source_url)")
seen = {}
for r in rows:
    deg = r["degree"].strip()
    if not deg:
        continue
    key = normalize_person_name(r["display_name"])
    key_full = normalize_person_name(r["full_name_ru"]) if r["full_name_ru"] else key
    # prefer the key derived from the fuller name when they differ
    use_key = key
    if key_full and key_full != key and len(key_full.split()) >= len(key.split()):
        use_key = key_full
    if use_key in seen:
        print(f"    # DUPLICATE KEY {use_key!r}: {r['display_name']!r} vs {seen[use_key]!r}")
    seen[use_key] = r["display_name"]
    yr = r["degree_year"].strip()
    url = r["degree_source_url"].strip()
    print(f"    {use_key!r}: ({deg!r}, {yr!r}, {url!r}),")
print("}")
print(f"\n# total with degree: {len(seen)}", file=sys.stderr)
