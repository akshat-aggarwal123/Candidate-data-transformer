from __future__ import annotations
"""
GitHub profile ingestor — uses the public GitHub REST API (no auth needed for public profiles).
Extracts: name, bio, location, blog (portfolio), email, repos, languages (as skills).
"""

import re
import urllib.request
import urllib.error
import json
from src.schema import RawRecord
from src.ingestors.base import BaseIngestor


_GITHUB_API = "https://api.github.com"
_USER_AGENT = "candidate-transformer/1.0"


def _get(url: str, token: str | None = None) -> dict | list | None:
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception:
        return None


def _extract_username(profile_url: str) -> str | None:
    """Extract username from github.com/username or raw username."""
    if not profile_url:
        return None
    m = re.search(r"github\.com/([A-Za-z0-9_-]+)", profile_url)
    if m:
        return m.group(1)
    # Might be passed as bare username
    if re.match(r"^[A-Za-z0-9_-]+$", profile_url.strip()):
        return profile_url.strip()
    return None


class GitHubIngestor(BaseIngestor):
    source_name = "github"
    method_name = "rest_api"

    def __init__(self, token: str | None = None):
        self.token = token  # optional PAT for higher rate limits

    def ingest(self, source) -> list[RawRecord]:
        """source: GitHub profile URL or username string."""
        username = _extract_username(source)
        if not username:
            print(f"[WARN] Cannot extract GitHub username from: {source!r}")
            return []

        user_data = _get(f"{_GITHUB_API}/users/{username}", self.token)
        if not user_data:
            print(f"[WARN] GitHub user not found or API unavailable: {username}")
            return []

        fields = {}

        if user_data.get("name"):
            fields["full_name"] = user_data["name"]
        if user_data.get("bio"):
            fields["headline"] = user_data["bio"]
        if user_data.get("email"):
            fields["email"] = user_data["email"]
        if user_data.get("location"):
            fields["location"] = user_data["location"]
        if user_data.get("blog"):
            fields["portfolio"] = user_data["blog"]
        if user_data.get("html_url"):
            fields["github"] = user_data["html_url"]
        if user_data.get("company"):
            fields["current_company"] = user_data["company"].lstrip("@").strip()

        # Collect languages across public repos as skill signals
        languages = self._collect_languages(username)
        if languages:
            fields["skills"] = languages

        # Rough years_experience heuristic: years since account creation
        created_at = user_data.get("created_at", "")
        if created_at:
            try:
                from datetime import datetime
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                now = datetime.now(tz=created.tzinfo)
                years = (now - created).days / 365.25
                fields["github_account_age_years"] = round(years, 1)
            except Exception:
                pass

        return [RawRecord(source=self.source_name, method=self.method_name, fields=fields)]

    def _collect_languages(self, username: str) -> list[str]:
        repos_data = _get(
            f"{_GITHUB_API}/users/{username}/repos?per_page=30&sort=updated",
            self.token,
        )
        if not repos_data or not isinstance(repos_data, list):
            return []

        lang_counts: dict[str, int] = {}
        for repo in repos_data:
            lang = repo.get("language")
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

        # Return languages sorted by frequency, top 10
        return [
            lang for lang, _ in sorted(lang_counts.items(), key=lambda x: -x[1])
        ][:10]
