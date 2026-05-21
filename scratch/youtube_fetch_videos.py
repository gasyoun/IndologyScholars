"""
Fetch all video metadata (videoId, title, position, publishedAt) from the
Zograf playlists listed in analytics_output/youtube_playlist_summary.csv.

Reads YOUTUBE_API_KEY from .env. Writes analytics_output/youtube_video_list.csv.

Quota cost: ~1 unit per playlistItems.list call, with up to 50 items per page.
For 4 playlists × ~50 videos avg → ~8-16 units. Free tier is 10,000/day.

Usage:
    python scratch/youtube_fetch_videos.py

Then run scratch/youtube_match_videos.py to fuzzy-match against presentations.
"""

import csv
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv()
API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
PLAYLISTS_CSV = Path("analytics_output/youtube_playlist_summary.csv")
OUT_CSV = Path("analytics_output/youtube_video_list.csv")
API_URL = "https://www.googleapis.com/youtube/v3/playlistItems"


def fetch_playlist(playlist_id):
    """Yield items from a YouTube playlist, paginating until exhausted."""
    page_token = None
    while True:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": API_KEY,
        }
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(API_URL, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"  ERROR {resp.status_code} for {playlist_id}: {resp.text[:200]}", file=sys.stderr)
            return
        data = resp.json()
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            video_id = content.get("videoId") or snippet.get("resourceId", {}).get("videoId")
            yield {
                "video_id": video_id,
                "video_title": snippet.get("title", ""),
                "position": snippet.get("position"),
                "published_at": content.get("videoPublishedAt") or snippet.get("publishedAt", ""),
            }
        page_token = data.get("nextPageToken")
        if not page_token:
            return


def load_playlists():
    """Read playlist metadata from the existing summary CSV."""
    playlists = []
    with PLAYLISTS_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            label = row.get("playlist", "").strip()
            pid = row.get("playlist_id", "").strip()
            if not pid:
                continue
            # Extract year if label starts with "YYYY"; otherwise None
            year = None
            head = label.split()[0] if label else ""
            if head.isdigit() and len(head) == 4:
                year = int(head)
            playlists.append({"label": label, "playlist_id": pid, "year": year})
    return playlists


def main():
    if not API_KEY:
        print("ERROR: YOUTUBE_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    playlists = load_playlists()
    if not playlists:
        print(f"ERROR: no playlists found in {PLAYLISTS_CSV}", file=sys.stderr)
        sys.exit(1)

    rows = []
    for pl in playlists:
        print(f"Fetching '{pl['label']}' ({pl['playlist_id']})...")
        for item in fetch_playlist(pl["playlist_id"]):
            rows.append({
                "year": pl["year"] or "",
                "playlist_label": pl["label"],
                "playlist_id": pl["playlist_id"],
                "video_id": item["video_id"],
                "video_url": f"https://www.youtube.com/watch?v={item['video_id']}",
                "video_title": item["video_title"],
                "position": item["position"],
                "published_at": item["published_at"],
            })
        print(f"  → {sum(1 for r in rows if r['playlist_id'] == pl['playlist_id'])} videos cumulatively")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        if not rows:
            print("ERROR: no videos fetched", file=sys.stderr)
            sys.exit(1)
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {OUT_CSV} ({len(rows)} videos across {len(playlists)} playlists)")
    print("Next: python scratch/youtube_match_videos.py")


if __name__ == "__main__":
    main()
