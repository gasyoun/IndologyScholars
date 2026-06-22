"""Assemble provider-agnostic input datasets for the DeepSeek week.

Produces three artifacts under scratch/ that the DeepSeek runners consume once
inference is reachable. No DeepSeek/openmodel.ai call happens here.

1. scratch/classification_input.csv
   All 1362 talks (id, year, series, title) with their existing labels as the
   prior, for the k=5 self-consistency re-coding + agreement scoring.

2. scratch/program_talks.json
   Catalogue built from site_data scholars[].talks: presentation_id -> speaker,
   title, year, series, session context. Plus an index by (year, series).

3. scratch/segmentation_inputs/<video_id>.json
   For every video that has a transcript and an alignment task (needs_review,
   skip=session recording, or auto), a self-contained bundle: video meta +
   transcript pointer + candidate program talks for that year/series. This is
   the input for DeepSeek session->talk chaptering and alignment.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
ANALYTICS = ROOT / "analytics_output"
TRANSDIR = ROOT / "scratch" / "transcripts"
SEGDIR = ROOT / "scratch" / "segmentation_inputs"
CLASS_CSV = ANALYTICS / "expanded_classification_deepseek.csv"
MAPPING = ANALYTICS / "video_presentation_mapping.csv"
VIDEO_LIST = ANALYTICS / "youtube_video_list.csv"
SITE = ROOT / "site_data.json"


def series_from_label(label: str) -> str:
    low = label.lower()
    if "ограф" in low:
        return "zograf"
    if "ерих" in low:
        return "roerich"
    return ""


def build_classification_input() -> int:
    cols = ["presentation_id", "year", "series", "raw_title", "title",
            "prior_theme_l1", "prior_period_l2", "prior_material_l3",
            "prior_character_l4", "prior_gumilyov_level", "prior_confidence"]
    out = ROOT / "scratch" / "classification_input.csv"
    n = 0
    with open(CLASS_CSV, encoding="utf-8") as f, open(out, "w", encoding="utf-8", newline="") as g:
        w = csv.DictWriter(g, fieldnames=cols)
        w.writeheader()
        for r in csv.DictReader(f):
            w.writerow({
                "presentation_id": r["presentation_id"], "year": r["year"],
                "series": r["series"], "raw_title": r["raw_title"], "title": r["title"],
                "prior_theme_l1": r["theme_l1"], "prior_period_l2": r["period_l2"],
                "prior_material_l3": r["material_l3"], "prior_character_l4": r["character_l4"],
                "prior_gumilyov_level": r["gumilyov_level"], "prior_confidence": r["confidence"],
            })
            n += 1
    print(f"[1] classification_input.csv: {n} talks -> {out}")
    return n


def build_program_catalogue() -> dict:
    site = json.load(open(SITE, encoding="utf-8"))
    catalogue: dict[str, dict] = {}
    by_year_series: dict[str, list[str]] = {}
    for sch in site["scholars"]:
        speaker = sch.get("full_name_ru") or sch.get("name") or ""
        for t in sch.get("talks", []):
            pid = t.get("presentation_id")
            if not pid:
                continue
            entry = catalogue.setdefault(pid, {
                "presentation_id": pid, "title": t.get("title", ""),
                "year": t.get("year", ""), "series": t.get("series", ""),
                "session_title": t.get("session_title", ""),
                "time_interval": t.get("time_interval", ""),
                "order_in_session": t.get("order_in_session", ""),
                "total_in_session": t.get("total_in_session", ""),
                "speakers": [],
            })
            if speaker and speaker not in entry["speakers"]:
                entry["speakers"].append(speaker)
            key = f"{t.get('year','')}|{(t.get('series','') or '').lower()}"
            by_year_series.setdefault(key, [])
            if pid not in by_year_series[key]:
                by_year_series[key].append(pid)
    out = ROOT / "scratch" / "program_talks.json"
    out.write_text(json.dumps({"talks": catalogue, "by_year_series": by_year_series},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[2] program_talks.json: {len(catalogue)} talks, "
          f"{len(by_year_series)} year/series buckets -> {out}")
    return {"talks": catalogue, "by_year_series": by_year_series}


def build_segmentation_inputs(catalogue: dict) -> int:
    SEGDIR.mkdir(parents=True, exist_ok=True)
    have = {os.path.splitext(f)[0] for f in os.listdir(TRANSDIR) if f.endswith(".json")
            and f not in ("index.csv",)}
    vid_series = {}
    for r in csv.DictReader(open(VIDEO_LIST, encoding="utf-8")):
        vid_series.setdefault(r["video_id"], series_from_label(r.get("playlist_label", "")))

    talks = catalogue["talks"]
    bys = catalogue["by_year_series"]
    index_rows = []
    n = 0
    for r in csv.DictReader(open(MAPPING, encoding="utf-8")):
        vid = r["video_id"]
        if vid not in have:
            continue
        status = r["status"]
        if status not in ("needs_review", "skip", "auto"):
            continue
        task = ("segment_session" if status == "skip"
                else "align_single" if status == "needs_review" else "verify_match")
        year = r.get("year", "")
        series = vid_series.get(vid, "")
        # Candidate talks: that year+series, else whole year (both series).
        cand_ids = bys.get(f"{year}|{series}", []) if series else []
        if not cand_ids:
            cand_ids = [pid for k, ids in bys.items() if k.startswith(f"{year}|") for pid in ids]
        candidates = [{"presentation_id": pid, "title": talks[pid]["title"],
                       "speakers": talks[pid]["speakers"],
                       "session_title": talks[pid]["session_title"],
                       "time_interval": talks[pid]["time_interval"]}
                      for pid in cand_ids if pid in talks]
        tmeta = json.load(open(TRANSDIR / f"{vid}.json", encoding="utf-8"))
        bundle = {
            "video_id": vid, "video_url": r.get("video_url", ""),
            "video_title": r.get("video_title", ""), "year": year, "series": series,
            "mapping_status": status, "task_type": task,
            "similarity": r.get("similarity", ""), "title_hint": r.get("title_hint", ""),
            "speaker_hint": r.get("speaker_hint", ""),
            "transcript": {"path": f"scratch/transcripts/{vid}.json",
                           "n_segments": tmeta["n_segments"],
                           "duration_min_approx": round(tmeta["duration_sec_approx"] / 60, 1)},
            "candidate_talks": candidates,
        }
        (SEGDIR / f"{vid}.json").write_text(
            json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
        index_rows.append({"video_id": vid, "year": year, "series": series,
                           "task_type": task, "n_candidates": len(candidates),
                           "transcript_min": bundle["transcript"]["duration_min_approx"],
                           "est_tokens": int(tmeta["n_chars"] / 2.5)})
        n += 1

    with open(SEGDIR / "index.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["video_id", "year", "series", "task_type",
                                          "n_candidates", "transcript_min", "est_tokens"])
        w.writeheader()
        w.writerows(sorted(index_rows, key=lambda r: (r["task_type"], -r["est_tokens"])))

    from collections import Counter
    by_task = Counter(r["task_type"] for r in index_rows)
    print(f"[3] segmentation_inputs/: {n} bundles -> {SEGDIR}")
    for k in sorted(by_task):
        print(f"      {k}: {by_task[k]}")
    return n


def main() -> None:
    build_classification_input()
    cat = build_program_catalogue()
    build_segmentation_inputs(cat)
    print("\nProvider-agnostic prep complete. Runners can fire once inference is reachable.")


if __name__ == "__main__":
    main()
