import json
from pathlib import Path

import pytest
from transformers import BertTokenizerFast
import transformers

from scripts.fetch_pubmed import parse_pubmed
from scripts.preprocess_articles import chunk_ids, preprocess


def tokenizer(tmp_path):
    vocab = Path(__file__).resolve().parents[1] / 'data/examples/vocab.txt'
    key = 'vocab' if int(transformers.__version__.split('.')[0]) >= 5 else 'vocab_file'
    tok = BertTokenizerFast(**{key: str(vocab)}, do_lower_case=True)
    tok.save_pretrained(tmp_path)
    return tok


def test_windows_preserve_tail_and_overlap_without_extra_window(tmp_path):
    tok = tokenizer(tmp_path)
    ids = [5, 6, 7, 8, 9, 10, 11, 12, 13]
    windows = list(chunk_ids(ids, tok, 8, 2))  # capacity=6, step=4
    assert [w['input_ids'][1:-1] for w in windows] == [ids[:6], ids[4:]]
    assert [len(w['input_ids']) for w in windows] == [8, 7]
    assert len(list(chunk_ids(ids[:6], tok, 8, 2))) == 1
    assert len(list(chunk_ids(ids[:1], tok, 8, 0))) == 1
    with pytest.raises(ValueError):
        list(chunk_ids(ids, tok, 8, 6))


def test_preprocess_provenance_and_duplicate_rejection(tmp_path):
    model = tmp_path / 'tokenizer'
    model.mkdir()
    tokenizer(model)
    source = tmp_path / 'source.jsonl'
    row = dict(pmid='DEMO-X', title='synthetic example', abstract='red circle ' * 30,
               label=1, data_status='demo-only')
    source.write_text(json.dumps(row) + '\n')
    dest = tmp_path / 'out.jsonl'
    manifest = preprocess(source, dest, model, 16, 2, 'demo-only')
    chunks = [json.loads(s) for s in dest.read_text().splitlines()]
    assert len(chunks) > 1 and all(len(x['input_ids']) <= 16 for x in chunks)
    assert [x['chunk_index'] for x in chunks] == list(range(len(chunks)))
    assert manifest['paper_preprocessing'] is False
    assert manifest['tokenizer_files']
    with pytest.raises(ValueError, match='already exist'):
        preprocess(source, dest, model, 16, 2, 'demo-only')
    source.write_text((json.dumps(row) + '\n') * 2)
    with pytest.raises(ValueError, match='duplicate'):
        preprocess(source, tmp_path / 'duplicate.jsonl', model, 16, 2, 'demo-only')
    assert not (tmp_path / 'duplicate.jsonl').exists()


def test_pubmed_parser_handles_markup_sections_and_no_abstract():
    xml = b'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
    <ArticleTitle>A <i>toy</i> title</ArticleTitle><Abstract>
    <AbstractText Label="FIRST">one <b>two</b></AbstractText><AbstractText>three</AbstractText>
    </Abstract></Article></MedlineCitation></PubmedArticle>
    <PubmedArticle><MedlineCitation><PMID>2</PMID><Article><ArticleTitle>Empty</ArticleTitle>
    </Article></MedlineCitation></PubmedArticle></PubmedArticleSet>'''
    rows = parse_pubmed(xml, 0)
    assert rows[0]['title'] == 'A toy title'
    assert rows[0]['abstract'] == 'one two\nthree'
    assert rows[1]['abstract'] == ''
    assert all(x['data_status'] == 'reconstruction' for x in rows)
