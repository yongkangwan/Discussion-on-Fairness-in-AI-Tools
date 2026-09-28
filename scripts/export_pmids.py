#!/usr/bin/env python3
"""Export a de-duplicated PMID list from one or more internal JSONL files.

This utility is intended for preparing a public release without redistributing
titles, abstracts, affiliations, token arrays, or other third-party text.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export unique PMIDs from JSONL files, one identifier per line."
    )
    parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        type=Path,
        help="One or more JSONL files containing a 'pmid' field.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination text file. Parent directories are created automatically.",
    )
    return parser.parse_args()


def load_pmids(paths: list[Path]) -> set[str]:
    pmids: set[str] = set()
    for raw_path in paths:
        path = raw_path.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Input file does not exist: {path}")

        with path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSON") from exc

                if not isinstance(row, dict):
                    raise ValueError(f"{path}:{line_number}: expected a JSON object")

                raw_pmid = row.get("pmid")
                if raw_pmid is None:
                    raise ValueError(f"{path}:{line_number}: missing 'pmid'")

                pmid = str(raw_pmid).strip()
                if not pmid:
                    raise ValueError(f"{path}:{line_number}: empty 'pmid'")

                pmids.add(pmid)

    return pmids


def pmid_sort_key(pmid: str) -> tuple[int, int | str]:
    if pmid.isdigit():
        return (0, int(pmid))
    return (1, pmid)


def main() -> None:
    args = parse_args()
    pmids = load_pmids(args.input)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(f"{pmid}\n" for pmid in sorted(pmids, key=pmid_sort_key)),
        encoding="utf-8",
    )
    print(f"Wrote {len(pmids)} unique PMIDs to {output}")


if __name__ == "__main__":
    main()
