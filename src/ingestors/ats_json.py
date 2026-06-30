"""
ATS JSON blob ingestor.
ATS field names do NOT match our canonical names — we map them here.
The blob may be a list of candidates or a single candidate object.
"""

import json
from src.schema import RawRecord
from src.ingestors.base import BaseIngestor


class ATSJsonIngestor(BaseIngestor):
    source_name = "ats_json"
    method_name = "json_parse"

    # ATS field → canonical raw key
    # These represent common ATS field naming conventions (Greenhouse, Lever, Workday, etc.)
    _FIELD_MAP = {
        # Identity
        "candidate_name": "full_name", "applicant_name": "full_name",
        "first_name": "first_name", "last_name": "last_name",
        "firstname": "first_name", "lastname": "last_name",
        "name": "full_name",

        # Contact
        "email_address": "email", "email_addresses": "email", "email": "email",
        "primary_email": "email",
        "phone_number": "phone", "phone_numbers": "phone", "phone": "phone",
        "mobile_number": "phone",

        # Location
        "location": "location", "address": "location", "city": "location",
        "current_location": "location",

        # Professional
        "current_employer": "current_company", "current_company": "current_company",
        "employer": "current_company", "company": "current_company",
        "job_title": "title", "current_title": "title", "title": "title",
        "position": "title",

        # Links
        "linkedin_url": "linkedin", "linkedin_profile": "linkedin",
        "linkedin": "linkedin",
        "github_url": "github", "github_profile": "github", "github": "github",
        "portfolio_url": "portfolio", "website": "portfolio",

        # Profile
        "summary": "headline", "bio": "headline", "headline": "headline",
        "skills": "skills", "skill_set": "skills", "technologies": "skills",
        "years_of_experience": "years_experience", "experience_years": "years_experience",
        "years_experience": "years_experience",

        # Arrays
        "work_experience": "work_experience", "experience": "work_experience",
        "employment_history": "work_experience",
        "education": "education", "education_history": "education",
    }

    def ingest(self, source) -> list[RawRecord]:
        if isinstance(source, str):
            with open(source, encoding="utf-8") as f:
                data = json.load(f)
        elif hasattr(source, "read"):
            data = json.load(source)
        elif isinstance(source, (dict, list)):
            data = source
        else:
            raise ValueError(f"Unsupported source type: {type(source)}")

        candidates = data if isinstance(data, list) else [data]
        records = []

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            fields = {}
            for ats_key, val in candidate.items():
                mapped = self._FIELD_MAP.get(ats_key.lower().strip())
                if mapped is None:
                    # Store unmapped fields under their original key — don't discard
                    mapped = f"_ats_{ats_key}"
                if val is not None:
                    fields[mapped] = val

            # Reconstruct full_name from first/last if not present
            if "full_name" not in fields:
                first = fields.pop("first_name", "") or ""
                last = fields.pop("last_name", "") or ""
                combined = f"{first} {last}".strip()
                if combined:
                    fields["full_name"] = combined

            records.append(
                RawRecord(
                    source=self.source_name,
                    method=self.method_name,
                    fields=fields,
                )
            )

        return records
