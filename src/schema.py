from __future__ import annotations
"""
Canonical profile schema — the internal truth representation.
All ingestors produce RawRecord dicts; the merger produces a CanonicalProfile.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawRecord:
    """Flat bag of raw extracted fields from one source. Values are un-normalized strings/lists."""
    source: str            # e.g. "recruiter_csv", "github", "ats_json", "recruiter_notes"
    method: str            # e.g. "csv_parse", "rest_api", "regex_extract"
    fields: dict           # raw field name → raw value


@dataclass
class ProvenanceEntry:
    field: str
    source: str
    method: str


@dataclass
class SkillEntry:
    name: str
    confidence: float
    sources: list


@dataclass
class ExperienceEntry:
    company: str | None
    title: str | None
    start: str | None      # YYYY-MM
    end: str | None        # YYYY-MM or "present"
    summary: str | None


@dataclass
class EducationEntry:
    institution: str | None
    degree: str | None
    field: str | None
    end_year: int | None


@dataclass
class Location:
    city: str | None
    region: str | None
    country: str | None    # ISO-3166 alpha-2


@dataclass
class Links:
    linkedin: str | None
    github: str | None
    portfolio: str | None
    other: list


@dataclass
class CanonicalProfile:
    candidate_id: str
    full_name: str | None
    emails: list                   # [str]
    phones: list                   # [str] E.164
    location: Location
    links: Links
    headline: str | None
    years_experience: float | None
    skills: list                   # [SkillEntry]
    experience: list               # [ExperienceEntry]
    education: list                # [EducationEntry]
    provenance: list               # [ProvenanceEntry]
    overall_confidence: float

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "full_name": self.full_name,
            "emails": self.emails,
            "phones": self.phones,
            "location": {
                "city": self.location.city,
                "region": self.location.region,
                "country": self.location.country,
            },
            "links": {
                "linkedin": self.links.linkedin,
                "github": self.links.github,
                "portfolio": self.links.portfolio,
                "other": self.links.other,
            },
            "headline": self.headline,
            "years_experience": self.years_experience,
            "skills": [
                {"name": s.name, "confidence": s.confidence, "sources": s.sources}
                for s in self.skills
            ],
            "experience": [
                {
                    "company": e.company,
                    "title": e.title,
                    "start": e.start,
                    "end": e.end,
                    "summary": e.summary,
                }
                for e in self.experience
            ],
            "education": [
                {
                    "institution": e.institution,
                    "degree": e.degree,
                    "field": e.field,
                    "end_year": e.end_year,
                }
                for e in self.education
            ],
            "provenance": [
                {"field": p.field, "source": p.source, "method": p.method}
                for p in self.provenance
            ],
            "overall_confidence": self.overall_confidence,
        }
