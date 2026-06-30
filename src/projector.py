from __future__ import annotations
"""
Projection layer — applies a runtime config to a CanonicalProfile dict
to produce a custom-shaped output.

Config schema:
{
  "fields": [
    {
      "path": "output_key",         # required — key in the output dict
      "from": "canonical.path",     # optional — path in canonical record; defaults to same as path
      "type": "string|string[]|number|object",  # optional, for normalization hints
      "normalize": "E164|canonical|...",        # optional normalization
      "required": true|false        # optional, default false
    }
  ],
  "include_provenance": true|false,   # default true
  "include_confidence": true|false,   # default true
  "on_missing": "null|omit|error"     # default "null"
}

Path expression language:
  "full_name"          → canonical["full_name"]
  "emails[0]"          → canonical["emails"][0]
  "skills[].name"      → [s["name"] for s in canonical["skills"]]
  "location.city"      → canonical["location"]["city"]
"""

import re
from src.normalizers.phone import normalize_phone
from src.normalizers.skills import canonicalize_skill


class ProjectionError(Exception):
    pass


def _resolve_path(doc: dict, path: str):
    """
    Walk a dot-separated path with optional array syntax into doc.
    Supports:
      - simple keys: "full_name"
      - dot access: "location.city"
      - index: "emails[0]"
      - map: "skills[].name"  (returns list)
    Returns the value or raises KeyError/IndexError.
    """
    # Tokenize: split on '.' but keep array parts attached to preceding key
    tokens = _tokenize_path(path)
    return _walk(doc, tokens)


def _tokenize_path(path: str) -> list:
    """
    "skills[].name" → [("key", "skills"), ("map", None), ("key", "name")]
    "emails[0]"     → [("key", "emails"), ("index", 0)]
    "location.city" → [("key", "location"), ("key", "city")]
    """
    tokens = []
    parts = path.split(".")

    for part in parts:
        # Check for array suffix
        m = re.match(r"^([^\[]+)\[(\d*)\]$", part)
        if m:
            key, idx = m.group(1), m.group(2)
            tokens.append(("key", key))
            if idx == "":
                tokens.append(("map", None))  # [] = iterate all
            else:
                tokens.append(("index", int(idx)))
        else:
            tokens.append(("key", part))

    return tokens


def _walk(node, tokens: list):
    if not tokens:
        return node

    kind, val = tokens[0]
    rest = tokens[1:]

    if kind == "key":
        if isinstance(node, dict):
            child = node.get(val)
            return _walk(child, rest)
        raise KeyError(f"Cannot access key '{val}' on {type(node)}")

    elif kind == "index":
        if isinstance(node, list):
            if val >= len(node):
                return None
            return _walk(node[val], rest)
        raise IndexError(f"Cannot index {type(node)}")

    elif kind == "map":
        if not isinstance(node, list):
            raise TypeError(f"'[]' on non-list: {type(node)}")
        return [_walk(item, rest) for item in node]

    raise ValueError(f"Unknown token kind: {kind}")


def _normalize_value(value, normalize_hint: str | None, field_type: str | None):
    """Apply per-field normalization based on the config hint."""
    if value is None:
        return None

    if normalize_hint == "E164":
        if isinstance(value, list):
            return [normalize_phone(v) for v in value if v is not None]
        return normalize_phone(str(value))

    if normalize_hint == "canonical":
        if isinstance(value, list):
            return [canonicalize_skill(v) for v in value if v is not None]
        return canonicalize_skill(str(value))

    # Type coercion
    if field_type == "string" and not isinstance(value, str):
        return str(value) if value is not None else None
    if field_type == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    return value


def project(canonical_dict: dict, config: dict) -> dict:
    """
    Apply config to canonical_dict and return the projected output.
    Raises ProjectionError on required-field missing when on_missing="error".
    """
    fields_spec = config.get("fields")
    include_provenance = config.get("include_provenance", True)
    include_confidence = config.get("include_confidence", True)
    on_missing = config.get("on_missing", "null")

    # If no fields spec, return the full canonical + optional provenance/confidence
    if not fields_spec:
        result = dict(canonical_dict)
        if not include_provenance:
            result.pop("provenance", None)
        if not include_confidence:
            result.pop("overall_confidence", None)
        return result

    result = {}
    for field_def in fields_spec:
        output_key = field_def.get("path")
        if not output_key:
            continue

        from_path = field_def.get("from", output_key)
        field_type = field_def.get("type")
        normalize_hint = field_def.get("normalize")
        required = field_def.get("required", False)

        try:
            value = _resolve_path(canonical_dict, from_path)
        except (KeyError, IndexError, TypeError, AttributeError):
            value = None

        if value is None:
            if required and on_missing == "error":
                raise ProjectionError(
                    f"Required field '{output_key}' (from '{from_path}') is missing"
                )
            if on_missing == "omit":
                continue
            # on_missing == "null" (default)
            result[output_key] = None
            continue

        value = _normalize_value(value, normalize_hint, field_type)
        result[output_key] = value

    # Append provenance / confidence if requested
    if include_provenance and "provenance" in canonical_dict:
        result["provenance"] = canonical_dict["provenance"]
    if include_confidence and "overall_confidence" in canonical_dict:
        result["overall_confidence"] = canonical_dict["overall_confidence"]

    return result


def validate_required(result: dict, fields_spec: list, on_missing: str) -> list[str]:
    """Return list of validation errors (empty = valid)."""
    errors = []
    for field_def in fields_spec:
        output_key = field_def.get("path", "")
        if field_def.get("required") and result.get(output_key) is None:
            errors.append(f"Required field missing: {output_key}")
    return errors
