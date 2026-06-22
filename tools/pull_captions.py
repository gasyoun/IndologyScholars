"""Pull Russian auto-caption tracks for collected YouTube recordings.

Reads analytics_output/caption_inventory.csv and downloads the Russian
automatic-caption track (VTT, with timestamps) for every video flagged
has_auto_ru, plus retries the videos that errored during inventory. Captions
land in scratch/youtube_captions/<id>.<lang>.vtt with a manifest CSV.

Timestamps are preserved deliberately: DeepSeek will use them to segment
multi-hour session recordings into per-talk chapters aligned to the programme.

This step touches YouTube only; it does not use DeepSeek/openmodel.ai.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "analytics_output" / "caption_inventory.csv"
OUTDIR = ROOT / "scratch" / "youtube_captions"
MANIFEST = OUTDIR / "manifest.csv"


def existing_vtt(video_id: str) -> Path | None:
    hits = sorted(OUTDIR.glob(f"{video_id}.*.vtt"))
    return hits[0] if hits else None


def pull(video_id: str) -> dict:
    """Download the RU auto-caption track for one video. Idempotent."""
    prior = existing_vtt(video_id)
    if prior is not None and prior.stat().st_size > 0:
        return {"status": "cached", "file": prior.name, "bytes": prior.stat().st_size}
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        proc = subprocess.run(
            ["yt-dlp", "--skip-download", "--no-warnings", "--write-auto-subs",
             "--sub-langs", "ru.*", "--sub-format", "vtt",
             "-o", str(OUTDIR / "%(id)s.%(ext)s"), url],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        f = existing_vtt(video_id)
        if f is not None and f.stat().st_size > 0:
            return {"status": "pulled", "file": f.name, "bytes": f.stat().st_size}
        tail = (proc.stderr or proc.stdout or "no caption track").strip().splitlines()
        return {"status": "no_file", "file": "", "bytes": 0,
                "note": (tail[-1][:120] if tail else "")}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "file": "", "bytes": 0}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "file": "", "bytes": 0, "note": f"{type(exc).__name__}: {exc}"[:120]}


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    targets: list[dict] = []
    with open(INV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            has_ru = (row.get("has_auto_ru") or "").strip().lower() == "true"
            errored = bool((row.get("error") or "").strip())
            if has_ru or errored:
                targets.append({"video_id": row["video_id"], "year": row.get("year", ""),
                                "reason": "auto_ru" if has_ru else "retry_error"})

    total = len(targets)
    print(f"Pulling RU captions for {total} videos "
          f"({sum(t['reason']=='auto_ru' for t in targets)} flagged, "
          f"{sum(t['reason']=='retry_error' for t in targets)} retries)...", flush=True)

    counts: dict[str, int] = {}
    with open(MANIFEST, "w", encoding="utf-8", newline="") as mf:
        w = csv.DictWriter(mf, fieldnames=["video_id", "year", "reason", "status", "file", "bytes", "note"])
        w.writeheader()
        for i, t in enumerate(targets, 1):
            r = pull(t["video_id"])
            row = {"video_id": t["video_id"], "year": t["year"], "reason": t["reason"],
                   "status": r["status"], "file": r.get("file", ""), "bytes": r.get("bytes", 0),
                   "note": r.get("note", "")}
            w.writerow(row)
            mf.flush()
            counts[r["status"]] = counts.get(r["status"], 0) + 1
            if i % 10 == 0 or i == total:
                got = counts.get("pulled", 0) + counts.get("cached", 0)
                print(f"  {i}/{total}  have={got}  no_file={counts.get('no_file',0)}  "
                      f"timeout={counts.get('timeout',0)}  error={counts.get('error',0)}", flush=True)

    print("\n=== CAPTION PULL SUMMARY ===")
    for k in sorted(counts):
        print(f"{k:10s}: {counts[k]}")
    have = counts.get("pulled", 0) + counts.get("cached", 0)
    print(f"transcripts available: {have}")
    print(f"output dir: {OUTDIR}")
    print(f"manifest:   {MANIFEST}")


if __name__ == "__main__":
    main()
