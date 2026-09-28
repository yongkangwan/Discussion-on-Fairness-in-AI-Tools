#!/usr/bin/env python3
"""Remove records whose PMID appears in one or more exclusion files.

This replaces the old one-off local script with a portable command-line utility.
Only the JSON objects are copied; no interpretation of labels is performed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filter JSONL records by PMID using one or more exclusion JSONL files."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input JSONL to filter.")
    parser.add_argument(
        "--exclude",
        nargs="+",
        required=True,
        type=Path,
        help="JSONL file(s) whose PMIDs should be excluded.",
    )
    parser.add_argument("--output", required=True, type=Path, help="Filtered JSONL output.")
    parser.add_argument(
        "--removed-pmids",
        type=Path,
        default=None,
        help="Optional text file containing removed PMIDs, one per line.",
    )
    return parser.parse_args()


def iter_jsonl(path: Path):
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
            yield line_number, row


def get_pmid(path: Path, line_number: int, row: dict) -> str:
    raw = row.get("pmid")
    if raw is None or not str(raw).strip():
        raise ValueError(f"{path}:{line_number}: missing or empty PMID")
    return str(raw).strip()


def main() -> None:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    exclusion_paths = [p.expanduser().resolve() for p in args.exclude]

    if output_path == input_path:
        raise ValueError("--output must differ from --input")

    excluded: set[str] = set()
    for path in exclusion_paths:
        if not path.is_file():
            raise FileNotFoundError(f"Exclusion file does not exist: {path}")
        for line_number, row in iter_jsonl(path):
            excluded.add(get_pmid(path, line_number, row))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    removed: set[str] = set()
    kept = 0
    total = 0

    with output_path.open("w", encoding="utf-8") as out:
        for line_number, row in iter_jsonl(input_path):
            total += 1
            pmid = get_pmid(input_path, line_number, row)
            if pmid in excluded:
                removed.add(pmid)
                continue
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            kept += 1

    if args.removed_pmids is not None:
        removed_path = args.removed_pmids.expanduser().resolve()
        removed_path.parent.mkdir(parents=True, exist_ok=True)
        removed_path.write_text(
            "".join(f"{pmid}\n" for pmid in sorted(removed)),
            encoding="utf-8",
        )

    print(
        f"Filtered {input_path}: total_rows={total}, kept_rows={kept}, "
        f"removed_unique_pmids={len(removed)}"
    )


if __name__ == "__main__":
    main()
