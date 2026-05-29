"""Carry forward DeepSeek classification artifacts: old PRES_ID -> new PRES_ID.

The parser fix re-segmented some sessions, shifting `session_order` and thus the
`stable_presentation_id` hash for talks in the affected years. Presentation
*content* is unchanged except: one restored talk (Erchenkov) and ~20 titles whose
trailing programme junk was trimmed. We remap by the session-order-independent
`stable_key_candidate` content hash in the manifest, with a
(series, year, first_speaker, title-prefix) fallback, then append a single
provisional L1 row for each genuinely new talk.

IDEMPOTENT: the three target CSVs are reset to their committed (HEAD) state at the
start of every run, so running this multiple times is safe.
"""
import csv, io, re, subprocess, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")

CLS = "analytics_output/expanded_classification_deepseek.csv"
MESO = "analytics_output/meso_codes_deepseek.csv"
AUDIT = "analytics_output/expanded_gumilyov_elevated_audit.csv"
MANIFEST = "analytics_output/presentation_id_manifest.csv"

# --- 0. reset targets to committed state (idempotency) ---
subprocess.run(["git", "checkout", "HEAD", "--", CLS, MESO, AUDIT], check=True)
print("reset CLS/MESO/AUDIT to HEAD")


def norm(s):
    s = (s or "").replace("\xa0", " ").replace("ё", "е").replace("Ё", "Е")
    return re.sub(r"\s+", " ", s.strip().lower())


# --- 1. manifests ---
old_text = subprocess.run(
    ["git", "show", f"HEAD:{MANIFEST}"], capture_output=True, text=True, encoding="utf-8"
).stdout
old_rows = list(csv.DictReader(io.StringIO(old_text)))
with open(MANIFEST, encoding="utf-8") as f:
    new_rows = list(csv.DictReader(f))
print(f"old manifest={len(old_rows)} new manifest={len(new_rows)}")

# --- 2. old_pid -> new_pid ---
new_by_key = defaultdict(list)
for r in new_rows:
    new_by_key[r["stable_key_candidate"]].append(r)

old2new, used = {}, set()
unmatched = []
for r in old_rows:
    cands = [c for c in new_by_key.get(r["stable_key_candidate"], []) if c["presentation_id"] not in used]
    if len(cands) == 1:
        old2new[r["presentation_id"]] = cands[0]["presentation_id"]
        used.add(cands[0]["presentation_id"])
    else:
        unmatched.append(r)

idx = defaultdict(list)
for r in new_rows:
    if r["presentation_id"] not in used:
        idx[(r["series"], r["year"], norm(r["first_speaker"]))].append(r)

still = []
for r in unmatched:
    cands = idx.get((r["series"], r["year"], norm(r["first_speaker"])), [])
    ot = norm(r["title"])
    best = next((c for c in cands if norm(c["title"]).startswith(ot[:25]) or ot.startswith(norm(c["title"])[:25])), None)
    if best is None and len(cands) == 1:
        best = cands[0]
    if best is not None:
        old2new[r["presentation_id"]] = best["presentation_id"]
        used.add(best["presentation_id"])
        cands.remove(best)
    else:
        still.append(r)

new_unmapped = [r for r in new_rows if r["presentation_id"] not in used]
print(f"mapped={len(old2new)} old-unmapped={len(still)} new-talks={len(new_unmapped)}")
for r in still:
    print("  OLD-UNMAPPED", r["presentation_id"], r["year"], r["first_speaker"], r["title"][:50])
for r in new_unmapped:
    print("  NEW-TALK", r["presentation_id"], r["year"], r["first_speaker"], r["title"][:50])

new_meta = {r["presentation_id"]: r for r in new_rows}


def rekey(path, refresh_title=False):
    with open(path, encoding="utf-8") as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames
        rows = list(rd)
    out, dropped = [], 0
    for row in rows:
        npid = old2new.get(row["presentation_id"])
        if not npid:
            dropped += 1
            continue
        row["presentation_id"] = npid
        if refresh_title and "title" in row and new_meta.get(npid, {}).get("title"):
            row["title"] = new_meta[npid]["title"]
        out.append(row)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print(f"rekeyed {path}: kept={len(out)} dropped={dropped}")
    return cols, out


cls_cols, cls_rows = rekey(CLS, refresh_title=True)
rekey(MESO, refresh_title=True)
rekey(AUDIT)

# --- 3. append provisional rows for genuinely new talks ---
have = {r["presentation_id"] for r in cls_rows}
with open(CLS, "a", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cls_cols)
    for r in new_rows:
        if r["presentation_id"] in have:
            continue
        row = {c: "" for c in cls_cols}
        row.update({
            "presentation_id": r["presentation_id"], "year": r.get("year", ""),
            "series_id": "1" if r.get("series", "").startswith("Zograf") else "2",
            "series": r.get("series", ""), "raw_title": r.get("title", ""),
            "title": r.get("title", ""), "theme_l1": "philosophy",
            "period_l2": "classical", "material_l3": "text", "character_l4": "fundamental",
            "gumilyov_level": "1", "meso_codes": "", "proposed_meso": "", "confidence": "0.5",
            "rationale": "Восстановленный доклад (исправление слипания парсера); предварительный L1, без DeepSeek-аудита.",
            "source": "carry-forward-parser-fix", "prompt_version": "carry-forward-2026-05-29", "valid": "yes",
        })
        w.writerow(row)
        print("  APPENDED", r["presentation_id"], r.get("title", "")[:50])

with open(MESO, encoding="utf-8") as f:
    meso_cols = csv.DictReader(f).fieldnames
have_m = set()
with open(MESO, encoding="utf-8") as f:
    have_m = {r["presentation_id"] for r in csv.DictReader(f)}
with open(MESO, "a", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=meso_cols)
    for r in new_rows:
        if r["presentation_id"] in have_m:
            continue
        row = {c: "" for c in meso_cols}
        row.update({"presentation_id": r["presentation_id"], "year": r.get("year", ""),
                    "series": r.get("series", ""), "title": r.get("title", ""),
                    "meso_codes": "", "proposed_meso": "", "source": "carry-forward-parser-fix", "confidence": "0.5"})
        w.writerow(row)

with open(CLS, encoding="utf-8") as f:
    total = sum(1 for _ in f) - 1
print(f"DONE classification rows={total} (manifest new={len(new_rows)})")
