from __future__ import annotations
"""Date normalization to YYYY-MM format."""

import re
from datetime import datetime


_MONTH_NAMES = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}


def normalize_date(raw: str) -> str | None:
    """
    Normalize a date string to YYYY-MM.
    Accepts: "2020-03", "March 2020", "03/2020", "2020", "Jan 2019", etc.
    Returns None if unparseable — never invents a date.
    """
    if not raw or not isinstance(raw, str):
        return None

    raw = raw.strip()
    if not raw or raw.lower() in ("present", "current", "now", "ongoing"):
        return "present"

    # Already YYYY-MM
    if re.match(r"^\d{4}-\d{2}$", raw):
        return raw

    # YYYY-MM-DD → truncate
    m = re.match(r"^(\d{4})-(\d{2})-\d{2}$", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # YYYY only
    if re.match(r"^\d{4}$", raw):
        return f"{raw}-01"

    # MM/YYYY or MM-YYYY
    m = re.match(r"^(\d{1,2})[/-](\d{4})$", raw)
    if m:
        return f"{m.group(2)}-{m.group(1).zfill(2)}"

    # "Month YYYY" or "YYYY Month"
    m = re.match(r"^([A-Za-z]+)\s+(\d{4})$", raw)
    if m:
        mon = _MONTH_NAMES.get(m.group(1).lower())
        if mon:
            return f"{m.group(2)}-{mon}"

    m = re.match(r"^(\d{4})\s+([A-Za-z]+)$", raw)
    if m:
        mon = _MONTH_NAMES.get(m.group(2).lower())
        if mon:
            return f"{m.group(1)}-{mon}"

    # Try dateutil as a last resort
    try:
        from dateutil import parser as dparser
        dt = dparser.parse(raw, default=datetime(1900, 1, 1))
        if dt.year != 1900:
            return f"{dt.year}-{str(dt.month).zfill(2)}"
    except Exception:
        pass

    return None
