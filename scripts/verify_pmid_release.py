#!/usr/bin/env python3
"""Verify released identifier integrity and independently recompute all overlaps."""
from __future__ import annotations
import csv
import hashlib
import itertools
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def verify(root=ROOT / 'data/pmids'):
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest['data_status'] != 'verified-historical-rebuttal' or manifest['paper_cohort_verified']:
        raise ValueError('Unexpected release provenance')
    sets = {}
    for cohort in manifest['cohorts']:
        content = (root / cohort['path']).read_bytes()
        ids = content.decode('utf-8').splitlines()
        if (any(not re.fullmatch(r'[1-9][0-9]*', x) for x in ids)
                or ids != sorted(set(ids), key=int)
                or len(ids) != cohort['unique_pmids']
                or content != ''.join(x + '\n' for x in ids).encode()
                or hashlib.sha256(content).hexdigest() != cohort['pmid_file_sha256']):
            raise ValueError(f'Identifier integrity failed: {cohort["path"]}')
        if cohort['data_status'] != manifest['data_status'] or cohort['paper_cohort_verified']:
            raise ValueError('Unexpected cohort provenance')
        sets[cohort['cohort_id']] = set(ids)
    expected_overlap = {(a, b): len(sets[a] & sets[b]) for a, b in itertools.combinations(sets, 2)}
    with (root / 'overlap_counts.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    recorded = {(r['cohort_a'], r['cohort_b']): int(r['shared_pmids']) for r in rows}
    if recorded != expected_overlap or len(rows) != len(expected_overlap):
        raise ValueError('Overlap table mismatch')
    internal = set().union(*(sets[n] for n in (
        'internal_positive_pool', 'internal_negative_top_china',
        'internal_negative_top_other_train', 'internal_negative_top_taiwan')))
    china, other = sets['audit_china_5000'], sets['audit_other_5000']
    checks = dict(
        internal_unique_articles=len(internal),
        external_raw_internal_overlap=len(sets['external_negative_raw'] & internal),
        clean_equals_raw_minus_internal=sets['external_negative_clean'] == sets['external_negative_raw'] - internal,
        audit_group_overlap=len(china & other),
        audit_china_internal_overlap=len(china & internal),
        audit_other_internal_overlap=len(other & internal),
        audit_china_external_positive_overlap=len(china & sets['external_positive_pubpeer']),
        audit_other_external_positive_overlap=len(other & sets['external_positive_pubpeer']),
        audit_other_external_negative_overlap=len(other & sets['external_negative_raw']),
    )
    if checks != manifest['checks']:
        raise ValueError('Cohort relationship checks differ from manifest')
    distinct = len(set().union(*sets.values()))
    if distinct != manifest['distinct_pmids_across_all_lists']:
        raise ValueError('Distinct PMID count mismatch')
    return dict(cohorts=len(sets), distinct_pmids=distinct, checks=checks)


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
