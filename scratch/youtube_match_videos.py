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
    re.compile(r"^(?:XL(?:IV)?+|XLI+|XLV+|XLVI*|XLVII)\b.*\d{1,2}[.\-:]\d{1,2}", re.IGNORECASE),
    re.compile(r"(?:XL(?:IV)?+|XLI+|XLV+|XLVI*|XLVII)\b.*зограф", re.IGNORECASE),
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


def extract_speaker_from_title(title: str) -> str:
    """Try to extract speaker name from YouTube video title.
    
    Common patterns: "Фамилия И.О. Название" or "И.О. Фамилия. Название"
    """
    # Pattern: Lastname (possibly with initials) followed by period and title
    # "Корнеева Н.А. Буддийская иконография..."
    # "Н.А. Корнеева Буддийская иконография..."
    m = re.match(
        r"^([А-ЯЁ][а-яё]*(?:\s+[А-ЯЁ]\.)*\s+[А-ЯЁ][а-яё]+)\.",
        title, re.IGNORECASE
    )
    if m:
        return normalize(m.group(1))
    m = re.match(
        r"^((?:[А-ЯЁ]\.\s*)+[А-ЯЁ][а-яё]+)\.",
        title, re.IGNORECASE
    )
    if m:
        return normalize(m.group(1))
    return ""


def extract_year_from_published(published_at: str) -> int | None:
    """Extract year from ISO datetime string."""
    if not published_at:
        return None
    try:
        # "2024-05-15T10:30:00Z" → 2024
        return int(published_at[:4])
    except (ValueError, IndexError):
        return None


def keyword_overlap(text1: str, text2: str) -> float:
    """Jaccard similarity on content words (length >= 4)."""
    words1 = {w for w in normalize(text1).split() if len(w) >= 4}
    words2 = {w for w in normalize(text2).split() if len(w) >= 4}
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union) if union else 0.0


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


def best_match(video_title, candidates, video_year=None):
    """Return (best_candidate, similarity) — candidates is list of presentation dicts.
    
    Uses multi-signal scoring: title similarity + speaker match + year alignment + keyword overlap.
    """
    if not candidates:
        return None, 0.0
    norm_video = normalize(video_title)
    video_speaker = extract_speaker_from_title(video_title)
    best = None
    best_score = 0.0
    for cand in candidates:
        title_norm = normalize(cand["title"])
        speaker_norm = normalize(cand.get("speakers") or "")
        # Title similarity
        r_title = difflib.SequenceMatcher(None, norm_video, title_norm).ratio()
        combined_norm = (title_norm + " " + speaker_norm).strip()
        r_combined = difflib.SequenceMatcher(None, norm_video, combined_norm).ratio()
        title_sim = max(r_title, r_combined)
        # Speaker match (binary)
        speaker_match = 1.0 if (video_speaker and video_speaker in speaker_norm) else 0.0
        # Year alignment
        cand_year = cand.get("year", 0)
        year_score = 1.0 if (video_year and cand_year == video_year) else 0.5 if (video_year and abs(cand_year - video_year) <= 2) else 0.0
        # Keyword overlap
        kw_sim = keyword_overlap(video_title, cand["title"])
        # Composite score
        composite = 0.45 * title_sim + 0.25 * speaker_match + 0.15 * year_score + 0.15 * kw_sim
        if composite > best_score:
            best_score = composite
            best = cand
    return best, best_score


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
    # NEW: use published_at as year upper bound, multi-signal scoring, dedup by video_id.
    out_rows = []
    counts = {"auto": 0, "needs_review": 0, "skip": 0}
    all_presentations = presentations
    seen_video_ids = {}  # video_id → (best_row, best_score)
    best_threshold = 0.50  # new lower threshold with multi-signal

    for v in videos:
        video_title = normalize_time_interval(v.get("video_title", ""))

        # Noise filter
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

        # published_at constraint: video can't be for a conference AFTER it was published
        pub_year = extract_year_from_published(v.get("published_at", ""))
        if pub_year and primary_year and primary_year > pub_year:
            # The nominal year is after publish date — fall back to pub_year
            primary_year = pub_year

        # Pass 1: nominal year
        match, score = (None, 0.0)
        if primary_year is not None:
            match, score = best_match(video_title, by_year.get(primary_year, []), primary_year)

        # Pass 2: cross-year fallback
        used_year = primary_year
        if score < best_threshold:
            xmatch, xscore = best_match(video_title, all_presentations, None)
            if xscore > score:
                match, score = xmatch, xscore
                used_year = (xmatch or {}).get("year") if xmatch else primary_year

        status = "auto" if score >= best_threshold else "needs_review"
        row = {
            "video_id": v["video_id"],
            "video_url": v["video_url"],
            "video_title": video_title,
            "year": str(used_year) if used_year is not None else "",
            "title_hint": (match or {}).get("title", ""),
            "speaker_hint": (match or {}).get("speakers", ""),
            "similarity": round(score, 3),
            "status": status,
            "presentation_id_snapshot": (match or {}).get("presentation_id", ""),
        }

        # Deduplication: keep best match per video_id
        vid = v["video_id"]
        if vid in seen_video_ids:
            prev = seen_video_ids[vid]
            if score > prev[1]:
                seen_video_ids[vid] = (row, score)
                out_rows = [r for r in out_rows if r["video_id"] != vid]
                out_rows.append(row)
            # else: discard this lower-score duplicate
            continue

        seen_video_ids[vid] = (row, score)
        counts[status] = counts.get(status, 0) + 1
        out_rows.append(row)

    # Sort: needs_review first (worst similarity first), then auto (best last)
    out_rows.sort(key=lambda r: (0 if r["status"] != "auto" else 1, r["similarity"]))

    MAPPING_CSV.parent.mkdir(parents=True, exist_ok=True)
    with MAPPING_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"\nWrote {MAPPING_CSV}")
    print(f"  auto (score >= {best_threshold}): {counts.get('auto', 0)}")
    print(f"  needs_review: {counts.get('needs_review', 0)}")
    print(f"  skip (noise): {counts.get('skip', 0)}")
    print("\nReview the needs_review rows. Set status to 'manual_confirmed' to accept the match,")
    print("'skip' to drop the video, or replace presentation_id with the correct value.")
    print("Then commit the CSV; the build pipeline picks up 'auto' and 'manual_confirmed' rows.")


if __name__ == "__main__":
    main()
