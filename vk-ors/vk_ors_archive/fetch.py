"""Stage 0 (optional): refresh ``vk_posts_all.xlsx`` from the live VK wall.

``ingest.py`` treats the xlsx as a static, read-only export. This module is
the producer of that export: it paginates ``wall.get`` for the public wall
behind vk.com/wall-88831040 (community short name in ``VK_DOMAIN``) and
writes a fresh ``vk_posts_all.xlsx`` in the exact column layout ``ingest.py``
expects (ID поста / Ссылка / Дата / Текст поста / Лайки / Репосты /
Комментарии / Просмотры / Кол-во вложений / Типы вложений), so a refresh is
a drop-in replacement for the original manual export.

Additionally (wave-1a advanced viz): in the same ``wall.get`` pass, write
``data/attachments_raw.json`` — per-post attachment metadata (type, url,
width/height, position) for the media gallery. One API pass only; xlsx
column layout is unchanged.

Credentials come from ``.env`` (gitignored, never committed): VK_ACCESS_TOKEN,
VK_DOMAIN, VK_API_VERSION.

Usage::

    python -m vk_ors_archive.fetch                # full re-pull, overwrite xlsx + attachments
    python -m vk_ors_archive.fetch --dry-run       # fetch, print count, don't write

After a refresh, re-run the normal pipeline (ingest -> insights -> page).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import openpyxl
import requests
from dotenv import load_dotenv

load_dotenv()

PKG = Path(__file__).resolve().parents[1]
XLSX_PATH = PKG / "vk_posts_all.xlsx"
ATTACHMENTS_RAW = PKG / "data" / "attachments_raw.json"

HEADERS = [
    "ID поста", "Ссылка", "Дата", "Текст поста", "Лайки",
    "Репосты", "Комментарии", "Просмотры", "Кол-во вложений", "Типы вложений",
]


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _best_size(sizes: list[dict]) -> dict | None:
    if not sizes:
        return None
    return max(sizes, key=lambda s: (s.get("width") or 0) * (s.get("height") or 0))


def extract_attachment_meta(post: dict) -> list[dict]:
    """Extract gallery-usable attachment rows from a raw wall.get item.

    Video: thumbnail only (no ``video.get`` playable URL this wave).
    Audio/poll: type recorded, url usually empty (still useful for facets).
    """
    out: list[dict] = []
    for i, att in enumerate(post.get("attachments") or []):
        t = att.get("type") or "unknown"
        item = att.get(t) if isinstance(att.get(t), dict) else {}
        url: str | None = None
        width: int | None = None
        height: int | None = None

        if t == "photo":
            best = _best_size(item.get("sizes") or [])
            if best:
                url = best.get("url")
                width = best.get("width")
                height = best.get("height")
        elif t == "doc":
            # Prefer preview photo when present (thumbnails for gallery).
            preview_sizes = (
                (item.get("preview") or {}).get("photo") or {}
            ).get("sizes") or []
            best = _best_size(preview_sizes)
            if best:
                url = best.get("url")
                width = best.get("width")
                height = best.get("height")
            if not url:
                url = item.get("url")  # direct doc download; may not render as <img>
        elif t == "video":
            images = item.get("image") or item.get("first_frame") or []
            best = _best_size(images) if images else None
            if best:
                url = best.get("url")
                width = best.get("width")
                height = best.get("height")
            if not url:
                for key in ("photo_800", "photo_640", "photo_320", "photo_130"):
                    if item.get(key):
                        url = item[key]
                        break
        elif t == "link":
            photo = item.get("photo") or {}
            best = _best_size(photo.get("sizes") or [])
            if best:
                url = best.get("url")
                width = best.get("width")
                height = best.get("height")
            if not url:
                url = item.get("url")
        elif t == "audio":
            # Rarely has art; record type only.
            pass
        elif t == "poll":
            pass
        else:
            # Unknown type: try common nested shapes.
            if isinstance(item, dict):
                best = _best_size(item.get("sizes") or [])
                if best:
                    url = best.get("url")
                    width = best.get("width")
                    height = best.get("height")
                url = url or item.get("url")

        out.append({
            "type": t,
            "url": url or "",
            "width": width,
            "height": height,
            "position": i,
        })
    return out


def fetch_all_posts(token: str, domain: str, version: str, count: int = 100) -> list[dict]:
    offset = 0
    items: list[dict] = []
    backoff = 0.34
    while True:
        try:
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
        except requests.RequestException as exc:
            print(f"Network error at offset {offset}: {exc}; backoff {backoff:.1f}s", file=sys.stderr)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)
            continue

        if "response" not in resp:
            err = resp.get("error") or {}
            code = err.get("error_code")
            # 6 = too many requests; 29 = rate limit
            if code in (6, 29):
                print(f"VK rate limit at offset {offset}: {err}; backoff {backoff:.1f}s", file=sys.stderr)
                time.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                continue
            print(f"VK API error at offset {offset}: {err}", file=sys.stderr)
            break

        backoff = 0.34
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


def write_attachments_raw(posts: list[dict], out_path: Path) -> int:
    """Write {post_id: [attachment_meta, ...]} JSON. Returns total attachment count."""
    payload: dict[str, list[dict]] = {}
    n = 0
    for post in posts:
        meta = extract_attachment_meta(post)
        if meta:
            payload[str(post["id"])] = meta
            n += len(meta)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=None), encoding="utf-8")
    return n


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", default=os.environ.get("VK_DOMAIN", "").strip())
    ap.add_argument("--out", type=Path, default=XLSX_PATH)
    ap.add_argument("--attachments-out", type=Path, default=ATTACHMENTS_RAW)
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
        n_att = sum(len(p.get("attachments") or []) for p in posts)
        print(f"Dry-run: would write {len(posts)} xlsx rows, ~{n_att} attachments.", flush=True)
        return

    write_xlsx(posts, args.out)
    print(f"Wrote {args.out}", flush=True)
    n_att = write_attachments_raw(posts, args.attachments_out)
    print(f"Wrote {args.attachments_out} ({n_att} attachments across {len(posts)} posts)", flush=True)
    print(
        "Next: python -m vk_ors_archive.ingest && python -m vk_ors_archive.insights "
        "&& python -m vk_ors_archive.page",
        flush=True,
    )


if __name__ == "__main__":
    main()
