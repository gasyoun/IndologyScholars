"""Align YouTube recordings to programme talks, and chapter session blocks.

Consumes the bundles built by tools/build_deepseek_inputs.py:
  - align_single  (needs_review): pick the single best-matching talk.
  - verify_match  (auto)        : confirm or correct the existing match.
  - segment_session (skip)      : a multi-hour block covering many talks ->
                                  chapter it into per-talk segments with
                                  timestamps, aligned to candidate talks.

Output is a REVIEW QUEUE, never a silent publish: every row carries a
confidence and an inline (?) marker when uncertain, status defaults to 'todo'.
High-confidence rows are tagged 'auto' so a curator can fast-path them.

Run on a clean-egress host (smoke test first):
    python tools/openmodel_client.py --selftest
    python tools/run_video_segmentation.py --limit 3        # trial
    python tools/run_video_segmentation.py --task segment_session

Output: analytics_output/video_segment_candidates.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from openmodel_client import chat_json, GatewayError  # noqa: E402

SEGDIR = ROOT / "scratch" / "segmentation_inputs"
TRANSDIR = ROOT / "scratch" / "transcripts"
OUT = ROOT / "analytics_output" / "video_segment_candidates.csv"

AUTO_CONF = 0.80          # >= this -> status 'auto' (fast-path), else 'todo'
CHUNK_SEGMENTS = 160      # transcript segments per session-chunk call
CHUNK_OVERLAP = 15        # carried-over segments so boundaries are not split

FIELDS = ["video_id", "video_url", "year", "series", "task_type", "segment_index",
          "start_sec", "matched_presentation_id", "speaker_guess", "title_guess",
          "confidence", "marked", "status", "evidence"]

ALIGN_SYS = """Ты сопоставляешь аудиозапись одного доклада с программой конференции.
На входе: начало расшифровки (русский) и список возможных докладов (id, докладчик, название).
Определи, какому доклгу из списка соответствует запись. Если совпадения нет — верни пустой id.
Опирайся на названного докладчика, тему и формулировки во вступлении.
Верни строго JSON без markdown:
{"presentation_id":"<id или пусто>","speaker":"","title":"","confidence":0.0,"evidence":"<краткая цитата-основание>"}"""

SEGMENT_SYS = """Запись содержит несколько докладов подряд (сессия конференции).
На входе: фрагмент расшифровки с таймкодами в секундах и список докладов программы (id, докладчик, название).
Найди начала отдельных докладов в этом фрагменте (смена докладчика, объявление названия, слова ведущего).
Для каждого найденного доклада укажи время начала (start_sec из таймкодов), докладчика, название,
наиболее вероятный presentation_id из списка (или пусто) и уверенность.
Не выдумывай доклады: если фрагмент — продолжение одного выступления, верни пустой список.
Верни строго JSON без markdown:
{"segments":[{"start_sec":0,"speaker":"","title":"","presentation_id":"","confidence":0.0,"evidence":""}]}"""


def transcript_lines(segments: list[dict], lo: int, hi: int) -> str:
    out = []
    for s in segments[lo:hi]:
        t = int(s["t"])
        out.append(f"[{t//60:02d}:{t%60:02d}|{t}s] {s['text']}")
    return "\n".join(out)


def candidate_block(cands: list[dict]) -> str:
    rows = []
    for c in cands:
        sp = ", ".join(c.get("speakers", [])) or "?"
        rows.append(f'- id={c["presentation_id"]}; speaker={sp}; title="{c["title"]}"')
    return "\n".join(rows)


def align_single(bundle: dict, segments: list[dict]) -> list[dict]:
    head = transcript_lines(segments, 0, min(len(segments), 90))  # ~first minutes
    user = (f'Начало записи:\n{head}\n\nВозможные доклады:\n{candidate_block(bundle["candidate_talks"])}\n\n'
            f'Подсказки: title_hint="{bundle.get("title_hint","")}"; speaker_hint="{bundle.get("speaker_hint","")}"')
    res = chat_json([{"role": "system", "content": ALIGN_SYS},
                     {"role": "user", "content": user}], temperature=0.0, max_tokens=600)
    conf = float(res.get("confidence", 0) or 0)
    return [{"segment_index": 0, "start_sec": 0,
             "matched_presentation_id": str(res.get("presentation_id", "") or ""),
             "speaker_guess": res.get("speaker", ""), "title_guess": res.get("title", ""),
             "confidence": round(conf, 3), "evidence": str(res.get("evidence", ""))[:300]}]


def segment_session(bundle: dict, segments: list[dict]) -> list[dict]:
    cand = candidate_block(bundle["candidate_talks"])
    found: list[dict] = []
    seen_ids: set[str] = set()
    idx = 0
    start = 0
    while start < len(segments):
        hi = min(len(segments), start + CHUNK_SEGMENTS)
        chunk = transcript_lines(segments, start, hi)
        user = f"Фрагмент расшифровки:\n{chunk}\n\nДоклады программы:\n{cand}"
        try:
            res = chat_json([{"role": "system", "content": SEGMENT_SYS},
                             {"role": "user", "content": user}], temperature=0.0, max_tokens=1500)
        except (ValueError, KeyError):
            res = {"segments": []}
        for seg in res.get("segments", []) if isinstance(res, dict) else []:
            pid = str(seg.get("presentation_id", "") or "")
            try:
                start_sec = int(float(seg.get("start_sec", 0) or 0))
            except (TypeError, ValueError):
                start_sec = 0
            key = pid or f"t{start_sec}"
            if key in seen_ids:
                continue
            seen_ids.add(key)
            found.append({"segment_index": idx, "start_sec": start_sec,
                          "matched_presentation_id": pid,
                          "speaker_guess": seg.get("speaker", ""), "title_guess": seg.get("title", ""),
                          "confidence": round(float(seg.get("confidence", 0) or 0), 3),
                          "evidence": str(seg.get("evidence", ""))[:300]})
            idx += 1
        if hi >= len(segments):
            break
        start = hi - CHUNK_OVERLAP
    return found


def done_videos() -> set[str]:
    if not OUT.exists():
        return set()
    with open(OUT, encoding="utf-8") as f:
        return {r["video_id"] for r in csv.DictReader(f)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="first N bundles only")
    ap.add_argument("--task", choices=["align_single", "verify_match", "segment_session"],
                    help="process only one task type")
    ap.add_argument("--restart", action="store_true", help="ignore existing output rows")
    args = ap.parse_args()

    bundles = sorted(p for p in SEGDIR.glob("*.json"))
    already = set() if args.restart else done_videos()
    work = []
    for p in bundles:
        b = json.loads(p.read_text(encoding="utf-8"))
        if args.task and b["task_type"] != args.task:
            continue
        if b["video_id"] in already:
            continue
        work.append(b)
    if args.limit:
        work = work[:args.limit]
    print(f"bundles to process: {len(work)} (skipping {len(already)} done)")

    mode = "w" if (args.restart or not OUT.exists()) else "a"
    with open(OUT, mode, encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if mode == "w":
            w.writeheader()
        for i, b in enumerate(work, 1):
            tmeta = json.loads((TRANSDIR / f'{b["video_id"]}.json').read_text(encoding="utf-8"))
            segments = tmeta["segments"]
            try:
                rows = (segment_session(b, segments) if b["task_type"] == "segment_session"
                        else align_single(b, segments))
            except GatewayError as exc:
                raise SystemExit(f"Gateway rejected request ({exc}). Verify endpoint on this "
                                 "host: python tools/openmodel_client.py --selftest")
            for r in rows:
                conf = r["confidence"]
                r.update({"video_id": b["video_id"], "video_url": b.get("video_url", ""),
                          "year": b["year"], "series": b["series"], "task_type": b["task_type"],
                          "status": "auto" if conf >= AUTO_CONF else "todo",
                          "marked": (r["matched_presentation_id"] or "NO_MATCH")
                          + ("" if conf >= AUTO_CONF else "(?)")})
                w.writerow(r)
            f.flush()
            print(f"[{i}/{len(work)}] {b['video_id']} {b['task_type']}: {len(rows)} segment(s)", flush=True)

    print(f"\nWrote candidates -> {OUT}")


if __name__ == "__main__":
    main()
