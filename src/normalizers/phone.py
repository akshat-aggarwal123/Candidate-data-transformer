from __future__ import annotations
"""Phone normalization to E.164 format."""

import re


def normalize_phone(raw: str, default_region: str = "US") -> str | None:
    """
    Normalize a phone string to E.164 (e.g. +14155551234).
    Returns None if the number is unparseable rather than inventing a value.
    Default region US is applied only when no country code is present.
    """
    if not raw or not isinstance(raw, str):
        return None

    raw = raw.strip()
    if not raw:
        return None

    try:
        import phonenumbers
        parsed = phonenumbers.parse(raw, default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
        return None
    except Exception:
        # phonenumbers not available or parse failed — fall back to digit-only heuristic
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) == 11 and digits[0] == "1":
            return f"+{digits}"
        return None  # can't normalize safely → honest null
