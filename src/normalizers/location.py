from __future__ import annotations
"""Location normalization — country codes to ISO-3166 alpha-2."""

import re

# Subset covering common values in recruiting data
_COUNTRY_MAP = {
    "united states": "US", "usa": "US", "us": "US", "u.s.a.": "US", "u.s.": "US",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB",
    "india": "IN", "canada": "CA", "australia": "AU", "germany": "DE",
    "france": "FR", "singapore": "SG", "netherlands": "NL", "sweden": "SE",
    "switzerland": "CH", "new zealand": "NZ", "ireland": "IE",
    "brazil": "BR", "mexico": "MX", "japan": "JP", "china": "CN",
    "south korea": "KR", "korea": "KR", "israel": "IL", "uae": "AE",
    "united arab emirates": "AE", "portugal": "PT", "spain": "ES",
    "italy": "IT", "poland": "PL", "ukraine": "UA", "russia": "RU",
    "pakistan": "PK", "nigeria": "NG", "kenya": "KE", "south africa": "ZA",
    "argentina": "AR", "chile": "CL", "colombia": "CO",
    "philippines": "PH", "indonesia": "ID", "vietnam": "VN", "malaysia": "MY",
    "hong kong": "HK", "taiwan": "TW", "thailand": "TH",
    "egypt": "EG", "turkey": "TR", "romania": "RO", "hungary": "HU",
    "czech republic": "CZ", "czechia": "CZ", "austria": "AT", "denmark": "DK",
    "finland": "FI", "norway": "NO", "belgium": "BE",
}

# Known 2-letter uppercase codes (already ISO-3166)
_VALID_ALPHA2 = set(_COUNTRY_MAP.values())


def normalize_country(raw: str) -> str | None:
    if not raw or not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if len(cleaned) == 2 and cleaned.upper() in _VALID_ALPHA2:
        return cleaned.upper()
    mapped = _COUNTRY_MAP.get(cleaned.lower())
    return mapped  # None if unknown — honest null


def parse_location_string(raw: str) -> dict:
    """
    Parse a freeform location string like 'San Francisco, CA, US'
    or 'New York, NY' into {city, region, country}.
    """
    if not raw or not isinstance(raw, str):
        return {"city": None, "region": None, "country": None}

    parts = [p.strip() for p in raw.split(",")]
    city = region = country = None

    if len(parts) == 1:
        # Could be just a city or a country
        c = normalize_country(parts[0])
        if c:
            country = c
        else:
            city = parts[0] or None

    elif len(parts) == 2:
        city = parts[0] or None
        # Second could be region (state) or country
        c = normalize_country(parts[1])
        if c:
            country = c
        else:
            region = parts[1] or None

    elif len(parts) >= 3:
        city = parts[0] or None
        region = parts[1] or None
        country = normalize_country(parts[2]) or (parts[2] if parts[2] else None)

    return {"city": city, "region": region, "country": country}
