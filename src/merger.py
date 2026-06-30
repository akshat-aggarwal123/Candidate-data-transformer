"""
Merger — groups RawRecords by candidate identity, resolves conflicts,
and produces one CanonicalProfile per candidate.

Match key:   primary = email (normalized, exact)
             fallback = normalized full_name

Conflict resolution (per field):
  Source reliability ranking (higher = more trusted):
    1. ats_json        (authoritative system of record)
    2. recruiter_csv   (structured, human-curated)
    3. github          (verified identity, limited scope)
    4. linkedin        (self-reported, structured)
    5. recruiter_notes (informal, regex-extracted)

  For scalar fields: highest-trust source wins.
  For list fields (emails, phones, skills, experience, education): union across all sources,
  deduplicated, sorted stably.
"""

import uuid
import re
from typing import Any

from src.schema import (
    RawRecord, CanonicalProfile, ProvenanceEntry,
    SkillEntry, ExperienceEntry, EducationEntry, Location, Links,
)
from src.normalizers.phone import normalize_phone
from src.normalizers.date import normalize_date
from src.normalizers.location import parse_location_string
from src.normalizers.skills import canonicalize_skill
from src.confidence import score_field, overall_confidence


SOURCE_TRUST = {
    "ats_json": 5,
    "recruiter_csv": 4,
    "github": 3,
    "linkedin": 3,
    "recruiter_notes": 2,
}


def _trust(source: str) -> int:
    return SOURCE_TRUST.get(source, 1)


def _norm_email(email: str) -> str:
    return email.strip().lower()


def _norm_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _candidate_key(record: RawRecord) -> str:
    """Deterministic grouping key: prefer email, fall back to name."""
    raw_email = record.fields.get("email")
    if isinstance(raw_email, list):
        raw_email = raw_email[0] if raw_email else None
    if raw_email:
        return f"email:{_norm_email(str(raw_email).split(',')[0])}"

    name = record.fields.get("full_name")
    if name:
        return f"name:{_norm_name(str(name))}"

    return f"unknown:{id(record)}"


def _deterministic_id(key: str) -> str:
    """UUID v5 from the candidate key — same inputs always produce same ID."""
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # URL namespace
    return str(uuid.uuid5(namespace, key))


def _pick_winner(values_by_source: list[tuple[str, Any]]) -> tuple[Any, str]:
    """Return (value, winning_source) using trust ranking. Deterministic on tie."""
    if not values_by_source:
        return None, ""
    return max(values_by_source, key=lambda x: _trust(x[0]))


def _collect_emails(records: list[RawRecord]) -> tuple[list[str], list[ProvenanceEntry]]:
    seen = {}
    provenance = []
    for rec in records:
        raw = rec.fields.get("email")
        if raw is None:
            continue
        if isinstance(raw, list):
            items = raw
        else:
            items = str(raw).split(",")
        for item in items:
            e = _norm_email(item.strip())
            if e and e not in seen:
                seen[e] = rec.source
                provenance.append(ProvenanceEntry("emails", rec.source, rec.method))
    return list(seen.keys()), provenance


def _collect_phones(records: list[RawRecord]) -> tuple[list[str], list[ProvenanceEntry]]:
    seen = {}
    provenance = []
    for rec in records:
        raw = rec.fields.get("phone")
        if raw is None:
            continue
        items = raw if isinstance(raw, list) else str(raw).split(",")
        for item in items:
            normalized = normalize_phone(item.strip())
            if normalized and normalized not in seen:
                seen[normalized] = rec.source
                provenance.append(ProvenanceEntry("phones", rec.source, rec.method))
    return list(seen.keys()), provenance


def _merge_scalar(
    field_name: str,
    records: list[RawRecord],
    raw_key: str,
    transform=None,
) -> tuple[Any, list[ProvenanceEntry]]:
    """Pick the highest-trust non-null value for a scalar field."""
    candidates = []
    for rec in records:
        val = rec.fields.get(raw_key)
        if val is None or val == "":
            continue
        if transform:
            val = transform(val)
        if val is not None and val != "":
            candidates.append((rec.source, val, rec.method))

    if not candidates:
        return None, []

    # Sort by trust desc, then source name for determinism on tie
    candidates.sort(key=lambda x: (-_trust(x[0]), x[0]))
    winner = candidates[0]
    provenance = [ProvenanceEntry(field_name, winner[0], winner[2])]
    return winner[1], provenance


def _collect_skills(records: list[RawRecord]) -> tuple[list[SkillEntry], list[ProvenanceEntry]]:
    skill_sources: dict[str, list[str]] = {}  # canonical_name → [source, ...]
    skill_methods: dict[str, str] = {}

    for rec in records:
        raw = rec.fields.get("skills", [])
        if isinstance(raw, str):
            raw = [s.strip() for s in re.split(r"[,;/|]", raw) if s.strip()]
        if not isinstance(raw, list):
            raw = []

        for item in raw:
            if isinstance(item, dict):
                name = item.get("name", "")
            else:
                name = str(item)
            canonical = canonicalize_skill(name)
            if not canonical:
                continue
            if canonical not in skill_sources:
                skill_sources[canonical] = []
                skill_methods[canonical] = rec.method
            if rec.source not in skill_sources[canonical]:
                skill_sources[canonical].append(rec.source)

    entries = []
    provenance = []
    for skill_name in sorted(skill_sources.keys()):
        sources = skill_sources[skill_name]
        confidence = score_field(sources)
        entries.append(SkillEntry(name=skill_name, confidence=confidence, sources=sources))
        for src in sources:
            provenance.append(ProvenanceEntry("skills", src, skill_methods[skill_name]))

    return entries, provenance


def _collect_experience(records: list[RawRecord]) -> tuple[list[ExperienceEntry], list[ProvenanceEntry]]:
    entries = []
    provenance = []
    seen_keys = set()

    for rec in records:
        work = rec.fields.get("work_experience", [])
        if not isinstance(work, list):
            work = []

        for item in work:
            if not isinstance(item, dict):
                continue
            company = item.get("company") or item.get("employer") or item.get("organization")
            title = item.get("title") or item.get("position") or item.get("role")
            start = normalize_date(str(item.get("start_date") or item.get("start") or ""))
            end_raw = item.get("end_date") or item.get("end") or ""
            end = normalize_date(str(end_raw)) if end_raw else None
            summary = item.get("summary") or item.get("description")

            key = (str(company).lower().strip(), str(title).lower().strip())
            if key in seen_keys:
                continue
            seen_keys.add(key)

            entries.append(ExperienceEntry(
                company=company, title=title, start=start, end=end, summary=summary
            ))
            provenance.append(ProvenanceEntry("experience", rec.source, rec.method))

    # Fold in single current role from CSV/ATS (sorted by trust desc so highest-trust is first)
    # Existing company names from work_experience entries (for dedup)
    existing_companies = {e.company.lower().strip() for e in entries if e.company}
    current_role_records = sorted(records, key=lambda r: -_trust(r.source))
    for rec in current_role_records:
        company = rec.fields.get("current_company")
        title = rec.fields.get("title")
        if not (company or title):
            continue
        company_norm = str(company or "").lower().strip()
        # Skip if this company already has a richer entry from work_experience
        if company_norm in existing_companies:
            continue
        key = (company_norm, str(title or "").lower().strip())
        if key not in seen_keys:
            seen_keys.add(key)
            entries.insert(0, ExperienceEntry(
                company=company, title=title, start=None, end=None, summary=None
            ))
            provenance.append(ProvenanceEntry("experience", rec.source, rec.method))
            break  # Only insert once — highest-trust current role wins

    return entries, provenance


def _collect_education(records: list[RawRecord]) -> tuple[list[EducationEntry], list[ProvenanceEntry]]:
    entries = []
    provenance = []
    seen_keys = set()

    for rec in records:
        edu_list = rec.fields.get("education", [])
        if not isinstance(edu_list, list):
            edu_list = []

        for item in edu_list:
            if not isinstance(item, dict):
                continue
            institution = item.get("institution") or item.get("school") or item.get("university")
            degree = item.get("degree")
            field = item.get("field") or item.get("major") or item.get("field_of_study")
            end_year_raw = item.get("end_year") or item.get("graduation_year") or item.get("end_date")
            end_year = None
            if end_year_raw:
                try:
                    end_year = int(str(end_year_raw)[:4])
                except (ValueError, TypeError):
                    pass

            key = (str(institution or "").lower().strip(), str(degree or "").lower().strip())
            if key in seen_keys:
                continue
            seen_keys.add(key)

            entries.append(EducationEntry(
                institution=institution, degree=degree, field=field, end_year=end_year
            ))
            provenance.append(ProvenanceEntry("education", rec.source, rec.method))

    return entries, provenance


def merge(records: list[RawRecord]) -> list[CanonicalProfile]:
    """
    Group records by candidate identity key, then merge each group
    into one CanonicalProfile.
    """
    groups: dict[str, list[RawRecord]] = {}
    for rec in records:
        key = _candidate_key(rec)
        groups.setdefault(key, []).append(rec)

    profiles = []
    for key, group in groups.items():
        # Sort each group by trust (highest first) for deterministic processing
        group.sort(key=lambda r: -_trust(r.source))

        provenance: list[ProvenanceEntry] = []

        candidate_id = _deterministic_id(key)

        full_name, prov = _merge_scalar("full_name", group, "full_name")
        provenance.extend(prov)

        emails, prov = _collect_emails(group)
        provenance.extend(prov)

        phones, prov = _collect_phones(group)
        provenance.extend(prov)

        # Location: build from highest-trust source
        loc_str, prov = _merge_scalar("location", group, "location")
        provenance.extend(prov)
        if loc_str:
            loc_parts = parse_location_string(str(loc_str))
        else:
            loc_parts = {"city": None, "region": None, "country": None}

        linkedin_val, prov = _merge_scalar("links.linkedin", group, "linkedin")
        provenance.extend(prov)

        github_val, prov = _merge_scalar("links.github", group, "github")
        provenance.extend(prov)

        portfolio_val, prov = _merge_scalar("links.portfolio", group, "portfolio")
        provenance.extend(prov)

        headline, prov = _merge_scalar("headline", group, "headline")
        provenance.extend(prov)

        yoe, prov = _merge_scalar(
            "years_experience", group, "years_experience",
            transform=lambda v: float(v) if v else None,
        )
        provenance.extend(prov)

        skills, prov = _collect_skills(group)
        provenance.extend(prov)

        experience, prov = _collect_experience(group)
        provenance.extend(prov)

        education, prov = _collect_education(group)
        provenance.extend(prov)

        sources_contributing = list({r.source for r in group})
        conf = overall_confidence(sources_contributing, len(skills), yoe)

        profiles.append(CanonicalProfile(
            candidate_id=candidate_id,
            full_name=full_name,
            emails=emails,
            phones=phones,
            location=Location(**loc_parts),
            links=Links(
                linkedin=linkedin_val,
                github=github_val,
                portfolio=portfolio_val,
                other=[],
            ),
            headline=headline,
            years_experience=yoe,
            skills=skills,
            experience=experience,
            education=education,
            provenance=provenance,
            overall_confidence=conf,
        ))

    return profiles
