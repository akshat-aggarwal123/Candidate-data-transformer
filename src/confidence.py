from __future__ import annotations
"""
Confidence scoring.

Design:
- Single source: 0.5 (we have data but can't cross-verify)
- Each additional source that contributes: +0.1 (capped)
- Fields well-populated (skills, experience): small bonus
- Returns overall_confidence in [0.0, 1.0]
"""

SOURCE_TRUST = {
    "ats_json": 0.9,
    "recruiter_csv": 0.8,
    "github": 0.75,
    "linkedin": 0.7,
    "recruiter_notes": 0.5,
}


def score_field(sources: list[str]) -> float:
    """Per-field confidence based on how many independent sources agree."""
    if not sources:
        return 0.0
    if len(sources) == 1:
        return SOURCE_TRUST.get(sources[0], 0.5)
    # Multiple sources: average trust + agreement bonus
    avg = sum(SOURCE_TRUST.get(s, 0.5) for s in sources) / len(sources)
    agreement_bonus = min(0.1 * (len(sources) - 1), 0.15)
    return min(1.0, round(avg + agreement_bonus, 3))


def overall_confidence(
    sources: list[str],
    num_skills: int,
    years_experience: float | None,
) -> float:
    """
    Composite confidence for the whole profile.
    Reflects: source diversity, richness of extracted data.
    """
    if not sources:
        return 0.0

    base = sum(SOURCE_TRUST.get(s, 0.5) for s in sources) / len(sources)
    diversity_bonus = min(0.05 * (len(sources) - 1), 0.15)

    richness = 0.0
    if num_skills >= 5:
        richness += 0.05
    if years_experience is not None:
        richness += 0.03

    return min(1.0, round(base + diversity_bonus + richness, 3))
