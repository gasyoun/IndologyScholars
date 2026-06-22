"""Caption inventory for collected YouTube recordings.

Reads analytics_output/youtube_video_list.csv and, for every unique video_id,
asks yt-dlp which subtitle / automatic-caption languages exist. Writes
analytics_output/caption_inventory.csv and prints a summary that sizes the
Whisper bottleneck (how many videos have NO pullable Russian captions).

This step touches YouTube only; it does not use DeepSeek/openmodel.ai.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "analytics_output" / "youtube_video_list.csv"
OUT = ROOT / "analytics_output" / "caption_inventory.csv"


def is_ru(lang: str) -> bool:
    return lang.lower().startswith("ru")


def probe(video_id: str) -> dict:
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        proc = subprocess.run(
            ["yt-dlp", "--skip-download", "--no-warnings", "--dump-json", url],
            capture_output=True, text=True, encoding="utf-8", timeout=90,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return {"error": (proc.stderr or "no output").strip().splitlines()[-1][:120]}
        d = json.loads(proc.stdout)
        manual = sorted((d.get("subtitles") or {}).keys())
        auto = sorted((d.get("automatic_captions") or {}).keys())
        return {
            "duration_sec": d.get("duration") or "",
            "manual_langs": ";".join(manual),
            "auto_langs": ";".join(auto),
            "has_manual_ru": any(is_ru(x) for x in manual),
            "has_auto_ru": any(is_ru(x) for x in auto),
            "error": "",
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"[:120]}


def main() -> None:
    seen: dict[str, str] = {}
    with open(SRC, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vid = (row.get("video_id") or "").strip()
            if vid and vid not in seen:
                seen[vid] = (row.get("year") or "").strip()

    total = len(seen)
    print(f"Probing {total} unique videos...", flush=True)
    fields = ["video_id", "year", "duration_sec", "has_manual_ru", "has_auto_ru",
              "manual_langs", "auto_langs", "error"]
    n_manual_ru = n_auto_ru = n_none = n_err = 0
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, (vid, year) in enumerate(seen.items(), 1):
            r = probe(vid)
            row = {"video_id": vid, "year": year, "duration_sec": r.get("duration_sec", ""),
                   "has_manual_ru": r.get("has_manual_ru", ""), "has_auto_ru": r.get("has_auto_ru", ""),
                   "manual_langs": r.get("manual_langs", ""), "auto_langs": r.get("auto_langs", ""),
                   "error": r.get("error", "")}
            w.writerow(row)
            f.flush()
            if r.get("error"):
                n_err += 1
            elif r.get("has_manual_ru"):
                n_manual_ru += 1
            elif r.get("has_auto_ru"):
                n_auto_ru += 1
            else:
                n_none += 1
            if i % 10 == 0 or i == total:
                print(f"  {i}/{total}  manual_ru={n_manual_ru} auto_ru={n_auto_ru} "
                      f"no_ru={n_none} err={n_err}", flush=True)

    print("\n=== CAPTION INVENTORY SUMMARY ===")
    print(f"total videos      : {total}")
    print(f"manual RU subs    : {n_manual_ru}")
    print(f"auto RU captions  : {n_auto_ru}")
    print(f"NO RU captions    : {n_none}   <- these need Whisper")
    print(f"errors            : {n_err}")
    print(f"written: {OUT}")


if __name__ == "__main__":
    main()
