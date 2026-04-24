"""Canonical filename generation for user resumes.

Keeps one source of truth so the UI, the `/api/me/resume` download, the email
attachment, and the Playwright upload to Naukri all present the same name
format: `<Name_Parts>_DD_Mon_YYYY.pdf` — e.g. `Harsh_Nargide_24_Apr_2026.pdf`.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

# Locale-independent month abbreviations. `strftime('%b')` is locale-sensitive
# and we don't want "Apr" to ever come back as "avr." on a server set to fr_FR.
_MONTH_ABBR = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

# Split on any run of whitespace, hyphen, or underscore so hyphenated /
# underscored names collapse cleanly ("Harsh-Nargide" → "Harsh_Nargide").
_SEP_RE = re.compile(r"[-_\s]+")

# Keep only ASCII letters + digits inside each part. Drops punctuation, emoji,
# non-ASCII (safest for Naukri's uploader, which reacts badly to unicode paths).
_KEEP_RE = re.compile(r"[^A-Za-z0-9]+")


def _sanitize_parts(name: str) -> list[str]:
    parts: list[str] = []
    for raw in _SEP_RE.split(name or ""):
        cleaned = _KEEP_RE.sub("", raw)
        if cleaned:
            parts.append(cleaned)
    return parts


def build_resume_filename(
    user_name: str,
    on_date: Optional[date] = None,
) -> str:
    """Return the canonical resume filename for a user on the given date.

    Examples
    --------
    >>> build_resume_filename("Harsh", date(2026, 4, 24))
    'Harsh_24_Apr_2026.pdf'
    >>> build_resume_filename("Harsh Nargide", date(2026, 4, 24))
    'Harsh_Nargide_24_Apr_2026.pdf'

    If `user_name` sanitises to an empty string (e.g. non-ASCII only), falls
    back to `Resume_DD_Mon_YYYY.pdf` so the download link is never broken.
    """
    d = on_date or date.today()
    parts = _sanitize_parts(user_name)
    base = "_".join(parts) if parts else "Resume"
    datestr = f"{d.day:02d}_{_MONTH_ABBR[d.month - 1]}_{d.year}"
    return f"{base}_{datestr}.pdf"
