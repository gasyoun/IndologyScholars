"""
Fuzzy-match YouTube video titles against Zograf presentations in conferences.db.

Inputs:
  - analytics_output/youtube_video_list.csv   (from youtube_fetch_videos.py)
  - conferences.db                            (DB built by build_and_populate_db.py)

Output:
  - analytics_output/video_presentation_mapping.csv

Columns in output: video_id, video_url, video_title, year, title_hint,
speaker_hint, similarity (0..1), status, presentation_id_snapshot

The mapping is keyed by *natural* attributes (year + title_hint + speaker_hint),
NOT by presentation_id. This matters because build_and_populate_db.py
currently assigns random UUIDs to presentations on each rebuild — any
external CSV keyed on presentation_id is invalidated on every CI run.
The hints survive rebuilds; ingestion re-matches them against the current DB.

The presentation_id_snapshot column is informational only — it records
which presentation the matcher saw at match time, useful for auditing but
not used by the ingestion step.

status values:
  - auto              similarity >= AUTO_THRESHOLD; safe to ingest as-is
  - needs_review      below threshold; reviewer should confirm or correct
  - manual_confirmed  set by reviewer after checking — ingestion will pick this up
  - skip              set by reviewer for off-topic videos (opening remarks etc.)

The build pipeline (build_and_populate_db.py) re-fuzzy-matches each
auto/manual_confirmed row against the current DB at build time and
inserts the result into the media table.

Usage:
    python scratch/youtube_match_videos.py
"""

import csv
import difflib
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from publication_helpers import normalize_time_interval

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

VIDEO_CSV = Path("analytics_output/youtube_video_list.csv")
MAPPING_CSV = Path("analytics_output/video_presentation_mapping.csv")
DB_PATH = "conferences.db"
AUTO_THRESHOLD = 0.55  # ratio above which we accept without review

# Patterns identifying videos that are NOT individual talks (full-session
# recordings, deleted entries, private entries). These get status=skip so
# they don't clog the needs_review queue.
# Catches:
#   "XLIV Зографские чтения, 23.05.2023, 14.00 – 17.15"    (numeric date+time)
#   "XLI Зографские чтения (13 мая 2020 г.), ч. 2"          (Russian month name + часть)
#   "XLV ЗОГРАФСКИЕ ЧТЕНИЯ, 17 мая 2024 г. Часть 1"        (Russian month name + Часть)
#   "Институт Восточных Рукописей РАН. 1-ый день, ..."     (whole-day recording)
SESSION_RECORDING_RES = [
    re.compile(r"^(?:XL+|XLI+|XLV+|XLVI*|XLVII)\b.*\d{1,2}[.\-:]\d{1,2}", re.IGNORECASE),
    re.compile(r"(?:XL+|XLI+|XLV+|XLVI*|XLVII)\b.*зограф", re.IGNORECASE),
    re.compile(r"\bзограф.*\b(ч\.|часть|часов|день)\s*\d", re.IGNORECASE),
    re.compile(r"^Институт\s+Восточных\s+Рукописей.*день", re.IGNORECASE),
]


def is_noise_title(title):
    """True if the video is obvious non-talk content."""
    if not title:
        return True, "empty_title"
    t = title.strip()
    if t == "Deleted video":
        return True, "deleted"
    if "Private video" in t:
        return True, "private"
    for pat in SESSION_RECORDING_RES:
        if pat.search(t):
            return True, "session_recording"
    return False, ""


def normalize(text):
    """Lowercase, strip punctuation, collapse whitespace. Cyrillic-safe."""
    if not text:
        return ""
    t = text.lower()
    # Strip common YouTube boilerplate
    t = re.sub(r"\b(зографские|зограф|чтения|conference|2023|2024|2025|2026)\b", " ", t, flags=re.IGNORECASE)
    # Replace ё with е (often missing in titles)
    t = t.replace("ё", "е")
    # Remove non-letter punctuation except internal hyphens
    t = re.sub(r"[^\w\s\-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def load_zograf_presentations():
    """Return list of dicts for ALL Zograf presentations across all years."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT pr.presentation_id, pr.title, e.year,
               GROUP_CONCAT(pers.display_name, ' / ') AS speakers
        FROM presentation pr
        JOIN session s ON s.session_id = pr.session_id
        JOIN event_day_venue edv ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN event_day ed ON ed.event_day_id = edv.event_day_id
        JOIN event e ON e.event_id = ed.event_id
        JOIN presentation_person pp ON pp.presentation_id = pr.presentation_id
        JOIN person pers ON pers.person_id = pp.person_id
        WHERE e.event_series_id = 1
        GROUP BY pr.presentation_id
    """).fetchall()
    conn.close()
    return [{"presentation_id": pid, "title": title, "year": year, "speakers": speakers}
            for pid, title, year, speakers in rows]


def best_match(video_title, candidates):
    """Return (best_candidate, similarity) — candidates is list of presentation dicts."""
    if not candidates:
        return None, 0.0
    norm_video = normalize(video_title)
    best = None
    best_ratio = 0.0
    for cand in candidates:
        # Build comparison string: title + speaker name (boost when speaker mentioned in video title)
        title_norm = normalize(cand["title"])
        speaker_norm = normalize(cand.get("speakers") or "")
        # Pure title similarity
        r_title = difflib.SequenceMatcher(None, norm_video, title_norm).ratio()
        # Title+speaker similarity (sometimes YouTube title is "Lastname. Talk title")
        combined_norm = (title_norm + " " + speaker_norm).strip()
        r_combined = difflib.SequenceMatcher(None, norm_video, combined_norm).ratio()
        # Use the better of the two
        r = max(r_title, r_combined)
        if r > best_ratio:
            best_ratio = r
            best = cand
    return best, best_ratio


def main():
    if not VIDEO_CSV.exists():
        print(f"ERROR: {VIDEO_CSV} not found. Run youtube_fetch_videos.py first.", file=sys.stderr)
        sys.exit(1)

    videos = []
    with VIDEO_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            videos.append(row)

    presentations = load_zograf_presentations()
    by_year = defaultdict(list)
    for p in presentations:
        by_year[p["year"]].append(p)
    print(f"Loaded {len(videos)} videos and {len(presentations)} Zograf presentations across years {sorted(by_year.keys())}")

    # Strategy: try the video's nominal year first; if no good match, fall back
    # to searching all Zograf years (some playlists mix multi-year content).
    # Auto-skip obvious noise (deleted/private/session-recording videos).
    out_rows = []
    counts = {"auto": 0, "needs_review": 0, "skip": 0}
    all_presentations = presentations
    for v in videos:
        video_title = normalize_time_interval(v.get("video_title", ""))
        # Noise filter — short-circuit before any fuzzy matching
        noise, reason = is_noise_title(video_title)
        if noise:
            counts["skip"] += 1
            out_rows.append({
                "video_id": v["video_id"],
                "video_url": v["video_url"],
                "video_title": video_title,
                "year": v.get("year", ""),
                "title_hint": "",
                "speaker_hint": f"(auto-skipped: {reason})",
                "similarity": 0.0,
                "status": "skip",
                "presentation_id_snapshot": "",
            })
            continue

        year_str = v.get("year", "")
        primary_year = int(year_str) if year_str.isdigit() else None

        # Pass 1: nominal year
        match, ratio = (None, 0.0)
        if primary_year is not None:
            match, ratio = best_match(video_title, by_year.get(primary_year, []))

        # Pass 2: cross-year fallback if nominal year didn't produce a confident hit
        used_year = primary_year
        if ratio < AUTO_THRESHOLD:
            xmatch, xratio = best_match(video_title, all_presentations)
            if xratio > ratio:
                match, ratio = xmatch, xratio
                used_year = (xmatch or {}).get("year") if xmatch else primary_year

        status = "auto" if ratio >= AUTO_THRESHOLD else "needs_review"
        counts[status] = counts.get(status, 0) + 1
        out_rows.append({
            "video_id": v["video_id"],
            "video_url": v["video_url"],
            "video_title": video_title,
            "year": str(used_year) if used_year is not None else "",
            "title_hint": (match or {}).get("title", ""),
            "speaker_hint": (match or {}).get("speakers", ""),
            "similarity": round(ratio, 3),
            "status": status,
            "presentation_id_snapshot": (match or {}).get("presentation_id", ""),
        })

    # Sort: needs_review first (worst similarity first), then auto (best last)
    out_rows.sort(key=lambda r: (0 if r["status"] != "auto" else 1, r["similarity"]))

    MAPPING_CSV.parent.mkdir(parents=True, exist_ok=True)
    with MAPPING_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"\nWrote {MAPPING_CSV}")
    print(f"  auto (similarity ≥ {AUTO_THRESHOLD}): {counts.get('auto', 0)}")
    print(f"  needs_review: {counts.get('needs_review', 0)}")
    print(f"  skip (noise: deleted/private/session-recording): {counts.get('skip', 0)}")
    print("\nReview the needs_review rows. Set status to 'manual_confirmed' to accept the match,")
    print("'skip' to drop the video, or replace presentation_id with the correct value.")
    print("Then commit the CSV; the build pipeline picks up 'auto' and 'manual_confirmed' rows.")


if __name__ == "__main__":
    main()
