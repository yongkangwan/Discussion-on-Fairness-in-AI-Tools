#!/usr/bin/env python3
"""Re-export pinned historical Git blobs as PMID-only lists; archive access required."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(archive, *args):
    return subprocess.check_output(['git', '-C', str(archive), *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory must be new or empty')
    manifest = json.loads((ROOT / 'data/pmids/manifest.json').read_text())
    commit = manifest['source_commit']
    results = []
    # Verify every source first, before writing any lists. No raw text is saved.
    for c in manifest['cohorts']:
        blob = git(args.archive, 'rev-parse', f'{commit}:{c["source_path"]}').decode().strip()
        if blob != c['source_git_blob_sha']:
            raise ValueError(f'Source blob mismatch: {c["source_path"]}')
        raw = git(args.archive, 'cat-file', 'blob', blob)
        if hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest() != blob:
            raise ValueError('Git object content hash mismatch')
        rows = [json.loads(x) for x in raw.decode('utf-8-sig').splitlines() if x.strip()]
        ids, counts = set(), {}
        for row in rows:
            pmid = str(row.get('pmid', '')).strip()
            if not re.fullmatch(r'[1-9][0-9]*', pmid):
                raise ValueError('Source includes non-PMID identifiers')
            ids.add(pmid)
            counts[pmid] = counts.get(pmid, 0) + 1
        text = ''.join(x + '\n' for x in sorted(ids, key=int))
        if (len(raw) != c['source_bytes'] or len(rows) != c['source_rows']
                or len(ids) != c['unique_pmids']
                or hashlib.sha256(text.encode()).hexdigest() != c['pmid_file_sha256']):
            raise ValueError(f'Source count/export mismatch: {c["source_path"]}')
        if 'sampling_evidence' in c:
            evidence = c['sampling_evidence']
            sampled_blob = git(args.archive, 'rev-parse', f'{commit}:{evidence["source_path"]}').decode().strip()
            if sampled_blob != evidence['source_git_blob_sha']:
                raise ValueError('Sampling manifest blob mismatch')
            sampled = json.loads(git(args.archive, 'cat-file', 'blob', sampled_blob))
            if (len(sampled['sampled_pmids']) != len(ids)
                    or {x['pmid']: x['n_chunks'] for x in sampled['sampled_pmids']} != counts):
                raise ValueError('Sampled membership/chunk counts mismatch')
            if hashlib.sha256(raw).hexdigest() != sampled['output']['sha256']:
                raise ValueError('Sampled JSONL hash mismatch')
        results.append((c['path'], text))
    for relative, text in results:
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
    print(f'Verified and exported {len(results)} historical cohort lists.')


if __name__ == '__main__':
    main()
