"""Parse pulled YouTube VTT auto-captions into timestamped transcript JSON.

YouTube auto-captions use a rolling-window format: every cue repeats the prior
line plus a new line carrying inline <hh:mm:ss.mmm><c>word</c> timing tags. The
fresh text is exactly the tagged lines; the untagged lines are carried-over
duplicates. We keep the tagged lines, strip tags, and attach each to its cue
start time, yielding a clean, de-duplicated, timestamped transcript.

Input : scratch/youtube_captions/<id>.ru-orig.vtt (preferred) or <id>.ru.vtt
Output: scratch/transcripts/<id>.json  -> {video_id, segments:[{t, text}], ...}
        scratch/transcripts/index.csv  -> per-video size/token estimates
        scratch/transcripts/whisper_queue.csv -> videos with no caption track

Provider-agnostic prep: no DeepSeek/openmodel.ai involved. The segments feed the
DeepSeek session->talk chaptering step once inference is reachable.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CAPDIR = ROOT / "scratch" / "youtube_captions"
OUTDIR = ROOT / "scratch" / "transcripts"
MANIFEST = CAPDIR / "manifest.csv"

TS = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})\.(\d{3})")
INLINE_TS = re.compile(r"<\d{2}:\d{2}:\d{2}\.\d{3}>")
TAG = re.compile(r"<[^>]+>")


def to_sec(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def strip_tags(line: str) -> str:
    return re.sub(r"\s+", " ", TAG.sub("", line)).strip()


def parse_vtt(path: Path) -> list[dict]:
    segments: list[dict] = []
    start = None
    last_text = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TS.search(raw)
        if m:
            start = to_sec(*m.groups()[:4])
            continue
        if start is None or not raw.strip():
            continue
        # Only lines that carried inline word-timing tags are "new" speech.
        if INLINE_TS.search(raw):
            text = strip_tags(raw)
            if text and text != last_text:
                segments.append({"t": round(start, 2), "text": text})
                last_text = text
    return segments


def pick_vtt(video_id: str) -> Path | None:
    orig = CAPDIR / f"{video_id}.ru-orig.vtt"
    if orig.exists():
        return orig
    alt = CAPDIR / f"{video_id}.ru.vtt"
    return alt if alt.exists() else None


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    # Distinct video ids that produced a caption file, from the manifest.
    pulled: list[dict] = []
    whisper_queue: list[dict] = []
    with open(MANIFEST, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["status"] in ("pulled", "cached"):
                pulled.append(row)
            elif row["status"] in ("no_file", "timeout", "error"):
                whisper_queue.append(row)

    seen: set[str] = set()
    index_rows: list[dict] = []
    total_chars = 0
    for row in pulled:
        vid = row["video_id"]
        if vid in seen:
            continue
        seen.add(vid)
        vtt = pick_vtt(vid)
        if vtt is None:
            continue
        segments = parse_vtt(vtt)
        text_plain = " ".join(s["text"] for s in segments)
        n_chars = len(text_plain)
        total_chars += n_chars
        dur = segments[-1]["t"] if segments else 0.0
        out = {"video_id": vid, "year": row.get("year", ""), "lang": "ru",
               "duration_sec_approx": dur, "n_segments": len(segments),
               "n_chars": n_chars, "segments": segments, "text_plain": text_plain}
        (OUTDIR / f"{vid}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        index_rows.append({"video_id": vid, "year": row.get("year", ""),
                           "n_segments": len(segments), "n_chars": n_chars,
                           "est_tokens": int(n_chars / 2.5),
                           "duration_min_approx": round(dur / 60, 1)})

    with open(OUTDIR / "index.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["video_id", "year", "n_segments", "n_chars",
                                          "est_tokens", "duration_min_approx"])
        w.writeheader()
        w.writerows(sorted(index_rows, key=lambda r: -r["n_chars"]))

    with open(OUTDIR / "whisper_queue.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["video_id", "year", "reason", "status", "note"])
        w.writeheader()
        for r in whisper_queue:
            w.writerow({"video_id": r["video_id"], "year": r.get("year", ""),
                        "reason": r.get("reason", ""), "status": r["status"],
                        "note": r.get("note", "")})

    est_tokens = int(total_chars / 2.5)
    print("=== TRANSCRIPT PARSE SUMMARY ===")
    print(f"transcripts written : {len(index_rows)}  -> {OUTDIR}")
    print(f"total chars         : {total_chars:,}")
    print(f"est. total tokens   : ~{est_tokens:,}  (rough, Russian)")
    print(f"whisper queue       : {len(whisper_queue)}  -> whisper_queue.csv")
    if index_rows:
        big = max(index_rows, key=lambda r: r["n_chars"])
        print(f"largest transcript  : {big['video_id']}  {big['duration_min_approx']} min, "
              f"~{big['est_tokens']:,} tokens  (will need chunking)")


if __name__ == "__main__":
    main()
