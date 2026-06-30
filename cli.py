#!/usr/bin/env python3
"""
Multi-Source Candidate Data Transformer — CLI

Usage:
  python cli.py --csv samples/candidates.csv --github torvalds --config configs/default.json
  python cli.py --csv samples/candidates.csv --ats samples/ats_data.json --out output/profiles.json
  python cli.py --help
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.pipeline import run


def main():
    parser = argparse.ArgumentParser(
        prog="candidate-transformer",
        description="Transform multi-source candidate data into a canonical profile.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default schema, CSV + GitHub
  python cli.py --csv samples/candidates.csv --github torvalds

  # ATS JSON + GitHub, custom output config
  python cli.py --ats samples/ats_data.json --github torvalds \\
                --config configs/custom.json --out output/custom.json

  # All sources
  python cli.py --csv samples/candidates.csv --ats samples/ats_data.json \\
                --github torvalds octocat --notes samples/recruiter_notes.txt \\
                --config configs/default.json
        """,
    )

    parser.add_argument("--csv", metavar="PATH", help="Recruiter CSV file path")
    parser.add_argument("--ats", metavar="PATH", help="ATS JSON file path")
    parser.add_argument(
        "--github",
        metavar="URL_OR_USER",
        nargs="+",
        help="GitHub profile URL(s) or username(s)",
    )
    parser.add_argument(
        "--notes",
        metavar="PATH",
        nargs="+",
        help="Recruiter notes .txt file path(s)",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Output config JSON (default: canonical schema, no transformation)",
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        help="Write JSON output to this file (default: print to stdout)",
    )
    parser.add_argument(
        "--github-token",
        metavar="TOKEN",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub PAT for higher API rate limits (or set GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: true)",
    )

    args = parser.parse_args()

    if not any([args.csv, args.ats, args.github, args.notes]):
        parser.error("Provide at least one source: --csv, --ats, --github, or --notes")

    profiles = run(
        csv_path=args.csv,
        ats_json_path=args.ats,
        github_urls=args.github,
        notes_paths=args.notes,
        config_path=args.config,
        github_token=args.github_token,
    )

    indent = 2 if args.pretty else None
    output_json = json.dumps(profiles, indent=indent, ensure_ascii=False)

    if args.out:
        os.makedirs(os.path.dirname(args.out) if os.path.dirname(args.out) else ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"[INFO] Output written to {args.out}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
