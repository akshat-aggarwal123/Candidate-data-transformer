from __future__ import annotations
"""
Pipeline orchestrator — wires together ingest → normalize → merge → project → validate.

Each source is isolated: a failure in one source degrades that source to "no data"
without crashing the rest of the run.
"""

import json
import os
from typing import Any

from src.schema import RawRecord
from src.ingestors.csv_ingestor import RecruiterCSVIngestor
from src.ingestors.ats_json import ATSJsonIngestor
from src.ingestors.github_ingestor import GitHubIngestor
from src.ingestors.notes_ingestor import RecruiterNotesIngestor
from src.merger import merge
from src.projector import project, validate_required, ProjectionError


def _load_config(config_path: str | None) -> dict:
    if not config_path:
        return {}
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def run(
    *,
    csv_path: str | None = None,
    ats_json_path: str | None = None,
    github_urls: list[str] | None = None,
    notes_paths: list[str] | None = None,
    config_path: str | None = None,
    github_token: str | None = None,
) -> list[dict]:
    """
    Run the full pipeline. Returns list of projected profile dicts.

    Arguments:
      csv_path       — path to recruiter CSV
      ats_json_path  — path to ATS JSON file
      github_urls    — list of GitHub profile URLs or usernames
      notes_paths    — list of recruiter notes .txt paths
      config_path    — path to output config JSON (optional)
      github_token   — GitHub PAT for higher rate limits (optional)
    """
    all_records: list[RawRecord] = []

    # ── Structured sources ──────────────────────────────────────────────────
    if csv_path:
        ingestor = RecruiterCSVIngestor()
        records = ingestor._safe_ingest(csv_path)
        print(f"[INFO] CSV: {len(records)} records from {csv_path}")
        all_records.extend(records)

    if ats_json_path:
        ingestor = ATSJsonIngestor()
        records = ingestor._safe_ingest(ats_json_path)
        print(f"[INFO] ATS JSON: {len(records)} records from {ats_json_path}")
        all_records.extend(records)

    # ── Unstructured sources ─────────────────────────────────────────────────
    if github_urls:
        gh_ingestor = GitHubIngestor(token=github_token)
        for url in github_urls:
            records = gh_ingestor._safe_ingest(url)
            print(f"[INFO] GitHub {url}: {len(records)} records")
            all_records.extend(records)

    if notes_paths:
        notes_ingestor = RecruiterNotesIngestor()
        for path in notes_paths:
            records = notes_ingestor._safe_ingest(path)
            print(f"[INFO] Notes {path}: {len(records)} records")
            all_records.extend(records)

    if not all_records:
        print("[WARN] No records extracted from any source.")
        return []

    # ── Merge ────────────────────────────────────────────────────────────────
    canonical_profiles = merge(all_records)
    print(f"[INFO] Merged into {len(canonical_profiles)} canonical profile(s)")

    # ── Project & Validate ───────────────────────────────────────────────────
    config = _load_config(config_path)
    fields_spec = config.get("fields", [])
    on_missing = config.get("on_missing", "null")

    results = []
    for profile in canonical_profiles:
        canonical_dict = profile.to_dict()
        try:
            projected = project(canonical_dict, config)
        except ProjectionError as e:
            print(f"[ERROR] Projection failed for {profile.candidate_id}: {e}")
            continue

        # Validation
        errors = validate_required(projected, fields_spec, on_missing)
        if errors:
            for err in errors:
                print(f"[WARN] {profile.candidate_id}: {err}")

        results.append(projected)

    return results
