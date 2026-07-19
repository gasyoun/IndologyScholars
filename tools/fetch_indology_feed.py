"""Fetch the small Renou feed published by gasyoun/IndologyArchiveAtlas.

`Indology/` split out into its own repo (H460) so this site no longer reads
that tree directly. `generate_renou_layer.py`'s cross-site comparison instead
consumes this one-way feed, cached locally under `analytics_output/indology_feed/`.
Safe to skip: a missing feed just means the archive-side columns in the Renou
comparison come back empty (`read_csv` already tolerates a missing file).
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path
from urllib.error import URLError

FEED_BASE_URL = "https://raw.githubusercontent.com/gasyoun/IndologyArchiveAtlas/main/feed"
FEED_FILES = [
    "renou_coverage.csv",
    "renou_export_index.csv",
    "renou_state_summary.csv",
    "renou_register_summary.csv",
    "renou_message_matches.csv",
]
LOCAL_FEED_DIR = Path(__file__).resolve().parents[1] / "analytics_output" / "indology_feed"


def fetch_feed(dest_dir: Path = LOCAL_FEED_DIR) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in FEED_FILES:
        url = f"{FEED_BASE_URL}/{name}"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read()
        except URLError as exc:
            print(f"skip {name}: {exc}", file=sys.stderr)
            continue
        destination = dest_dir / name
        destination.write_bytes(data)
        written.append(destination)
    return written


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    files = fetch_feed()
    print(f"fetched {len(files)}/{len(FEED_FILES)} feed files into {LOCAL_FEED_DIR}")
