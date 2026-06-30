"""
Recruiter CSV ingestor.
Expected columns (case-insensitive): name, email, phone, current_company, title,
location, linkedin, github, skills, years_experience, headline
Any missing column is silently skipped.
"""

import csv
import io
from src.schema import RawRecord
from src.ingestors.base import BaseIngestor


class RecruiterCSVIngestor(BaseIngestor):
    source_name = "recruiter_csv"
    method_name = "csv_parse"

    # Maps CSV header variants → canonical raw key
    _HEADER_MAP = {
        "name": "full_name", "full name": "full_name", "fullname": "full_name",
        "email": "email", "email address": "email", "e-mail": "email",
        "phone": "phone", "phone number": "phone", "mobile": "phone",
        "current_company": "current_company", "company": "current_company",
        "employer": "current_company",
        "title": "title", "job title": "title", "position": "title",
        "location": "location", "city": "location",
        "linkedin": "linkedin", "linkedin url": "linkedin",
        "github": "github", "github url": "github",
        "skills": "skills", "skill set": "skills",
        "years_experience": "years_experience", "years experience": "years_experience",
        "experience": "years_experience",
        "headline": "headline", "summary": "headline",
    }

    def ingest(self, source) -> list[RawRecord]:
        """
        source: file path (str) or file-like object.
        Returns one RawRecord per non-empty row.
        """
        if isinstance(source, str):
            with open(source, newline="", encoding="utf-8-sig") as f:
                content = f.read()
        elif hasattr(source, "read"):
            content = source.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8-sig")
        else:
            raise ValueError(f"Unsupported source type: {type(source)}")

        reader = csv.DictReader(io.StringIO(content))
        records = []

        for row in reader:
            if not any(v.strip() for v in row.values()):
                continue  # skip blank rows

            fields = {}
            for col, val in row.items():
                if col is None:
                    continue
                mapped = self._HEADER_MAP.get(col.strip().lower())
                if mapped and val and val.strip():
                    # Accumulate; last-wins if column appears twice
                    existing = fields.get(mapped)
                    if existing:
                        # For emails/phones, comma-split may give multiple
                        fields[mapped] = f"{existing},{val.strip()}"
                    else:
                        fields[mapped] = val.strip()

            if not fields:
                continue

            records.append(
                RawRecord(
                    source=self.source_name,
                    method=self.method_name,
                    fields=fields,
                )
            )

        return records
