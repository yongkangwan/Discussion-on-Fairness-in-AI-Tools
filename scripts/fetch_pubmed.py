#!/usr/bin/env python3
"""Retrieve current PubMed XML by PMID; produces a NEW reconstruction, never paper data."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ENDPOINT = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'


def parse_pubmed(xml_bytes, label):
    root = ET.fromstring(xml_bytes)
    if root.find('.//ERROR') is not None:
        raise ValueError('Provider returned an XML error')
    rows = []
    for item in root.findall('./PubmedArticle'):
        citation = item.find('MedlineCitation')
        article = citation.find('Article')
        def text(element):
            return ''.join(element.itertext()).strip() if element is not None else ''
        rows.append(dict(pmid=text(citation.find('PMID')), label=label,
                         title=text(article.find('ArticleTitle')),
                         abstract='\n'.join(text(e) for e in article.findall('Abstract/AbstractText')),
                         data_status='reconstruction'))
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pmids', type=Path, required=True)
    p.add_argument('--email', required=True, help='Contact email sent to NCBI')
    p.add_argument('--label', type=int, choices=[0, 1], required=True,
                   help='Explicit research role for this cohort, not a misconduct determination')
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--batch-size', type=int, default=100)
    args = p.parse_args()
    ids = args.pmids.read_text(encoding='utf-8').splitlines()
    if not ids or any(not re.fullmatch(r'[1-9][0-9]*', x) for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('PMID file must contain unique numeric identifiers, one per line')
    if not 1 <= args.batch_size <= 200:
        raise ValueError('batch-size must be between 1 and 200')
    out = args.output_dir
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use a new or empty output directory')
    out.mkdir(parents=True, exist_ok=True)
    records, files = {}, []
    for offset in range(0, len(ids), args.batch_size):
        batch = ids[offset:offset + args.batch_size]
        data = urlencode(dict(db='pubmed', id=','.join(batch), retmode='xml',
                              tool='fairness_ai_reconstruction', email=args.email)).encode()
        request = Request(ENDPOINT, data=data, headers={'User-Agent': 'fairness-ai-reconstruction/1.0'})
        with urlopen(request, timeout=60) as response:
            xml = response.read()
        path = out / f'batch_{offset // args.batch_size:05}.xml'
        path.write_bytes(xml)
        rows = parse_pubmed(xml, args.label)
        if len(rows) != len(batch) or {x['pmid'] for x in rows} != set(batch):
            raise ValueError('Returned PMID set differs from request; inspect saved XML. No final manifest written.')
        records.update({x['pmid']: x for x in rows})
        files.append(dict(path=path.name, sha256=hashlib.sha256(xml).hexdigest()))
        time.sleep(0.4)  # at most 2.5 sequential requests/s, without an API key
    output = out / 'articles.jsonl'
    output.write_text(''.join(json.dumps(records[x], ensure_ascii=False) + '\n' for x in ids), encoding='utf-8')
    manifest = dict(data_status='reconstruction', paper_data=False, endpoint=ENDPOINT,
                    retrieved_at_utc=datetime.now(timezone.utc).isoformat(), n_articles=len(ids),
                    pmid_file_sha256=hashlib.sha256(args.pmids.read_bytes()).hexdigest(),
                    output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(), raw_xml=files,
                    missing_abstract_pmids=[x for x in ids if not records[x]['abstract']],
                    extraction='ArticleTitle itertext; AbstractText itertext joined with newline; no section-label insertion')
    (out / 'retrieval_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Reconstructed {len(ids)} current records in {out}; not the historical text snapshot')


if __name__ == '__main__':
    main()
