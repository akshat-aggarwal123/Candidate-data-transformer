# Multi-Source Candidate Data Transformer

A deterministic pipeline that ingests candidate data from multiple structured and unstructured sources, merges them into one canonical profile per person, and projects the output to any shape via a runtime config — with full provenance and confidence tracking.

## Architecture

```
Sources → Ingest → Normalize → Merge → Project → Validate → JSON output
```

| Layer | What it does |
|---|---|
| **Ingest** | Source-specific parsers (CSV, ATS JSON, GitHub API, recruiter notes). Each is isolated — one bad source never crashes the run. |
| **Normalize** | Phones → E.164, dates → YYYY-MM, countries → ISO-3166 alpha-2, skills → canonical names. |
| **Merge** | Groups records by email (primary) or name (fallback). Conflict resolution via source-trust hierarchy. Skills, emails, phones, experience unioned across sources. |
| **Canonical record** | One `CanonicalProfile` per candidate — always the full schema. |
| **Project** | Applies the runtime config to reshape, rename, or subset the canonical record. Supports dot-access (`location.city`), array index (`emails[0]`), and array-map (`skills[].name`) path expressions. |
| **Validate** | Checks required fields and missing-value policy before returning. |

### Source trust hierarchy (for conflict resolution)

```
ats_json (5) > recruiter_csv (4) > github / linkedin (3) > recruiter_notes (2)
```

Higher trust wins on scalar conflicts. Lists (emails, phones, skills, experience, education) are unioned across all sources.

### Confidence scoring

- Per-field: based on which sources contributed. Single source = source's base score; each additional agreeing source adds a small bonus.
- Overall: weighted average of source trust + diversity bonus + richness bonus.

## Quick start

### Prerequisites

```bash
pip3 install -r requirements.txt
```

### Run with sample data

```bash
# Default schema (full canonical output)
python3 cli.py --csv samples/candidates.csv --ats samples/ats_data.json \
               --notes samples/recruiter_notes.txt \
               --config configs/default.json --out output/default_output.json

# Custom config (renamed fields, subset, no provenance)
python3 cli.py --csv samples/candidates.csv --ats samples/ats_data.json \
               --notes samples/recruiter_notes.txt \
               --config configs/custom.json --out output/custom_output.json

# Add GitHub (fetches live data — requires internet)
python3 cli.py --csv samples/candidates.csv --github torvalds octocat \
               --config configs/default.json

# All sources at once
python3 cli.py --csv samples/candidates.csv --ats samples/ats_data.json \
               --github torvalds --notes samples/recruiter_notes.txt \
               --config configs/default.json --out output/all_sources.json
```

### Run tests

```bash
python3 -m pytest tests/ -v
```

## CLI reference

```
python3 cli.py [OPTIONS]

Options:
  --csv PATH              Recruiter CSV file
  --ats PATH              ATS JSON file
  --github URL_OR_USER    GitHub profile URL(s) or username(s) (space-separated)
  --notes PATH            Recruiter notes .txt file(s) (space-separated)
  --config PATH           Output config JSON (default: full canonical schema)
  --out PATH              Write output to file (default: stdout)
  --github-token TOKEN    GitHub PAT for higher API rate limits
                          (or set GITHUB_TOKEN env var)
```

## Runtime config format

The config reshapes output without changing the engine:

```json
{
  "fields": [
    { "path": "full_name", "type": "string", "required": true },
    { "path": "primary_email", "from": "emails[0]", "type": "string", "required": true },
    { "path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164" },
    { "path": "skills", "from": "skills[].name", "type": "string[]", "normalize": "canonical" },
    { "path": "location_city", "from": "location.city", "type": "string" }
  ],
  "include_provenance": false,
  "include_confidence": true,
  "on_missing": "null"
}
```

**Path expressions:**

| Expression | Meaning |
|---|---|
| `"full_name"` | Top-level field |
| `"location.city"` | Nested dot-access |
| `"emails[0]"` | First element of array |
| `"skills[].name"` | Map over array, extract `name` from each |

**`on_missing`:** `"null"` (default) | `"omit"` (skip field) | `"error"` (raise on required fields)

## Canonical output schema

```json
{
  "candidate_id": "uuid-v5-from-email",
  "full_name": "string",
  "emails": ["string"],
  "phones": ["E.164 string"],
  "location": { "city": "string|null", "region": "string|null", "country": "ISO-3166-alpha2|null" },
  "links": { "linkedin": "url|null", "github": "url|null", "portfolio": "url|null", "other": [] },
  "headline": "string|null",
  "years_experience": "number|null",
  "skills": [{ "name": "canonical", "confidence": 0.0–1.0, "sources": ["source_name"] }],
  "experience": [{ "company": "string", "title": "string", "start": "YYYY-MM", "end": "YYYY-MM|present|null", "summary": "string|null" }],
  "education": [{ "institution": "string", "degree": "string", "field": "string", "end_year": "int|null" }],
  "provenance": [{ "field": "field_name", "source": "source_name", "method": "method_name" }],
  "overall_confidence": 0.0–1.0
}
```

## Design decisions

**Two-layer architecture:** The canonical record is always built in full. The projection layer is a pure transformation applied afterward — these concerns are strictly separated.

**Email as primary match key:** Email is the strongest unique identifier for a person. If missing, falls back to normalized full_name. `candidate_id` is UUID v5 derived from this key — same inputs always produce the same ID (deterministic).

**"Honest empty" over invented values:** Every normalization step returns `null` on failure rather than guessing. A garbage phone number yields `null`, not a garbled string.

**Source isolation:** Each ingestor is wrapped in `_safe_ingest()` — exceptions are caught and logged; the run continues with the remaining sources.

**Notes files:** Recruiter notes are split by `---` separator. Each block is treated as one candidate's notes. A file with no separator is treated as one block. Fields found in a notes block have the lowest trust score.

## Assumptions and descoped items

- **LinkedIn ingestor:** Not implemented — LinkedIn's API requires OAuth and blocks scraping. The schema supports it and the CSV/ATS fields can carry LinkedIn URLs.
- **PDF/DOCX resume parser:** Descoped. Would require `pdfminer` or `python-docx` plus significant NLP; the design supports adding it as another ingestor.
- **Education deduplication:** Currently simple key-based dedup on (institution, degree); fuzzy matching not implemented.
- **Confidence decay over time:** Older work history not downweighted; implementing this would require more reliable date parsing across all sources.
- **Multi-region phone defaults:** Default region is US when no country code present. International numbers with country codes are handled correctly.

## Produced output

The `output/` directory contains the sample outputs:
- `output/default_output.json` — full canonical schema, all sources
- `output/custom_output.json` — custom config (renamed fields, no provenance)
