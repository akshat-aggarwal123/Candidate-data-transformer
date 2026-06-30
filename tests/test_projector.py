"""Tests for the projection layer and path resolver."""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.projector import project, _resolve_path, ProjectionError


CANONICAL = {
    "candidate_id": "abc-123",
    "full_name": "Alice Doe",
    "emails": ["alice@example.com", "alice@work.com"],
    "phones": ["+14155550100"],
    "location": {"city": "San Francisco", "region": "CA", "country": "US"},
    "links": {"linkedin": "https://linkedin.com/in/alicedoe", "github": None, "portfolio": None, "other": []},
    "headline": "Senior Engineer",
    "years_experience": 8.0,
    "skills": [
        {"name": "Python", "confidence": 0.9, "sources": ["ats_json", "recruiter_csv"]},
        {"name": "AWS", "confidence": 0.8, "sources": ["ats_json"]},
    ],
    "experience": [
        {"company": "BigCo", "title": "Staff Engineer", "start": "2020-01", "end": None, "summary": "Led platform team"},
    ],
    "education": [{"institution": "MIT", "degree": "B.S.", "field": "CS", "end_year": 2015}],
    "provenance": [{"field": "full_name", "source": "ats_json", "method": "json_parse"}],
    "overall_confidence": 0.88,
}


class TestPathResolver:
    def test_simple_key(self):
        assert _resolve_path(CANONICAL, "full_name") == "Alice Doe"

    def test_nested_key(self):
        assert _resolve_path(CANONICAL, "location.city") == "San Francisco"

    def test_array_index(self):
        assert _resolve_path(CANONICAL, "emails[0]") == "alice@example.com"
        assert _resolve_path(CANONICAL, "emails[1]") == "alice@work.com"

    def test_array_index_out_of_bounds(self):
        assert _resolve_path(CANONICAL, "emails[99]") is None

    def test_map_operator(self):
        result = _resolve_path(CANONICAL, "skills[].name")
        assert result == ["Python", "AWS"]

    def test_map_nested(self):
        result = _resolve_path(CANONICAL, "skills[].confidence")
        assert result == [0.9, 0.8]

    def test_missing_key_returns_none(self):
        assert _resolve_path(CANONICAL, "nonexistent") is None


class TestProject:
    def test_no_config_returns_full_canonical(self):
        result = project(CANONICAL, {})
        assert result["full_name"] == "Alice Doe"
        assert "provenance" in result

    def test_field_subset(self):
        config = {
            "fields": [
                {"path": "full_name"},
                {"path": "primary_email", "from": "emails[0]"},
            ],
            "include_provenance": False,
            "include_confidence": False,
        }
        result = project(CANONICAL, config)
        assert set(result.keys()) == {"full_name", "primary_email"}
        assert result["primary_email"] == "alice@example.com"

    def test_on_missing_omit(self):
        config = {
            "fields": [
                {"path": "full_name"},
                {"path": "nonexistent_field"},
            ],
            "on_missing": "omit",
            "include_provenance": False,
            "include_confidence": False,
        }
        result = project(CANONICAL, config)
        assert "nonexistent_field" not in result
        assert "full_name" in result

    def test_on_missing_null(self):
        config = {
            "fields": [
                {"path": "nonexistent_field"},
            ],
            "on_missing": "null",
            "include_provenance": False,
            "include_confidence": False,
        }
        result = project(CANONICAL, config)
        assert result.get("nonexistent_field") is None

    def test_on_missing_error_raises(self):
        config = {
            "fields": [
                {"path": "ghost", "required": True},
            ],
            "on_missing": "error",
            "include_provenance": False,
            "include_confidence": False,
        }
        with pytest.raises(ProjectionError):
            project(CANONICAL, config)

    def test_e164_normalization(self):
        config = {
            "fields": [
                {"path": "phone", "from": "phones[0]", "normalize": "E164"},
            ],
            "include_provenance": False,
            "include_confidence": False,
        }
        result = project(CANONICAL, config)
        assert result["phone"] == "+14155550100"

    def test_skill_map(self):
        config = {
            "fields": [
                {"path": "skill_names", "from": "skills[].name", "normalize": "canonical"},
            ],
            "include_provenance": False,
            "include_confidence": False,
        }
        result = project(CANONICAL, config)
        assert "Python" in result["skill_names"]

    def test_provenance_excluded(self):
        result = project(CANONICAL, {"include_provenance": False})
        assert "provenance" not in result

    def test_confidence_excluded(self):
        result = project(CANONICAL, {"include_confidence": False})
        assert "overall_confidence" not in result
