"""Stage 0 (optional): refresh ``vk_posts_all.xlsx`` from the live VK wall.

``ingest.py`` treats the xlsx as a static, read-only export. This module is
the producer of that export: it paginates ``wall.get`` for the public wall
behind vk.com/wall-88831040 (community short name in ``VK_DOMAIN``) and
writes a fresh ``vk_posts_all.xlsx`` in the exact column layout ``ingest.py``
expects (ID поста / Ссылка / Дата / Текст поста / Лайки / Репосты /
Комментарии / Просмотры / Кол-во вложений / Типы вложений), so a refresh is
a drop-in replacement for the original manual export.

Credentials come from ``.env`` (gitignored, never committed): VK_ACCESS_TOKEN,
VK_DOMAIN, VK_API_VERSION.

Usage::

    python -m vk_ors_archive.fetch                # full re-pull, overwrite xlsx
    python -m vk_ors_archive.fetch --dry-run       # fetch, print count, don't write

After a refresh, re-run the normal pipeline (ingest -> insights -> page).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import openpyxl
import requests
from dotenv import load_dotenv

load_dotenv()

XLSX_PATH = Path(__file__).resolve().parents[1] / "vk_posts_all.xlsx"

HEADERS = [
    "ID поста", "Ссылка", "Дата", "Текст поста", "Лайки",
    "Репосты", "Комментарии", "Просмотры", "Кол-во вложений", "Типы вложений",
]


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def fetch_all_posts(token: str, domain: str, version: str, count: int = 100) -> list[dict]:
    offset = 0
    items: list[dict] = []
    while True:
        resp = requests.get(
            "https://api.vk.com/method/wall.get",
            params={
                "access_token": token,
                "v": version,
                "domain": domain,
                "count": count,
                "offset": offset,
                "filter": "all",
            },
            timeout=30,
        ).json()
        if "response" not in resp:
            print(f"VK API error at offset {offset}: {resp.get('error')}", file=sys.stderr)
            break
        batch = resp["response"]["items"]
        if not batch:
            break
        items.extend(batch)
        offset += count
        print(f"  ... {offset} posts", flush=True)
        time.sleep(0.34)  # VK limit: 3 req/sec
    return items


def to_row(post: dict) -> list:
    attachments = post.get("attachments", [])
    return [
        post["id"],
        f"https://vk.com/wall{post['owner_id']}_{post['id']}",
        datetime.fromtimestamp(post["date"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        post.get("text", ""),
        post.get("likes", {}).get("count", 0),
        post.get("reposts", {}).get("count", 0),
        post.get("comments", {}).get("count", 0),
        post.get("views", {}).get("count", 0),
        len(attachments),
        ", ".join(sorted({a["type"] for a in attachments})),
    ]


def write_xlsx(posts: list[dict], out_path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(HEADERS)
    for post in posts:
        ws.append(to_row(post))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", default=os.environ.get("VK_DOMAIN", "").strip())
    ap.add_argument("--out", type=Path, default=XLSX_PATH)
    ap.add_argument("--dry-run", action="store_true", help="fetch and print count only")
    args = ap.parse_args(argv)

    token = os.environ.get("VK_ACCESS_TOKEN", "").strip()
    version = os.environ.get("VK_API_VERSION", "5.199").strip()
    if not token:
        print("ERROR: VK_ACCESS_TOKEN not set in .env", file=sys.stderr)
        sys.exit(1)
    if not args.domain:
        print("ERROR: no VK domain given (set VK_DOMAIN in .env or pass --domain)", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching all wall posts for vk.com/{args.domain} ...", flush=True)
    posts = fetch_all_posts(token, args.domain, version)
    print(f"Fetched {len(posts)} posts.", flush=True)

    if args.dry_run:
        return

    write_xlsx(posts, args.out)
    print(f"Wrote {args.out}", flush=True)
    print("Next: python -m vk_ors_archive.ingest && python -m vk_ors_archive.insights "
          "&& python -m vk_ors_archive.page", flush=True)


if __name__ == "__main__":
    main()
