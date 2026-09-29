import json
from pathlib import Path

import pytest

from scripts.export_pmids import load_pmids
from scripts.verify_pmid_release import verify


def test_released_pmids_have_verified_hashes_and_cohort_relationships():
    result = verify()
    assert result['cohorts'] == 11
    assert result['checks']['clean_equals_raw_minus_internal']
    assert result['checks']['audit_group_overlap'] == 0


def test_export_numeric_pmids_and_sampling_manifest(tmp_path):
    path = tmp_path / 'input.jsonl'
    path.write_text('{"pmid":"123"}\n{"pmid":123}\n{"pmid":"456"}\n')
    assert load_pmids([path]) == {'123', '456'}
    path.write_text('{"pmid":"DEMO-INT-1"}\n')
    with pytest.raises(ValueError, match='numeric PMID'):
        load_pmids([path])
    path.write_text(json.dumps(dict(sampled_articles=2, sampled_pmids=[dict(pmid='123'), dict(pmid='456')])))
    assert load_pmids([path], 'sampling-manifest') == {'123', '456'}
    path.write_text(json.dumps(dict(sampled_articles=3, sampled_pmids=[dict(pmid='123')])))
    with pytest.raises(ValueError, match='inconsistent'):
        load_pmids([path], 'sampling-manifest')


def test_archive_recovery_validates_source_and_manifest_before_export(tmp_path, monkeypatch):
    import hashlib
    import sys
    from scripts import recover_historical_pmids as recovery
    raw = b'{"pmid":"123","chunk_index":0}\n{"pmid":"123","chunk_index":1}\n'
    blob = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
    sampled = json.dumps(dict(sampled_pmids=[dict(pmid='123', n_chunks=2)],
                              output=dict(sha256=hashlib.sha256(raw).hexdigest()))).encode()
    sampled_sha = hashlib.sha1(f'blob {len(sampled)}\0'.encode() + sampled).hexdigest()
    metadata = tmp_path / 'data/pmids'
    metadata.mkdir(parents=True)
    cohort = dict(source_path='sample.jsonl', source_git_blob_sha=blob,
                  source_bytes=len(raw), source_rows=2, unique_pmids=1,
                  path='historical/sample.txt', pmid_file_sha256=hashlib.sha256(b'123\n').hexdigest(),
                  sampling_evidence=dict(source_path='sample.manifest.json', source_git_blob_sha=sampled_sha))
    (metadata / 'manifest.json').write_text(json.dumps(dict(source_commit='fixture', cohorts=[cohort])))
    responses = {('rev-parse', 'fixture:sample.jsonl'): blob.encode(),
                 ('rev-parse', 'fixture:sample.manifest.json'): sampled_sha.encode(),
                 ('cat-file', 'blob', blob): raw,
                 ('cat-file', 'blob', sampled_sha): sampled}
    monkeypatch.setattr(recovery, 'ROOT', tmp_path)
    monkeypatch.setattr(recovery, 'git', lambda archive, *args: responses[args])
    out = tmp_path / 'export'
    monkeypatch.setattr(sys, 'argv', ['recover', '--archive', str(tmp_path), '--output-dir', str(out)])
    recovery.main()
    assert (out / 'historical/sample.txt').read_bytes() == b'123\n'
    responses[('cat-file', 'blob', blob)] = raw + b'\n'
    monkeypatch.setattr(sys, 'argv', ['recover', '--archive', str(tmp_path), '--output-dir', str(tmp_path / 'bad')])
    with pytest.raises(ValueError, match='hash mismatch'):
        recovery.main()
    assert not (tmp_path / 'bad').exists()
