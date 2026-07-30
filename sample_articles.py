"""Reproducibly sample whole articles while retaining all of their chunks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from paper_mill_common import (
    SCHEMA_VERSION,
    file_fingerprint,
    load_labeled_corpus,
    load_manifest_pmids,
    select_chunks,
    write_json,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sample N PMIDs from one pre-tokenized JSONL file, keep every chunk "
            "belonging to each sampled PMID, and force a cohort label."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n-articles", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--label", type=int, choices=[0, 1], default=0)
    parser.add_argument(
        "--exclude-jsonl",
        nargs="*",
        type=Path,
        default=[],
        help="Exclude every PMID occurring in these JSONL files before sampling.",
    )
    parser.add_argument(
        "--exclude-manifest",
        nargs="*",
        type=Path,
        default=[],
        help="Exclude every PMID listed in these split_manifest.json files.",
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=None,
        help="Default: OUTPUT with '.manifest.json' appended.",
    )
    parser.add_argument("--max-length", type=int, default=512)
    return parser.parse_args()


def pmids_from_jsonl(path: Path) -> set[str]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Exclusion JSONL does not exist: {resolved}")
    pmids: set[str] = set()
    with resolved.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{resolved}:{line_number}: invalid JSON") from exc
            raw_pmid = row.get("pmid") if isinstance(row, dict) else None
            if raw_pmid is None or not str(raw_pmid).strip():
                raise ValueError(f"{resolved}:{line_number}: missing or empty pmid")
            pmids.add(str(raw_pmid).strip())
    return pmids


def main() -> None:
    args = parse_args()
    if args.n_articles < 1:
        raise ValueError("--n-articles must be positive")
    if args.max_length < 1:
        raise ValueError("--max-length must be positive")

    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    manifest_path = (
        args.manifest_output.expanduser().resolve()
        if args.manifest_output is not None
        else Path(str(output_path) + ".manifest.json")
    )
    if output_path == input_path:
        raise ValueError("--output must differ from --input")
    for destination in (output_path, manifest_path):
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite existing output: {destination}")

    corpus = load_labeled_corpus(
        [input_path] if args.label == 1 else [],
        [input_path] if args.label == 0 else [],
        max_length=args.max_length,
    )
    excluded_pmids: set[str] = set()
    exclusion_details: list[dict[str, Any]] = []
    for raw_path in args.exclude_jsonl:
        path = raw_path.expanduser().resolve()
        file_pmids = pmids_from_jsonl(path)
        excluded_pmids.update(file_pmids)
        detail = file_fingerprint(path)
        detail.update({"kind": "jsonl", "n_unique_pmids": len(file_pmids)})
        exclusion_details.append(detail)
    for raw_path in args.exclude_manifest:
        path = raw_path.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Exclusion manifest does not exist: {path}")
        file_pmids = load_manifest_pmids(path)
        excluded_pmids.update(file_pmids)
        detail = file_fingerprint(path)
        detail.update({"kind": "manifest", "n_unique_pmids": len(file_pmids)})
        exclusion_details.append(detail)

    all_pmids = set(corpus.article_ids)
    overlapping_exclusions = all_pmids & excluded_pmids
    eligible_pmids = sorted(all_pmids - excluded_pmids)
    if len(eligible_pmids) < args.n_articles:
        raise ValueError(
            f"Only {len(eligible_pmids)} eligible articles remain after exclusions; "
            f"cannot sample {args.n_articles}"
        )
    # Hash ranking is deterministic across Python/NumPy versions and does not
    # depend on source-file row order.
    def sample_rank(pmid: str) -> tuple[bytes, str]:
        digest = hashlib.sha256(f"{args.seed}\0{pmid}".encode("utf-8")).digest()
        return digest, pmid

    sampled_pmids = sorted(
        sorted(eligible_pmids, key=sample_rank)[: args.n_articles]
    )
    sampled_chunks = select_chunks(corpus, sampled_pmids)
    compact_rows = [
        {
            "pmid": record.pmid,
            "chunk_index": record.chunk_index,
            "label": args.label,
            "input_ids": record.input_ids,
            "attention_mask": record.attention_mask,
            "token_type_ids": record.token_type_ids,
        }
        for record in sampled_chunks
    ]
    write_jsonl(output_path, compact_rows)

    chunk_counts: dict[str, int] = {pmid: 0 for pmid in sampled_pmids}
    for record in sampled_chunks:
        chunk_counts[record.pmid] += 1
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "sampling_unit": "article/pmid",
        "input": file_fingerprint(input_path),
        "output": file_fingerprint(output_path),
        "forced_label": args.label,
        "seed": args.seed,
        "sampling_algorithm": "first N by sha256(f'{seed}\\0{pmid}'), PMID tie-break",
        "requested_articles": args.n_articles,
        "input_articles": corpus.n_articles,
        "input_chunks": len(corpus.chunks),
        "excluded_input_articles": len(overlapping_exclusions),
        "eligible_articles": len(eligible_pmids),
        "sampled_articles": len(sampled_pmids),
        "sampled_chunks": len(sampled_chunks),
        "exclusion_sources": exclusion_details,
        "sampled_pmids": [
            {"pmid": pmid, "n_chunks": chunk_counts[pmid]}
            for pmid in sampled_pmids
        ],
    }
    write_json(manifest_path, manifest)
    print(
        f"Sampled {len(sampled_pmids)} articles / {len(sampled_chunks)} chunks "
        f"from {input_path.name}; excluded {len(overlapping_exclusions)} input PMIDs."
    )
    print(f"JSONL: {output_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
