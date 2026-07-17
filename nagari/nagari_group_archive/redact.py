"""Shared redaction helpers for the closed-list nagari archive.

Both consumers of the ingested archive — the interactive retrospective page
(:mod:`page`) and the full-text Markdown mirror (:mod:`export_md`) — must not
leak a third-party member's real email address anywhere in their output.
Names are public (that's how the group's own members knew each other);
addresses are not. This module is the single place that decides what
"redacted" means, so the two consumers cannot drift.
"""

from __future__ import annotations

import re

NAME_STOP = {"mārcis", "marcis", "gasūns", "gasuns", "gmail", "googlegroups"}

_LOCAL = r"[A-Za-z0-9._%+-]+"
_DOMAIN = r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
EMAIL_RE = re.compile(rf"^\s*({_LOCAL})@{_DOMAIN}\s*$")
EMAIL_SUB = re.compile(rf"({_LOCAL})@{_DOMAIN}")


def mask_name(s: str) -> str:
    """Mask an email-shaped display name to ``local@…`` (names are public, addresses are not)."""
    m = EMAIL_RE.match(s or "")
    return f"{m.group(1)}@…" if m else (s or "")


def redact_emails(s: str) -> str:
    """Redact any email *substring* inside free text (subjects, bodies, quoted headers, signatures) to ``local@…``."""
    return EMAIL_SUB.sub(lambda m: f"{m.group(1)}@…", s or "")
