"""
Recruiter notes (.txt) ingestor.
Uses regex heuristics to extract structured fields from free text.
This is inherently lower confidence than structured sources.
"""

import re
from src.schema import RawRecord
from src.ingestors.base import BaseIngestor


_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?\d[\s\-.]?)?(?:\(?\d{3}\)?[\s\-.]?)?\d{3}[\s\-.]?\d{4}"
)
_LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w\-]+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"github\.com/[\w\-]+", re.IGNORECASE)
_NAME_RE = re.compile(
    r"(?:candidate|applicant|name)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)",
    re.IGNORECASE,
)
_SKILLS_LABEL_RE = re.compile(
    r"(?:skills?|tech(?:nologies)?|stack|expertise)[:\s]+([^\n]+)",
    re.IGNORECASE,
)
_COMPANY_RE = re.compile(
    r"(?:currently?\s+at|works?\s+at|company)[:\s]+([^\n,\.;]+?)(?=\s+as\b|\s+in\b|[,\.\n]|$)",
    re.IGNORECASE,
)
_TITLE_RE = re.compile(
    r"(?:title|role|position)[:\s]+([^\n,]+)",
    re.IGNORECASE,
)
_YOE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*years?\s*(?:of\s+)?(?:experience|exp)",
    re.IGNORECASE,
)


class RecruiterNotesIngestor(BaseIngestor):
    source_name = "recruiter_notes"
    method_name = "regex_extract"

    def ingest(self, source) -> list[RawRecord]:
        """
        source: file path (str) or string content.
        If the file contains multiple candidates separated by '---', each block
        is extracted independently — one RawRecord per block.
        """
        if isinstance(source, str):
            try:
                with open(source, encoding="utf-8") as f:
                    text = f.read()
            except (FileNotFoundError, IsADirectoryError):
                text = source
        elif hasattr(source, "read"):
            text = source.read()
        else:
            raise ValueError(f"Unsupported source: {type(source)}")

        if not text.strip():
            return []

        # Split on '---' separator; fall back to treating whole file as one block
        blocks = [b.strip() for b in re.split(r"\n---+\n?", text) if b.strip()]
        records = []
        for block in blocks:
            rec = self._extract_block(block)
            if rec:
                records.append(rec)
        return records

    def _extract_block(self, text: str):
        """Extract a RawRecord from a single candidate text block."""
        fields = {}

        emails = _EMAIL_RE.findall(text)
        if emails:
            fields["email"] = emails[0]

        phones = _PHONE_RE.findall(text)
        if phones:
            fields["phone"] = phones[0]

        m = _NAME_RE.search(text)
        if m:
            fields["full_name"] = m.group(1).strip()

        m = _LINKEDIN_RE.search(text)
        if m:
            fields["linkedin"] = f"https://{m.group()}"

        m = _GITHUB_RE.search(text)
        if m:
            fields["github"] = f"https://{m.group()}"

        m = _SKILLS_LABEL_RE.search(text)
        if m:
            raw_skills = [s.strip() for s in re.split(r"[,;/]", m.group(1))]
            fields["skills"] = [s for s in raw_skills if s]

        m = _COMPANY_RE.search(text)
        if m:
            fields["current_company"] = m.group(1).strip()

        m = _TITLE_RE.search(text)
        if m:
            fields["title"] = m.group(1).strip()

        m = _YOE_RE.search(text)
        if m:
            fields["years_experience"] = float(m.group(1))

        if not fields:
            return None

        return RawRecord(source=self.source_name, method=self.method_name, fields=fields)
