#!/usr/bin/env python3
"""Explicit new preprocessing recipe; NOT recovered paper preprocessing."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def chunk_ids(ids, tokenizer, max_length, overlap):
    """Single-sequence windows; overlap counts content tokens, excluding specials."""
    capacity = max_length - tokenizer.num_special_tokens_to_add(pair=False)
    if capacity < 1 or not 0 <= overlap < capacity:
        raise ValueError('Require max_length > special-token count and 0 <= overlap < capacity')
    start = 0
    while start < len(ids):
        window = ids[start:start + capacity]
        encoded = tokenizer.prepare_for_model(
            window, add_special_tokens=True, truncation=False,
            return_attention_mask=True, return_token_type_ids=True,
        )
        yield dict(encoded)
        if start + capacity >= len(ids):
            break
        start += capacity - overlap


def preprocess(input_path, output_path, tokenizer_path, max_length, overlap, status):
    from transformers import AutoTokenizer
    import transformers
    if output_path.exists() or output_path.with_suffix(output_path.suffix + '.manifest.json').exists():
        raise ValueError('Output and manifest must not already exist')
    # A local tokenizer snapshot is mandatory: no drifting remote model revision.
    tokenizer_path = tokenizer_path.resolve(strict=True)
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path), local_files_only=True)
    list(chunk_ids([], tokenizer, max_length, overlap))  # validate even for empty inputs
    seen, output = set(), []
    for line_no, line in enumerate(input_path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f'Line {line_no}: expected object')
        pmid = str(row.get('pmid', '')).strip()
        if not pmid or pmid in seen:
            raise ValueError(f'Line {line_no}: missing or duplicate article identifier')
        if status == 'demo-only' and (not pmid.startswith('DEMO-') or row.get('data_status') != status):
            raise ValueError('Demo inputs must have DEMO- identifiers and data_status=demo-only')
        if status == 'reconstruction' and (not pmid.isascii() or not pmid.isdigit()):
            raise ValueError('Reconstruction inputs must use numeric PMIDs')
        if type(row.get('label')) is not int or row['label'] not in (0, 1):
            raise ValueError(f'Line {line_no}: label must be integer 0 or 1')
        if not all(isinstance(row.get(k), str) for k in ('title', 'abstract')):
            raise ValueError(f'Line {line_no}: title and abstract must be strings')
        text = row['title'].strip() + '\n\n' + row['abstract'].strip()
        if not text.strip():
            raise ValueError(f'Line {line_no}: empty text')
        ids = tokenizer.encode(text, add_special_tokens=False, truncation=False)
        if not ids:
            raise ValueError(f'Line {line_no}: no tokens')
        seen.add(pmid)
        for index, encoded in enumerate(chunk_ids(ids, tokenizer, max_length, overlap)):
            output.append(dict(pmid=pmid, chunk_index=index, label=row['label'],
                               data_status=status, **encoded))
    if not output:
        raise ValueError('No articles found')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(''.join(json.dumps(r) + '\n' for r in output), encoding='utf-8')
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = dict(
        schema_version=1, data_status=status, recipe='explicit-single-sequence-v1',
        paper_preprocessing=False, input_sha256=digest(input_path),
        output_sha256=digest(output_path), articles=len(seen), chunks=len(output),
        text_composition='title.strip() + two newlines + abstract.strip()',
        tokenizer_files={str(p.relative_to(tokenizer_path)): digest(p)
                         for p in sorted(tokenizer_path.rglob('*')) if p.is_file()
                         and p.suffix in ('.json', '.txt')},
        transformers_version=transformers.__version__, max_length=max_length,
        overlap_content_tokens=overlap, padding='none; batch padding in training',
        short_final_chunk='retained', chunk_index='zero-based per article',
    )
    output_path.with_suffix(output_path.suffix + '.manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tokenizer-dir', type=Path, required=True)
    parser.add_argument('--max-length', type=int, required=True)
    parser.add_argument('--overlap', type=int, required=True)
    parser.add_argument('--status', choices=['demo-only', 'reconstruction'], required=True)
    args = parser.parse_args()
    print(json.dumps(preprocess(args.input, args.output, args.tokenizer_dir,
                                args.max_length, args.overlap, args.status), indent=2))


if __name__ == '__main__':
    main()
