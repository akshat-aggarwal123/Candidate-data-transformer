"""Tests for the merger — identity matching, conflict resolution, provenance."""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.schema import RawRecord
from src.merger import merge, _candidate_key, _deterministic_id


class TestCandidateKey:
    def test_email_key(self):
        rec = RawRecord("csv", "csv_parse", {"email": "alice@example.com", "full_name": "Alice"})
        assert _candidate_key(rec) == "email:alice@example.com"

    def test_email_normalized(self):
        rec = RawRecord("csv", "csv_parse", {"email": "  Alice@EXAMPLE.COM  "})
        assert _candidate_key(rec) == "email:alice@example.com"

    def test_fallback_to_name(self):
        rec = RawRecord("csv", "csv_parse", {"full_name": "Bob Smith"})
        assert _candidate_key(rec) == "name:bob smith"

    def test_same_email_different_sources_merge(self):
        records = [
            RawRecord("recruiter_csv", "csv_parse", {
                "email": "alice@example.com", "full_name": "Alice Smith", "phone": "4155550100"
            }),
            RawRecord("github", "rest_api", {
                "email": "alice@example.com", "full_name": "Alice Smith",
                "skills": ["Python", "Go"], "headline": "Engineer at BigCo"
            }),
        ]
        profiles = merge(records)
        assert len(profiles) == 1  # merged into one

    def test_different_emails_different_profiles(self):
        records = [
            RawRecord("recruiter_csv", "csv_parse", {"email": "alice@example.com", "full_name": "Alice"}),
            RawRecord("recruiter_csv", "csv_parse", {"email": "bob@example.com", "full_name": "Bob"}),
        ]
        profiles = merge(records)
        assert len(profiles) == 2


class TestMergeOutput:
    def _base_records(self):
        return [
            RawRecord("ats_json", "json_parse", {
                "full_name": "Priya Sharma",
                "email": "priya@example.com",
                "phone": "+14155550192",
                "skills": ["Python", "Spark", "AWS"],
                "years_experience": 6,
            }),
            RawRecord("recruiter_csv", "csv_parse", {
                "full_name": "Priya Sharma",
                "email": "priya@example.com",
                "phone": "(415) 555-0193",
                "skills": ["Python", "Kafka"],
            }),
        ]

    def test_phone_normalized(self):
        profiles = merge(self._base_records())
        assert len(profiles) == 1
        profile = profiles[0]
        for phone in profile.phones:
            assert phone.startswith("+"), f"Phone not E.164: {phone}"

    def test_skills_unioned(self):
        profiles = merge(self._base_records())
        skill_names = {s.name for s in profiles[0].skills}
        assert "Python" in skill_names
        assert "Apache Spark" in skill_names or "Spark" in skill_names or any("Spark" in s for s in skill_names)

    def test_provenance_populated(self):
        profiles = merge(self._base_records())
        assert len(profiles[0].provenance) > 0
        for prov in profiles[0].provenance:
            assert prov.source in ("ats_json", "recruiter_csv")
            assert prov.field

    def test_confidence_gt_zero(self):
        profiles = merge(self._base_records())
        assert profiles[0].overall_confidence > 0

    def test_deterministic_id(self):
        """Same input always produces same candidate_id."""
        id1 = _deterministic_id("email:alice@example.com")
        id2 = _deterministic_id("email:alice@example.com")
        assert id1 == id2

    def test_conflict_resolution_ats_wins_over_csv(self):
        """ATS has higher trust than CSV; years_experience from ATS should win."""
        records = [
            RawRecord("ats_json", "json_parse", {
                "email": "x@example.com", "years_experience": 10
            }),
            RawRecord("recruiter_csv", "csv_parse", {
                "email": "x@example.com", "years_experience": 3
            }),
        ]
        profiles = merge(records)
        assert profiles[0].years_experience == 10

    def test_empty_records_returns_empty(self):
        assert merge([]) == []

    def test_garbage_source_isolated(self):
        """A record with no usable fields should still produce a profile without crashing."""
        records = [
            RawRecord("recruiter_csv", "csv_parse", {"email": "good@example.com", "full_name": "Good Candidate"}),
            RawRecord("recruiter_notes", "regex_extract", {}),  # empty fields — garbage
        ]
        profiles = merge(records)
        assert any(p.full_name == "Good Candidate" for p in profiles)
