"""Tests for normalization functions."""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.normalizers.phone import normalize_phone
from src.normalizers.date import normalize_date
from src.normalizers.location import normalize_country, parse_location_string
from src.normalizers.skills import canonicalize_skill, canonicalize_skills


class TestPhoneNormalization:
    def test_ten_digit_us(self):
        assert normalize_phone("4155550192") == "+14155550192"

    def test_formatted_us(self):
        assert normalize_phone("(415) 555-0192") == "+14155550192"

    def test_already_e164(self):
        assert normalize_phone("+14155550192") == "+14155550192"

    def test_international(self):
        result = normalize_phone("+44 20 7946 0958")
        assert result is not None
        assert result.startswith("+44")

    def test_empty_returns_none(self):
        assert normalize_phone("") is None
        assert normalize_phone(None) is None

    def test_garbage_returns_none(self):
        assert normalize_phone("not-a-phone") is None

    def test_brazil_number(self):
        result = normalize_phone("+55 11 99999-1234")
        assert result is not None
        assert result.startswith("+55")


class TestDateNormalization:
    def test_already_yyyy_mm(self):
        assert normalize_date("2020-03") == "2020-03"

    def test_yyyy_mm_dd(self):
        assert normalize_date("2020-03-15") == "2020-03"

    def test_month_name_year(self):
        assert normalize_date("March 2020") == "2020-03"
        assert normalize_date("Jan 2019") == "2019-01"

    def test_year_only(self):
        assert normalize_date("2022") == "2022-01"

    def test_present(self):
        assert normalize_date("present") == "present"
        assert normalize_date("current") == "present"

    def test_none_returns_none(self):
        assert normalize_date(None) is None
        assert normalize_date("") is None

    def test_garbage_returns_none(self):
        assert normalize_date("whenever") is None

    def test_mm_yyyy(self):
        assert normalize_date("06/2021") == "2021-06"


class TestLocationNormalization:
    def test_full_us_location(self):
        result = parse_location_string("San Francisco, CA, US")
        assert result["city"] == "San Francisco"
        assert result["region"] == "CA"
        assert result["country"] == "US"

    def test_country_name(self):
        assert normalize_country("United States") == "US"
        assert normalize_country("India") == "IN"
        assert normalize_country("uk") == "GB"

    def test_already_iso2(self):
        assert normalize_country("SG") == "SG"

    def test_unknown_returns_none(self):
        assert normalize_country("Atlantis") is None

    def test_city_country(self):
        result = parse_location_string("Singapore")
        assert result["country"] == "SG"

    def test_two_part(self):
        result = parse_location_string("Dubai, UAE")
        assert result["city"] == "Dubai"
        assert result["country"] == "AE"


class TestSkillNormalization:
    def test_canonical_known(self):
        assert canonicalize_skill("js") == "JavaScript"
        assert canonicalize_skill("nodejs") == "Node.js"
        assert canonicalize_skill("sklearn") == "scikit-learn"
        assert canonicalize_skill("k8s") == "Kubernetes"

    def test_case_insensitive(self):
        assert canonicalize_skill("PYTHON") == "Python"
        assert canonicalize_skill("React") == "React"

    def test_unknown_returns_original(self):
        result = canonicalize_skill("SomeObscureFramework")
        assert result == "SomeObscureFramework"

    def test_deduplicated_list(self):
        skills = canonicalize_skills(["js", "JavaScript", "python", "Python"])
        assert skills.count("JavaScript") == 1
        assert skills.count("Python") == 1
        assert len(skills) == 2
