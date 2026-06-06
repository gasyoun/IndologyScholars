"""Shared scraping utilities for the indologist-collection scripts.

Centralises the things that were previously copy-pasted (or missing) across
expand_wikipedia_indologists.py / scrape_institutions.py / scrape_wikidata.py:

  * a hardened HTTP GET with retry + exponential backoff (the Wikimedia link
    from inside RU is slow and drops SSL handshakes — a single try is not
    enough), with an on-disk response cache so re-runs are fast and resilient;
  * atomic JSON writes (never truncate a good output file on a failed run —
    this is what made the documented "full cycle" destructive);
  * one canonical name-normaliser (ё→е, case, spacing) used everywhere.

Pure stdlib. UTF-8 everywhere, no BOM.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SCRATCH = Path(__file__).resolve().parent
CACHE_DIR = SCRATCH / ".http_cache"

# Wikimedia asks for a descriptive UA with contact info; a bare/absent UA is
# increasingly rate-limited or rejected outright.
USER_AGENT = (
    "IndologyScholars/1.0 "
    "(https://github.com/gasyoun/IndologyScholars; gasyoun@gmail.com) "
    "python-urllib"
)

_RETRYABLE_HTTP = {429, 500, 502, 503, 504}


def setup_utf8() -> None:
    """Make stdout/stderr UTF-8 on Windows consoles. Call from entry scripts."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _cache_path(url: str) -> Path:
    key = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{key}.bin"


def http_get(
    url: str,
    *,
    timeout: int = 30,
    retries: int = 4,
    backoff: float = 1.7,
    cache: bool = True,
    verbose: bool = False,
) -> bytes | None:
    """GET a URL, returning the raw body bytes, or None if all retries fail.

    Retries on timeouts, SSL handshake drops, connection resets and the
    retryable HTTP status codes. Successful responses are cached on disk
    (keyed by URL) unless ``cache=False``; cache hits skip the network.
    """
    if cache:
        cp = _cache_path(url)
        if cp.exists():
            return cp.read_bytes()

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
            if cache:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                _cache_path(url).write_bytes(body)
            return body
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code not in _RETRYABLE_HTTP:
                if verbose:
                    print(f"    HTTP {e.code} (non-retryable): {url}")
                return None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
        if attempt < retries:
            sleep_s = backoff ** attempt
            if verbose:
                print(f"    retry {attempt}/{retries - 1} in {sleep_s:.1f}s "
                      f"({type(last_err).__name__}) {url}")
            time.sleep(sleep_s)
    if verbose:
        print(f"    GAVE UP after {retries} tries ({last_err}): {url}")
    return None


def get_json(url: str, **kw) -> dict | None:
    body = http_get(url, **kw)
    if body is None:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def api_get(base: str, params: dict, **kw) -> dict | None:
    """GET a MediaWiki-style API endpoint with urlencoded params."""
    return get_json(base + "?" + urllib.parse.urlencode(params), **kw)


def atomic_write_json(path: Path | str, obj, *, indent: int = 2) -> None:
    """Write JSON to a temp file then os.replace() it into place.

    A crashed or killed run can never leave a half-written / empty output
    where a good file used to be. UTF-8, no BOM, trailing newline.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    os.replace(tmp, path)


def normalize_name(name: str) -> str:
    """Canonical key for matching person names: ё→е, lowercase, single spaces."""
    s = (name or "").lower().replace("ё", "е").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def clear_cache() -> int:
    """Delete the on-disk HTTP cache. Returns number of files removed."""
    if not CACHE_DIR.exists():
        return 0
    n = 0
    for f in CACHE_DIR.glob("*.bin"):
        f.unlink()
        n += 1
    return n
